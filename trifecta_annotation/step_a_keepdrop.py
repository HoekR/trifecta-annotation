"""Binary Step A keep/drop export + encoder sieve (genre-routed weak regimes)."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Protocol

from trifecta_annotation.gijsbert_export import mark_kwic_context
from trifecta_annotation.regime_routing import (
    DROP_LABEL,
    KEEP_DROP_ID2LABEL,
    KEEP_DROP_LABEL2ID,
    KEEP_DROP_LABELS,
    KEEP_LABEL,
    needs_encoder_sieve,
    parse_regime,
    tei_scope_from_record,
)
from trifecta_annotation.schemas import TrifectaAnnotation
from trifecta_annotation.text_regime import TextRegime


class StepAKeepDropSieve(Protocol):
    def predict_keep(self, text: str) -> bool: ...


def step_a_keep_label(record: dict[str, Any]) -> str | None:
    """KEEP if Step A would send the row to B; DROP if A rejects; None if unusable."""
    if record.get("error"):
        return None
    ann = TrifectaAnnotation.model_validate(record)
    if ann.dropped:
        return DROP_LABEL
    if ann.step_a is not None and (ann.step_a.is_metaphor or not ann.step_a.is_food_entity):
        return DROP_LABEL
    if ann.step_a is None and not ann.dropped:
        # Survived without stored step_a (rare) — treat as KEEP if B present.
        if ann.step_b is not None:
            return KEEP_LABEL
        return None
    return KEEP_LABEL


def annotation_to_keepdrop_row(record: dict[str, Any]) -> dict[str, Any] | None:
    label = step_a_keep_label(record)
    if label is None:
        return None
    ann = TrifectaAnnotation.model_validate(record)
    provenance = ann.provenance
    text = mark_kwic_context(
        provenance.context_text,
        target_word=provenance.target_word,
        discovery_verb=provenance.discovery_verb,
        lexical_unit=ann.step_b.lexical_unit if ann.step_b else None,
        mark_mode="food",
    )
    regime = parse_regime(provenance.text_regime)
    return {
        "record_id": provenance.record_id,
        "text": text,
        "label": label,
        "label_id": KEEP_DROP_LABEL2ID[label],
        "corpus": provenance.corpus,
        "date": provenance.date,
        "target_word": provenance.target_word,
        "source_path": provenance.source_path,
        "text_regime": regime.value if regime else None,
        "kwic_mode": provenance.kwic_mode,
        "task": "step_a_keepdrop",
    }


def _work_key(row: dict[str, Any]) -> str:
    return str(row.get("source_path") or row.get("corpus") or "unknown")


def split_keepdrop_by_work(
    rows: list[dict[str, Any]],
    *,
    dev_fraction: float = 0.15,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Hold out whole works so regime metrics are not leaked across splits."""
    by_work: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_work[_work_key(row)].append(row)
    works = sorted(by_work)
    rng = random.Random(seed)
    rng.shuffle(works)
    n_dev = max(1, int(round(len(works) * dev_fraction))) if works else 0
    # Prefer at least one KEEP and one DROP in dev when possible: take more works
    # if a tiny split collapses to one class.
    dev_works = set(works[:n_dev])
    train = [row for work, group in by_work.items() if work not in dev_works for row in group]
    dev = [row for work, group in by_work.items() if work in dev_works for row in group]
    if not train and dev:
        # Single-work corpora: fall back to row shuffle.
        shuffled = list(rows)
        rng.shuffle(shuffled)
        cut = max(1, int(round(len(shuffled) * (1 - dev_fraction))))
        return shuffled[:cut], shuffled[cut:]
    return train, dev


