"""Step C span-extraction export tests."""

from trifecta_annotation.schemas import TrifectaFrame
from trifecta_annotation.stepc_span_export import (
    FRAME_FIELD_QUERIES,
    build_stepc_span_examples,
    find_span,
)


def test_find_span_exact_match() -> None:
    context = "Deze siroop van honing is goed voor de droge hoest bij koorts."
    span = find_span(context, "droge hoest")
    assert span is not None
    start, end = span
    assert context[start:end] == "droge hoest"


def test_find_span_case_insensitive() -> None:
    context = "Men gebruikt Kamille voor de maagpijn."
    span = find_span(context, "kamille")
    assert span is not None
    start, end = span
    assert context[start:end] == "Kamille"


def test_find_span_missing_returns_none() -> None:
    context = "Men gebruikt kamille voor de maagpijn."
    assert find_span(context, "koorts") is None


def test_find_span_empty_value_returns_none() -> None:
    assert find_span("any context", "") is None
    assert find_span("any context", "   ") is None


def test_all_frame_fields_have_queries() -> None:
    assert set(FRAME_FIELD_QUERIES) == {
        TrifectaFrame.CURE.value,
        TrifectaFrame.COOKING_CREATION.value,
        TrifectaFrame.PRESERVING.value,
        TrifectaFrame.INGESTION.value,
    }
    for queries in FRAME_FIELD_QUERIES.values():
        assert all(query.strip() for query in queries.values())


def test_build_examples_grounded_field_gets_span() -> None:
    record = {
        "provenance": {
            "record_id": "rec1",
            "corpus": "voc_recipes",
            "target_word": "honing",
            "context_text": "Deze siroop van honing is goed voor de droge hoest bij koorts.",
        },
        "step_a": None,
        "step_b": {
            "selected_frame": "CURE",
            "lexical_unit": "goed voor",
            "reasoning": "test",
        },
        "step_c": {
            "frame": "CURE",
            "CURE_Affliction": "droge hoest",
            "CURE_Food_Treatment": "siroop",
            "lexical_unit": "goed voor",
        },
    }
    examples, skipped = build_stepc_span_examples([record])
    assert skipped == []
    by_field = {ex["field_name"]: ex for ex in examples}
    assert by_field["CURE_Affliction"]["answer_text"] == "droge hoest"
    assert by_field["CURE_Affliction"]["answer_start_char"] is not None
    assert by_field["CURE_Food_Treatment"]["answer_text"] == "siroop"


def test_build_examples_ungrounded_field_is_skipped() -> None:
    record = {
        "provenance": {
            "record_id": "rec2",
            "corpus": "voc_recipes",
            "target_word": "boom-olie",
            "context_text": "Boom-olie wordt gebruikt om schimmel in wijn te voorkomen.",
        },
        "step_a": None,
        "step_b": {
            "selected_frame": "CURE",
            "lexical_unit": "gebruikt",
            "reasoning": "test",
        },
        "step_c": {
            "frame": "CURE",
            "CURE_Affliction": "Kaan (yeast)",
            "CURE_Food_Treatment": "Boom-olie is used to prevent the growth of yeast in wine.",
            "lexical_unit": "gebruikt",
        },
    }
    examples, skipped = build_stepc_span_examples([record])
    assert examples == []
    assert {row["field_name"] for row in skipped} == {"CURE_Affliction", "CURE_Food_Treatment"}


def test_build_examples_empty_field_is_true_negative() -> None:
    record = {
        "provenance": {
            "record_id": "rec3",
            "corpus": "voc_recipes",
            "target_word": "wijn",
            "context_text": "Gasten dronken wijn aan tafel.",
        },
        "step_a": None,
        "step_b": {
            "selected_frame": "INGESTION",
            "lexical_unit": "dronken",
            "reasoning": "test",
        },
        "step_c": {
            "frame": "INGESTION",
            "INGESTION_Context": "aan tafel",
            "INGESTION_Ingestor": "Gasten",
            "INGESTION_Manner": "",
            "INGESTION_Food_Patient": "wijn",
            "INGESTION_Purpose": "",
            "lexical_unit": "dronken",
        },
    }
    examples, skipped = build_stepc_span_examples([record])
    assert skipped == []
    by_field = {ex["field_name"]: ex for ex in examples}
    assert by_field["INGESTION_Manner"]["answer_start_char"] is None
    assert by_field["INGESTION_Purpose"]["answer_start_char"] is None
    assert by_field["INGESTION_Food_Patient"]["answer_text"] == "wijn"
