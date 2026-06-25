#!/usr/bin/env python3
"""Export existing gold set to CSV for editing."""

from __future__ import annotations

import argparse

from trifecta_annotation.gold_io import export_existing_gold_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Export gold set to CSV.")
    parser.add_argument("--gold-logical", default="trifecta_gold")
    parser.add_argument("--gold-path", default=None, help="Parquet, JSONL, or CSV path")
    parser.add_argument("--output-logical", default="trifecta_gold_csv")
    parser.add_argument("--output-path", default=None)
    args = parser.parse_args()

    path = export_existing_gold_csv(
        gold_logical=args.gold_logical,
        gold_path=args.gold_path,
        output_logical=args.output_logical,
        output_path=args.output_path,
    )
    print(path)


if __name__ == "__main__":
    main()