def export_keepdrop_splits(
    records: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    dev_fraction: float = 0.15,
    seed: int = 42,
    model_base: str = "globalise/GloBERTise",
) -> dict[str, Path]:
    """Write train/dev JSONL + label_manifest for binary Step A keep/drop."""
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = [row for record in records if (row := annotation_to_keepdrop_row(record)) is not None]
    train, dev = split_keepdrop_by_work(rows, dev_fraction=dev_fraction, seed=seed)

    def _write(path: Path, payload: list[dict[str, Any]]) -> Path:
        with path.open("w", encoding="utf-8") as handle:
            for row in payload:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return path

    paths = {
        "train": _write(out / "train.jsonl", train),
        "dev": _write(out / "dev.jsonl", dev),
    }
    by_regime: dict[str, dict[str, int]] = defaultdict(lambda: {KEEP_LABEL: 0, DROP_LABEL: 0})
    for row in rows:
        regime = str(row.get("text_regime") or "absent")
        by_regime[regime][str(row["label"])] += 1
    manifest = {
        "labels": KEEP_DROP_LABELS,
        "label2id": KEEP_DROP_LABEL2ID,
        "id2label": {str(k): v for k, v in KEEP_DROP_ID2LABEL.items()},
        "task": "step_a_keepdrop",
        "model_base": model_base,
        "counts": {
            "train": len(train),
            "dev": len(dev),
            "total": len(rows),
            "keep": sum(1 for r in rows if r["label"] == KEEP_LABEL),
            "drop": sum(1 for r in rows if r["label"] == DROP_LABEL),
            "by_regime": {regime: dict(counts) for regime, counts in sorted(by_regime.items())},
        },
    }
    manifest_path = out / "label_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    paths["manifest"] = manifest_path
    return paths


def metrics_by_regime(
    rows: list[dict[str, Any]],
    pred_labels: list[str],
) -> dict[str, dict[str, float | int]]:
    """Per-regime keep-recall and drop-precision for sieve operating points."""
    buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row, pred in zip(rows, pred_labels, strict=True):
        regime = str(row.get("text_regime") or "absent")
        buckets[regime].append((str(row["label"]), pred))

    report: dict[str, dict[str, float | int]] = {}
    for regime, pairs in sorted(buckets.items()):
        gold_keep = [(g, p) for g, p in pairs if g == KEEP_LABEL]
        pred_drop = [(g, p) for g, p in pairs if p == DROP_LABEL]
        keep_recall = (
            sum(1 for g, p in gold_keep if p == KEEP_LABEL) / len(gold_keep) if gold_keep else 0.0
        )
        drop_precision = (
            sum(1 for g, p in pred_drop if g == DROP_LABEL) / len(pred_drop) if pred_drop else 0.0
        )
        accuracy = sum(1 for g, p in pairs if g == p) / len(pairs) if pairs else 0.0
        report[regime] = {
            "n": len(pairs),
            "accuracy": accuracy,
            "keep_recall": keep_recall,
            "drop_precision": drop_precision,
        }
    return report


class HfStepAKeepDropSieve:
    """Load a fine-tuned sequence classifier and predict KEEP vs DROP."""

    def __init__(self, model_dir: str | Path, *, device: str | None = None, max_length: int = 256):
        from trifecta_annotation.gijsbert_train import _resolve_device
        from trifecta_annotation.hf_cache import configure_hf_hub_cache

        configure_hf_hub_cache()
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.path = Path(model_dir).expanduser().resolve()
        self.max_length = max_length
        self.device = _resolve_device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(self.path)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.path)
        self.model.to(self.device)
        self.model.eval()
        self._torch = torch
        id2label = getattr(self.model.config, "id2label", None) or KEEP_DROP_ID2LABEL
        self.id2label = {int(k): str(v) for k, v in id2label.items()}

    def predict_label(self, text: str) -> str:
        enc = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding=True,
        )
        enc = {key: value.to(self.device) for key, value in enc.items()}
        with self._torch.no_grad():
            logits = self.model(**enc).logits
        pred_id = int(logits.argmax(dim=-1).item())
        return self.id2label.get(pred_id, DROP_LABEL)

    def predict_keep(self, text: str) -> bool:
        return self.predict_label(text) == KEEP_LABEL


def should_apply_sieve_to_input(
    record: dict[str, Any],
    *,
    sieve_enabled: bool,
) -> bool:
    if not sieve_enabled:
        return False
    regime = record.get("text_regime")
    if regime is None:
        provenance = record.get("provenance") or {}
        if isinstance(provenance, dict):
            regime = provenance.get("text_regime")
    return needs_encoder_sieve(
        text_regime=regime,
        tei_scope_head=tei_scope_from_record(record),
    )


def marked_text_for_sieve(record: dict[str, Any]) -> str:
    """Build the same marked string used at train time (food [TGT] only)."""
    target = str(record.get("target_word") or "")
    context = str(record.get("context_text") or "")
    if not context and isinstance(record.get("provenance"), dict):
        provenance = record["provenance"]
        target = str(provenance.get("target_word") or target)
        context = str(provenance.get("context_text") or "")
    return mark_kwic_context(context, target_word=target, mark_mode="food")
