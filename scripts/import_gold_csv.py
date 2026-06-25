#!/usr/bin/env python3
"""Import labelled gold CSV into trifecta_gold parquet + JSONL."""

from __future__ import annotations

import argparse

from trifecta_annotation.gold_io import import_gold_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Import labelled gold CSV.")
    parser.add_argument("--input-logical", default="trifecta_gold_csv")
    parser.add_argument("--input-path", default=None)
    parser.add_argument("--output-logical", default="trifecta_gold")
    parser.add_argument("--output-jsonl-logical", default="trifecta_gold_jsonl")
    args = parser.parse_args()

    annotations, parquet_path, jsonl_path = import_gold_csv(
        input_logical=args.input_logical,
        input_path=args.input_path,
        output_logical=args.output_logical,
        output_jsonl_logical=args.output_jsonl_logical,
        script=__file__,
    )
    print(f"Imported {len(annotations)} labelled rows")
    print(f"Parquet: {parquet_path}")
    print(f"JSONL:   {jsonl_path}")


if __name__ == "__main__":
    main()
