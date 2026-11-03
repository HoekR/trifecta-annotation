#!/usr/bin/env python3
"""Fine-tune GijsBERT on exported TRIFECTA frame-classification splits."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from trifecta_annotation.gijsbert_train import train_gijsbert


def _resolve_gijsbert_dir() -> Path:
    from data_io import resolve

    return Path(resolve("trifecta_gijsbert"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune GijsBERT macro-frame classifier.")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory with train.jsonl, dev.jsonl, label_manifest.json (default: trifecta_gijsbert manifest)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Run output dir (default: data-dir/runs/<timestamp>)",
    )
    parser.add_argument(
        "--model",
        "--model-name",
        dest="model_name",
        default=None,
        help="HuggingFace model id (default: label_manifest model_base)",
    )
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default=None, help="cpu | mps | cuda (auto if omitted)")
    parser.add_argument(
        "--oversample-none",
        type=int,
        default=1,
        help="Duplicate NONE train rows N times total (1 = off)",
    )
    parser.add_argument(
        "--class-weight-balance",
        action="store_true",
        help="Inverse-frequency class weights in loss",
    )
    parser.add_argument(
        "--none-weight-boost",
        type=float,
        default=2.0,
        help="Extra multiplier on NONE class weight",
    )
    parser.add_argument(
        "--frames-only",
        action="store_true",
        help="Train on 4 frame classes only (exclude NONE)",
    )
    args = parser.parse_args()

    data_dir = (
        Path(args.data_dir).expanduser().resolve()
        if args.data_dir
        else _resolve_gijsbert_dir()
    )
    manifest_path = data_dir / "label_manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Missing GijsBERT export: {manifest_path} (run export_gijsbert.py)")
    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
    else:
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_dir = data_dir / "runs" / stamp
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = train_gijsbert(
        data_dir=data_dir,
        output_dir=output_dir,
        model_name=args.model_name,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        seed=args.seed,
        device=args.device,
        oversample_none=args.oversample_none,
        class_weight_balance=args.class_weight_balance,
        none_weight_boost=args.none_weight_boost,
        frames_only=args.frames_only,
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
