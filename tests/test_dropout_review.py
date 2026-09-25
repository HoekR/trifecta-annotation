"""Tests for Step A dropout review helpers."""

import pandas as pd

from trifecta_annotation.dropout_review import (
    accepted_record_ids,
    build_dropout_review_rows,
    filter_dropout_records,
)


def _dropout(record_id: str, *, metaphor: bool = True) -> dict:
    return {
        "provenance": {
            "record_id": record_id,
            "target_word": "water",
            "context_text": "in het water gracht",
        },
        "step_a": {
            "is_metaphor": metaphor,
            "is_food_entity": False,
            "reasoning": "not food",
        },
        "dropped": True,
        "drop_reason": "metaphor",
    }


def test_build_dropout_review_rows() -> None:
    rows = build_dropout_review_rows([_dropout("a"), {"provenance": {"record_id": "b"}, "dropped": False}])
    assert len(rows) == 1
    assert rows[0]["record_id"] == "a"
    assert "context_snippet" in rows[0]


def test_filter_dropout_records_with_review_csv() -> None:
    records = [_dropout("a"), _dropout("b")]
    review = pd.DataFrame(
        [
            {"record_id": "a", "verdict": "accept"},
            {"record_id": "b", "verdict": "reject"},
        ],
    )
    filtered = filter_dropout_records(records, review=review)
    assert [r["provenance"]["record_id"] for r in filtered] == ["a"]
    assert accepted_record_ids(review) == {"a"}
