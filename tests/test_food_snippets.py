"""Food snippets adapter tests."""

import pytest

from data_io import resolve
from trifecta_annotation.adapters.food_snippets import (
    load_kwic_inputs_from_food_snippets,
    parse_found_terms,
    pick_target_word,
    terms_in_snippet,
)


def test_parse_found_terms() -> None:
    terms = parse_found_terms("['bier', 'zout', 'brood']")
    assert terms == ["bier", "zout", "brood"]


def test_pick_target_word_leftmost() -> None:
    snippet = "men doet zout in het bier en brood"
    target, candidates = pick_target_word(snippet, ["brood", "bier", "zout"])
    assert target == "zout"
    assert candidates == ["zout", "bier", "brood"]


@pytest.mark.skipif(
    not resolve("food_snippets_source").exists(),
    reason="food_snippets_source not available",
)
def test_load_manual_subset() -> None:
    if not resolve("food_snippets_manual").exists():
        pytest.skip("run scripts/ingest_food_snippets.py first")
    records, skipped = load_kwic_inputs_from_food_snippets(manual_only=True)
    assert len(records) >= 50
    assert records[0].corpus == "cort_voc_db"
    assert records[0].target_word
