#!/usr/bin/env python3
"""Copy TRIFECTA food snippet sources from OneDrive/Downloads to scratch tier."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from data_io import resolve


def _copy(src: Path, logical_name: str) -> Path:
    dest = resolve(logical_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest food snippet CSV/txt into scratch-tier manifest datasets.",
    )
    parser.add_argument(
        "--csv-source",
        default="/Users/rikhoekstra/Library/CloudStorage/OneDrive-KNAW/data/trifecta/cort_voc_db/processed_outputs/food_snippets_for_annotation.csv",
        help="Canonical food_snippets CSV on OneDrive",
    )
    parser.add_argument(
        "--txt-source",
        default="/Users/rikhoekstra/Downloads/snippets_for_annotation.txt",
        help="Manual annotation snippet list (txt)",
    )
    parser.add_argument("--skip-csv", action="store_true")
    parser.add_argument("--skip-txt", action="store_true")
    args = parser.parse_args()

    if not args.skip_csv:
        csv_dest = _copy(Path(args.csv_source), "food_snippets")
        print(f"CSV: {csv_dest}")
    if not args.skip_txt:
        txt_dest = _copy(Path(args.txt_source), "food_snippets_manual")
        print(f"TXT: {txt_dest}")


if __name__ == "__main__":
    main()
