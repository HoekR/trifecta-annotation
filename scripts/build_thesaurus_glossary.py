#!/usr/bin/env python3
"""Export top-frequency thesaurus pref_labels with English glosses for human review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.glossary import (
    GLOSSARY_COLUMNS,
    build_glossary_candidates,
    translate_glossary_candidates,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build bilingual thesaurus glossary (top pref_labels by snippet_freq).",
    )
    parser.add_argument("--thesaurus-path", default=None, help="Override trifecta_thesaurus.csv")
    parser.add_argument("--snippets-path", default=None, help="Override food_snippets_long.csv")
    parser.add_argument("--limit", type=int, default=100, help="Max pref_labels (default: 100)")
    parser.add_argument("--output-logical", default="trifecta_thesaurus_glossary")
    parser.add_argument("--output-path", default=None)
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Export candidates only (fill English columns yourself or via DeepL).",
    )
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    if args.thesaurus_path:
        thesaurus = pd.read_csv(Path(args.thesaurus_path).expanduser())
    else:
        thesaurus = pd.read_csv(resolve("trifecta_thesaurus"))

    snippets = None
    if args.snippets_path:
        snippets = pd.read_csv(Path(args.snippets_path).expanduser())
    else:
        try:
            snippets = pd.read_csv(resolve("food_snippets_long"))
        except Exception:
            snippets = None

    candidates = build_glossary_candidates(thesaurus, snippets=snippets, limit=args.limit)
    if not args.no_translate:
        candidates = translate_glossary_candidates(
            candidates,
            batch_size=args.batch_size,
            backend="llm",
        )

    if args.output_path:
        out = Path(args.output_path).expanduser().resolve()
    else:
        out = resolve(args.output_logical)
    out.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(out, index=False)
    print(out)

    if args.summary:
        print(
            json.dumps(
                {
                    "rows": len(candidates),
                    "translated": int(candidates["pref_label_en"].astype(str).str.strip().ne("").sum()),
                    "top": candidates.head(10)[["pref_label", "pref_label_en", "snippet_freq"]].to_dict(
                        orient="records",
                    ),
                },
                indent=2,
            ),
        )


if __name__ == "__main__":
    main()
