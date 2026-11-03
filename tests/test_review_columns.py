"""Review CSV column helpers."""

from trifecta_annotation.review_columns import (
    HOMONYM_CHECK_VALUES,
    HOMONYM_REVIEW_COLUMNS,
    empty_homonym_review_row,
)


def test_homonym_review_defaults() -> None:
    row = empty_homonym_review_row()
    assert row["homonym_check"] == ""
    assert row["homonym_note"] == ""
    assert set(row) == set(HOMONYM_REVIEW_COLUMNS)


def test_homonym_check_values() -> None:
    assert "food_sense" in HOMONYM_CHECK_VALUES
    assert "other_sense" in HOMONYM_CHECK_VALUES
    assert "metaphor" in HOMONYM_CHECK_VALUES
