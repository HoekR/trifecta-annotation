#!/usr/bin/env python3
"""Export food-target collocation skeleton from food_snippets_long KWICs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.collocation_skeleton import (
    SKELETON_COLUMNS,
    collect_collocation_skeleton,
    skeleton_summary,
)


def _parse_targets(raw: str) -> set[str]:
    return {part.strip() for part in raw.split(",") if part.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--targets",
        default="",
        help="Comma-separated food targets (default: all thesaurus terms in snippets)",
    )
    parser.add_argument("--snippets-long-path", type=Path, default=None)
    parser.add_argument("--thesaurus-path", default=None)
    parser.add_argument("--no-thesaurus-filter", action="store_true")
    parser.add_argument("--window", type=int, default=5, help="±tokens around target")
    parser.add_argument("--min-cooc", type=int, default=3)
    parser.add_argument("--min-pmi", type=float, default=0.0)
    parser.add_argument("--by-regime", action="store_true", help="Stratify by text_regime")
    parser.add_argument("--max-per-target", type=int, default=20)
    parser.add_argument("--verbs-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Row limit for quick runs")
    parser.add_argument(
        "--train-fasttext",
        action="store_true",
        help="Train a small FastText model on snippets (requires gensim extra)",
    )
    parser.add_argument(
        "--fasttext-model",
        default=None,
        help="Path to pre-trained .vec or .bin for similarity boost",
    )
    parser.add_argument("--fasttext-train-limit", type=int, default=40_000)
    parser.add_argument("--fasttext-epochs", type=int, default=5)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Default: scratch/eval/collocation_skeleton.csv",
    )
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    targets = _parse_targets(args.targets) or None
    scratch = Path(resolve("trifecta_gold")).parent
    out_path = args.output_path or scratch / "eval" / "collocation_skeleton.csv"

    hits = collect_collocation_skeleton(
        path=args.snippets_long_path,
        thesaurus_path=args.thesaurus_path,
        thesaurus_filter=not args.no_thesaurus_filter,
        targets=targets,
        limit=args.limit,
        window_tokens=args.window,
        min_cooc=args.min_cooc,
        min_pmi=args.min_pmi,
        by_regime=args.by_regime,
        max_per_target=args.max_per_target,
        verbs_only=args.verbs_only,
        fasttext_model_path=args.fasttext_model,
        train_fasttext=args.train_fasttext,
        fasttext_train_limit=args.fasttext_train_limit,
        fasttext_epochs=args.fasttext_epochs,
        seed=args.seed,
    )

    if args.summary:
        print(json.dumps(skeleton_summary(hits), indent=2), file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([hit.to_dict() for hit in hits], columns=list(SKELETON_COLUMNS)).to_csv(
        out_path,
        index=False,
    )
    print(f"Wrote {len(hits)} rows → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
