#!/usr/bin/env python3
"""Fine-tune GloBERTise as a Step C qualia span-extraction (BERT-QA) prototype."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from trifecta_annotation.stepc_span_train import train_stepc_span


def _resolve_stepc_span_dir() -> Path:
    from data_io import resolve

    return Path(resolve("trifecta_stepc_span"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fine-tune a GloBERTise Step C qualia span-extraction model."
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory with train.jsonl, dev.jsonl, field_manifest.json (default: trifecta_stepc_span manifest)",
    )
    parser.add_argument("--output-dir", default=None, help="Run output dir (default: data-dir/runs/<timestamp>)")
    parser.add_argument(
        "--model",
        "--model-name",
        dest="model_name",
        default=None,
        help="HuggingFace model id (default: field_manifest model_base)",
    )
    parser.add_argument("--epochs", type=float, default=10.0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default=None, help="cpu | mps | cuda (auto if omitted)")
    args = parser.parse_args()

    data_dir = (
        Path(args.data_dir).expanduser().resolve() if args.data_dir else _resolve_stepc_span_dir()
    )
    manifest_path = data_dir / "field_manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Missing Step C span export: {manifest_path} (run export_stepc_span.py)")
    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
    else:
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        output_dir = data_dir / "runs" / stamp
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = train_stepc_span(
        data_dir=data_dir,
        output_dir=output_dir,
        model_name=args.model_name,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        seed=args.seed,
        device=args.device,
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
