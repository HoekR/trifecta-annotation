"""KWIC adapter tests."""

import pytest

from data_io import resolve
from trifecta_annotation.adapters import _find_food_terms, load_kwic_inputs_from_review


@pytest.mark.skipif(
    not resolve("food_terms").exists(),
    reason="food_terms not available",
)
def test_find_food_terms_longest_match() -> None:
    index = {"zout": "zout", "suiker": "suiker"}
    matched = _find_food_terms("een hand vol zout en wat suiker", index)
    assert "zout" in matched
    assert "suiker" in matched


@pytest.mark.skipif(
    not resolve("kwic_gold_review").exists(),
    reason="kwic_gold_review not available",
)
def test_load_kwic_inputs_from_review() -> None:
    records, skipped = load_kwic_inputs_from_review()
    assert isinstance(records, list)
    assert isinstance(skipped, list)
    if records:
        assert records[0].corpus == "voc_recipes"
        assert records[0].target_word
