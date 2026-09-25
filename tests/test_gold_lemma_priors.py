"""Tests for gold lemma priors builder (G2)."""

from __future__ import annotations

import json
from pathlib import Path

from trifecta_annotation.gold_lemma_priors import (
    PriorThresholds,
    build_priors_payload,
    should_hard_block,
)
from trifecta_annotation.gold_target_filter import (
    REASON_LEMMA_PRIOR,
    GoldTargetFilter,
    prior_blocked_lemmas,
)


def _row(
    target: str,
    *,
    labelled: str = "true",
    dropped: str = "false",
    food: str = "true",
    metaphor: str = "false",
    homonym: str = "",
    frame: str = "COOKING_CREATION",
    regime: str = "RECIPE",
) -> dict[str, str]:
    return {
        "record_id": f"{target}-{dropped}-{food}",
        "target_word": target,
        "labelled": labelled,
        "dropped": dropped,
        "is_food_entity": food,
        "is_metaphor": metaphor,
        "homonym_check": homonym,
        "selected_frame": frame,
        "text_regime": regime,
    }


def test_build_priors_blocks_high_drop_low_food() -> None:
    rows = [
        *[_row("Mede", dropped="true", food="false", frame="") for _ in range(4)],
        *[_row("boter", dropped="false", food="true") for _ in range(3)],
        _row("skip_me", labelled="false", dropped="true", food="false"),
    ]
    payload = build_priors_payload(rows, source="test", generated_at="2026-09-17T00:00:00Z")
    assert payload["version"] == 1
    assert "mede" in payload["blocked"]
    assert "boter" not in payload["blocked"]
    assert payload["lemmas"]["mede"]["hard_skip"] is True
    assert payload["lemmas"]["mede"]["n"] == 4
    assert payload["lemmas"]["mede"]["food_pass_rate"] == 0.0
    assert payload["meta"]["n_labelled"] == 7
    # Unlabelled row ignored
    assert "skip_me" not in payload["lemmas"]


def test_other_sense_rate_hard_blocks() -> None:
    rows = [
        _row("bloem", dropped="true", food="false", homonym="other_sense"),
        _row("bloem", dropped="true", food="false", homonym="other_sense"),
        _row("bloem", dropped="false", food="true", homonym="food_sense"),
    ]
    thr = PriorThresholds(min_n=3, min_other_sense_rate=0.5, max_food_pass_rate=0.0)
    payload = build_priors_payload(rows, thresholds=thr)
    assert "bloem" in payload["blocked"]
    assert payload["lemmas"]["bloem"]["other_sense_rate"] >= 0.5


def test_mixed_lemma_gets_disambiguation_not_block() -> None:
    rows = [
        _row("water", dropped="true", food="false", metaphor="true"),
        _row("water", dropped="true", food="false"),
        _row("water", dropped="false", food="true"),
        _row("water", dropped="false", food="true"),
    ]
    payload = build_priors_payload(rows, thresholds=PriorThresholds(min_n=3))
    assert "water" not in payload["blocked"]
    assert "water" in payload["require_disambiguation"]
    assert payload["lemmas"]["water"]["require_disambiguation"] is True


def test_soft_deprioritize_saturated_food() -> None:
    rows = [_row("boter") for _ in range(5)]
    payload = build_priors_payload(
        rows,
        thresholds=PriorThresholds(soft_food_pass_cap=5, min_n=3),
    )
    assert "boter" not in payload["blocked"]
    assert "boter" in payload["soft_deprioritize"]


def test_payload_compatible_with_gold_target_filter() -> None:
    rows = [_row("noot", dropped="true", food="false") for _ in range(3)]
    payload = build_priors_payload(rows)
    blocked = prior_blocked_lemmas(payload)
    assert blocked == frozenset({"noot"})
    filt = GoldTargetFilter.from_priors(payload)
    decision = filt.decide("Noot")
    assert decision.hard_skip is True
    assert decision.reason == REASON_LEMMA_PRIOR
    assert filt.should_hard_skip("boter") is False


def test_should_hard_block_respects_min_n() -> None:
    stats = {
        "n": 2,
        "food_pass_rate": 0.0,
        "drop_rate": 1.0,
        "other_sense_rate": 0.0,
    }
    assert should_hard_block(stats, PriorThresholds(min_n=3)) is False


def test_load_written_json_roundtrip(tmp_path: Path) -> None:
    rows = [_row("huid", dropped="true", food="false") for _ in range(3)]
    payload = build_priors_payload(rows)
    path = tmp_path / "gold_lemma_priors.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    filt = GoldTargetFilter.from_priors(priors_path=path)
    assert filt.should_hard_skip("huid") is True
    assert loaded["blocked"] == ["huid"]
