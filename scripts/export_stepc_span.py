#!/usr/bin/env python3
"""Export Step C qualia span-extraction train/dev JSONL from gold-only data.

Gold-only (not silver + gold like GijsBERT) — see
``trifecta_annotation/stepc_span_export.py`` module docstring for why.
"""

from __future__ import annotations

import argparse
import json

from trifecta_annotation.gold_io import load_gold_records
from trifecta_annotation.stepc_span_export import (
    DEFAULT_MODEL_BASE,
    export_stepc_span_splits,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Step C span-extraction splits.")
    parser.add_argument("--gold-logical", default="trifecta_gold")
    parser.add_argument("--gold-path", default=None)
    parser.add_argument("--output-dir", default=None, help="Default: scratch trifecta/stepc_span")
    parser.add_argument("--model-base", default=DEFAULT_MODEL_BASE)
    parser.add_argument("--dev-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    gold = load_gold_records(gold_logical=args.gold_logical, gold_path=args.gold_path)

    out = args.output_dir
    if out is None:
        out = _resolve_output_dir()

    paths = export_stepc_span_splits(
        gold_records=gold,
        output_dir=out,
        model_base=args.model_base,
        dev_fraction=args.dev_fraction,
        seed=args.seed,
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))


def _resolve_output_dir() -> str:
    from data_io import resolve

    try:
        return resolve("trifecta_stepc_span")
    except Exception:
        return "trifecta/stepc_span"


if __name__ == "__main__":
    main()
