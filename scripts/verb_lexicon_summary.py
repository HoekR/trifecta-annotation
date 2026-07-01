#!/usr/bin/env python3
"""Print merged frame-verb lexicon stats (guideline + technique + curated corpus CSV)."""

from __future__ import annotations

import argparse
import json

from trifecta_annotation.frame_verbs import get_frame_verb_lexicon, lexicon_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Show active frame-verb lexicon summary.")
    parser.add_argument(
        "--no-corpus",
        action="store_true",
        help="Exclude trifecta_frame_verb_corpus.csv (keep=yes rows)",
    )
    parser.add_argument("--reload", action="store_true", help="Rebuild lexicon (re-read CSV)")
    args = parser.parse_args()

    lexicon = get_frame_verb_lexicon(
        include_corpus=not args.no_corpus,
        reload=args.reload,
    )
    print(json.dumps(lexicon.summary(), indent=2))
    print(f"entries: {len(lexicon.entries)}")


if __name__ == "__main__":
    main()
