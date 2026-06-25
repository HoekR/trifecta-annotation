#!/usr/bin/env python3
"""Build normalized KwicInput JSONL from TRIFECTA food snippets."""

from __future__ import annotations

import argparse

from data_io import save_semi_structured

from trifecta_annotation.adapters.food_snippets import load_kwic_inputs_from_food_snippets


def main() -> None:
    parser = argparse.ArgumentParser(description="Build kwic_inputs from food snippets.")
    parser.add_argument(
        "--all-snippets",
        action="store_true",
        help="Use full food_snippets CSV (~31k rows) instead of manual txt subset",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    manual_only = not args.all_snippets
    records, skipped = load_kwic_inputs_from_food_snippets(
        manual_only=manual_only,
        limit=args.limit,
    )
    parent = "food_snippets_manual" if manual_only else "food_snippets"
    save_semi_structured(
        [record.model_dump(mode="json") for record in records],
        logical_name="kwic_inputs",
        parent_sources=[parent],
        description="Normalized KwicInput records from cort_voc_db food snippets",
        script=__file__,
    )
    subset = "manual" if manual_only else "full"
    print(f"Wrote {len(records)} inputs ({len(skipped)} skipped, source={subset})")


if __name__ == "__main__":
    main()
