#!/usr/bin/env python3
"""Export Step C gold-vs-pred review CSV (good matches + misses for few-shots)."""

from __future__ import annotations

import argparse
from pathlib import Path

from trifecta_annotation.step_c_review import (
    StepCReviewConfig,
    load_review_frame,
    review_summary,
    save_review_frame,
)


def _parse_csv_list(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-path", type=Path, default=None)
    parser.add_argument("--predictions-path", type=Path, default=None)
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Default: eval_reports/step_c_review.csv",
    )
    parser.add_argument(
        "--frames",
        default="",
        help="Comma-separated gold frames (empty=all). Example: COOKING_CREATION",
    )
    parser.add_argument(
        "--tiers",
        default="",
        help="Comma-separated tiers (empty=all). Example: joint,partial_strong",
    )
    parser.add_argument(
        "--fewshot-only",
        action="store_true",
        help="Only rows flagged fewshot_candidate",
    )
    parser.add_argument(
        "--fewshot-levels",
        default="yes,maybe",
        help="With --fewshot-only: which levels (default: yes,maybe)",
    )
    parser.add_argument("--min-hits", type=int, default=0)
    parser.add_argument(
        "--frame-ok-only",
        action="store_true",
        help="Only rows where pred Step C frame matches gold",
    )
    args = parser.parse_args()

    config = StepCReviewConfig(
        gold_path=args.gold_path,
        predictions_path=args.predictions_path,
        output_path=args.output_path,
        frames=_parse_csv_list(args.frames),
        tiers=_parse_csv_list(args.tiers),
        fewshot_only=args.fewshot_only,
        fewshot_levels=_parse_csv_list(args.fewshot_levels) or ("yes", "maybe"),
        min_hits=args.min_hits,
        frame_ok_only=args.frame_ok_only,
    )
    frame = load_review_frame(config)
    out = save_review_frame(frame, config)
    summary = review_summary(frame)
    print(f"Wrote {summary['rows']} rows → {out}")
    print(f"tiers: {summary['tiers']}")
    print(f"by_frame: {summary['by_frame']}")
    print(f"fewshot_flagged: {summary['fewshot_flagged']}")
    if not frame.empty:
        print("Top few-shot picks:")
        picks = frame[frame["fewshot_candidate"].astype(str).str.len() > 0].head(8)
        for _, row in picks.iterrows():
            print(
                f"  [{row['fewshot_candidate']}] {row['tier']} "
                f"{row['target_word']} · {row['gold_frame']} · {row['hits']}/{row['n_fields']}",
            )


if __name__ == "__main__":
    main()
