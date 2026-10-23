"""Tests for the corpus-overview <-> dbnl_work_genre join."""

from __future__ import annotations

from trifecta_annotation.corpus_genre_join import (
    build_genre_index,
    lookup_for_filename,
)


def _dbnl_record(work_id: str, titel: str, year: int | None, assertions: list[dict]) -> dict:
    return {
        "work_id": work_id, "id_scheme": "dbnl_ti_id", "ti_id": work_id,
        "titel": titel, "year": year,
        "year_provenance": "dbnl_titels_pd.csv:_jaar|jaar",
        "has_xml": True, "ggc_records": None,
        "genre_assertions": assertions,
        "schemes": sorted({a["scheme"] for a in assertions}),
    }


def _kb_record(work_id: str, titel: str, year: int | None) -> dict:
    return {
        "work_id": work_id, "id_scheme": "kb_row", "titel": titel, "year": year,
        "year_provenance": "kb_titles_parsed.csv:Jaar (may be the digitisation year)",
        "has_xml": False, "ggc_records": None, "auteur": None,
        "genre_assertions": [
            {"value": "49.25 eetwaren naar bereiding", "scheme": "kb_basisclassificatie",
             "source": "kb_titles_parsed.csv", "method": "x", "retrieved": "2026-10-22"},
        ],
        "schemes": ["kb_basisclassificatie"],
    }


def test_year_comes_from_dbnl_when_present() -> None:
    records = [_dbnl_record("chom003huis01", "Huishoudelyk woordboek", 1743, [
        {"value": "RECIPE_PRACTICE", "scheme": "text_regime", "source": "x",
         "method": "x", "retrieved": "x"},
    ])]
    index = build_genre_index(records)
    hit = lookup_for_filename(index, "_chom003huis01_01.xml")
    assert hit.year == 1743
    assert "dbnl_titels" in hit.year_source


def test_basisclassificatie_is_preferred_category_scheme() -> None:
    """Rik's stated preference: Basisclassificatie over free-text subjects."""
    records = [_dbnl_record("pha001phar05", "Pharmacopoea Amstelredamensis", 1709, [
        {"value": "MEDICAL", "scheme": "text_regime", "source": "x", "method": "x", "retrieved": "x"},
        {"value": "44.42 farmacie", "scheme": "basisclassificatie", "source": "x", "method": "x", "retrieved": "x"},
        {"value": "Apotheken", "scheme": "ggc_subject", "source": "x", "method": "x", "retrieved": "x"},
    ])]
    index = build_genre_index(records)
    hit = lookup_for_filename(index, "_pha001phar05_01.xml")
    assert hit.category == "44.42 farmacie"
    assert hit.category_scheme == "basisclassificatie"


def test_falls_back_to_earliest_kb_title_match_when_dbnl_has_no_year() -> None:
    """Several KB rows for one title (reprints) -> the earliest is used, as a
    way to place the work in time, not to pick a specific edition."""
    records = [
        _dbnl_record("not001nota02", "Een notabel boecxken van cokeryen", None, []),
        _kb_record("kb:1", "Een notabel boecxken van cokeryen (1991 ed.)", 1920),
        _kb_record("kb:2", "Een notabel boecxken van cokeryen", 1514),
        _kb_record("kb:3", "Een notabel boecxken van cokeryen", 1998),
    ]
    index = build_genre_index(records)
    hit = lookup_for_filename(index, "_not001nota02_01.xml")
    assert hit.year == 1514
    assert "title match" in hit.year_source


def test_kb_rows_dated_1900_or_later_are_never_used_as_fallback() -> None:
    """97% of KB rows are modern catalogue/digitisation dates, not the work's
    own era (PLAN: the Digby example, KB row dated [2016] for an 1680 work)."""
    records = [
        _dbnl_record("xxx001yyy01", "Some Work", None, []),
        _kb_record("kb:1", "Some Work", 1958),
    ]
    index = build_genre_index(records)
    hit = lookup_for_filename(index, "_xxx001yyy01_01.xml")
    assert hit.year is None


def test_unmatched_filename_returns_empty_lookup() -> None:
    index = build_genre_index([])
    hit = lookup_for_filename(index, "_unknown001_01.xml")
    assert hit.year is None
    assert hit.category is None
