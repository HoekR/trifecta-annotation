"""Tests for gold labelling UI store helpers."""

from pathlib import Path

import pandas as pd

from gold_labeller.store import (
    display_snippet_text,
    highlight_target,
    is_labelled,
    stats,
    update_row,
)
from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS


def test_highlight_target() -> None:
    html = highlight_target("een hand vol zout", "zout")
    assert "<mark" in html
    assert "zout" in html


def test_display_snippet_prefers_review_snippet() -> None:
    text = display_snippet_text(
        {
            "target_word": "zout",
            "context_text": "AAA " + ("pad " * 80) + " zout " + ("pad " * 80) + " ZZZ",
            "review_snippet": "…neem [TGT]zout[/TGT] en water…",
        },
    )
    assert text == "…neem zout en water…"
    assert "AAA" not in text


def test_display_snippet_centers_long_context() -> None:
    pad = "woord " * 100
    context = f"{pad}target_food{pad}"
    text = display_snippet_text(
        {"target_word": "target_food", "context_text": context, "lexical_unit": "eten"},
    )
    assert "target_food" in text
    assert len(text) < len(context)
    assert text.startswith("…") or text.endswith("…")


def test_update_row_marks_labelled(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {
                "record_id": "r1",
                "corpus": "cort_voc_db",
                "target_word": "zout",
                "context_text": "zout in water",
                "labelled": "false",
            },
        ],
    )
    for col in GOLD_CSV_COLUMNS:
        if col not in frame.columns:
            frame[col] = ""
    updated = update_row(
        frame,
        "r1",
        {
            "is_food_entity": "true",
            "is_metaphor": "false",
            "selected_frame": "PRESERVING",
            "lexical_unit": "zout",
            "labelled": "true",
        },
    )
    row = updated.iloc[0].to_dict()
    assert row["selected_frame"] == "PRESERVING"
    assert is_labelled(row)
    assert stats(updated)["labelled"] == 1


def test_explicit_unlabelled_row_stays_pending() -> None:
    row = {
        "labelled": "false",
        "is_food_entity": "true",
        "is_metaphor": "false",
        "dropped": "false",
    }
    assert not is_labelled(row)
