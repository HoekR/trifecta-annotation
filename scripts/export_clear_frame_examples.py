#!/usr/bin/env python3
"""Export unambiguous COOKING_CREATION / INGESTION examples from food snippets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.clear_frame_examples import (
    clear_frame_summary,
    mine_clear_frame_candidates,
    sample_clear_frame_candidates,
    target_centered_snippet,
)
from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS, kwic_input_to_candidate_row
from trifecta_annotation.review_columns import (
    HOMONYM_REVIEW_COLUMNS,
    HOMONYM_REVIEW_HELP,
    empty_homonym_review_row,
)
from trifecta_annotation.schemas import TrifectaFrame


def _existing_gold_ids() -> set[str]:
    path = Path(resolve("trifecta_gold")).parent / "gold_labelling_all.csv"
    if not path.exists():
        return set()
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return {str(rid).strip() for rid in frame["record_id"].dropna() if str(rid).strip()}


def _parse_frames(raw: str) -> tuple[TrifectaFrame, ...]:
    names = [part.strip() for part in raw.split(",") if part.strip()]
    return tuple(TrifectaFrame(name) for name in names)


def _parse_quotas(raw: str) -> dict[TrifectaFrame, int]:
    if not raw.strip():
        return {}
    out: dict[TrifectaFrame, int] = {}
    for part in raw.split(","):
        name, _, count = part.partition(":")
        out[TrifectaFrame(name.strip())] = int(count.strip())
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frames",
        default="COOKING_CREATION,INGESTION",
        help="Comma-separated macro-frames to mine",
    )
    parser.add_argument("--limit", type=int, default=40, help="Rows to export after sampling")
    parser.add_argument("--pool-limit", type=int, default=0, help="Cap mined pool before sampling (0=all)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--min-score", type=int, default=5)
    parser.add_argument("--high-only", action="store_true", help="Only confidence_tier=high")
    parser.add_argument(
        "--allow-corpus-verbs",
        action="store_true",
        help="Include corpus-grown verbs (default: guideline verbs only)",
    )
    parser.add_argument("--max-per-target", type=int, default=2)
    parser.add_argument("--max-per-work", type=int, default=3)
    parser.add_argument(
        "--frame-quota",
        default="",
        help="Optional COOKING_CREATION:25,INGESTION:25 style quotas",
    )
    parser.add_argument("--include-gold", action="store_true", help="Do not exclude existing gold ids")
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Review CSV (default: scratch/eval/clear_frame_examples.csv)",
    )
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pool-summary", action="store_true", help="Summarize full mined pool")
    parser.add_argument(
        "--homonym-filter",
        action="store_true",
        help="Drop rows auto-flagged as high-risk homographs (default: export all, mark in CSV)",
    )
    args = parser.parse_args()

    frames = _parse_frames(args.frames)
    exclude = set() if args.include_gold else _existing_gold_ids()

    pool = mine_clear_frame_candidates(
        frames=frames,
        exclude_record_ids=exclude,
        min_score=args.min_score,
        high_only=args.high_only,
        guideline_only=not args.allow_corpus_verbs,
        require_homonym_clear=args.homonym_filter,
    )
    if args.pool_summary:
        print(json.dumps(clear_frame_summary(pool), indent=2), file=sys.stderr)

    if args.pool_limit > 0:
        pool = pool[: args.pool_limit]

    selected = sample_clear_frame_candidates(
        pool,
        limit=args.limit,
        seed=args.seed,
        max_per_target=args.max_per_target,
        max_per_work=args.max_per_work,
        frame_quotas=_parse_quotas(args.frame_quota),
    )

    if args.summary:
        print(json.dumps(clear_frame_summary(selected), indent=2), file=sys.stderr)

    rows: list[dict[str, object]] = []
    for item in selected:
        row = kwic_input_to_candidate_row(item.record)
        row["selected_frame"] = item.suggested_frame.value
        row["lexical_unit"] = item.discovery_verb
        row["step_b_reasoning"] = (
            f"clear_frame_mine; score={item.confidence_score}; "
            f"tier={item.confidence_tier}; reasons={','.join(item.reasons)}"
        )
        row["homonym_hint"] = item.homonym.risk if item.homonym else ""
        row.update(empty_homonym_review_row())
        row["review_snippet"] = target_centered_snippet(
            item.record.context_text,
            item.record.target_word,
        )
        rows.append(row)

    out_path = args.output_path
    if out_path is None:
        scratch = Path(resolve("trifecta_gold")).parent
        out_path = scratch / "eval" / "clear_frame_examples.csv"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    extra_cols = ["review_snippet", "homonym_hint", *HOMONYM_REVIEW_COLUMNS]
    columns = [c for c in GOLD_CSV_COLUMNS if c in rows[0]] + [
        c for c in extra_cols if c not in GOLD_CSV_COLUMNS
    ]
    pd.DataFrame(rows, columns=columns).to_csv(out_path, index=False)
    print(f"Wrote {len(rows)} rows to {out_path}", file=sys.stderr)
    print(f"Homonym review: {HOMONYM_REVIEW_HELP}", file=sys.stderr)
    if pool:
        print(
            f"Pool: {len(pool)} candidates (excluded {len(exclude)} gold ids)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
