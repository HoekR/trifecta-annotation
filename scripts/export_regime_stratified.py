#!/usr/bin/env python3
"""Export regime-stratified gold candidate batch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from data_io import resolve

from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS, export_gold_csv, kwic_input_to_candidate_row
from trifecta_annotation.regime_sampling import (
    parse_regime_quotas,
    sample_inception_silver,
    sample_kwic_by_regime,
)
from trifecta_annotation.text_regime import TextRegime


def _existing_gold_ids() -> set[str]:
    path = Path(resolve("trifecta_gold")).parent / "gold_labelling_all.csv"
    if not path.exists():
        return set()
    import pandas as pd

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return {str(rid).strip() for rid in frame["record_id"].dropna() if str(rid).strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--regime-quota",
        default="RECIPE_PRACTICE:25,MEDICAL:25",
        help="Comma-separated REGIME:count pairs",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-per-target", type=int, default=2)
    parser.add_argument("--no-inception", action="store_true")
    parser.add_argument(
        "--inception-quota",
        default="",
        help=(
            "Optional: append INCEpTION silver by regime quota "
            "(e.g. RECIPE_PRACTICE:25,MEDICAL:25). "
            "Leave empty to keep INCEpTION as a separate view."
        ),
    )
    parser.add_argument("--no-thesaurus-filter", action="store_true")
    parser.add_argument("--thesaurus-path", default=None)
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Output CSV (default: gold_labelling_regime_batch.csv on scratch)",
    )
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    quotas = parse_regime_quotas(args.regime_quota)
    records, filled = sample_kwic_by_regime(
        quotas,
        seed=args.seed,
        exclude_record_ids=_existing_gold_ids(),
        max_per_target=args.max_per_target,
        include_inception=not args.no_inception,
        thesaurus_filter=not args.no_thesaurus_filter,
        thesaurus_path=args.thesaurus_path,
    )

    rows = [kwic_input_to_candidate_row(record) for record in records]
    inception_filled: dict[str, int] = {}
    inception_rows: list[dict[str, object]] = []
    if args.inception_quota.strip():
        inception_quotas = parse_regime_quotas(args.inception_quota)
        inception_rows, inception_filled = sample_inception_silver(
            inception_quotas,
            seed=args.seed + 1,
            exclude_record_ids=_existing_gold_ids(),
            max_per_target=args.max_per_target,
        )
        seen = {str(row.get("record_id")) for row in rows}
        for row in inception_rows:
            record_id = str(row.get("record_id") or "")
            if record_id and record_id not in seen:
                rows.append({col: row.get(col, "") for col in GOLD_CSV_COLUMNS})
                seen.add(record_id)

    if args.summary:
        by_regime: dict[str, int] = {}
        by_frame_hint: dict[str, int] = {}
        by_source: dict[str, int] = {"kwic_candidates": 0, "inception_silver": 0}
        for record in records:
            regime = (record.text_regime or TextRegime.UNKNOWN).value
            by_regime[regime] = by_regime.get(regime, 0) + 1
            if record.frame_hint:
                by_frame_hint[record.frame_hint] = by_frame_hint.get(record.frame_hint, 0) + 1
            by_source["kwic_candidates"] += 1
        for row in inception_rows:
            regime = str(row.get("text_regime") or TextRegime.UNKNOWN.value)
            by_regime[regime] = by_regime.get(regime, 0) + 1
            frame = str(row.get("selected_frame") or "")
            if frame:
                by_frame_hint[frame] = by_frame_hint.get(frame, 0) + 1
            by_source["inception_silver"] += 1
        print(
            json.dumps(
                {
                    "requested": {k.value: v for k, v in quotas.items()},
                    "filled_kwic": filled,
                    "inception_requested": (
                        {k.value: v for k, v in parse_regime_quotas(args.inception_quota).items()}
                        if args.inception_quota.strip()
                        else {}
                    ),
                    "filled_inception": inception_filled,
                    "total": len(rows),
                    "by_regime": by_regime,
                    "frame_hints": by_frame_hint,
                    "by_source": by_source,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
    default_out = Path(resolve("trifecta_gold")).parent / "gold_labelling_regime_batch.csv"
    path = export_gold_csv(
        rows,
        output_path=args.output_path or default_out,
    )
    print(path)
    print(
        f"Exported {len(rows)} rows "
        f"({len(records)} KWIC candidates + {len(inception_rows)} INCEpTION silver; "
        f"filled KWIC: {filled}, INCEpTION: {inception_filled})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
