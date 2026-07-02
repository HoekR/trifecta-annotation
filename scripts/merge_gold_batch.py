#!/usr/bin/env python3
"""Append a new gold candidate batch into gold_labelling_all.csv."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.gold_io import export_gold_csv, import_gold_csv, merge_labelling_rows


def _default_batch_csv() -> Path:
    return Path(resolve("trifecta_gold_csv"))


def _default_merged_csv() -> Path:
    parent = Path(resolve("trifecta_gold")).parent
    merged = parent / "gold_labelling_all.csv"
    if merged.exists():
        return merged
    return _default_batch_csv()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge a candidate batch (gold_labelling.csv) into gold_labelling_all.csv. "
            "New record_ids are appended; overlaps update only unlabelled rows unless "
            "--overwrite-labelled."
        ),
    )
    parser.add_argument("--batch-path", type=Path, default=None, help="New batch CSV")
    parser.add_argument("--into-path", type=Path, default=None, help="Merged gold CSV")
    parser.add_argument("--overwrite-labelled", action="store_true")
    parser.add_argument(
        "--import-after",
        action="store_true",
        help="Import labelled rows from merged CSV into gold.parquet",
    )
    args = parser.parse_args()

    batch_path = args.batch_path or _default_batch_csv()
    into_path = args.into_path or _default_merged_csv()
    if not batch_path.exists():
        raise SystemExit(f"Batch CSV not found: {batch_path}")

    batch = pd.read_csv(batch_path, dtype=str, keep_default_na=False)
    if into_path.exists() and into_path.resolve() != batch_path.resolve():
        existing = pd.read_csv(into_path, dtype=str, keep_default_na=False)
    else:
        existing = pd.DataFrame(columns=batch.columns)

    before = len(existing)
    merged = merge_labelling_rows(
        existing,
        batch.to_dict(orient="records"),
        overwrite_labelled=args.overwrite_labelled,
    )
    export_gold_csv(merged.to_dict(orient="records"), output_path=into_path)
    added = len(merged) - before
    print(f"Merged CSV: {into_path}")
    print(f"Rows: {before} → {len(merged)} (+{added} new record_ids)")

    if args.import_after:
        annotations, parquet_path, jsonl_path = import_gold_csv(
            input_path=into_path,
            script=__file__,
        )
        print(f"Imported {len(annotations)} labelled rows")
        print(f"Parquet: {parquet_path}")
        print(f"JSONL:   {jsonl_path}")


if __name__ == "__main__":
    main()
