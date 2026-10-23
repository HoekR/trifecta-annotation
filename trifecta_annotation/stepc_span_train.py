"""Fine-tune GloBERTise as a BERT-QA span extractor for Step C qualia fields.

One shared encoder across all 4 frames / 12 fields (joint, not split-per-frame —
see PLAN.md Step 4 for why: per-frame row counts are already small, and the Step B
2-stage hierarchical split regressed for the same data-fragmentation reason).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trifecta_annotation.eval import soft_qualia_match
from trifecta_annotation.gijsbert_train import _resolve_device
from trifecta_annotation.stepc_span_export import DEFAULT_MODEL_BASE, load_stepc_span_jsonl

CLS_INDEX = 0


def load_field_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@dataclass
class SpanEvalResult:
    total: int
    exact_match: float
    token_f1: float
    soft_match: float
    positive_exact_match: float
    positive_token_f1: float
    positive_soft_match: float
    per_field: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "exact_match": self.exact_match,
            "token_f1": self.token_f1,
            "soft_match": self.soft_match,
            "positive_exact_match": self.positive_exact_match,
            "positive_token_f1": self.positive_token_f1,
            "positive_soft_match": self.positive_soft_match,
            "per_field": self.per_field,
        }


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _token_f1(gold: str, pred: str) -> float:
    gold_tokens = _normalize_text(gold).split()
    pred_tokens = _normalize_text(pred).split()
    if not gold_tokens and not pred_tokens:
        return 1.0
    if not gold_tokens or not pred_tokens:
        return 0.0
    common: dict[str, int] = defaultdict(int)
    for tok in pred_tokens:
        common[tok] += 1
    num_same = 0
    remaining = dict(common)
    for tok in gold_tokens:
        if remaining.get(tok, 0) > 0:
            num_same += 1
            remaining[tok] -= 1
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


def char_span_to_token_span(
    offsets: list[tuple[int, int]],
    sequence_ids: list[int | None],
    start_char: int | None,
    end_char: int | None,
) -> tuple[int, int]:
    """Map a gold char span to a (start_token, end_token) index pair within the
    context segment (sequence_id == 1). Returns (CLS_INDEX, CLS_INDEX) when the
    answer is unanswerable or falls outside the (possibly truncated) context window.
    """
    context_token_idxs = [i for i, sid in enumerate(sequence_ids) if sid == 1]
    if not context_token_idxs:
        return CLS_INDEX, CLS_INDEX
    context_start = context_token_idxs[0]
    context_end = context_token_idxs[-1]

    if start_char is None or end_char is None:
        return CLS_INDEX, CLS_INDEX

    if offsets[context_start][0] > start_char or offsets[context_end][1] < end_char:
        return CLS_INDEX, CLS_INDEX

    token_start = context_start
    while token_start <= context_end and offsets[token_start][0] <= start_char:
        token_start += 1
    token_start -= 1

    token_end = context_end
    while token_end >= context_start and offsets[token_end][1] >= end_char:
        token_end -= 1
    token_end += 1

    if token_start > token_end:
        return CLS_INDEX, CLS_INDEX
    return token_start, token_end


def train_stepc_span(
    *,
    data_dir: str | Path,
    output_dir: str | Path,
    model_name: str | None = None,
    epochs: float = 10.0,
    batch_size: int = 8,
    learning_rate: float = 3e-5,
    max_length: int = 384,
    seed: int = 42,
    device: str | None = None,
) -> dict[str, Path]:
    """Fine-tune a span-extraction QA model and evaluate on dev split."""
    from trifecta_annotation.hf_cache import configure_hf_hub_cache

    configure_hf_hub_cache()
    from datasets import Dataset
    from transformers import (
        AutoModelForQuestionAnswering,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    data_path = Path(data_dir).expanduser().resolve()
    out_path = Path(output_dir).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    manifest = load_field_manifest(data_path / "field_manifest.json")
    model_base = model_name or str(manifest.get("model_base") or DEFAULT_MODEL_BASE)

    train_rows = load_stepc_span_jsonl(data_path / "train.jsonl")
    dev_rows = load_stepc_span_jsonl(data_path / "dev.jsonl")

    set_seed(seed)
    resolved_device = _resolve_device(device)
    hf_cache = configure_hf_hub_cache()

    tokenizer = AutoTokenizer.from_pretrained(model_base, cache_dir=str(hf_cache))
    if not tokenizer.is_fast:
        raise RuntimeError(
            f"Model base '{model_base}' has no fast tokenizer — required for offset_mapping."
        )
    model = AutoModelForQuestionAnswering.from_pretrained(model_base, cache_dir=str(hf_cache))

    def _to_dataset(rows: list[dict[str, Any]]) -> Dataset:
        return Dataset.from_dict(
            {
                "field_query": [row["field_query"] for row in rows],
                "context_text": [row["context_text"] for row in rows],
                "answer_start_char": [row["answer_start_char"] for row in rows],
                "answer_end_char": [row["answer_end_char"] for row in rows],
            }
        )

    def _tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        tokenized = tokenizer(
            batch["field_query"],
            batch["context_text"],
            truncation="only_second",
            max_length=max_length,
            padding="max_length",
            return_offsets_mapping=True,
        )
        start_positions = []
        end_positions = []
        for i in range(len(batch["field_query"])):
            offsets = tokenized["offset_mapping"][i]
            sequence_ids = tokenized.sequence_ids(i)
            start_tok, end_tok = char_span_to_token_span(
                offsets,
                sequence_ids,
                batch["answer_start_char"][i],
                batch["answer_end_char"][i],
            )
            start_positions.append(start_tok)
            end_positions.append(end_tok)
        tokenized["start_positions"] = start_positions
        tokenized["end_positions"] = end_positions
        return tokenized

    train_ds = _to_dataset(train_rows).map(
        _tokenize, batched=True, remove_columns=["field_query", "context_text"]
    )
    dev_ds_tokenized = _to_dataset(dev_rows).map(
        _tokenize, batched=True, remove_columns=["field_query", "context_text"]
    )
    dev_offsets = [row["offset_mapping"] for row in dev_ds_tokenized]
    train_ds = train_ds.remove_columns(["offset_mapping", "answer_start_char", "answer_end_char"])
    dev_ds = dev_ds_tokenized.remove_columns(
        ["offset_mapping", "answer_start_char", "answer_end_char"]
    )

    use_fp16 = resolved_device == "cuda"
    args = TrainingArguments(
        output_dir=str(out_path / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_steps=50,
        save_total_limit=2,
        seed=seed,
        fp16=use_fp16,
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=dev_ds,
        processing_class=tokenizer,
    )

    train_result = trainer.train()
    trainer.save_model(str(out_path / "model"))
    tokenizer.save_pretrained(str(out_path / "model"))

    pred_output = trainer.predict(dev_ds)
    start_logits, end_logits = pred_output.predictions
    metrics = _evaluate_predictions(
        dev_rows=dev_rows,
        dev_offsets=dev_offsets,
        start_logits=start_logits,
        end_logits=end_logits,
    )

    skipped_by_field = manifest.get("counts", {}).get("skipped_ungrounded_by_field", {})
    field_to_frame = manifest.get("field_to_frame", {})

    run_meta = {
        "model_base": model_base,
        "hf_hub_cache": str(hf_cache),
        "data_dir": str(data_path),
        "output_dir": str(out_path),
        "device": resolved_device,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "max_length": max_length,
        "train_rows": len(train_rows),
        "dev_rows": len(dev_rows),
        "train_loss": float(train_result.training_loss),
        "finished_at": datetime.now(UTC).isoformat(),
        "dev_metrics": metrics.to_dict(),
    }
    metrics_path = out_path / "dev_metrics.json"
    metrics_path.write_text(json.dumps(run_meta, indent=2, ensure_ascii=False), encoding="utf-8")

    report_lines = [
        "# Step C span-extraction (GloBERTise QA) fine-tune report",
        "",
        f"- Model: `{model_base}`",
        f"- Train rows: {len(train_rows)}",
        f"- Dev rows: {len(dev_rows)}",
        f"- Device: {resolved_device}",
        f"- Dev exact match (all fields, incl. true-negative empties): **{metrics.exact_match:.3f}**",
        f"- Dev token F1 (all fields, incl. true-negative empties): **{metrics.token_f1:.3f}**",
        f"- Dev soft/containment match (all fields): **{metrics.soft_match:.3f}**",
        f"- Dev exact match (**positive spans only** — the real span-recall number): **{metrics.positive_exact_match:.3f}**",
        f"- Dev token F1 (**positive spans only**): **{metrics.positive_token_f1:.3f}**",
        f"- Dev soft/containment match (**positive spans only** — the number to trust): **{metrics.positive_soft_match:.3f}**",
        "",
        "The \"all fields\" numbers above are inflated by fields that are mostly/entirely "
        "empty in gold (e.g. `INGESTION_Manner`, `INGESTION_Purpose`) — a model that "
        "always predicts \"no answer\" scores perfectly on those for free. The "
        "**positive spans only** numbers restrict to rows where gold actually has a "
        "value to extract. Within those, **exact match understates quality**: span "
        "boundaries are debatable (what should be included?) and historical text has "
        "no single canonical wording, so **soft/containment match (bidirectional "
        "substring, same `soft_qualia_match` logic used for the LLM Step C eval) is "
        "the number to trust**, not raw EM.",
        "",
        "## Per-field (dev) — EM / F1 / soft / n, vs. groundedness ceiling",
        "",
        "Ceiling = fraction of non-empty gold values in the full export that were "
        "literal spans at all (the rest are paraphrases/glosses this extractor "
        "structurally cannot recover; see `skipped_ungrounded.jsonl`). `n_empty` / "
        "`n_positive` show how much of each field's dev score is trivial true-negatives "
        "vs. real extraction; `pos EM` / `pos F1` / `pos soft` are scored on the "
        "positive subset only — **`pos soft` is the number to trust**.",
        "",
        "| Field | EM (all) | F1 (all) | soft (all) | n | n_empty | n_positive | pos EM | pos F1 | pos soft | train-time skipped (ungrounded) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for field, stats in sorted(metrics.per_field.items()):
        skipped_n = skipped_by_field.get(field, 0)
        n_pos = int(stats["n_positive"])
        pos_em = f"{stats['positive_exact_match']:.3f}" if n_pos else "n/a"
        pos_f1 = f"{stats['positive_token_f1']:.3f}" if n_pos else "n/a"
        pos_soft = f"{stats['positive_soft_match']:.3f}" if n_pos else "n/a"
        report_lines.append(
            f"| {field} ({field_to_frame.get(field, '?')}) "
            f"| {stats['exact_match']:.3f} | {stats['token_f1']:.3f} | {stats['soft_match']:.3f} "
            f"| {int(stats['n'])} | {int(stats['n_empty'])} | {n_pos} "
            f"| {pos_em} | {pos_f1} | {pos_soft} | {skipped_n} |"
        )
    report_path = out_path / "report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return {
        "model": out_path / "model",
        "metrics": metrics_path,
        "report": report_path,
    }


def _evaluate_predictions(
    *,
    dev_rows: list[dict[str, Any]],
    dev_offsets: list[list[tuple[int, int]]],
    start_logits: Any,
    end_logits: Any,
) -> SpanEvalResult:
    """Score predictions, split by whether gold is empty (true negative — a model
    that always predicts "no answer" gets this for free) or non-empty (a real span
    to recover). The blended "all" metric is dominated by whichever fields happen
    to be mostly empty in gold, so the positive-only numbers are what actually
    reflect span-extraction capability.
    """
    import numpy as np

    per_field: dict[str, list[tuple[float, float, float, bool]]] = defaultdict(list)
    em_total = 0.0
    f1_total = 0.0
    soft_total = 0.0
    pos_em_total = 0.0
    pos_f1_total = 0.0
    pos_soft_total = 0.0
    n_positive = 0

    for i, row in enumerate(dev_rows):
        context = row["context_text"]
        offsets = dev_offsets[i]
        pred_start = int(np.argmax(start_logits[i]))
        pred_end = int(np.argmax(end_logits[i]))

        gold_text = row["answer_text"] or ""
        is_positive = row["answer_start_char"] is not None
        if pred_start == CLS_INDEX or pred_end == CLS_INDEX or pred_end < pred_start:
            pred_text = ""
        else:
            start_char = offsets[pred_start][0]
            end_char = offsets[pred_end][1]
            pred_text = context[start_char:end_char] if end_char > start_char else ""

        norm_pred = _normalize_text(pred_text)
        norm_gold = _normalize_text(gold_text)
        em = 1.0 if norm_pred == norm_gold else 0.0
        f1 = _token_f1(gold_text, pred_text) if gold_text or pred_text else 1.0
        # Soft/containment match (bidirectional substring, like soft_qualia_match
        # elsewhere in the project): span boundaries are debatable and there's no
        # single canonical wording, so exact char match understates real quality —
        # same reasoning as the LLM Step C soft-match bar in docs/GOLD_LABELLING.md.
        soft = 1.0 if soft_qualia_match(norm_gold, norm_pred) else 0.0

        em_total += em
        f1_total += f1
        soft_total += soft
        if is_positive:
            n_positive += 1
            pos_em_total += em
            pos_f1_total += f1
            pos_soft_total += soft
        per_field[row["field_name"]].append((em, f1, soft, is_positive))

    total = len(dev_rows)
    per_field_metrics: dict[str, dict[str, float]] = {}
    for field, quads in per_field.items():
        n = len(quads)
        pos_quads = [t for t in quads if t[3]]
        n_pos = len(pos_quads)
        per_field_metrics[field] = {
            "exact_match": sum(t[0] for t in quads) / n if n else 0.0,
            "token_f1": sum(t[1] for t in quads) / n if n else 0.0,
            "soft_match": sum(t[2] for t in quads) / n if n else 0.0,
            "n": float(n),
            "n_positive": float(n_pos),
            "n_empty": float(n - n_pos),
            "positive_exact_match": (sum(t[0] for t in pos_quads) / n_pos if n_pos else float("nan")),
            "positive_token_f1": (sum(t[1] for t in pos_quads) / n_pos if n_pos else float("nan")),
            "positive_soft_match": (sum(t[2] for t in pos_quads) / n_pos if n_pos else float("nan")),
        }

    return SpanEvalResult(
        total=total,
        exact_match=em_total / total if total else 0.0,
        token_f1=f1_total / total if total else 0.0,
        soft_match=soft_total / total if total else 0.0,
        positive_exact_match=pos_em_total / n_positive if n_positive else float("nan"),
        positive_token_f1=pos_f1_total / n_positive if n_positive else float("nan"),
        positive_soft_match=pos_soft_total / n_positive if n_positive else float("nan"),
        per_field=per_field_metrics,
    )
