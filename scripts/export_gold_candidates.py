#!/usr/bin/env python3
"""Export verb-seeded and food-seeded gold candidate batches."""

from __future__ import annotations

import argparse
import json
import sys

from trifecta_annotation.gold_io import export_candidates_csv
from trifecta_annotation.sampling import sample_kwic_inputs_for_gold, sample_summary
from trifecta_annotation.verb_kwic import sample_verb_kwic_for_gold, verb_sample_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export gold labelling candidates (diverse, mixed, verb, …).",
    )
    parser.add_argument("--limit", type=int, default=50, help="Number of examples")
    parser.add_argument(
        "--source",
        default="diverse",
        choices=["diverse", "mixed", "verb", "kwic_inputs", "manual", "food_snippets", "long"],
        help="mixed = 50%% verb-seeded + 50%% food; verb = frame verbs only",
    )
    parser.add_argument(
        "--verb-share",
        type=float,
        default=0.0,
        help="For diverse source: fraction of rows from verb-seeded KWIC (0–1)",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-manual-seed", action="store_true")
    parser.add_argument("--output-logical", default="trifecta_gold_csv")
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--no-thesaurus-filter", action="store_true")
    parser.add_argument("--thesaurus-path", default=None)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    if args.summary:
        if args.source == "verb":
            records = sample_verb_kwic_for_gold(
                limit=args.limit,
                seed=args.seed,
                thesaurus_path=args.thesaurus_path,
            )
            print(json.dumps(verb_sample_summary(records), indent=2), file=sys.stderr)
        elif args.source in {"diverse", "mixed"}:
            share = 0.5 if args.source == "mixed" else args.verb_share
            records = sample_kwic_inputs_for_gold(
                limit=args.limit,
                seed=args.seed,
                include_manual=not args.no_manual_seed,
                verb_share=share,
                thesaurus_path=args.thesaurus_path,
            )
            modes: dict[str, int] = {}
            for record in records:
                modes[record.kwic_mode] = modes.get(record.kwic_mode, 0) + 1
            print(
                json.dumps(
                    {"works": sample_summary(records), "kwic_mode": modes},
                    indent=2,
                ),
                file=sys.stderr,
            )

    path = export_candidates_csv(
        limit=args.limit,
        source=args.source,
        seed=args.seed,
        include_manual=not args.no_manual_seed,
        verb_share=args.verb_share,
        output_logical=args.output_logical,
        output_path=args.output_path,
        thesaurus_filter=not args.no_thesaurus_filter,
        thesaurus_path=args.thesaurus_path,
    )
    print(path)


if __name__ == "__main__":
    main()
