#!/usr/bin/env python3
"""Copy TRIFECTA food snippet sources from OneDrive/Downloads to scratch tier."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.adapters.food_snippets import (
    dedupe_food_snippets_long_frame,
    explode_food_snippets_wide_frame,
)


def _copy(src: Path, logical_name: str) -> Path:
    dest = resolve(logical_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def _resolve_kwic_xlsx_source(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser()
    try:
        path = resolve("food_snippets_kwic_xlsx_source")
    except Exception:
        return None
    return path if path.exists() else None


def _ingest_kwic_xlsx(
    xlsx_source: Path,
    *,
    dedupe_subset: tuple[str, ...],
    skip_wide: bool,
    skip_long: bool,
) -> None:
    wide = pd.read_excel(xlsx_source)
    if not skip_wide:
        wide_dest = resolve("food_snippets_kwic")
        wide_dest.parent.mkdir(parents=True, exist_ok=True)
        wide.to_csv(wide_dest, index=False)
        print(f"KWIC wide CSV: {wide_dest} ({len(wide):,} rows)")

    if skip_long:
        return

    long_raw = explode_food_snippets_wide_frame(wide)
    long_deduped, dropped = dedupe_food_snippets_long_frame(
        long_raw,
        subset=dedupe_subset,
    )
    long_dest = resolve("food_snippets_long_kwic")
    long_dest.parent.mkdir(parents=True, exist_ok=True)
    long_deduped.to_csv(long_dest, index=False)
    print(
        f"KWIC long CSV: {long_dest} "
        f"({len(long_deduped):,} rows from {len(long_raw):,} exploded; "
        f"{len(dropped):,} duplicate keys)",
    )


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
        "--long-csv-source",
        default="/Users/rikhoekstra/Library/CloudStorage/OneDrive-KNAW/data/trifecta/cort_voc_db/processed_outputs/food_snippets_long.csv",
        help="Exploded food_snippets_long CSV (one matched_term per row)",
    )
    parser.add_argument(
        "--txt-source",
        default="/Users/rikhoekstra/Downloads/snippets_for_annotation.txt",
        help="Manual annotation snippet list (txt)",
    )
    parser.add_argument(
        "--kwic-xlsx-source",
        default=None,
        help="KWIC batch xlsx (default: manifest food_snippets_kwic_xlsx_source)",
    )
    parser.add_argument(
        "--dedupe-long-by",
        choices=("snippet_term", "doc_term"),
        default="snippet_term",
        help="Long dedupe key: snippet+term (default) or doc_id+term (legacy kwic_inputs)",
    )
    parser.add_argument("--skip-csv", action="store_true")
    parser.add_argument("--skip-long-csv", action="store_true")
    parser.add_argument("--skip-txt", action="store_true")
    parser.add_argument(
        "--skip-kwic-xlsx",
        action="store_true",
        help="Skip KWIC xlsx ingest (wide + deduped long with manual_labels)",
    )
    args = parser.parse_args()

    dedupe_subset = (
        ("doc_id", "matched_term_norm")
        if args.dedupe_long_by == "doc_term"
        else ("snippet", "matched_term_norm")
    )

    if not args.skip_kwic_xlsx:
        kwic_source = _resolve_kwic_xlsx_source(args.kwic_xlsx_source)
        if kwic_source is None:
            print("KWIC xlsx: skipped (manifest source missing or not found)")
        else:
            _ingest_kwic_xlsx(
                kwic_source,
                dedupe_subset=dedupe_subset,
                skip_wide=False,
                skip_long=False,
            )

    if not args.skip_csv:
        csv_dest = _copy(Path(args.csv_source), "food_snippets")
        print(f"CSV: {csv_dest}")
    if not args.skip_long_csv:
        long_dest = _copy(Path(args.long_csv_source), "food_snippets_long")
        print(f"LONG CSV: {long_dest}")
    if not args.skip_txt:
        txt_dest = _copy(Path(args.txt_source), "food_snippets_manual")
        print(f"TXT: {txt_dest}")


if __name__ == "__main__":
    main()
