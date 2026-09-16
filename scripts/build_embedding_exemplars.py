#!/usr/bin/env python3
"""Build per-frame embedding query exemplars from hand gold (E2)."""

from __future__ import annotations

import argparse
from pathlib import Path

from data_io import save_semi_structured

from trifecta_annotation.embedding_candidates import (
    FRAME_QUERY_LABELS,
    build_frame_exemplars,
    exemplar_summary,
)
from trifecta_annotation.gold_io import load_gold_records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build frame exemplars for embedding candidate retrieval."
    )
    parser.add_argument(
        "--gold-path",
        type=Path,
        default=None,
        help="Override gold parquet/jsonl/csv (default: manifest trifecta_gold)",
    )
    parser.add_argument("--per-frame-cap", type=int, default=30)
    parser.add_argument(
        "--output-logical",
        default="embedding_exemplars",
        help="Manifest logical name (default: embedding_exemplars)",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Write JSONL here instead of manifest logical path",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print per-frame counts",
    )
    args = parser.parse_args()

    records = load_gold_records(gold_path=args.gold_path)
    exemplars = build_frame_exemplars(
        records,
        per_frame_cap=args.per_frame_cap,
        frames=FRAME_QUERY_LABELS,
    )
    rows: list[dict] = []
    for frame in FRAME_QUERY_LABELS:
        rows.extend(exemplars.get(frame, []))

    if args.output_path is not None:
        path = save_semi_structured(
            rows,
            out_path=args.output_path,
            script=__file__,
            description="Per-frame gold exemplars for embedding queries",
            parent_sources=["trifecta_gold"],
        )
    else:
        path = save_semi_structured(
            rows,
            logical_name=args.output_logical,
            script=__file__,
        )

    if args.summary:
        counts = exemplar_summary(exemplars)
        total = sum(counts.values())
        print(f"exemplars: {total} (cap={args.per_frame_cap})")
        for frame in FRAME_QUERY_LABELS:
            print(f"  {frame}: {counts.get(frame, 0)}")
        print(f"wrote -> {path}")
    else:
        print(path)


if __name__ == "__main__":
    main()
