"""Corpus-grown frame verb lexicon tests."""

from pathlib import Path

import pandas as pd

from trifecta_annotation.frame_verb_corpus import (
    auto_keep_mask,
    load_corpus_lexicon,
    mine_frame_verb_candidates,
)
from trifecta_annotation.frame_verbs import FrameVerbLexicon, build_merged_lexicon
from trifecta_annotation.schemas import TrifectaFrame


def test_mine_candidates_near_anchor() -> None:
    """Prose miner finds verbs not already in the seed lexicon."""
    snippets = pd.DataFrame(
        [
            {
                "doc_id": "d1",
                "snippet": "Men moet het vleesch wel koken en daarna laten schuimen in de pot.",
                "original_found_terms": "['vleesch']",
            },
            {
                "doc_id": "d2",
                "snippet": "Het vleesch moet men schuimen na het koken in water.",
                "original_found_terms": "['vleesch', 'water']",
            },
            {
                "doc_id": "d3",
                "snippet": "Men moet het vleesch wel schuimen tot het gaar is.",
                "original_found_terms": "['vleesch']",
            },
        ],
    )
    lookup = {"vleesch": "vlees", "water": "water"}

    candidates = mine_frame_verb_candidates(snippets, food_lookup=lookup, max_window=80)
    by_term = {item.term_norm: item for item in candidates}

    assert "schuimen" in by_term
    assert by_term["schuimen"].frame == TrifectaFrame.COOKING_CREATION


def test_load_corpus_lexicon_respects_keep(tmp_path: Path) -> None:
    csv_path = tmp_path / "corpus.csv"
    pd.DataFrame(
        [
            {
                "term_norm": "koken",
                "historic_forms": "sieden,syeden",
                "term_example": "sieden",
                "frame_hint": "COOKING_CREATION",
                "snippet_freq": 10,
                "anchor_agreement": 0.8,
                "anchor_frames": "",
                "keep": "yes",
                "notes": "",
            },
            {
                "term_norm": "wandelen",
                "historic_forms": "",
                "term_example": "wandelen",
                "frame_hint": "INGESTION",
                "snippet_freq": 1,
                "anchor_agreement": 0.5,
                "anchor_frames": "",
                "keep": "",
                "notes": "noise",
            },
        ],
    ).to_csv(csv_path, index=False)

    loaded = load_corpus_lexicon(csv_path, approved_only=True)
    assert "sieden" in loaded
    assert "syeden" in loaded
    assert loaded["sieden"].canonical_lemma == "koken"
    assert "wandelen" not in loaded


def test_corpus_respects_user_canonical_lemma(tmp_path: Path) -> None:
    csv_path = tmp_path / "corpus.csv"
    pd.DataFrame(
        [
            {
                "term_norm": "koken",
                "historic_forms": "sieden",
                "term_example": "sieden",
                "frame_hint": "COOKING_CREATION",
                "snippet_freq": 31,
                "anchor_agreement": 1.0,
                "anchor_frames": "",
                "keep": "yes",
                "notes": "",
            },
        ],
    ).to_csv(csv_path, index=False)

    loaded = load_corpus_lexicon(csv_path, approved_only=True)
    assert loaded["sieden"].canonical_lemma == "koken"
    assert loaded["koken"].frame == TrifectaFrame.COOKING_CREATION


def test_merged_lexicon_includes_corpus(tmp_path: Path) -> None:
    csv_path = tmp_path / "corpus.csv"
    pd.DataFrame(
        [
            {
                "term_norm": "koken",
                "historic_forms": "sieden",
                "term_example": "sieden",
                "frame_hint": "COOKING_CREATION",
                "snippet_freq": 8,
                "anchor_agreement": 0.75,
                "anchor_frames": "",
                "keep": "yes",
                "notes": "",
            },
        ],
    ).to_csv(csv_path, index=False)

    merged = build_merged_lexicon(
        include_technique_seeds=False,
        include_technique_expanded=False,
        include_corpus=True,
        corpus_lexicon_path=csv_path,
    )
    assert merged["sieden"].frame == TrifectaFrame.COOKING_CREATION
    assert any(source.startswith("corpus:") for source in merged["sieden"].sources)

    lexicon = FrameVerbLexicon(
        include_technique_seeds=False,
        include_technique_expanded=False,
        include_corpus=True,
        corpus_lexicon_path=csv_path,
    )
    hits = lexicon.find_in_text("men moet het vleesch sieden in de pot")
    assert any(hit.verb.lower() == "sieden" for hit in hits)
