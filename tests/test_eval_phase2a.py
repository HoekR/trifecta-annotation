"""Tests for Phase 2a comparative evaluation."""

import json
from pathlib import Path
import pandas as pd

from trifecta_annotation.eval_phase2a import evaluate_phase2a, format_phase2a_report


def test_evaluate_phase2a_basic(tmp_path: Path) -> None:
    gold_csv = tmp_path / "gold.csv"
    preds_jsonl = tmp_path / "preds.jsonl"
    out_json = tmp_path / "eval.json"
    out_csv = tmp_path / "comparison.csv"

    rows = [
        {
            "record_id": "r1",
            "target_word": "mostacciolen",
            "frame_verb": "sieden",
            "frame_verb_frame": "COOKING_CREATION",
            "source_step_b": "COOKING_CREATION",
            "reviewed_frame": "COOKING_CREATION",
            "reviewed_lexical_unit": "siedt",
            "COOKING_CREATION_Method": "sieden",
            "COOKING_CREATION_Process": "koken",
            "COOKING_CREATION_Food_Product": "",
            "reviewed": "true",
            "uncertainty_note": "",
        },
        {
            "record_id": "r2",
            "target_word": "amandelen",
            "frame_verb": "eten",
            "frame_verb_frame": "INGESTION",
            "source_step_b": "INGESTION",
            "reviewed_frame": "CURE",
            "reviewed_lexical_unit": "giet in neusgaten",
            "CURE_Affliction": "hoest",
            "CURE_Food_Treatment": "giet in neusgaten",
            "reviewed": "true",
            "uncertainty_note": "therapeutic use for sheep",
        },
    ]
    pd.DataFrame(rows).to_csv(gold_csv, index=False)

    preds = [
        {
            "provenance": {"record_id": "r1", "target_word": "mostacciolen"},
            "step_b": {"selected_frame": "COOKING_CREATION", "lexical_unit": "siedt"},
            "step_c": {
                "frame": "COOKING_CREATION",
                "COOKING_CREATION_Method": "sieden",
                "COOKING_CREATION_Process": "koken",
                "COOKING_CREATION_Food_Product": "",
            },
        },
        {
            "provenance": {"record_id": "r2", "target_word": "amandelen"},
            "step_b": {"selected_frame": "INGESTION", "lexical_unit": "eten"},
            "step_c": {
                "frame": "INGESTION",
                "INGESTION_Context": "voeren",
                "INGESTION_Ingestor": "schapen",
            },
        },
    ]
    with open(preds_jsonl, "w", encoding="utf-8") as f:
        for p in preds:
            f.write(json.dumps(p) + "\n")

    metrics, comp_df = evaluate_phase2a(
        gold_csv_path=gold_csv,
        predictions_path=preds_jsonl,
        output_json=out_json,
        output_csv=out_csv,
    )

    assert metrics["evaluated_rows"] == 2
    # r1 matches source step B, r2 differs (COOKING vs CURE/INGESTION)
    assert metrics["source_step_b_comparison"]["agreement_count"] == 1
    assert metrics["source_step_b_comparison"]["agreement_rate"] == 0.5
    assert metrics["verb_lexicon_comparison"]["agreement_count"] == 1

    # Step C: r1 is exact match on all 3 fields, r2 pred is INGESTION while gold is CURE
    assert metrics["step_c_comparison"]["joint_exact_hits"] == 1
    assert metrics["step_c_comparison"]["evaluated_rows"] == 2

    assert out_json.exists()
    assert out_csv.exists()
    assert len(comp_df) == 2

    report_text = format_phase2a_report(metrics)
    assert "PHASE 2a EVALUATION" in report_text
    assert "HUMAN REVIEWED_FRAME VS SOURCE_STEP_B" in report_text
