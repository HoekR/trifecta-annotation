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
    DEFAULT_CONTEXT_RADIUS,
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
    parser.add_argument(
        "--context-radius",
        type=int,
        default=DEFAULT_CONTEXT_RADIUS,
        help=(
            "Chars each side of target_word to keep (target-centered window) before "
            f"span-matching. Default {DEFAULT_CONTEXT_RADIUS}; some Dutch gold context_text "
            "is passage-length (unclipped --source long KWIC build) and needs this to match "
            "what Step C would see in production."
        ),
    )
    parser.add_argument(
        "--full-context",
        action="store_true",
        help="Keep passage-length context_text as-is (no target-centered clip)",
    )
    args = parser.parse_args()

    gold = load_gold_records(gold_logical=args.gold_logical, gold_path=args.gold_path)

    out = args.output_dir
    if out is None:
        out = _resolve_output_dir()

    context_radius = None if args.full_context else args.context_radius

    paths = export_stepc_span_splits(
        gold_records=gold,
        output_dir=out,
        model_base=args.model_base,
        dev_fraction=args.dev_fraction,
        seed=args.seed,
        context_radius=context_radius,
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
