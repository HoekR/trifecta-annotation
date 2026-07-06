#!/usr/bin/env python3
"""Export UNKNOWN text_regime rows for hand review and merge fixes back."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.gold_io import export_gold_csv
from trifecta_annotation.regime_review import (
    REVIEW_COLUMNS,
    apply_regime_review,
    build_review_rows,
)
from trifecta_annotation.regime_sampling import title_lookup_from_snippets


def _scratch_gold_all() -> Path:
    merged = Path(resolve("trifecta_gold")).parent / "gold_labelling_all.csv"
    if merged.exists():
        return merged
    return Path(resolve("trifecta_gold_csv"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-csv", type=Path, default=None)
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Review CSV (default: eval/regime_review_unknown.csv)",
    )
    parser.add_argument(
        "--to-gold-ui",
        action="store_true",
        help="Copy UNKNOWN labelled rows to gold_labelling.csv for UI review",
    )
    parser.add_argument(
        "--apply",
        type=Path,
        default=None,
        help="Merge review_text_regime from review CSV into gold_labelling_all.csv",
    )
    parser.add_argument(
        "--apply-gold-ui",
        action="store_true",
        help="Merge text_regime from gold_labelling.csv into gold_labelling_all.csv",
    )
    parser.add_argument(
        "--import-after",
        action="store_true",
        help="With --apply / --apply-gold-ui, re-import gold.parquet after merge",
    )
    args = parser.parse_args()

    gold_path = args.gold_csv or _scratch_gold_all()
    if not gold_path.exists():
        raise SystemExit(f"Gold CSV not found: {gold_path}")

    eval_dir = Path(resolve("eval_reports"))
    review_path = args.output_path or eval_dir / "regime_review_unknown.csv"

    if args.apply_gold_ui:
        ui_path = Path(resolve("trifecta_gold_csv"))
        if not ui_path.exists():
            raise SystemExit(f"Gold UI CSV not found: {ui_path}")
        ui = pd.read_csv(ui_path, dtype=str, keep_default_na=False)
        gold_all = pd.read_csv(gold_path, dtype=str, keep_default_na=False)
        merged, applied = apply_regime_review(gold_all, ui)
        export_gold_csv(merged.to_dict(orient="records"), output_path=gold_path)
        print(f"Applied {applied} regime updates from UI → {gold_path}")
        if args.import_after and applied:
            from trifecta_annotation.gold_io import import_gold_csv

            import_gold_csv(input_path=gold_path, script=__file__)
            print("Re-imported gold.parquet")
        return

    if args.apply:
        review = pd.read_csv(args.apply, dtype=str, keep_default_na=False)
        gold_all = pd.read_csv(gold_path, dtype=str, keep_default_na=False)
        merged, applied = apply_regime_review(gold_all, review)
        export_gold_csv(merged.to_dict(orient="records"), output_path=gold_path)
        print(f"Applied {applied} regime fixes → {gold_path}")
        if args.import_after and applied:
            from trifecta_annotation.gold_io import import_gold_csv

            import_gold_csv(input_path=gold_path, script=__file__)
            print("Re-imported gold.parquet")
        return

    gold_all = pd.read_csv(gold_path, dtype=str, keep_default_na=False)
    labelled = gold_all[gold_all["labelled"].astype(str).str.lower() == "true"]
    titles = title_lookup_from_snippets()
    review_rows = build_review_rows(labelled, titles=titles)

    review_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(review_rows, columns=REVIEW_COLUMNS).to_csv(review_path, index=False)
    print(f"Wrote {len(review_rows)} UNKNOWN rows → {review_path}", file=sys.stderr)

    suggested_counts = (
        pd.Series([row["suggested_text_regime"] for row in review_rows])
        .value_counts()
        .to_dict()
    )
    print("Suggested (heuristic only — please verify):", suggested_counts, file=sys.stderr)

    if args.to_gold_ui:
        unknown_ids = {row["record_id"] for row in review_rows}
        ui_rows = labelled[labelled["record_id"].isin(unknown_ids)].to_dict(orient="records")
        ui_path = Path(resolve("trifecta_gold_csv"))
        export_gold_csv(ui_rows, output_path=ui_path)
        print(f"Gold UI queue: {len(ui_rows)} rows → {ui_path}")
        print("Run: uv run trifecta-gold-ui  (edit text_regime dropdown per row)")


if __name__ == "__main__":
    main()
