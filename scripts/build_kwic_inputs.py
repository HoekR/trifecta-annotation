#!/usr/bin/env python3
"""Build normalized KwicInput JSONL from TRIFECTA food snippets."""

from __future__ import annotations

import argparse

from data_io import save_semi_structured

from trifecta_annotation.adapters.food_snippets import (
    load_kwic_inputs_from_food_snippets,
    load_kwic_inputs_from_food_snippets_long,
)
from trifecta_annotation.verb_kwic import sample_verb_kwic_for_gold


def main() -> None:
    parser = argparse.ArgumentParser(description="Build kwic_inputs from food snippets.")
    parser.add_argument(
        "--source",
        choices=["manual", "wide", "long", "verb"],
        default="long",
        help="manual = curated txt; wide/long = food keyword; verb = frame-verb discovery",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--no-thesaurus-filter",
        action="store_true",
        help="Include all long-format rows (skip thesaurus filter)",
    )
    parser.add_argument("--thesaurus-path", default=None)
    args = parser.parse_args()

    thesaurus_filter = not args.no_thesaurus_filter
    thesaurus_path = args.thesaurus_path

    if args.source == "manual":
        records, skipped = load_kwic_inputs_from_food_snippets(
            manual_only=True,
            limit=args.limit,
        )
        parent = "food_snippets_manual"
    elif args.source == "wide":
        records, skipped = load_kwic_inputs_from_food_snippets(
            manual_only=False,
            limit=args.limit,
        )
        parent = "food_snippets"
    elif args.source == "verb":
        records = sample_verb_kwic_for_gold(
            limit=args.limit or 500,
            thesaurus_path=thesaurus_path,
        )
        skipped = []
        parent = "food_snippets"
    else:
        records, skipped = load_kwic_inputs_from_food_snippets_long(
            limit=args.limit,
            thesaurus_filter=thesaurus_filter,
            thesaurus_path=thesaurus_path,
        )
        parent = "food_snippets_long"

    save_semi_structured(
        [record.model_dump(mode="json") for record in records],
        logical_name="kwic_inputs",
        parent_sources=[parent],
        description="Normalized KwicInput records from cort_voc_db food snippets",
        script=__file__,
    )
    print(f"Wrote {len(records)} inputs ({len(skipped)} skipped, source={args.source})")


if __name__ == "__main__":
    main()
