"""Vocabulary loader tests (requires food_terms on disk)."""

import pytest

from data_io import resolve
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms


@pytest.mark.skipif(
    not resolve("food_terms").exists(),
    reason="food_terms not available (check data_manifest.toml)",
)
def test_load_food_terms() -> None:
    df = load_food_terms()
    assert "Pref_label" in df.columns
    assert len(df) > 100


@pytest.mark.skipif(
    not resolve("food_terms").exists(),
    reason="food_terms not available",
)
def test_alt_label_index() -> None:
    df = load_food_terms()
    index = alt_label_index(df)
    assert "azijn" in index or "suiker" in index
