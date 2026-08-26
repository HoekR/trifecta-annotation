#!/usr/bin/env python3
"""Phase 2a comparative evaluation: human gold vs predictions and verb priors."""

from __future__ import annotations

import argparse
from pathlib import Path
from data_io import resolve

from trifecta_annotation.eval_phase2a import evaluate_phase2a, format_phase2a_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-csv", default=None, help="Path to verb_phase2a/gold.csv")
    parser.add_argument("--predictions", default=None, help="Path to predictions JSONL")
    parser.add_argument("--output-json", default=None, help="Path to output JSON")
    parser.add_argument("--output-csv", default=None, help="Path to output side-by-side CSV")
    parser.add_argument("--all-rows", action="store_true", help="Include unreviewed rows")
    args = parser.parse_args()

    out_json = args.output_json
    if out_json is None:
        try:
            out_json = resolve("verb_phase2a_eval")
        except Exception:
            out_json = Path("eval/verb_phase2a_eval.json")

    metrics, _df = evaluate_phase2a(
        gold_csv_path=args.gold_csv,
        predictions_path=args.predictions,
        output_json=out_json,
        output_csv=args.output_csv,
        only_reviewed=not args.all_rows,
    )
    print(format_phase2a_report(metrics))


if __name__ == "__main__":
    main()