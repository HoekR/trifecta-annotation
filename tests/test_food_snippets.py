"""Food snippets adapter tests."""

import pandas as pd
import pytest

from data_io import resolve
from trifecta_annotation.adapters.food_snippets import (
    adapt_food_snippet_long_row,
    load_kwic_inputs_from_food_snippets,
    make_long_record_id,
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


def test_adapt_food_snippet_long_row() -> None:
    row = pd.Series(
        {
            "doc_id": "work.xml__ch1",
            "filename": "work.xml",
            "title": "Test work",
            "snippet": "men doet zout in het bier",
            "matched_term": "bier",
        },
    )
    result = adapt_food_snippet_long_row(row)
    assert result.input_record is not None
    assert result.input_record.target_word == "bier"
    assert result.input_record.record_id == make_long_record_id("work.xml__ch1", "bier")


def test_adapt_food_snippet_long_row_rejects_absent_term() -> None:
    row = pd.Series(
        {
            "doc_id": "work.xml__ch1",
            "filename": "work.xml",
            "title": "Test work",
            "snippet": "geen voedsel hier",
            "matched_term": "zout",
        },
    )
    result = adapt_food_snippet_long_row(row)
    assert result.input_record is None
    assert result.reason == "term_not_in_snippet"


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
