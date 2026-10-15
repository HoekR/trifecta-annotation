#!/usr/bin/env python3
"""Build merged TRIFECTA thesaurus from Food_terms + cort-voc-db + optional modern curations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.thesaurus import build_thesaurus, thesaurus_summary


def _read_optional(path: str | None) -> pd.DataFrame | None:
    if path is None:
        return None
    resolved = Path(path).expanduser()
    if not resolved.exists():
        return None
    return pd.read_csv(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build trifecta_thesaurus.csv (vectorized merge).")
    parser.add_argument(
        "--food-terms",
        default="/Users/rikhoekstra/develop/recepten-preservare-analysis/source_data/Food_terms.csv",
        help="Food_terms.csv path (default: preservare source_data)",
    )
    parser.add_argument(
        "--categories",
        default="/Users/rikhoekstra/develop/cort-voc-db/data/categories.csv",
    )
    parser.add_argument(
        "--types-merged",
        default="/Users/rikhoekstra/develop/cort-voc-db/data/types_merged.csv",
    )
    parser.add_argument(
        "--technique-assoc",
        default="/Users/rikhoekstra/develop/cort-voc-db/data/technique_term_association.csv",
    )
    parser.add_argument(
        "--modern-dir",
        default="/Users/rikhoekstra/develop/Dutch-historical-recipe-trends",
        help="Directory with vegetables_curated.csv, vlees.csv, …",
    )
    parser.add_argument("--output-logical", default="trifecta_thesaurus")
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument(
        "--no-decompose-compounds",
        action="store_true",
        help="Keep compound surface forms (skip modifier+head collapse).",
    )
    parser.add_argument(
        "--snippets",
        default=None,
        help="food_snippets_long CSV for snippet_freq (default: data manifest food_snippets_long)",
    )
    parser.add_argument(
        "--min-snippet-freq",
        type=int,
        default=1,
        help="Demote keep=yes/review aliases below this matched_term count (default: 1).",
    )
    args = parser.parse_args()

    modern_dir = Path(args.modern_dir)
    modern_paths = [
        modern_dir / name
        for name in ("vegetables_curated.csv", "vlees.csv", "vis.csv", "koolhydraten.csv")
    ]

    food_terms = pd.read_csv(args.food_terms)
    if args.snippets:
        snippets_path = Path(args.snippets).expanduser()
        snippets = pd.read_csv(snippets_path) if snippets_path.exists() else None
    else:
        try:
            snippets = pd.read_csv(resolve("food_snippets_long"))
        except Exception:
            snippets = None

    thesaurus = build_thesaurus(
        food_terms=food_terms,
        categories=_read_optional(args.categories),
        types_merged=_read_optional(args.types_merged),
        technique_assoc=_read_optional(args.technique_assoc),
        modern_curated=modern_paths,
        decompose_compounds=not args.no_decompose_compounds,
        snippets=snippets,
        min_snippet_freq=args.min_snippet_freq if snippets is not None else 0,
    )

    if args.output_path:
        out = Path(args.output_path).expanduser().resolve()
    else:
        out = resolve(args.output_logical)
    out.parent.mkdir(parents=True, exist_ok=True)
    thesaurus.to_csv(out, index=False)

    print(out)
    if args.summary:
        print(json.dumps(thesaurus_summary(thesaurus), indent=2))


if __name__ == "__main__":
    main()
