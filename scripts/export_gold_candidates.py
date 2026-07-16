#!/usr/bin/env python3
"""Export diverse gold-labelling CSV rows for manual annotation."""

from __future__ import annotations

import argparse
import json

from trifecta_annotation.gold_io import export_candidates_csv
from trifecta_annotation.sampling import sample_kwic_inputs_for_gold, sample_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export gold labelling candidates (diverse sample by default).",
    )
    parser.add_argument("--limit", type=int, default=50, help="Number of examples")
    parser.add_argument(
        "--source",
        default="diverse",
        choices=["diverse", "kwic_inputs", "manual", "food_snippets", "long"],
        help="diverse = stratified mix from food_snippets_long (default); manual = txt subset only",
    )
    parser.add_argument("--seed", type=int, default=0, help="Random seed for sampling")
    parser.add_argument(
        "--no-manual-seed",
        action="store_true",
        help="For diverse source: do not prioritise curated txt snippets",
    )
    parser.add_argument("--input-logical", default="kwic_inputs")
    parser.add_argument("--input-path", default=None)
    parser.add_argument("--output-logical", default="trifecta_gold_csv")
    parser.add_argument("--output-path", default=None)
    parser.add_argument(
        "--snippet-format",
        choices=["long", "wide"],
        default="long",
        help="For diverse source: long = food_snippets_long (default); wide = legacy food_snippets",
    )
    parser.add_argument(
        "--no-thesaurus-filter",
        action="store_true",
        help="Disable thesaurus filtering (include all matched_term rows)",
    )
    parser.add_argument("--thesaurus-path", default=None)
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print work distribution JSON to stderr",
    )
    args = parser.parse_args()

    if args.summary and args.source == "diverse":
        records = sample_kwic_inputs_for_gold(
            limit=args.limit,
            seed=args.seed,
            include_manual=not args.no_manual_seed,
            snippet_format=args.snippet_format,
            logical_name=(
                "food_snippets_long"
                if args.snippet_format == "long"
                else "food_snippets"
            ),
            thesaurus_filter=not args.no_thesaurus_filter,
            thesaurus_path=args.thesaurus_path,
        )
        import sys

        print(json.dumps(sample_summary(records), indent=2), file=sys.stderr)

    path = export_candidates_csv(
        limit=args.limit,
        source=args.source,
        seed=args.seed,
        include_manual=not args.no_manual_seed,
        input_logical=args.input_logical,
        input_path=args.input_path,
        output_logical=args.output_logical,
        output_path=args.output_path,
        thesaurus_filter=not args.no_thesaurus_filter,
        thesaurus_path=args.thesaurus_path,
    )
    print(path)


if __name__ == "__main__":
    main()
