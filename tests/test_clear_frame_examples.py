"""Clear frame example mining tests."""

from trifecta_annotation.clear_frame_examples import (
    mine_clear_frame_candidates,
    score_snippet_for_frame,
    target_centered_snippet,
)
from trifecta_annotation.schemas import TrifectaFrame
from trifecta_annotation.text_regime import TextRegime


def test_score_cooking_recipe_high() -> None:
    snippet = "Neem het vleesch en laat het koken in water tot het gaar is."
    scored = score_snippet_for_frame(
        snippet,
        ["vleesch"],
        TrifectaFrame.COOKING_CREATION,
        regime=TextRegime.RECIPE_PRACTICE,
    )
    assert scored is not None
    assert scored.confidence_tier == "high"
    assert scored.suggested_frame == TrifectaFrame.COOKING_CREATION
    assert scored.discovery_verb.lower() == "koken"


def test_score_ingestion_literary_high() -> None:
    snippet = "Men moet brood eten en melk drinken bij het ontbijt."
    scored = score_snippet_for_frame(
        snippet,
        ["brood", "melk"],
        TrifectaFrame.INGESTION,
        regime=TextRegime.LITERARY,
    )
    assert scored is not None
    assert scored.confidence_tier in {"high", "medium"}
    assert scored.suggested_frame == TrifectaFrame.INGESTION


def test_cure_conflict_downgrades_cooking() -> None:
    snippet = (
        "Het vleesch moet men koken en daarna genezen de zieke maag met deze bouillon."
    )
    scored = score_snippet_for_frame(
        snippet,
        ["vleesch"],
        TrifectaFrame.COOKING_CREATION,
        regime=TextRegime.MEDICAL,
    )
    assert scored is None or scored.confidence_tier != "high"


def test_target_centered_snippet_marks_target() -> None:
    text = "A" * 100 + " het brood " + "B" * 100
    out = target_centered_snippet(text, "brood", radius=30)
    assert "[TGT]brood[/TGT]" in out
    assert out.startswith("…")
    assert out.endswith("…")


def test_target_centered_snippet_no_ellipsis_at_edges() -> None:
    out = target_centered_snippet("het brood is lekker", "brood", radius=50)
    assert out == "[TGT]brood[/TGT] is lekker" or "[TGT]brood[/TGT]" in out
    assert not out.startswith("…")


def test_mine_returns_sorted_candidates() -> None:
    pool = mine_clear_frame_candidates(
        frames=(TrifectaFrame.COOKING_CREATION,),
        min_score=5,
        exclude_record_ids=set(),
    )
    if len(pool) < 2:
        return
    assert pool[0].confidence_score >= pool[1].confidence_score
