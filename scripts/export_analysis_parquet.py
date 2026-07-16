#!/usr/bin/env python3
"""Export bounded A→B→C batch JSONL to an analysis parquet table."""

from __future__ import annotations

import argparse
from pathlib import Path

from data_io import resolve

from trifecta_annotation.analysis_export import export_analysis_parquet


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Flatten TrifectaAnnotation JSONL to analysis parquet "
            "(LLM hypotheses — see uncertainty_note column)."
        ),
    )
    parser.add_argument(
        "--input-path",
        type=Path,
        default=None,
        help="Batch JSONL (default: scratch gold_predictions.jsonl)",
    )
    parser.add_argument("--input-logical", default=None)
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Override output path (default: trifecta_analysis logical)",
    )
    parser.add_argument(
        "--require-step-c",
        action="store_true",
        help="Keep only rows with step_c filled",
    )
    parser.add_argument(
        "--exclude-dropped",
        action="store_true",
        help="Drop early-exit rows",
    )
    args = parser.parse_args()

    input_path = args.input_path
    if input_path is None and args.input_logical is None:
        input_path = Path(resolve("trifecta_gold")).parent / "gold_predictions.jsonl"

    path = export_analysis_parquet(
        input_path=input_path,
        input_logical=args.input_logical,
        output_path=args.output_path,
        require_step_c=args.require_step_c,
        exclude_dropped=args.exclude_dropped,
        script=__file__,
    )
    print(f"Wrote analysis parquet: {path}")


if __name__ == "__main__":
    main()
