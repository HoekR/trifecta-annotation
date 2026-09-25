"""Guideline + variant lemma tests."""

from trifecta_annotation.frame_verb_corpus import CorpusCandidate, collapse_candidates_by_lemma
from trifecta_annotation.frame_verb_guidelines import (
    GUIDELINE_VERB_LEXICON,
    canonical_frame_verb,
    guideline_verb_entries,
)
from trifecta_annotation.frame_verbs import frame_for_verb, lexicon_summary
from trifecta_annotation.schemas import TrifectaFrame


def test_guideline_includes_koken() -> None:
    entries = guideline_verb_entries()
    assert "koken" in entries
    assert entries["koken"][0] == TrifectaFrame.COOKING_CREATION


def test_historic_variant_maps_to_canonical() -> None:
    assert canonical_frame_verb("sieden") == "koken"
    assert canonical_frame_verb("syeden") == "koken"
    assert canonical_frame_verb("drincken") == "drinken"


def test_runtime_lexicon_matches_sieden() -> None:
    assert frame_for_verb("sieden") == TrifectaFrame.COOKING_CREATION
    assert frame_for_verb("koken") == TrifectaFrame.COOKING_CREATION


def test_manual_brouwen_cooking_trigger() -> None:
    assert frame_for_verb("brouwen") == TrifectaFrame.COOKING_CREATION


def test_collapse_recipe_variants() -> None:
    raw = [
        CorpusCandidate("sieden", "sieden", TrifectaFrame.COOKING_CREATION, 31, 1.0, "gloss:koken"),
        CorpusCandidate("syeden", "syeden", TrifectaFrame.COOKING_CREATION, 3, 1.0, "gloss:koken"),
    ]
    collapsed = collapse_candidates_by_lemma(raw)
    assert len(collapsed) == 1
    assert collapsed[0].term_norm == "koken"
    assert collapsed[0].snippet_freq == 34


def test_guideline_verb_counts() -> None:
    entries = guideline_verb_entries()
    assert len(GUIDELINE_VERB_LEXICON[TrifectaFrame.COOKING_CREATION]) == 31
    assert len(GUIDELINE_VERB_LEXICON[TrifectaFrame.PRESERVING]) == 8
    assert len(GUIDELINE_VERB_LEXICON[TrifectaFrame.CURE]) == 7
    assert "sieden" in entries
