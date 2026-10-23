"""Tests for Step B few-shot export helpers."""

from __future__ import annotations

import json

from trifecta_annotation.fewshot_export import (
    frame_for_review_row,
    gallery_row_to_fewshot,
    spotcheck_row_to_fewshot,
    strip_tgt_markup,
)


def test_strip_tgt_markup() -> None:
    assert strip_tgt_markup("met [TGT]uijen[/TGT] in soep") == "met uijen in soep"


def test_frame_for_review_row_keep_gold() -> None:
    assert (
        frame_for_review_row(verdict="k", gold_frame="INGESTION", pred_frame="COOKING_CREATION")
        == "INGESTION"
    )


def test_frame_for_review_row_adopt_pred() -> None:
    assert (
        frame_for_review_row(verdict="a", gold_frame="INGESTION", pred_frame="NONE")
        == "NONE"
    )


def test_frame_for_review_row_dropped_maps_to_none() -> None:
    assert frame_for_review_row(verdict="k", gold_frame="DROPPED", pred_frame="COOKING_CREATION") == "NONE"


def test_spotcheck_row_to_fewshot() -> None:
    row = {
        "record_id": "x",
        "target_word": "biet",
        "gold_frame": "DROPPED",
        "pred_frame": "COOKING_CREATION",
        "gold_lexical_unit": "",
        "pred_lexical_unit": "",
        "verdict": "k",
        "review_notes": "biet is offer here, not food related",
        "context_marked": "en vreucht en [TGT]biet[/TGT] daer aen",
    }
    example = spotcheck_row_to_fewshot(row)
    assert example is not None
    assert example["target_word"] == "biet"
    payload = json.loads(example["output"])
    assert payload["selected_frame"] == "NONE"
    assert "offer" in payload["reasoning"]


def test_gallery_row_to_fewshot_requires_note() -> None:
    assert gallery_row_to_fewshot({"target_word": "noot", "review_snippet": "in eene noot"}) is None

    example = gallery_row_to_fewshot(
        {
            "target_word": "noot",
            "gold_frame": "DROPPED",
            "review_snippet": "in eene [TGT]noot[/TGT] zegt",
            "homonym_note": "footnote sense",
            "record_id": "rid",
        },
    )
    assert example is not None
    assert json.loads(example["output"])["selected_frame"] == "NONE"
