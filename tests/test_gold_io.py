"""Gold CSV roundtrip tests."""

import json
from pathlib import Path

import pandas as pd

from trifecta_annotation.gold_io import annotation_to_row, load_gold_records, row_to_annotation
from trifecta_annotation.schemas import (
    AnnotationProvenance,
    EntityValidation,
    FormalDimension,
    FrameClassification,
    GoldAnnotation,
    PreservingQualia,
    TrifectaFrame,
)


def test_gold_csv_roundtrip() -> None:
    ann = GoldAnnotation(
        provenance=AnnotationProvenance(
            record_id="g1",
            corpus="voc_recipes",
            target_word="zout",
            context_text="een hand vol zout",
            date="1750",
        ),
        step_a=EntityValidation(
            is_food_entity=True,
            is_metaphor=False,
            formal_dimension=FormalDimension.FOOD_WHOLE,
            canonical_pref_label="zout",
            ontology_match=True,
            reasoning="Literal salt.",
        ),
        step_b=FrameClassification(
            selected_frame=TrifectaFrame.PRESERVING,
            lexical_unit="zout",
            reasoning="Salting context.",
        ),
        step_c=PreservingQualia(
            PR_Technique="salting",
            PR_Medium="zout",
            PR_Food_Patient="vis",
            lexical_unit="zout",
        ),
        dropped=False,
    )
    row = annotation_to_row(ann)
    row["labelled"] = True
    parsed = row_to_annotation(row)
    assert parsed is not None
    assert parsed.provenance.record_id == "g1"
    assert parsed.step_b is not None
    assert parsed.step_b.selected_frame == TrifectaFrame.PRESERVING
    assert parsed.step_c is not None
    assert parsed.step_c.PR_Technique == "salting"


def test_gold_csv_legacy_frame_and_step_c() -> None:
    row = {
        "record_id": "g3",
        "corpus": "en_pilot",
        "target_word": "milk",
        "context_text": "Milk is commonly preserved",
        "date": "1791",
        "source_path": "",
        "dropped": "false",
        "drop_reason": "",
        "is_food_entity": "true",
        "is_metaphor": "false",
        "formal_dimension": "",
        "canonical_pref_label": "",
        "ontology_match": "false",
        "step_a_reasoning": "Literal milk.",
        "selected_frame": "PRESERVING",
        "lexical_unit": "preserved",
        "step_b_reasoning": "",
        "preservation_technique": "condensing",
        "preserving_agent": "",
        "target_food": "milk",
        "labelled": "true",
        "notes": "",
    }
    parsed = row_to_annotation(row)
    assert parsed is not None
    assert parsed.step_b is not None
    assert parsed.step_b.selected_frame == TrifectaFrame.PRESERVING
    assert parsed.step_c is not None
    assert parsed.step_c.PR_Technique == "condensing"
    assert parsed.step_c.PR_Food_Patient == "milk"


def test_gold_csv_dropout_row() -> None:
    row = {
        "record_id": "g2",
        "corpus": "voc_recipes",
        "target_word": "brood",
        "context_text": "het brood des levens",
        "date": "",
        "source_path": "",
        "dropped": "true",
        "drop_reason": "metaphor",
        "is_food_entity": "false",
        "is_metaphor": "true",
        "formal_dimension": "",
        "canonical_pref_label": "",
        "ontology_match": "false",
        "step_a_reasoning": "Religious idiom.",
        "selected_frame": "",
        "lexical_unit": "",
        "step_b_reasoning": "",
        "labelled": "true",
        "notes": "",
    }
    parsed = row_to_annotation(row)
    assert parsed is not None
    assert parsed.dropped is True
    assert parsed.drop_reason == "metaphor"
    assert parsed.step_b is None


def test_gold_csv_dropout_partial_step_a() -> None:
    row = {
        "record_id": "g4",
        "corpus": "nieuwen",
        "target_word": "rogge",
        "context_text": "rogge op het veld",
        "date": "",
        "source_path": "",
        "dropped": "true",
        "drop_reason": "irrelevant",
        "is_food_entity": "",
        "is_metaphor": "false",
        "formal_dimension": "",
        "canonical_pref_label": "",
        "ontology_match": "",
        "step_a_reasoning": "",
        "selected_frame": "",
        "lexical_unit": "",
        "step_b_reasoning": "",
        "labelled": "true",
        "notes": "",
    }
    parsed = row_to_annotation(row)
    assert parsed is not None
    assert parsed.dropped is True
    assert parsed.drop_reason == "irrelevant"
    assert parsed.step_a is None


def test_gold_csv_active_partial_step_a_defaults_false() -> None:
    row = {
        "record_id": "g5",
        "corpus": "hove",
        "target_word": "eieren",
        "context_text": "eieren in de pan",
        "date": "",
        "source_path": "",
        "dropped": "false",
        "drop_reason": "",
        "is_food_entity": "",
        "is_metaphor": "false",
        "formal_dimension": "FOOD_Whole",
        "canonical_pref_label": "ei",
        "ontology_match": "true",
        "step_a_reasoning": "eieren braken",
        "selected_frame": "NONE",
        "lexical_unit": "",
        "step_b_reasoning": "",
        "labelled": "true",
        "notes": "",
    }
    parsed = row_to_annotation(row)
    assert parsed is not None
    assert parsed.step_a is not None
    assert parsed.step_a.is_food_entity is True
    assert parsed.step_a.is_metaphor is False
    assert parsed.step_b is not None
    assert parsed.step_b.selected_frame.value == "NONE"


def test_load_gold_records_from_parquet_path(tmp_path: Path) -> None:
    from data_io.parquet_io import save_parquet

    ann = GoldAnnotation(
        provenance=AnnotationProvenance(
            record_id="g6",
            corpus="voc_recipes",
            target_word="zout",
            context_text="een hand vol zout",
        ),
        dropped=False,
    )
    frame = pd.DataFrame(
        [{"annotation_json": json.dumps(ann.model_dump(mode="json"))}],
    )
    parquet_path = tmp_path / "gold.parquet"
    save_parquet(frame, out_path=parquet_path, description="test gold")

    records = load_gold_records(gold_path=parquet_path)
    assert len(records) == 1
    assert records[0]["provenance"]["record_id"] == "g6"


def test_merge_labelling_rows_appends_new_record_ids() -> None:
    from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS, merge_labelling_rows

    existing = pd.DataFrame(
        [{"record_id": "a", "corpus": "c", "target_word": "x", "context_text": "t", "labelled": "true"}],
        columns=GOLD_CSV_COLUMNS,
    )
    merged = merge_labelling_rows(
        existing,
        [{"record_id": "b", "corpus": "c", "target_word": "y", "context_text": "u", "labelled": "false"}],
    )
    assert len(merged) == 2
    assert set(merged["record_id"]) == {"a", "b"}
