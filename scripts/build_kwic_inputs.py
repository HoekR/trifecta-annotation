#!/usr/bin/env python3
"""Build normalized KwicInput JSONL from TRIFECTA food snippets."""

from __future__ import annotations

import argparse
from pathlib import Path

from data_io import save_semi_structured

from trifecta_annotation.adapters.food_snippets import (
    DEFAULT_KWIC_CONTEXT_RADIUS,
    load_kwic_inputs_from_food_snippets,
    load_kwic_inputs_from_food_snippets_kwic,
    load_kwic_inputs_from_food_snippets_long,
)
from trifecta_annotation.adapters.inception_tsv import load_inception_kwic_inputs
from trifecta_annotation.verb_kwic import sample_verb_kwic_for_gold


def _default_inception_export_root() -> Path:
    from data_io import resolve

    scratch = Path(resolve("trifecta_gold")).parent
    dated = scratch / "inception_nl" / "export_20260703"
    return dated if dated.is_dir() else scratch


def main() -> None:
    parser = argparse.ArgumentParser(description="Build kwic_inputs from food snippets.")
    parser.add_argument(
        "--source",
        choices=["manual", "wide", "long", "kwic", "verb", "inception"],
        default="long",
        help="manual = curated txt; wide/long = legacy CSV; kwic = xlsx ingest with kwic_batch",
    )
    parser.add_argument(
        "--inception-export-root",
        type=Path,
        default=None,
        help="Unzipped INCEpTION export root (with source/ + annotation/)",
    )
    parser.add_argument(
        "--inception-annotator",
        action="append",
        default=[],
        help="Limit INCEpTION import to annotator username(s)",
    )
    parser.add_argument(
        "--kwic-batch",
        action="append",
        default=[],
        help="For --source kwic: keep rows matching batch tag(s): recept, reizen, inmaken, medicijn",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--context-radius",
        type=int,
        default=None,
        help=(
            "Chars each side of matched_term (target-centered window). "
            f"Default {DEFAULT_KWIC_CONTEXT_RADIUS} for --source kwic; off for long/wide unless set."
        ),
    )
    parser.add_argument(
        "--full-context",
        action="store_true",
        help="Keep passage-length snippets (no target-centered clip)",
    )
    parser.add_argument(
        "--no-thesaurus-filter",
        action="store_true",
        help="Include all long-format rows (skip thesaurus filter)",
    )
    parser.add_argument("--thesaurus-path", default=None)
    args = parser.parse_args()

    thesaurus_filter = not args.no_thesaurus_filter
    thesaurus_path = args.thesaurus_path
    kwic_batches = args.kwic_batch or None

    if args.full_context:
        context_radius = None
    elif args.context_radius is not None:
        context_radius = args.context_radius
    elif args.source == "kwic":
        context_radius = DEFAULT_KWIC_CONTEXT_RADIUS
    else:
        context_radius = None

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
    elif args.source == "inception":
        export_root = args.inception_export_root or _default_inception_export_root()
        annotators = set(args.inception_annotator) if args.inception_annotator else None
        records, skipped = load_inception_kwic_inputs(
            export_root,
            annotators=annotators,
        )
        if args.limit is not None:
            records = records[: args.limit]
        parent = str(export_root)
    elif args.source == "kwic":
        records, skipped = load_kwic_inputs_from_food_snippets_kwic(
            limit=args.limit,
            kwic_batches=kwic_batches,
            thesaurus_filter=thesaurus_filter,
            thesaurus_path=thesaurus_path,
            context_radius=context_radius,
        )
        parent = "food_snippets_long_kwic"
    else:
        records, skipped = load_kwic_inputs_from_food_snippets_long(
            limit=args.limit,
            thesaurus_filter=thesaurus_filter,
            thesaurus_path=thesaurus_path,
            context_radius=context_radius,
        )
        parent = "food_snippets_long"

    save_semi_structured(
        [record.model_dump(mode="json") for record in records],
        logical_name="kwic_inputs",
        parent_sources=[parent],
        description=f"Normalized KwicInput records (source={args.source})",
        script=__file__,
    )
    batch_note = f", kwic_batch={kwic_batches}" if kwic_batches else ""
    radius_note = (
        ", full_context"
        if context_radius is None
        else f", context_radius={context_radius}"
    )
    if records and context_radius is not None:
        lengths = [len(record.context_text) for record in records]
        radius_note += f", context_len_p50={sorted(lengths)[len(lengths) // 2]}"
    print(
        f"Wrote {len(records)} inputs ({len(skipped)} skipped, source={args.source}"
        f"{batch_note}{radius_note})",
    )


if __name__ == "__main__":
    main()
