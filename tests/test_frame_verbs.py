"""Frame-verb lexicon tests."""

from pathlib import Path

import pandas as pd

from trifecta_annotation.frame_verbs import (
    FrameVerbLexicon,
    build_merged_lexicon,
    find_frame_verbs_in_text,
    frame_for_verb,
    get_frame_verb_lexicon,
    lexicon_summary,
    load_technique_lexicon,
    pick_food_near_verb,
    term_positions,
)
from trifecta_annotation.schemas import TrifectaFrame


def test_find_preserving_verb() -> None:
    hits = find_frame_verbs_in_text("men moet het vleesch wel bewaren in pekel")
    assert any(h.verb.lower() == "bewaren" for h in hits)
    assert hits[0].frame == TrifectaFrame.PRESERVING
    assert "manual" in hits[0].lexicon_sources


def test_pick_food_near_verb_prefers_closest() -> None:
    snippet = "neem zout en bewaren het vleesch"
    positions = term_positions(snippet, ["zout", "vleesch"])
    food = pick_food_near_verb(
        next(h.start for h in find_frame_verbs_in_text(snippet)),
        positions,
    )
    assert food.lower() == "vleesch"


def test_frame_for_verb_lookup() -> None:
    assert frame_for_verb("koken") == TrifectaFrame.COOKING_CREATION
    assert frame_for_verb("drinken") == TrifectaFrame.INGESTION


def test_crossbreed_merges_technique_verbs(tmp_path: Path) -> None:
    csv_path = tmp_path / "technique_term_association.csv"
    pd.DataFrame(
        [
            {"technique": "fermentation", "term": "gisten", "is_seed": True, "recipe_freq": 4},
            {"technique": "salting", "term": "zouten", "is_seed": True, "recipe_freq": 12},
            {"technique": "salting", "term": "zout", "is_seed": True, "recipe_freq": 1143},
            {"technique": "drying", "term": "droogen", "is_seed": True, "recipe_freq": 88},
        ],
    ).to_csv(csv_path, index=False)

    technique_only = load_technique_lexicon(csv_path, verbs_only=True)
    assert "gisten" in technique_only
    assert "droogen" in technique_only
    assert "zout" not in technique_only

    merged = build_merged_lexicon(technique_assoc_path=csv_path, technique_verbs_only=True)
    assert merged["bewaren"].frame == TrifectaFrame.PRESERVING
    assert merged["gisten"].frame == TrifectaFrame.PRESERVING
    assert merged["gisten"].technique == "fermentation"
    assert "guideline" in merged["zouten"].sources
    assert "technique:salting" in merged["zouten"].sources

    lexicon = FrameVerbLexicon(technique_assoc_path=csv_path, technique_verbs_only=True)
    hits = lexicon.find_in_text("men moet het bier laten gisten in de ton")
    assert any(h.verb.lower() == "gisten" for h in hits)
    assert hits[0].technique == "fermentation"


def test_manual_wins_on_frame_conflict(tmp_path: Path) -> None:
    csv_path = tmp_path / "technique_term_association.csv"
    pd.DataFrame(
        [{"technique": "drying", "term": "stoven", "is_seed": True, "recipe_freq": 1}],
    ).to_csv(csv_path, index=False)

    merged = build_merged_lexicon(technique_assoc_path=csv_path, technique_verbs_only=False)
    assert merged["stoven"].frame == TrifectaFrame.COOKING_CREATION
    assert "guideline" in merged["stoven"].sources


def test_lexicon_summary_includes_both_sources() -> None:
    summary = lexicon_summary()
    assert summary["total"] > 0
    assert summary["manual"] > 0


def test_get_frame_verb_lexicon_can_disable_technique() -> None:
    manual_only = get_frame_verb_lexicon(include_technique_seeds=False)
    assert "gisten" not in manual_only.entries
