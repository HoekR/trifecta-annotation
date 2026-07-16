#!/usr/bin/env python3
"""Export PRESERVING gold-labelling candidates from recepten-preservare-analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.clear_frame_examples import target_centered_snippet
from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS, kwic_input_to_candidate_row
from trifecta_annotation.preservare_export import (
    DEFAULT_PRESERVARE_ROOT,
    DEFAULT_RECIPE_DATASET,
    DEFAULT_TECHNIQUE_ASSOC,
    mine_preservare_candidates,
    parse_technique_quotas,
    preservare_summary,
    sample_preservare_candidates,
)
from trifecta_annotation.review_columns import HOMONYM_REVIEW_COLUMNS, empty_homonym_review_row
from trifecta_annotation.schemas import TrifectaFrame


def _existing_gold_ids() -> set[str]:
    path = Path(resolve("trifecta_gold")).parent / "gold_labelling_all.csv"
    if not path.exists():
        return set()
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return {str(rid).strip() for rid in frame["record_id"].dropna() if str(rid).strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preservare-root", type=Path, default=DEFAULT_PRESERVARE_ROOT)
    parser.add_argument("--recipe-path", type=Path, default=None)
    parser.add_argument("--technique-assoc-path", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--technique-quota",
        default="",
        help="salting:2,smoking:2,drying:2,pickling:2,sugaring:1,fermentation:1",
    )
    parser.add_argument("--min-technique-score", type=float, default=0.0)
    parser.add_argument("--max-per-target", type=int, default=2)
    parser.add_argument("--max-per-work", type=int, default=3)
    parser.add_argument("--include-gold", action="store_true")
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pool-summary", action="store_true")
    args = parser.parse_args()

    root = args.preservare_root.expanduser()
    recipe_path = args.recipe_path or (root / "source_data" / "recipe_dataset_2.csv")
    technique_path = args.technique_assoc_path or (root / "data" / "technique_term_association.csv")
    exclude = set() if args.include_gold else _existing_gold_ids()

    pool = mine_preservare_candidates(
        recipe_path=recipe_path,
        technique_assoc_path=technique_path,
        exclude_record_ids=exclude,
        min_technique_score=args.min_technique_score,
    )
    if args.pool_summary:
        print(json.dumps(preservare_summary(pool), indent=2), file=sys.stderr)

    selected = sample_preservare_candidates(
        pool,
        limit=args.limit,
        seed=args.seed,
        technique_quotas=parse_technique_quotas(args.technique_quota),
        max_per_target=args.max_per_target,
        max_per_work=args.max_per_work,
    )
    if args.summary:
        print(json.dumps(preservare_summary(selected), indent=2), file=sys.stderr)

    rows: list[dict[str, object]] = []
    for item in selected:
        row = kwic_input_to_candidate_row(item.record)
        row["selected_frame"] = TrifectaFrame.PRESERVING.value
        row["lexical_unit"] = item.discovery_verb
        row["step_b_reasoning"] = (
            f"preservare_mine; technique={item.technique}; "
            f"score={item.technique_score:.3f}; verb={item.discovery_verb}"
        )
        row["notes"] = (
            f"preservare:{item.technique}; recipe_id={item.pres_features_recipe_id}. "
            f"{row.get('notes', '')}"
        ).strip()
        row.update(empty_homonym_review_row())
        row["review_snippet"] = target_centered_snippet(
            item.record.context_text,
            item.record.target_word,
        )
        rows.append(row)

    scratch = Path(resolve("trifecta_gold")).parent
    out = args.output_path or scratch / "eval" / "preservare_gold_candidates.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    extra_cols = ["review_snippet", *HOMONYM_REVIEW_COLUMNS]
    columns = [c for c in GOLD_CSV_COLUMNS if c in rows[0]] + [
        c for c in extra_cols if c not in GOLD_CSV_COLUMNS
    ]
    pd.DataFrame(rows, columns=columns).to_csv(out, index=False)
    print(f"Wrote {len(rows)} rows to {out}", file=sys.stderr)
    if pool:
        print(f"Pool: {len(pool)} preservare candidates (excluded {len(exclude)} gold ids)", file=sys.stderr)


if __name__ == "__main__":
    main()
