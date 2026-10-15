"""Tests for gold candidate target filter (G1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trifecta_annotation.gold_target_filter import (
    REASON_DENYLIST,
    REASON_LEMMA_PRIOR,
    GoldTargetFilter,
    load_prior_blocked,
    normalize_target,
    prior_blocked_lemmas,
)
from trifecta_annotation.thesaurus import DEFAULT_DENYLIST


def test_normalize_target_hist_dutch() -> None:
    assert normalize_target("Mede") == "mede"
    assert normalize_target("ſuiker") == "suiker"


def test_mede_blocked_by_denylist() -> None:
    filt = GoldTargetFilter()
    decision = filt.decide("Mede")
    assert decision.target_norm == "mede"
    assert decision.hard_skip is True
    assert decision.reason == REASON_DENYLIST
    assert filt.should_hard_skip("mede") is True
    assert "mede" in DEFAULT_DENYLIST


@pytest.mark.parametrize("lemma", ["boter", "suiker", "haring", "azijn"])
def test_food_lemma_passes(lemma: str) -> None:
    filt = GoldTargetFilter()
    decision = filt.decide(lemma)
    assert decision.hard_skip is False
    assert decision.reason is None
    assert decision.target_norm == lemma


def test_prior_blocked_overrides_food_lemma() -> None:
    filt = GoldTargetFilter.from_priors(["water", "WATER"])
    decision = filt.decide("Water")
    assert decision.hard_skip is True
    assert decision.reason == REASON_LEMMA_PRIOR
    # Denylist still wins when both would apply
    assert filt.decide("mede").reason == REASON_DENYLIST


def test_prior_blocked_from_mapping_shapes() -> None:
    assert prior_blocked_lemmas({"blocked": ["canal", "Water"]}) == frozenset({"canal", "water"})
    assert prior_blocked_lemmas({"hard_blocked": ["x"]}) == frozenset({"x"})
    assert prior_blocked_lemmas({"water": True, "boter": False}) == frozenset({"water"})
    assert prior_blocked_lemmas({"water": {"hard_skip": True}}) == frozenset({"water"})


def test_load_prior_blocked_json(tmp_path: Path) -> None:
    path = tmp_path / "priors.json"
    path.write_text(json.dumps({"blocked": ["Mede", "water"]}), encoding="utf-8")
    blocked = load_prior_blocked(path)
    assert blocked == frozenset({"mede", "water"})

    filt = GoldTargetFilter.from_priors(priors_path=path)
    assert filt.should_hard_skip("water") is True
    assert filt.should_hard_skip("boter") is False


def test_empty_target_hard_skips() -> None:
    filt = GoldTargetFilter()
    assert filt.should_hard_skip("") is True
    assert filt.should_hard_skip(None) is True


def test_soft_signals_from_priors_payload() -> None:
    filt = GoldTargetFilter.from_priors(
        {
            "blocked": ["bloed"],
            "require_disambiguation": ["water"],
            "soft_deprioritize": ["boter"],
        }
    )
    assert filt.decide("bloed").hard_skip is True
    water = filt.decide("water")
    assert water.hard_skip is False
    assert water.require_disambiguation is True
    boter = filt.decide("boter")
    assert boter.soft_deprioritize is True


def test_no_lemma_priors_keeps_denylist_only() -> None:
    filt = GoldTargetFilter.from_priors(
        {"blocked": ["boter"]},
        apply_lemma_priors=False,
    )
    assert filt.should_hard_skip("boter") is False
    assert filt.should_hard_skip("mede") is True


def test_filter_stats_and_batch_report() -> None:
    from trifecta_annotation.gold_target_filter import FilterStats, format_filter_report

    filt = GoldTargetFilter.from_priors({"blocked": ["water"]})
    stats = FilterStats()
    for target in ("mede", "water", "boter", "boter"):
        stats.record_decision(filt.decide(target))
    report = format_filter_report(
        stats,
        selected=[{"target_word": "boter", "frame_hint": "COOKING_CREATION"}],
        target_attr="target_word",
        frame_attr="frame_hint",
    )
    assert report["filter"]["hard_skip_denylist"] == 1
    assert report["filter"]["hard_skip_lemma_prior"] == 1
    assert report["filter"]["kept"] == 2
    assert report["selected"]["n"] == 1


def test_sample_prefers_non_soft_lemmas() -> None:
    from trifecta_annotation.clear_frame_examples import (
        ClearFrameCandidate,
        sample_clear_frame_candidates,
    )
    from trifecta_annotation.schemas import KwicInput, TrifectaFrame

    filt = GoldTargetFilter.from_priors({"soft_deprioritize": ["boter"]})

    def cand(rid: str, target: str) -> ClearFrameCandidate:
        return ClearFrameCandidate(
            record=KwicInput(
                record_id=rid,
                corpus="t",
                target_word=target,
                context_text=f"{target} koken",
                title=f"work-{rid}",
            ),
            suggested_frame=TrifectaFrame.COOKING_CREATION,
            discovery_verb="koken",
            verb_distance=1,
            confidence_score=10,
            confidence_tier="high",
        )

    pool = [cand("a", "boter"), cand("b", "suiker"), cand("c", "boter")]
    selected = sample_clear_frame_candidates(
        pool,
        limit=1,
        seed=0,
        max_per_target=2,
        max_per_work=5,
        target_filter=filt,
    )
    assert len(selected) == 1
    assert selected[0].record.target_word == "suiker"


def test_importable_alongside_exporters() -> None:
    """G1 done bar: helper usable from clear-frame and preservare modules."""
    from trifecta_annotation import clear_frame_examples, preservare_export
    from trifecta_annotation.gold_target_filter import GoldTargetFilter as Filt

    assert hasattr(clear_frame_examples, "mine_clear_frame_candidates")
    assert hasattr(preservare_export, "mine_preservare_candidates")
    assert Filt().should_hard_skip("mede") is True


def test_regime_sample_hard_skips_blocked(tmp_path: Path) -> None:
    from trifecta_annotation.regime_sampling import sample_kwic_by_regime
    from trifecta_annotation.schemas import KwicInput
    from trifecta_annotation.text_regime import TextRegime

    pool = [
        KwicInput(
            record_id="m1",
            corpus="c",
            target_word="mede",
            context_text="mede",
            text_regime=TextRegime.RECIPE_PRACTICE,
        ),
        KwicInput(
            record_id="b1",
            corpus="c",
            target_word="boter",
            context_text="boter",
            text_regime=TextRegime.RECIPE_PRACTICE,
        ),
    ]

    import trifecta_annotation.regime_sampling as mod

    original = mod._load_candidate_pool
    mod._load_candidate_pool = lambda **_k: pool  # type: ignore[assignment]
    try:
        records, filled = sample_kwic_by_regime(
            {TextRegime.RECIPE_PRACTICE: 5},
            max_per_target=2,
            seed=0,
            target_filter=GoldTargetFilter(),
        )
    finally:
        mod._load_candidate_pool = original

    assert filled["RECIPE_PRACTICE"] == 1
    assert [r.target_word for r in records] == ["boter"]
