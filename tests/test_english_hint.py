"""Tests for English reviewer hint helpers."""

from __future__ import annotations

from trifecta_annotation.english_hint import (
    append_english_hint_block,
    review_hint_lookup_from_glossary,
    review_hint_for_term,
)


def test_append_english_hint_block() -> None:
    base = "Target Word: boter\nContext: ..."
    out = append_english_hint_block(base, "butter — dairy fat")
    assert "English reviewer hint" in out
    assert "butter — dairy fat" in out
    assert append_english_hint_block(base, "") == base
    assert append_english_hint_block(base, None) == base


def test_review_hint_lookup_from_glossary(tmp_path) -> None:
    csv_path = tmp_path / "glossary.csv"
    csv_path.write_text(
        "pref_label,pref_label_en,gloss_en,semantic_type,snippet_freq,example_aliases,reviewed,review_notes\n"
        'boter,butter,dairy spread,food,1,"Boter, boter",true,\n',
        encoding="utf-8",
    )
    lookup = review_hint_lookup_from_glossary(csv_path)
    assert review_hint_for_term("boter", lookup) == "butter — dairy spread"
    assert review_hint_for_term("Boter", lookup) == "butter — dairy spread"
