"""Tests for silver JSONL merge helpers."""

from trifecta_annotation.silver_merge import is_step_a_dropout, merge_silver_records


def _row(record_id: str, *, dropped: bool = False, food: bool = True, metaphor: bool = False) -> dict:
    return {
        "provenance": {"record_id": record_id, "corpus": "cort_voc_db", "target_word": "zout", "context_text": "x"},
        "step_a": {"is_food_entity": food, "is_metaphor": metaphor, "formal_dimension": "FOOD_Whole"},
        "dropped": dropped,
        "drop_reason": "not_food_entity" if dropped else None,
    }


def test_merge_silver_dedupes_and_filters_dropouts() -> None:
    base = [_row("a"), _row("b")]
    append = [_row("b"), _row("c", dropped=True), _row("d", food=False, metaphor=False, dropped=True)]
    merged = merge_silver_records(base, append, dropout_only=True, append_limit=10)
    ids = [r["provenance"]["record_id"] for r in merged]
    assert ids == ["a", "b", "c", "d"]
    assert is_step_a_dropout(merged[-1])
