#!/usr/bin/env python3
"""Promote inter-annotator-agreed INCEpTION targets to gold-candidate rows.

Companion to export_inception_iaa.py: that script surfaces disagreements for
human adjudication; this one takes the targets where 2+ annotators independently
landed on the same frame (and, per Step C field, the same qualia value) and
writes them straight to the gold-labelling CSV schema. Qualia fields that
disagree or are only filled by one annotator are left blank rather than
guessed — those stay in the adjudication queue, not here.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from data_io import resolve

from trifecta_annotation.gold_io import annotation_to_silver_row, export_silver_csv
from trifecta_annotation.schemas import TrifectaAnnotation

AGREE = "agree"
DISAGREE = "disagree"
ONE_BLANK = "one_blank"
BOTH_BLANK = "both_blank"


def _scratch_root() -> Path:
    return Path(resolve("trifecta_gold")).parent


def _parse_record_id(record_id: str) -> tuple[str, str, str]:
    parts = record_id.split("__")
    return parts[1], parts[2], parts[3]


def _field_status(values: list[str]) -> str:
    filled = [v for v in values if v]
    if not filled:
        return BOTH_BLANK
    if len(filled) < len(values):
        return ONE_BLANK
    if len(set(filled)) == 1:
        return AGREE
    return DISAGREE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations-path", type=Path, default=None)
    parser.add_argument("--prefix", default="inception_en", help="Matches --output-prefix used on import")
    parser.add_argument("--output-path", type=Path, default=None)
    args = parser.parse_args()

    scratch = _scratch_root()
    annotations_path = args.annotations_path or scratch / f"{args.prefix}_annotations.jsonl"
    output_path = args.output_path or scratch / f"{args.prefix}_iaa_agreed_gold.csv"

    by_key: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    with annotations_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            rid = str((record.get("provenance") or {}).get("record_id") or "")
            if not rid:
                continue
            doc, annotator, sid = _parse_record_id(rid)
            by_key[(doc, sid, rid.split("__")[4])].append({**record, "_annotator": annotator})

    rows = []
    n_targets = 0
    for (_doc, _sid, _begin), records in by_key.items():
        if len(records) < 2:
            continue
        non_dropped = [r for r in records if not r.get("dropped")]
        frames = {(r.get("step_b") or {}).get("selected_frame") for r in non_dropped}
        frames.discard(None)
        if len(frames) != 1:
            continue  # no frame agreement -> leave for adjudication

        base = non_dropped[0]
        step_c_values = [r.get("step_c") or {} for r in non_dropped]
        all_fields = {k for sc in step_c_values for k in sc if k not in {"lexical_unit", "frame"}}

        merged_step_c = dict(base["step_c"] or {})
        for field in all_fields:
            values = [sc.get(field, "") for sc in step_c_values]
            if _field_status(values) == AGREE:
                merged_step_c[field] = values[0]
            else:
                merged_step_c[field] = ""

        annotators = sorted({r["_annotator"] for r in non_dropped})
        merged = {
            **base,
            "step_c": merged_step_c if base.get("step_c") else None,
            "annotator": "+".join(annotators),
            "annotation_type": "fine_inception_iaa_agreed",
            "model": f"inception_iaa_agreed:{'+'.join(annotators)}",
        }
        merged.pop("_annotator", None)
        for r in non_dropped:
            r.pop("_annotator", None)

        ann = TrifectaAnnotation.model_validate(merged)
        rows.append(
            annotation_to_silver_row(
                ann,
                notes=f"inception_iaa_agreed; {len(annotators)}_annotators; qualia_subset_agreed",
            ),
        )
        n_targets += 1

    gold_csv = export_silver_csv(rows, output_path=output_path)
    print(f"Agreed targets: {n_targets} -> {gold_csv}")


if __name__ == "__main__":
    main()
