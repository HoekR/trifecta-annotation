"""Tests for analysis parquet export."""

from __future__ import annotations

from trifecta_annotation.analysis_export import (
    UNCERTAINTY_NOTE,
    annotation_to_analysis_row,
    annotations_to_analysis_frame,
)


def test_annotation_to_analysis_row_cooking() -> None:
    record = {
        "provenance": {
            "record_id": "r1",
            "corpus": "t",
            "target_word": "vlees",
            "context_text": "braden het vlees",
            "text_regime": "RECIPE_PRACTICE",
            "date": "1700",
        },
        "dropped": False,
        "model": "qwen",
        "step_a": {
            "is_food_entity": True,
            "is_metaphor": False,
            "ontology_match": True,
            "reasoning": "",
        },
        "step_b": {
            "selected_frame": "COOKING_CREATION",
            "lexical_unit": "braden",
            "reasoning": "x",
        },
        "step_c": {
            "frame": "COOKING_CREATION",
            "COOKING_CREATION_Method": "braden",
            "COOKING_CREATION_Process": "",
            "COOKING_CREATION_Food_Product": "vlees",
            "lexical_unit": "braden",
        },
    }
    row = annotation_to_analysis_row(record)
    assert row["record_id"] == "r1"
    assert row["selected_frame"] == "COOKING_CREATION"
    assert row["COOKING_CREATION_Method"] == "braden"
    assert row["COOKING_CREATION_Food_Product"] == "vlees"
    assert row["uncertainty_note"] == UNCERTAINTY_NOTE


def test_annotations_to_analysis_frame_filters() -> None:
    records = [
        {
            "provenance": {
                "record_id": "a",
                "corpus": "t",
                "target_word": "x",
                "context_text": "y",
            },
            "dropped": True,
            "step_c": {
                "frame": "PRESERVING",
                "PR_Technique": "zout",
                "PR_Medium": "",
                "PR_Food_Patient": "",
                "lexical_unit": "zout",
            },
        },
        {
            "provenance": {
                "record_id": "b",
                "corpus": "t",
                "target_word": "x",
                "context_text": "y",
            },
            "dropped": False,
        },
        {
            "provenance": {
                "record_id": "c",
                "corpus": "t",
                "target_word": "x",
                "context_text": "y",
            },
            "dropped": False,
            "step_c": {
                "frame": "COOKING_CREATION",
                "COOKING_CREATION_Method": "koken",
                "COOKING_CREATION_Process": "",
                "COOKING_CREATION_Food_Product": "",
                "lexical_unit": "koken",
            },
        },
    ]
    all_rows = annotations_to_analysis_frame(records)
    assert len(all_rows) == 3
    kept = annotations_to_analysis_frame(
        records,
        require_step_c=True,
        exclude_dropped=True,
    )
    assert list(kept["record_id"]) == ["c"]
