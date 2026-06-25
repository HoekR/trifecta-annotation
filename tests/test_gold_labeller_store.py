"""Tests for gold labelling UI store helpers."""

from pathlib import Path

import pandas as pd

from gold_labeller.store import (
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
