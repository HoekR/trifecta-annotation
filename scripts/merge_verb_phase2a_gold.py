#!/usr/bin/env python3
"""Merge Phase 2a verb-KWIC gold into gold_labelling_all.csv and gold.parquet."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.gold_io import (
    GOLD_CSV_COLUMNS,
    export_gold_csv,
    import_gold_csv,
    merge_labelling_rows,
)
from trifecta_annotation.text_regime import infer_text_regime


def _default_phase2a_csv() -> Path:
    return Path(resolve("verb_phase2a_gold"))


def _default_merged_csv() -> Path:
    parent = Path(resolve("trifecta_gold")).parent
    merged = parent / "gold_labelling_all.csv"
    if merged.exists():
        return merged
    return Path(resolve("trifecta_gold_csv"))


def convert_phase2a_to_gold_rows(df: pd.DataFrame) -> list[dict[str, str]]:
    """Convert Phase 2a review rows to standard gold labelling CSV rows."""
    converted: list[dict[str, str]] = []
    for _, r in df.iterrows():
        # Handle anatomical non-food outlier (e.g. tonsils in veterinary context)
        is_tonsils = r.get("record_id") == "chom003huis01_01.xml__ch20__amandelen"

        inferred = infer_text_regime(
            corpus=r.get("corpus"),
            source_path=r.get("source_path"),
            text_regime=r.get("text_regime"),
        )
        regime = inferred.value if inferred else "UNKNOWN"

        row: dict[str, str] = {
            "record_id": str(r["record_id"]),
            "corpus": str(r.get("corpus") or ""),
            "text_regime": regime,
            "target_word": str(r.get("target_word") or ""),
            "context_text": str(r.get("context_text") or ""),
            "date": str(r.get("date") or ""),
            "source_path": str(r.get("source_path") or ""),
            "dropped": "True" if is_tonsils else "False",
            "drop_reason": "not_food_entity" if is_tonsils else "",
            "is_food_entity": "False" if is_tonsils else "True",
            "is_metaphor": "False",
            "formal_dimension": "",
            "canonical_pref_label": "",
            "ontology_match": "",
            "step_a_reasoning": (
                "Amandelen refers to anatomy (tonsils / keelklieren), not food."
                if is_tonsils
                else "Food entity in context."
            ),
            "selected_frame": "" if is_tonsils else str(r.get("reviewed_frame") or ""),
            "lexical_unit": "" if is_tonsils else str(r.get("reviewed_lexical_unit") or ""),
            "step_b_reasoning": "" if is_tonsils else "Adjudicated Phase 2a verb-KWIC review.",
            "COOKING_CREATION_Method": "" if is_tonsils else str(r.get("COOKING_CREATION_Method") or ""),
            "COOKING_CREATION_Process": "" if is_tonsils else str(r.get("COOKING_CREATION_Process") or ""),
            "COOKING_CREATION_Food_Product": "" if is_tonsils else str(r.get("COOKING_CREATION_Food_Product") or ""),
            "CURE_Affliction": "" if is_tonsils else str(r.get("CURE_Affliction") or ""),
            "CURE_Food_Treatment": "" if is_tonsils else str(r.get("CURE_Food_Treatment") or ""),
            "INGESTION_Context": "" if is_tonsils else str(r.get("INGESTION_Context") or ""),
            "INGESTION_Ingestor": "" if is_tonsils else str(r.get("INGESTION_Ingestor") or ""),
            "INGESTION_Manner": "" if is_tonsils else str(r.get("INGESTION_Manner") or ""),
            "PR_Technique": "" if is_tonsils else str(r.get("PR_Technique") or ""),
            "PR_Medium": "" if is_tonsils else str(r.get("PR_Medium") or ""),
            "PR_Food_Patient": "" if is_tonsils else str(r.get("PR_Food_Patient") or ""),
            "labelled": "True",
            "notes": "Phase 2a verb-KWIC gold" + (f"; {r['uncertainty_note']}" if r.get("uncertainty_note") else ""),
        }
        converted.append(row)
    return converted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge Phase 2a verb-KWIC gold into gold_labelling_all.csv and import to gold.parquet.",
    )
    parser.add_argument("--phase2a-path", type=Path, default=None, help="Phase 2a gold CSV path")
    parser.add_argument("--into-path", type=Path, default=None, help="Target gold_labelling_all.csv path")
    parser.add_argument("--overwrite-labelled", action="store_true")
    parser.add_argument(
        "--no-import",
        action="store_true",
        help="Skip importing into gold.parquet and gold.jsonl",
    )
    args = parser.parse_args()

    phase2a_path = args.phase2a_path or _default_phase2a_csv()
    into_path = args.into_path or _default_merged_csv()

    if not phase2a_path.exists():
        raise SystemExit(f"Phase 2a CSV not found: {phase2a_path}")

    phase2a_df = pd.read_csv(phase2a_path, dtype=str, keep_default_na=False)
    print(f"Loaded {len(phase2a_df)} rows from {phase2a_path}")

    converted_rows = convert_phase2a_to_gold_rows(phase2a_df)

    if into_path.exists():
        existing = pd.read_csv(into_path, dtype=str, keep_default_na=False)
    else:
        existing = pd.DataFrame(columns=GOLD_CSV_COLUMNS)

    before = len(existing)
    merged = merge_labelling_rows(
        existing,
        converted_rows,
        overwrite_labelled=args.overwrite_labelled,
    )
    export_gold_csv(merged.to_dict(orient="records"), output_path=into_path)
    added = len(merged) - before
    print(f"Updated merged CSV: {into_path}")
    print(f"Total rows: {before} → {len(merged)} (+{added} new rows)")

    if not args.no_import:
        annotations, parquet_path, jsonl_path = import_gold_csv(
            input_path=into_path,
            script=__file__,
        )
        print(f"Imported {len(annotations)} labelled rows")
        print(f"Parquet: {parquet_path}")
        print(f"JSONL:   {jsonl_path}")


if __name__ == "__main__":
    main()
