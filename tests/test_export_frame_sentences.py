"""Tests for the year-ordered three-frame sentence export."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "export_frame_sentences", Path(__file__).parent.parent / "scripts" / "export_frame_sentences.py"
)
export_frame_sentences = importlib.util.module_from_spec(_SPEC)
sys.modules["export_frame_sentences"] = export_frame_sentences
_SPEC.loader.exec_module(export_frame_sentences)

build_export = export_frame_sentences.build_export


def _annotation(frame, year_stem, target="bloed", context=None, source_path=None, dropped=False, error=None):
    return {
        "provenance": {
            "record_id": f"{year_stem}__{target}",
            "source_path": source_path or f"_{year_stem}_01.xml",
            "title": "Test Work",
            "target_word": target,
            "context_text": context or f"Dit is een zin met {target} erin. Nog een zin.",
        },
        "step_b": {"selected_frame": frame, "lexical_unit": target},
        "step_c": {"frame": frame} if frame else {},
        "dropped": dropped,
        "error": error,
    }


def _dbnl_record(ti_id, year, assertions=None):
    assertions = assertions or [
        {"value": "49.25 eetwaren naar bereiding", "scheme": "basisclassificatie",
         "source": "x", "method": "x", "retrieved": "x"},
    ]
    return {
        "work_id": ti_id, "id_scheme": "dbnl_ti_id", "ti_id": ti_id,
        "titel": "Test Work", "year": year,
        "year_provenance": "test", "has_xml": True, "ggc_records": None,
        "genre_assertions": assertions, "schemes": sorted({a["scheme"] for a in assertions}),
    }


def _index(*records):
    from trifecta_annotation.corpus_genre_join import build_genre_index
    return build_genre_index(list(records) or [_dbnl_record("yro017work01", 1743)])


def test_three_frame_row_is_exported_with_year() -> None:
    rows, counts = build_export([_annotation("CURE", "yro017work01")], _index())
    assert len(rows) == 1
    assert rows[0]["year"] == 1743
    assert rows[0]["frame"] == "CURE"
    assert counts["has_year"] == 1
    assert counts["no_year"] == 0


def test_non_three_frame_is_excluded_and_counted() -> None:
    rows, counts = build_export([_annotation("INGESTION", "yro017work01")], _index())
    assert rows == []
    assert counts["other_frame"] == 1
    assert counts["three_frame"] == 0


def test_dropped_or_errored_rows_are_excluded_and_counted() -> None:
    rows, counts = build_export([
        _annotation("CURE", "yro017work01", dropped=True),
        _annotation("CURE", "yro017work01", error="boom"),
    ], _index())
    assert rows == []
    assert counts["dropped_or_error"] == 2


def test_missing_year_excludes_but_counts_rather_than_crashes() -> None:
    rows, counts = build_export([_annotation("CURE", "unknown_work")], _index())
    assert rows == []
    assert counts["no_year"] == 1


def test_truncated_sentence_is_kept_with_a_flag() -> None:
    """Dropping truncated sentences would lose real data; flag instead."""
    context = "voorafgaand zinnetje. Dit kookt den bloed in een pot"  # no closing punctuation
    rows, counts = build_export(
        [_annotation("CURE", "yro017work01", target="bloed", context=context)], _index()
    )
    assert len(rows) == 1
    assert rows[0]["sentence_truncated_right"] is True
    assert counts["truncated"] == 1


def test_rows_are_sorted_by_year() -> None:
    idx = _index(_dbnl_record("aaa017bbb012", 1850), _dbnl_record("ccc017ddd012", 1700))
    rows, _ = build_export([
        _annotation("CURE", "aaa017bbb012", source_path="_aaa017bbb012_01.xml"),
        _annotation("PRESERVING", "ccc017ddd012", source_path="_ccc017ddd012_01.xml"),
    ], idx)
    assert [r["year"] for r in rows] == [1700, 1850]


def test_step_c_fields_present_per_frame() -> None:
    rows, _ = build_export([_annotation("PRESERVING", "yro017work01")], _index())
    assert "PR_Technique" in rows[0]
    assert "CURE_Affliction" not in rows[0]
