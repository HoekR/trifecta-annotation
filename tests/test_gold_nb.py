"""Tests for notebook gold labelling helpers."""

from pathlib import Path

import pandas as pd

from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS
from trifecta_annotation.gold_nb import (
    GoldBatchEditor,
    RowLabeller,
    focused_snippet_markup,
    is_export_note,
    snippet_preview,
    snippet_to_html,
    _tri_state_from_csv,
    _tri_state_options,
    _tri_state_to_csv,
)


def _sample_row(**overrides: str) -> dict[str, str]:
    row = {col: "" for col in GOLD_CSV_COLUMNS}
    row.update(
        {
            "record_id": "r1",
            "target_word": "bloem",
            "selected_frame": "COOKING_CREATION",
            "context_text": "Men neemt wat bloem en mengt het.",
            "review_snippet": "neemt wat [TGT]bloem[/TGT] en mengt",
            "labelled": "false",
        },
    )
    row.update(overrides)
    return row


def test_tri_state_dropdown_option_values() -> None:
    values = {value for _label, value in _tri_state_options()}
    assert values == {"__unset__", "true", "false"}
    assert _tri_state_from_csv("") == "__unset__"


def test_find_target_match_prefers_occurrence_near_verb() -> None:
    from trifecta_annotation.clear_frame_examples import find_target_match

    text = "A" * 50 + " men kookt het water " + "B" * 50 + " fontein zonder water " + "C" * 20
    match = find_target_match(text, "water", near_verb="kookt")
    assert match is not None
    assert "kookt" in text[max(0, match.start() - 20) : match.end() + 5]


def test_focused_snippet_remarks_target_from_context() -> None:
    row = _sample_row(
        review_snippet="stale snippet without markup",
        context_text="Men neemt wat bloem en mengt het goed door.",
        target_word="bloem",
    )
    markup = focused_snippet_markup(row)
    assert "[TGT]bloem[/TGT]" in markup


def test_target_callout_shows_target_word() -> None:
    from trifecta_annotation.gold_nb import target_callout_html

    html_out = target_callout_html(_sample_row())
    assert "bloem" in html_out
    assert "Cmd+F" in html_out or "highlighted" in html_out.lower()


def test_snippet_to_html_large_and_marked() -> None:
    html_out = snippet_to_html(_sample_row())
    assert "1.28em" in html_out
    assert "<mark" in html_out
    assert "bloem" in html_out


def test_snippet_preview_strips_tgt_markup() -> None:
    row = _sample_row()
    assert "[TGT]" not in snippet_preview(row)
    assert "bloem" in snippet_preview(row)


def test_overview_frame_has_snippet_column(tmp_path: Path) -> None:
    path = tmp_path / "batch.csv"
    pd.DataFrame([_sample_row()]).to_csv(path, index=False)
    editor = GoldBatchEditor(path)
    overview = editor.overview_frame()
    assert list(overview.columns) == [
        "snippet",
        "target",
        "regime",
        "homonym",
        "verb",
        "Method",
        "Process",
        "Product",
        "done",
    ]
    assert "bloem" in overview.iloc[0]["snippet"]


def test_is_export_note() -> None:
    assert is_export_note("discovery_verb=maken; kwic_mode=verb_food")
    assert not is_export_note("reviewer: check frame verb")


def test_snippet_to_html_marks_target() -> None:
    html_out = snippet_to_html(_sample_row())
    assert "<mark" in html_out
    assert "bloem" in html_out
    assert "[TGT]" not in html_out


def test_gold_batch_editor_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "batch.csv"
    frame = pd.DataFrame([_sample_row()])
    extra = pd.DataFrame([{"homonym_check": "food_sense", "homonym_note": "", "review_snippet": "x"}])
    pd.concat([frame, extra], axis=1).to_csv(path, index=False)

    editor = GoldBatchEditor(path)
    editor.update("r1", COOKING_CREATION_Method="koken", labelled="true")
    editor.save()

    reloaded = GoldBatchEditor(path)
    row = reloaded.row_dict("r1")
    assert row["COOKING_CREATION_Method"] == "koken"
    assert row["labelled"] == "true"
    assert row["homonym_check"] == "food_sense"


def test_row_labeller_filters_cooking_only(tmp_path: Path) -> None:
    path = tmp_path / "batch.csv"
    rows = [
        _sample_row(record_id="r1", selected_frame="COOKING_CREATION"),
        _sample_row(record_id="r2", selected_frame="INGESTION"),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)

    labeller = RowLabeller(path=path, frame_filter="COOKING_CREATION", pending_only=False)
    assert labeller._record_ids == ["r1"]


def test_row_labeller_pending_only_excludes_labelled(tmp_path: Path) -> None:
    path = tmp_path / "batch.csv"
    rows = [
        _sample_row(record_id="r1", labelled="true"),
        _sample_row(record_id="r2", labelled="false"),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)

    labeller = RowLabeller(path=path, frame_filter="COOKING_CREATION", pending_only=True)
    assert labeller._record_ids == ["r2"]


def test_row_labeller_refresh_drops_newly_labelled(tmp_path: Path) -> None:
    path = tmp_path / "batch.csv"
    rows = [
        _sample_row(record_id="r1", labelled="false"),
        _sample_row(record_id="r2", labelled="false"),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)

    labeller = RowLabeller(path=path, frame_filter="COOKING_CREATION", pending_only=True, autosave=False)
    assert labeller._record_ids == ["r1", "r2"]

    labeller.editor.update("r1", labelled="true")
    labeller.refresh()
    assert labeller._record_ids == ["r2"]
    assert labeller._current_record_id() == "r2"


def test_row_labeller_autosave_writes_csv(tmp_path: Path) -> None:
    path = tmp_path / "batch.csv"
    pd.DataFrame([_sample_row()]).to_csv(path, index=False)

    labeller = RowLabeller(path=path, autosave=True)
    labeller.editor.update("r1", COOKING_CREATION_Method="bakken", labelled="true")
    labeller.editor.save()

    reloaded = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert reloaded.iloc[0]["COOKING_CREATION_Method"] == "bakken"
