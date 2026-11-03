#!/usr/bin/env python3
"""Export Step A dropout rows to CSV for accept/reject review."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from data_io import load_jsonl, resolve

from trifecta_annotation.dropout_review import DROPOUT_REVIEW_COLUMNS, build_dropout_review_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--step-a-path",
        type=Path,
        default=None,
        help="Step A JSONL (default: scratch/reizen_step_a.jsonl if present)",
    )
    parser.add_argument("--output-path", type=Path, default=None)
    args = parser.parse_args()

    scratch = Path(resolve("trifecta_gold")).parent
    step_a_path = args.step_a_path or scratch / "reizen_step_a.jsonl"
    if not step_a_path.exists():
        raise SystemExit(f"Step A JSONL not found: {step_a_path}")

    out = args.output_path or Path(resolve("eval_reports")) / "step_a_dropout_review.csv"
    records = load_jsonl(step_a_path)
    rows = build_dropout_review_rows(records)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(DROPOUT_REVIEW_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} dropout review rows → {out}")
    print("Fill verdict: accept | reject (optional homonym_check / review_notes)")


if __name__ == "__main__":
    main()
