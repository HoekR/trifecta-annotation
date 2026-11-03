"""Tests for gold → embedding exemplar builder (E2)."""

from __future__ import annotations

from trifecta_annotation.embedding_candidates import (
    build_frame_exemplars,
    exemplar_from_gold_record,
    exemplar_summary,
)


def _gold(
    *,
    record_id: str,
    frame: str | None,
    context: str = "Neem boters en suiker.",
    target: str = "boter",
    dropped: bool = False,
) -> dict:
    rec: dict = {
        "dropped": dropped,
        "provenance": {
            "record_id": record_id,
            "corpus": "test",
            "target_word": target,
            "context_text": context,
            "text_regime": "RECIPE_PRACTICE",
        },
    }
    if frame is not None:
        rec["step_b"] = {"selected_frame": frame}
    return rec


def test_exemplar_from_gold_maps_legacy_cure() -> None:
    ex = exemplar_from_gold_record(_gold(record_id="1", frame="USING_CURE"))
    assert ex is not None
    assert ex["selected_frame"] == "CURE"
    assert ex["target_word"] == "boter"


def test_dropped_maps_to_none() -> None:
    ex = exemplar_from_gold_record(
        _gold(record_id="2", frame="COOKING_CREATION", dropped=True)
    )
    assert ex is not None
    assert ex["selected_frame"] == "NONE"
    assert ex["dropped"] is True


def test_build_frame_exemplars_caps_and_groups() -> None:
    records = [
        _gold(record_id=f"c{i}", frame="COOKING_CREATION", context=f"kook {i}")
        for i in range(5)
    ] + [
        _gold(record_id="n1", frame="NONE", context="reizen naar Indië"),
        _gold(record_id="p1", frame="PRESERVING", context="zout het vlees"),
        _gold(record_id="bad", frame=None, context="geen frame"),
    ]
    buckets = build_frame_exemplars(records, per_frame_cap=3)
    assert len(buckets["COOKING_CREATION"]) == 3
    assert len(buckets["NONE"]) == 1
    assert len(buckets["PRESERVING"]) == 1
    assert buckets["CURE"] == []
    assert buckets["INGESTION"] == []
    summary = exemplar_summary(buckets)
    assert summary["COOKING_CREATION"] == 3
    assert summary["NONE"] == 1


def test_skip_empty_context() -> None:
    assert exemplar_from_gold_record(_gold(record_id="x", frame="CURE", context="")) is None
