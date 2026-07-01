#!/usr/bin/env python3
"""Grow frame-verb lexicon from recipes + cort-voc expansions (not general prose)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from trifecta_annotation.frame_verb_corpus import (
    DEFAULT_CORPUS_LEXICON_PATH,
    candidates_to_dataframe,
    collapse_candidates_by_lemma,
    frequent_food_matched_terms,
    mine_frame_verb_candidates,
)
from trifecta_annotation.frame_verb_recipes import (
    DEFAULT_RECIPE_DATASET_PATH,
    load_recipe_dataset,
    mine_recipe_gloss_verbs,
)
from trifecta_annotation.vocabulary import resolve_thesaurus_lookup


def _recipe_candidates_to_df(candidates) -> pd.DataFrame:
    frame = candidates_to_dataframe(candidates)
    frame["keep"] = "yes"
    frame["notes"] = "recipe_gloss"
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grow frame-verb lexicon from recipe glosses and cort-voc technique expansions.",
    )
    parser.add_argument(
        "--recipe-dataset",
        default=str(DEFAULT_RECIPE_DATASET_PATH),
        help="Preservare recipe_dataset CSV with bracket glosses",
    )
    parser.add_argument(
        "--output-path",
        default=str(DEFAULT_CORPUS_LEXICON_PATH),
        help="Review CSV (recipe rows default keep=yes; add prose candidates with --prose-miner)",
    )
    parser.add_argument(
        "--prose-miner",
        action="store_true",
        help="Also mine cort_voc_db prose snippets (noisy; for manual review only)",
    )
    parser.add_argument("--snippets", default=None, help="food_snippets CSV for prose miner")
    parser.add_argument("--snippets-long", default=None, help="food_snippets_long for exclusions")
    parser.add_argument("--thesaurus-path", default=None)
    parser.add_argument("--max-window", type=int, default=120)
    parser.add_argument(
        "--collapse",
        action="store_true",
        help="Merge variant rows; default keeps one row per surface form for manual historic_forms",
    )
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    recipe_path = Path(args.recipe_dataset).expanduser()
    if not recipe_path.exists():
        raise SystemExit(f"Recipe dataset not found: {recipe_path}")

    recipes = load_recipe_dataset(recipe_path)
    mined = mine_recipe_gloss_verbs(recipes)
    if args.collapse:
        mined = collapse_candidates_by_lemma(mined)
    recipe_rows = _recipe_candidates_to_df(mined)

    frames = [recipe_rows]
    if args.prose_miner:
        from trifecta_annotation.adapters.food_snippets import (
            load_food_snippets_frame,
            load_food_snippets_long_frame,
        )

        lookup = resolve_thesaurus_lookup(thesaurus_path=args.thesaurus_path)
        if not lookup:
            raise SystemExit("No thesaurus lookup for prose miner.")
        snippets = (
            load_food_snippets_frame(path=args.snippets)
            if args.snippets
            else load_food_snippets_frame()
        )
        snippets_long = (
            load_food_snippets_long_frame(path=args.snippets_long)
            if args.snippets_long
            else load_food_snippets_long_frame()
        )
        prose = candidates_to_dataframe(
            mine_frame_verb_candidates(
                snippets,
                food_lookup=lookup,
                exclude_terms=frequent_food_matched_terms(snippets_long),
                max_window=args.max_window,
            ),
        )
        prose["notes"] = "prose_miner_review"
        frames.append(prose)

    out_frame = pd.concat(frames, ignore_index=True)
    out_frame = out_frame.drop_duplicates(subset=["term_norm"], keep="first")

    out = Path(args.output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out_frame.to_csv(out, index=False)
    print(out)

    if args.summary:
        print(
            json.dumps(
                {
                    "rows": len(out_frame),
                    "recipe_gloss": int((out_frame["notes"] == "recipe_gloss").sum()),
                    "prose_review": int((out_frame["notes"] == "prose_miner_review").sum()),
                    "top_recipe": out_frame.head(15)[
                        ["term_norm", "frame_hint", "snippet_freq", "anchor_frames"]
                    ].to_dict(orient="records"),
                },
                indent=2,
            ),
        )


if __name__ == "__main__":
    main()
