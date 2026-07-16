"""Tests for preservare PRESERVING candidate export."""

from __future__ import annotations

from trifecta_annotation.preservare_export import (
    mine_preservare_candidates,
    sample_preservare_candidates,
)


def test_mine_preservare_candidates_from_default_paths() -> None:
    pool = mine_preservare_candidates(exclude_record_ids=set(), min_technique_score=0.0)
    if not pool:
        return
    item = pool[0]
    assert item.record.corpus == "preservare"
    assert item.record.frame_hint == "PRESERVING"
    assert item.technique in {"salting", "smoking", "drying", "pickling", "sugaring", "fermentation"}
    assert item.record.target_word


def test_sample_preservare_respects_limit() -> None:
    pool = mine_preservare_candidates(exclude_record_ids=set())
    if len(pool) < 3:
        return
    picked = sample_preservare_candidates(pool, limit=3, seed=1)
    assert len(picked) <= 3
