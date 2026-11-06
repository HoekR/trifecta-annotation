#!/usr/bin/env python3
"""Fine-tune a binary Step A KEEP/DROP encoder (user-run; GPU preferred).

Reuses ``train_gijsbert`` on keep/drop splits from ``export_step_a_keepdrop.py``.
Reports keep-recall / drop-precision by ``text_regime`` on the held-out works.

    uv run python scripts/export_step_a_keepdrop.py --summary
    uv run python scripts/train_step_a_keepdrop.py \\
      --data-dir "$(uv run python -c 'from data_io import resolve; print(resolve(\"trifecta_step_a_keepdrop\"))')" \\
      --output-dir "$(uv run python -c 'from data_io import resolve; print(resolve(\"trifecta_step_a_keepdrop_models\"))')/globertise-keepdrop"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from trifecta_annotation.gijsbert_export import load_gijsbert_jsonl
from trifecta_annotation.gijsbert_train import train_gijsbert
from trifecta_annotation.step_a_keepdrop import HfStepAKeepDropSieve, metrics_by_regime


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-name", default=None, help="Override manifest model_base")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    paths = train_gijsbert(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        model_name=args.model_name,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        seed=args.seed,
        device=args.device,
        frames_only=False,
    )
    model_dir = Path(paths["model"])

    sieve = HfStepAKeepDropSieve(model_dir, device=args.device, max_length=args.max_length)
    dev_rows = load_gijsbert_jsonl(Path(args.data_dir) / "dev.jsonl")
    preds = [sieve.predict_label(str(row["text"])) for row in dev_rows]
    by_regime = metrics_by_regime(dev_rows, preds)
    report = {
        "model_dir": str(sieve.path),
        "train_paths": {key: str(path) for key, path in paths.items()},
        "dev_by_regime": by_regime,
        "dev_n": len(dev_rows),
        "dev_accuracy": (
            sum(1 for row, pred in zip(dev_rows, preds, strict=True) if row["label"] == pred)
            / len(dev_rows)
            if dev_rows
            else 0.0
        ),
    }
    report_path = Path(args.output_dir).expanduser().resolve() / "keepdrop_eval_by_regime.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {report_path}", flush=True)


if __name__ == "__main__":
    main()
