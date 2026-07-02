#!/usr/bin/env python3
"""Apply reviewed gold_fixes CSV back into the gold labelling CSV."""

from __future__ import annotations

import argparse
from pathlib import Path

from data_io import resolve

from trifecta_annotation.gold_io import GOLD_FIX_VERDICTS, import_gold_csv, merge_gold_csv_with_fixes


def _default_gold_csv() -> Path:
    parent = Path(resolve("trifecta_gold")).parent
    merged = parent / "gold_labelling_all.csv"
    if merged.exists():
        return merged
    return Path(resolve("trifecta_gold_csv"))


def _default_fixes_csv() -> Path:
    return Path(resolve("eval_reports")) / "gold_fixes.csv"


def _default_predictions() -> Path:
    return Path(resolve("trifecta_gold")).parent / "gold_predictions.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge gold_fixes.csv into the gold labelling CSV. "
            f"verdict: {', '.join(sorted(GOLD_FIX_VERDICTS))}"
        ),
    )
    parser.add_argument(
        "--fixes-path",
        type=Path,
        default=None,
        help="gold_fixes.csv (default) or .xlsx with gold_fixes sheet",
    )
    parser.add_argument("--gold-csv-path", type=Path, default=None)
    parser.add_argument("--predictions-path", type=Path, default=None)
    parser.add_argument("-o", "--output-csv-path", type=Path, default=None)
    parser.add_argument("--import-after", action="store_true")
    args = parser.parse_args()

    gold_csv = args.gold_csv_path or _default_gold_csv()
    fixes_path = args.fixes_path or _default_fixes_csv()
    predictions = args.predictions_path or _default_predictions()

    if not gold_csv.exists():
        raise SystemExit(f"Gold CSV not found: {gold_csv}")
    if not fixes_path.exists():
        raise SystemExit(f"Fixes file not found: {fixes_path}")

    _, applied, out_csv = merge_gold_csv_with_fixes(
        gold_csv_path=gold_csv,
        fixes_path=fixes_path,
        predictions_path=predictions if predictions.exists() else None,
        output_csv_path=args.output_csv_path,
    )
    print(f"Updated CSV: {out_csv}")
    print(f"Applied {len(applied)} gold_fixes rows")
    if not applied:
        print("No rows with verdict set — fill verdict in gold_fixes.csv and re-run.")
        return

    if args.import_after:
        annotations, parquet_path, jsonl_path = import_gold_csv(
            input_path=out_csv,
            script=__file__,
        )
        print(f"Imported {len(annotations)} labelled rows")
        print(f"Parquet: {parquet_path}")
        print(f"JSONL:   {jsonl_path}")


if __name__ == "__main__":
    main()
