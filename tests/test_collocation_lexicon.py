"""Collocation lexicon bridge tests."""

import pandas as pd

from trifecta_annotation.collocation_lexicon import (
    collocation_candidates_to_dataframe,
    mine_collocation_verb_candidates,
)
from trifecta_annotation.frame_verbs import FrameVerbLexicon
from trifecta_annotation.schemas import TrifectaFrame


def _seed_lexicon() -> FrameVerbLexicon:
    return FrameVerbLexicon(
        include_technique_seeds=False,
        include_technique_expanded=False,
        include_corpus=False,
    )


def test_collocation_miner_promotes_unknown_verb_near_anchor() -> None:
    snippets = pd.DataFrame(
        [
            {
                "doc_id": "d1",
                "snippet": "Men moet het vleesch wel koken en daarna laten schuimen in de pot.",
                "matched_term": "vleesch",
            },
            {
                "doc_id": "d2",
                "snippet": "Het vleesch moet men koken en schuimen tot het gaar is.",
                "matched_term": "vleesch",
            },
            {
                "doc_id": "d3",
                "snippet": "Kook het vleesch en schuim het goed door.",
                "matched_term": "vleesch",
            },
        ],
    )
    lookup = {"vleesch": "vlees"}
    candidates = mine_collocation_verb_candidates(
        snippets,
        food_lookup=lookup,
        lexicon=_seed_lexicon(),
        collocation_window=6,
        anchor_window=120,
        min_snippet_freq=2,
    )
    by_term = {item.term_norm: item for item in candidates}
    assert "schuimen" in by_term
    assert by_term["schuimen"].frame == TrifectaFrame.COOKING_CREATION
    assert by_term["schuimen"].snippet_freq >= 2


def test_collocation_auto_keep_thresholds() -> None:
    from trifecta_annotation.frame_verb_corpus import CorpusCandidate

    frame = collocation_candidates_to_dataframe(
        [
            CorpusCandidate(
                "schuimen",
                "schuimen",
                TrifectaFrame.COOKING_CREATION,
                6,
                0.9,
                "targets:vleesch=6",
            ),
            CorpusCandidate(
                "wandelen",
                "wandelen",
                TrifectaFrame.INGESTION,
                2,
                0.5,
                "targets:bier=2",
            ),
        ],
        min_freq=5,
        min_agreement=0.75,
    )
    keep = frame.set_index("term_norm")["keep"].astype(str).str.lower()
    assert keep["schuimen"] == "yes"
    assert keep["wandelen"] == "" or keep["wandelen"] == "nan"
