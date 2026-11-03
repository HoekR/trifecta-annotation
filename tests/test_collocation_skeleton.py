"""Collocation skeleton mining tests."""

import pandas as pd

from trifecta_annotation.collocation_skeleton import (
    collocates_near_target,
    mine_collocations,
    top_collocations_per_target,
)
from trifecta_annotation.frame_verbs import FrameVerbLexicon
from trifecta_annotation.schemas import TrifectaFrame


def _mini_lexicon() -> FrameVerbLexicon:
    return FrameVerbLexicon(
        include_technique_seeds=False,
        include_technique_expanded=False,
        include_corpus=False,
    )


def _vleesch_snippets(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "doc_id": f"d{i}",
                "filename": "recepten.txt",
                "title": "Kookboek",
                "snippet": f"Men moet het vleesch wel koken in water, regel {i}.",
                "matched_term": "vleesch",
            }
            for i in range(n)
        ],
    )


def test_collocates_near_target_finds_verbs() -> None:
    snippet = "Men moet het vleesch koken en schuimen in de pot."
    food_terms = frozenset({"vleesch", "water"})
    seed_terms = frozenset({"koken"})
    found = collocates_near_target(
        snippet,
        target_norm="vleesch",
        window_tokens=5,
        food_terms=food_terms,
        seed_terms=seed_terms,
    )
    norms = {norm for norm, _ in found}
    assert "koken" in norms
    assert "schuimen" in norms


def test_mine_collocations_pmi_and_frame_hint() -> None:
    hits = mine_collocations(
        _vleesch_snippets(3),
        food_lookup={"vleesch": "vlees", "water": "water"},
        lexicon=_mini_lexicon(),
        window_tokens=5,
        min_cooc=2,
        min_pmi=0.0,
    )
    by_pair = {(hit.target_norm, hit.collocate_norm): hit for hit in hits}
    assert ("vleesch", "koken") in by_pair
    assert by_pair[("vleesch", "koken")].frame_hint == TrifectaFrame.COOKING_CREATION.value
    assert by_pair[("vleesch", "koken")].in_frame_lexicon is True


def test_top_collocations_per_target_caps_rows() -> None:
    hits = mine_collocations(
        _vleesch_snippets(4),
        food_lookup={"vleesch": "vlees", "water": "water"},
        lexicon=_mini_lexicon(),
        min_cooc=1,
    )
    capped = top_collocations_per_target(hits, max_per_target=1)
    assert len(capped) == 1


def test_fasttext_sim_defaults_empty() -> None:
    hits = mine_collocations(
        _vleesch_snippets(1),
        food_lookup={"vleesch": "vlees"},
        lexicon=_mini_lexicon(),
        min_cooc=1,
    )
    assert hits[0].fasttext_sim is None
