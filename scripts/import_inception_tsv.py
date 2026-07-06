#!/usr/bin/env python3
"""Import INCEpTION WebAnno TSV exports into TRIFECTA pipeline artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from data_io import resolve, save_jsonl

from trifecta_annotation.adapters.inception_tsv import (
    load_inception_annotations,
    load_inception_kwic_inputs,
)
from trifecta_annotation.gold_io import annotation_to_labelling_row, export_gold_csv


def _scratch_root() -> Path:
    return Path(resolve("trifecta_gold")).parent


def _default_export_root() -> Path:
    scratch = _scratch_root()
    dated = scratch / "inception_nl" / "export_20260703"
    if dated.is_dir():
        return dated
    return scratch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export-root",
        type=Path,
        default=None,
        help="Unzipped INCEpTION export (annotation/ + source/)",
    )
    parser.add_argument(
        "--layer",
        choices=("annotation", "curation"),
        default="annotation",
        help="annotation = per-user TSV; curation = CURATION_USER.tsv",
    )
    parser.add_argument(
        "--annotator",
        action="append",
        default=[],
        help="Limit to annotator username(s); repeat flag for multiple",
    )
    parser.add_argument(
        "--output",
        choices=("kwic", "annotations", "gold_csv", "all"),
        default="all",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    export_root = args.export_root or _default_export_root()
    if not export_root.is_dir():
        raise SystemExit(f"Export root not found: {export_root}")

    annotators = set(args.annotator) if args.annotator else None
    layer = "curation" if args.layer == "curation" else "annotation"
    if args.layer == "curation":
        annotators = {"CURATION_USER"}

    scratch = _scratch_root()

    if args.output in {"kwic", "all"}:
        kwic_records, kwic_skipped = load_inception_kwic_inputs(
            export_root,
            layer=layer,
            annotators=annotators,
        )
        if args.limit is not None:
            kwic_records = kwic_records[: args.limit]
        kwic_path = save_jsonl(
            [record.model_dump(mode="json") for record in kwic_records],
            logical_name=None,
            out_path=scratch / "inception_kwic_inputs.jsonl",
            parent_sources=[str(export_root)],
            description="KwicInput records from INCEpTION WebAnno TSV",
            script=__file__,
        )
        print(f"KwicInput: {len(kwic_records)} records -> {kwic_path}")
        print(f"Skipped: {len(kwic_skipped)}", file=sys.stderr)

    if args.output in {"annotations", "gold_csv", "all"}:
        annotations, ann_skipped = load_inception_annotations(
            export_root,
            layer=layer,
            annotators=annotators,
        )
        if args.limit is not None:
            annotations = annotations[: args.limit]

        if args.output in {"annotations", "all"}:
            ann_path = save_jsonl(
                [ann.model_dump(mode="json") for ann in annotations],
                logical_name=None,
                out_path=scratch / "inception_annotations.jsonl",
                parent_sources=[str(export_root)],
                description="Silver TRIFECTA annotations from INCEpTION WebAnno TSV",
                script=__file__,
            )
            print(f"Annotations: {len(annotations)} records -> {ann_path}")

        if args.output in {"gold_csv", "all"}:
            rows = []
            for ann in annotations:
                row = annotation_to_labelling_row(
                    ann,
                    notes="inception_import; snippet_view; silver/unreconciled",
                    labelled=True,
                )
                rows.append(row)
            gold_csv = export_gold_csv(
                rows,
                output_path=scratch / "inception_silver_labelling.csv",
            )
            print(f"Gold CSV (silver, unreviewed): {len(rows)} rows -> {gold_csv}")

        print(f"Skipped: {len(ann_skipped)}", file=sys.stderr)


if __name__ == "__main__":
    main()
