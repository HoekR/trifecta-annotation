#!/usr/bin/env python3
"""Export Step B few-shot JSON from spot-check and target-reference review CSVs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from data_io import resolve

from trifecta_annotation.fewshot_export import (
    DEFAULT_STEP_B_FEWSHOT_RECORDS,
    build_step_b_fewshots,
    fewshots_document,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spotcheck-path",
        type=Path,
        default=None,
        help="Spot-check CSV (default: scratch/eval/spotcheck_literary_ingestion_2026-07-07.csv)",
    )
    parser.add_argument(
        "--gallery-path",
        type=Path,
        default=None,
        help="Target-reference gallery CSV (optional homonym_note rows)",
    )
    parser.add_argument(
        "--record-id",
        action="append",
        default=[],
        help="Spot-check record_id to include (repeatable; default: curated set)",
    )
    parser.add_argument(
        "--no-gallery",
        action="store_true",
        help="Skip gallery homonym_note rows",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Write JSON (default: trifecta_annotation/prompts/step_b_fewshots.json)",
    )
    parser.add_argument("--stdout", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    scratch = Path(resolve("trifecta_gold")).parent
    spotcheck = args.spotcheck_path or (
        scratch / "eval" / "spotcheck_literary_ingestion_2026-07-07.csv"
    )
    gallery = args.gallery_path or (scratch / "eval" / "target_reference_gallery.csv")
    record_ids = args.record_id or list(DEFAULT_STEP_B_FEWSHOT_RECORDS)

    examples = build_step_b_fewshots(
        spotcheck_path=spotcheck,
        gallery_path=gallery,
        record_ids=record_ids,
        include_gallery_notes=not args.no_gallery,
    )
    if not examples:
        raise SystemExit(f"No few-shot examples built from {spotcheck}")

    doc = fewshots_document(
        examples,
        notes=(
            "Cherry-picked from literary/ingestion spot-check (2026-07-07). "
            "Regenerate via scripts/export_step_b_fewshots.py."
        ),
    )

    payload = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if args.stdout:
        sys.stdout.write(payload)
        return

    repo_root = Path(__file__).resolve().parents[1]
    out = args.output_path or (
        repo_root / "trifecta_annotation" / "prompts" / "step_b_fewshots.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8")
    print(f"Wrote {len(examples)} examples to {out}")


if __name__ == "__main__":
    main()
