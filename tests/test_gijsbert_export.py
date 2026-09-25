"""GijsBERT export tests."""

from trifecta_annotation.gijsbert_export import (
    DEFAULT_TARGET_CLOSE,
    DEFAULT_TARGET_OPEN,
    DEFAULT_VERB_CLOSE,
    DEFAULT_VERB_OPEN,
    annotation_to_gijsbert_row,
    mark_kwic_context,
)


def test_mark_both_food_and_verb() -> None:
    text = mark_kwic_context(
        "Men moet het vleesch bewaren met zout.",
        target_word="vleesch",
        discovery_verb="bewaren",
        mark_mode="both",
    )
    assert f"{DEFAULT_TARGET_OPEN}vleesch{DEFAULT_TARGET_CLOSE}" in text
    assert f"{DEFAULT_VERB_OPEN}bewaren{DEFAULT_VERB_CLOSE}" in text


def test_annotation_to_gijsbert_row_verb_mode() -> None:
    record = {
        "provenance": {
            "corpus": "cort_voc_db",
            "target_word": "zout",
            "context_text": "Men moet het zout bewaren.",
            "record_id": "r1",
            "discovery_verb": "bewaren",
            "frame_hint": "PRESERVING",
            "kwic_mode": "verb_food",
        },
        "step_a": {
            "is_food_entity": True,
            "is_metaphor": False,
            "ontology_match": True,
            "reasoning": "",
        },
        "step_b": {
            "selected_frame": "PRESERVING",
            "lexical_unit": "bewaren",
            "reasoning": "",
        },
        "dropped": False,
    }
    row = annotation_to_gijsbert_row(record, mark_mode="verb")
    assert row is not None
    assert row["label"] == "PRESERVING"
    assert DEFAULT_VERB_OPEN in row["text"]


def test_out_of_scope_coarse_exports_as_none() -> None:
    record = {
        "provenance": {
            "corpus": "inception_snippets",
            "target_word": "bread",
            "context_text": "plain bread on the table",
            "record_id": "silver-none-1",
        },
        "step_a": {
            "is_food_entity": True,
            "is_metaphor": False,
            "ontology_match": False,
            "reasoning": "Imported from INCEpTION",
        },
        "coarse_frame": "OUT_OF_SCOPE",
        "annotation_type": "fine_inception",
        "dropped": False,
    }
    row = annotation_to_gijsbert_row(record)
    assert row is not None
    assert row["label"] == "NONE"


def test_dropped_exports_as_none() -> None:
    record = {
        "provenance": {
            "corpus": "cort_voc_db",
            "target_word": "brood",
            "context_text": "het brood des levens",
            "record_id": "silver-none-2",
        },
        "step_a": {
            "is_food_entity": False,
            "is_metaphor": True,
            "ontology_match": False,
            "reasoning": "metaphor",
        },
        "dropped": True,
        "drop_reason": "metaphor",
    }
    row = annotation_to_gijsbert_row(record)
    assert row is not None
    assert row["label"] == "NONE"
