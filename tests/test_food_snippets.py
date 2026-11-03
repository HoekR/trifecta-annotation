"""Food snippets adapter tests."""

import pandas as pd
import pytest

from data_io import resolve
from trifecta_annotation.adapters.food_snippets import (
    adapt_food_snippet_long_row,
    dedupe_food_snippets_long_frame,
    explode_food_snippets_wide_frame,
    filter_kwic_batch_frame,
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
            "kwic_batch": "reizen",
        },
    )
    result = adapt_food_snippet_long_row(row)
    assert result.input_record is not None
    assert result.input_record.target_word == "bier"
    assert result.input_record.kwic_batch == "reizen"
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


def test_explode_and_dedupe_food_snippets_wide_frame() -> None:
    wide = pd.DataFrame(
        [
            {
                "doc_id": "work.xml__ch1",
                "filename": "work.xml",
                "title": "Test work",
                "snippet": "men doet zout in het bier",
                "original_found_terms": "['zout', 'bier']",
                "term_count": 2,
                "matched_terms": "['zout', 'bier', 'zout']",
                "manual_labels": "['recept']",
            },
            {
                "doc_id": "work.xml__ch1",
                "filename": "work.xml",
                "title": "Test work",
                "snippet": "men doet zout in het bier",
                "original_found_terms": "['zout', 'bier']",
                "term_count": 2,
                "matched_terms": "['bier']",
                "manual_labels": "['reizen']",
            },
        ],
    )
    long_raw = explode_food_snippets_wide_frame(wide)
    assert list(long_raw["matched_term"]) == ["zout", "bier", "bier"]
    assert long_raw.iloc[0]["kwic_batch"] == "recept"
    assert long_raw.iloc[2]["kwic_batch"] == "reizen"

    deduped, dropped = dedupe_food_snippets_long_frame(long_raw)
    assert len(deduped) == 2
    assert set(deduped["matched_term"]) == {"zout", "bier"}
    bier = deduped.loc[deduped["matched_term"] == "bier"].iloc[0]
    assert bier["kwic_batch"] == "recept|reizen"
    assert len(dropped) == 1
    assert dropped.iloc[0]["duplicate_rows"] == 2


def test_adapt_food_snippet_long_row_clips_long_context() -> None:
    long_snippet = ("woord " * 200) + "men doet zout in het bier " + ("woord " * 200)
    row = pd.Series(
        {
            "doc_id": "work.xml__ch1",
            "filename": "work.xml",
            "title": "Test work",
            "snippet": long_snippet,
            "matched_term": "bier",
        },
    )
    result = adapt_food_snippet_long_row(row, context_radius=80)
    assert result.input_record is not None
    assert len(result.input_record.context_text) < len(long_snippet)
    assert "bier" in result.input_record.context_text.lower()
    assert "zout" in result.input_record.context_text.lower()


def test_filter_kwic_batch_frame() -> None:
    frame = pd.DataFrame(
        {
            "matched_term": ["zout", "bier", "thee"],
            "kwic_batch": ["recept", "reizen", "recept|reizen"],
        },
    )
    filtered = filter_kwic_batch_frame(frame, "reizen")
    assert list(filtered["matched_term"]) == ["bier", "thee"]


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
