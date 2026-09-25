"""Verb-seeded KWIC adapter tests."""

import pandas as pd

from trifecta_annotation.verb_kwic import verb_kwic_from_snippet_row


def test_verb_kwic_food_target_near_verb() -> None:
    row = pd.Series(
        {
            "doc_id": "doc1",
            "snippet": "Men moet het vleesch wel bewaren met goed zout.",
            "original_found_terms": "['vleesch', 'zout', 'goed']",
            "filename": "recipe.xml",
            "title": "Test recipe",
        },
    )
    lookup = {"vleesch": "vlees", "zout": "zout"}
    record = verb_kwic_from_snippet_row(row, lookup=lookup)
    assert record is not None
    assert record.discovery_verb.lower() == "bewaren"
    assert record.frame_hint == "PRESERVING"
    assert record.target_word.lower() in {"vleesch", "zout"}
    assert record.kwic_mode == "verb_food"
