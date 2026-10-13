#!/usr/bin/env python3
"""Re-score an already-trained Step C span model's dev predictions and rewrite
report.md / dev_metrics.json, without retraining.

One-off utility for when the eval/report logic changes (e.g. the positive-vs-empty
breakdown added after the first `train_stepc_span.py` run already completed).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from trifecta_annotation.stepc_span_export import DEFAULT_MODEL_BASE
from trifecta_annotation.stepc_span_train import (
    _evaluate_predictions,
    _resolve_device,
    load_field_manifest,
)
from trifecta_annotation.stepc_span_export import load_stepc_span_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-score an existing Step C span run.")
    parser.add_argument("--data-dir", required=True, help="Dir with dev.jsonl + field_manifest.json")
    parser.add_argument("--run-dir", required=True, help="Existing run dir with model/ + report.md")
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    from trifecta_annotation.hf_cache import configure_hf_hub_cache

    configure_hf_hub_cache()
    import torch
    from transformers import AutoModelForQuestionAnswering, AutoTokenizer

    data_path = Path(args.data_dir).expanduser().resolve()
    run_path = Path(args.run_dir).expanduser().resolve()
    model_path = run_path / "model"

    manifest = load_field_manifest(data_path / "field_manifest.json")
    dev_rows = load_stepc_span_jsonl(data_path / "dev.jsonl")

    device = _resolve_device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForQuestionAnswering.from_pretrained(model_path).to(device)
    model.eval()

    all_start_logits = []
    all_end_logits = []
    dev_offsets: list[list[tuple[int, int]]] = []
    batch_size = args.batch_size
    for i in range(0, len(dev_rows), batch_size):
        batch = dev_rows[i : i + batch_size]
        tokenized = tokenizer(
            [row["field_query"] for row in batch],
            [row["context_text"] for row in batch],
            truncation="only_second",
            max_length=args.max_length,
            padding="max_length",
            return_offsets_mapping=True,
            return_tensors="pt",
        )
        offsets_batch = tokenized.pop("offset_mapping").tolist()
        dev_offsets.extend([[tuple(pair) for pair in offs] for offs in offsets_batch])
        tokenized = {k: v.to(device) for k, v in tokenized.items()}
        with torch.no_grad():
            outputs = model(**tokenized)
        all_start_logits.append(outputs.start_logits.cpu().numpy())
        all_end_logits.append(outputs.end_logits.cpu().numpy())

    import numpy as np

    start_logits = np.concatenate(all_start_logits, axis=0)
    end_logits = np.concatenate(all_end_logits, axis=0)

    metrics = _evaluate_predictions(
        dev_rows=dev_rows,
        dev_offsets=dev_offsets,
        start_logits=start_logits,
        end_logits=end_logits,
    )

    metrics_path = run_path / "dev_metrics.json"
    existing = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else {}
    existing["dev_metrics"] = metrics.to_dict()
    existing["rescored"] = True
    metrics_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")

    skipped_by_field = manifest.get("counts", {}).get("skipped_ungrounded_by_field", {})
    field_to_frame = manifest.get("field_to_frame", {})
    model_base = existing.get("model_base", DEFAULT_MODEL_BASE)

    report_lines = [
        "# Step C span-extraction (GloBERTise QA) fine-tune report",
        "",
        f"- Model: `{model_base}`",
        f"- Dev rows: {len(dev_rows)}",
        f"- Dev exact match (all fields, incl. true-negative empties): **{metrics.exact_match:.3f}**",
        f"- Dev token F1 (all fields, incl. true-negative empties): **{metrics.token_f1:.3f}**",
        f"- Dev exact match (**positive spans only** — the real span-recall number): **{metrics.positive_exact_match:.3f}**",
        f"- Dev token F1 (**positive spans only**): **{metrics.positive_token_f1:.3f}**",
        "",
        "The \"all fields\" numbers above are inflated by fields that are mostly/entirely "
        "empty in gold (e.g. `INGESTION_Manner`, `INGESTION_Purpose`) — a model that "
        "always predicts \"no answer\" scores perfectly on those for free. The "
        "**positive spans only** numbers restrict to rows where gold actually has a "
        "value to extract, and are the number to trust for judging extraction quality.",
        "",
        "## Per-field (dev) — EM / F1 / n, vs. groundedness ceiling",
        "",
        "Ceiling = fraction of non-empty gold values in the full export that were "
        "literal spans at all (the rest are paraphrases/glosses this extractor "
        "structurally cannot recover; see `skipped_ungrounded.jsonl`). `n_empty` / "
        "`n_positive` show how much of each field's dev score is trivial true-negatives "
        "vs. real extraction; `pos EM` / `pos F1` are scored on the positive subset only.",
        "",
        "| Field | EM (all) | F1 (all) | n | n_empty | n_positive | pos EM | pos F1 | train-time skipped (ungrounded) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for field, stats in sorted(metrics.per_field.items()):
        skipped_n = skipped_by_field.get(field, 0)
        n_pos = int(stats["n_positive"])
        pos_em = f"{stats['positive_exact_match']:.3f}" if n_pos else "n/a"
        pos_f1 = f"{stats['positive_token_f1']:.3f}" if n_pos else "n/a"
        report_lines.append(
            f"| {field} ({field_to_frame.get(field, '?')}) "
            f"| {stats['exact_match']:.3f} | {stats['token_f1']:.3f} "
            f"| {int(stats['n'])} | {int(stats['n_empty'])} | {n_pos} "
            f"| {pos_em} | {pos_f1} | {skipped_n} |"
        )
    report_path = run_path / "report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Rewrote {report_path} and {metrics_path}")


if __name__ == "__main__":
    main()
