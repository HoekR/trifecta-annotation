#!/usr/bin/env python3
"""Export cort_voc source-text catalogue (titles, regimes, snippet/gold counts)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from data_io import resolve

from trifecta_annotation.corpus_overview import build_corpus_overview, overview_summary


def _default_output() -> Path:
    try:
        return Path(resolve("eval_reports")) / "corpus_texts_overview.csv"
    except Exception:
        return Path(resolve("trifecta_gold")).parent / "eval" / "corpus_texts_overview.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snippets-path", type=Path, default=None)
    parser.add_argument("--gold-csv", type=Path, default=None)
    parser.add_argument("--gold-parquet", type=Path, default=None)
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    frame = build_corpus_overview(
        snippets_path=args.snippets_path,
        gold_csv_path=args.gold_csv,
        gold_parquet_path=args.gold_parquet,
    )
    out = args.output_path or _default_output()
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    print(out)

    if args.summary:
        print(json.dumps(overview_summary(frame), indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
