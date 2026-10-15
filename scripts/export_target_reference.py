#!/usr/bin/env python3
"""Export stratified target-word sense gallery for homograph review."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.review_columns import HOMONYM_REVIEW_HELP
from trifecta_annotation.target_reference import (
    REFERENCE_COLUMNS,
    collect_gallery_pool,
    gallery_summary,
    load_gold_lookup,
    resolve_target_terms,
    stratify_gallery,
)


def _parse_targets(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--targets",
        default="",
        help="Comma-separated targets (default: polysemous set + gold/fixes when enabled)",
    )
    parser.add_argument(
        "--no-polysemous",
        action="store_true",
        help="Do not include default POLYSEMOUS_TARGETS list",
    )
    parser.add_argument(
        "--include-gold-targets",
        action="store_true",
        help="Also export every target_word present in gold.parquet",
    )
    parser.add_argument(
        "--from-gold-fixes",
        action="store_true",
        help="Add every target_word listed in gold_fixes.csv",
    )
    parser.add_argument(
        "--gold-fixes-path",
        type=Path,
        default=None,
        help="Also include targets from eval/gold_fixes.csv",
    )
    parser.add_argument("--gold-path", type=Path, default=None)
    parser.add_argument("--max-per-bucket", type=int, default=3)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--no-thesaurus-filter", action="store_true")
    parser.add_argument("--thesaurus-path", default=None)
    parser.add_argument("--snippets-long-path", type=Path, default=None)
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Default: scratch/eval/target_reference_gallery.csv",
    )
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    scratch = Path(resolve("trifecta_gold")).parent
    gold_path = args.gold_path or scratch / "gold.parquet"
    gold_fixes = args.gold_fixes_path or scratch / "eval" / "gold_fixes.csv"

    targets = resolve_target_terms(
        targets=_parse_targets(args.targets) or None,
        polysemous=not args.no_polysemous,
        gold_path=gold_path,
        gold_fixes_path=gold_fixes if args.from_gold_fixes and gold_fixes.exists() else None,
        include_gold_targets=args.include_gold_targets,
    )
    if not targets:
        print("No targets selected.", file=sys.stderr)
        raise SystemExit(1)

    gold_lookup = load_gold_lookup(gold_path) if gold_path.exists() else {}
    pool = collect_gallery_pool(
        targets=targets,
        path=args.snippets_long_path,
        thesaurus_filter=not args.no_thesaurus_filter,
        thesaurus_path=args.thesaurus_path,
        gold_lookup=gold_lookup,
    )
    rows = stratify_gallery(
        pool,
        max_per_bucket=args.max_per_bucket,
        seed=args.seed,
    )

    if args.summary:
        print(
            json.dumps(
                {
                    "targets": sorted(targets),
                    "pool_rows": len(pool),
                    **gallery_summary(rows),
                },
                indent=2,
            ),
            file=sys.stderr,
        )

    out_path = args.output_path or scratch / "eval" / "target_reference_gallery.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([row.to_dict() for row in rows], columns=list(REFERENCE_COLUMNS)).to_csv(
        out_path,
        index=False,
    )
    print(f"Wrote {len(rows)} rows ({len(targets)} targets) → {out_path}", file=sys.stderr)
    print(f"Fill sense_bucket / homonym columns during review. {HOMONYM_REVIEW_HELP}", file=sys.stderr)


if __name__ == "__main__":
    main()
