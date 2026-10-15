"""Glossary candidate tests (no LLM)."""

import pandas as pd

from trifecta_annotation.glossary import (
    build_glossary_candidates,
    glossary_en_lookup,
    read_glossary_csv,
)


def test_build_glossary_candidates_ranks_by_freq() -> None:
    thesaurus = pd.DataFrame(
        {
            "pref_label": ["brood", "brood", "ajuin"],
            "alias_norm": ["brood", "broots", "ajuin"],
            "keep_for_trifecta": ["yes", "yes", "yes"],
            "semantic_type": ["grain", "grain", "vegetable"],
            "snippet_freq": [100, 10, 50],
        },
    )
    snippets = pd.DataFrame({"matched_term": ["brood"] * 5 + ["ajuin"] * 2})
    out = build_glossary_candidates(thesaurus, snippets=snippets, limit=10)
    assert list(out["pref_label"]) == ["brood", "ajuin"]
    assert int(out.iloc[0]["snippet_freq"]) == 100
    assert "brood" in str(out.iloc[0]["example_aliases"])


def test_glossary_en_lookup_maps_aliases() -> None:
    frame = pd.DataFrame(
        {
            "pref_label": ["zout"],
            "pref_label_en": ["salt"],
            "example_aliases": ["zout, wit"],
        },
    )
    lookup = glossary_en_lookup(frame)
    assert lookup["zout"] == "salt"
    assert lookup["wit"] == "salt"


def test_read_glossary_csv_literal_backslash_t(tmp_path) -> None:
    path = tmp_path / "glossary.csv"
    path.write_text("pref_label\\tpref_label_en\nwater\\twater\n", encoding="utf-8")
    frame = read_glossary_csv(path)
    assert list(frame["pref_label"]) == ["water"]
    assert frame.iloc[0]["pref_label_en"] == "water"
