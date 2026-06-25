#!/usr/bin/env python3
"""Bootstrap unlabelled gold_labelling.csv rows using the TRIFECTA LLM pipeline."""

from __future__ import annotations

import argparse

import pandas as pd
from data_io import resolve

from trifecta_annotation.gold_io import (
    GOLD_CSV_COLUMNS,
    bootstrap_gold_rows_from_annotations,
    export_gold_csv,
    import_gold_csv,
    merge_labelling_rows,
)
from trifecta_annotation.pipeline import annotate_record
from trifecta_annotation.schemas import KwicInput


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill unlabelled gold CSV rows via LLM (bootstrap for import/eval).",
    )
    parser.add_argument("--input-logical", default="trifecta_gold_csv")
    parser.add_argument("--kwic-logical", default="kwic_inputs")
    parser.add_argument("--import-after", action="store_true", help="Import parquet/jsonl after write")
    parser.add_argument("--overwrite-labelled", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--notes", default="llm_bootstrap")
    args = parser.parse_args()

    csv_path = resolve(args.input_logical)
    frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    kwic_records = {
        str(row["record_id"]): row
        for row in __import__("data_io").load_jsonl(resolve(args.kwic_logical))
    }

    pending_ids = []
    for row in frame.to_dict(orient="records"):
        labelled = str(row.get("labelled", "")).strip().lower()
        if labelled in {"true", "1", "yes"} and not args.overwrite_labelled:
            continue
        pending_ids.append(str(row["record_id"]))
    if args.limit is not None:
        pending_ids = pending_ids[: args.limit]

    annotations = []
    for record_id in pending_ids:
        raw = kwic_records.get(record_id)
        if raw is None:
            print(f"skip {record_id}: not in kwic_inputs")
            continue
        inp = KwicInput.model_validate(raw)
        ann = annotate_record(inp)
        annotations.append(ann)
        print(f"annotated {record_id} dropped={ann.dropped}")

    if not annotations:
        print("No rows to bootstrap.")
        return

    updates = bootstrap_gold_rows_from_annotations(annotations, notes=args.notes)
    merged = merge_labelling_rows(
        frame,
        updates,
        overwrite_labelled=args.overwrite_labelled,
    )
    export_gold_csv(merged.to_dict(orient="records"), output_path=csv_path)
    print(f"Wrote {len(updates)} bootstrap rows to {csv_path}")

    if args.import_after:
        gold, parquet_path, jsonl_path = import_gold_csv(
            input_path=csv_path,
            script=__file__,
        )
        print(f"Imported {len(gold)} gold records → {parquet_path}, {jsonl_path}")


if __name__ == "__main__":
    main()
