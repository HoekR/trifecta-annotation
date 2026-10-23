#!/usr/bin/env python3
"""Merge silver JSONL files (e.g. INCEpTION + KWIC Step-A NONE tranche)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from data_io import load_jsonl

from trifecta_annotation.dropout_review import filter_dropout_records
from trifecta_annotation.silver_merge import is_step_a_dropout, merge_silver_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge TRIFECTA silver JSONL sources.")
    parser.add_argument("--base", required=True, help="Base silver JSONL (e.g. inception_annotations.jsonl)")
    parser.add_argument("--append", required=True, help="Rows to append (e.g. reizen Step A output)")
    parser.add_argument(
        "--dropout-only",
        action="store_true",
        help="Keep only Step A dropouts from --append (NONE silver candidates)",
    )
    parser.add_argument(
        "--append-limit",
        type=int,
        default=200,
        help="Max rows to take from --append after filtering (default 200)",
    )
    parser.add_argument(
        "--review-csv",
        type=Path,
        default=None,
        help="Review CSV from export_step_a_dropout_review.py (verdict=accept only)",
    )
    parser.add_argument("--output", required=True, help="Merged silver JSONL path")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    review = (
        pd.read_csv(args.review_csv, dtype=str, keep_default_na=False)
        if args.review_csv
        else None
    )
    append_records = load_jsonl(args.append)
    if args.dropout_only or review is not None:
        append_records = filter_dropout_records(append_records, review=review)
    if args.append_limit is not None:
        append_records = append_records[: args.append_limit]

    merged = merge_silver_records(load_jsonl(args.base), append_records)

    out = Path(args.output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for record in merged:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    base_n = sum(1 for _ in open(args.base, encoding="utf-8"))
    added = len(merged) - base_n
    print(f"Merged silver: {out} ({base_n} base + {added} new = {len(merged)} total)")
    if args.summary:
        dropouts = sum(1 for record in merged if is_step_a_dropout(record))
        print(f"  Step A dropouts in merged file: {dropouts}")


if __name__ == "__main__":
    main()
