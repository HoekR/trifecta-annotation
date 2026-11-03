"""Tests for the DBNL genre-assertion sidecar."""

from __future__ import annotations

from trifecta_annotation.dbnl_genre import (
    assertions_for,
    build_records,
    parse_ggc,
    title_screen,
    work_stem,
)

_GGC_XML = """<srw:searchRetrieveResponse xmlns:srw="x" xmlns:dc="y">
<srw:numberOfRecords>3</srw:numberOfRecords>
<dc:subject>49.25 eetwaren naar bereiding</dc:subject>
<dc:subject>Kookkunst</dc:subject>
<dc:subject>Recepten (vorm)</dc:subject>
</srw:searchRetrieveResponse>"""


def test_parse_ggc_splits_basisclassificatie_from_headings() -> None:
    parsed = parse_ggc(_GGC_XML)
    assert parsed["records"] == 3
    assert parsed["basisclassificatie"] == ["49.25 eetwaren naar bereiding"]
    assert parsed["subjects"] == ["Kookkunst", "Recepten (vorm)"]


def test_parse_ggc_handles_no_results() -> None:
    parsed = parse_ggc("<x><srw:numberOfRecords>0</srw:numberOfRecords></x>")
    assert parsed == {"records": 0, "basisclassificatie": [], "subjects": []}


def test_title_screen_needs_word_boundaries() -> None:
    # The unbounded version of this screen matched "kok" inside Grandisson and
    # "recept" inside Bijbelsch magazijn, which is why boundaries are enforced.
    assert title_screen("Een notabel boecxken van cokeryen") == ["cookery"]
    assert title_screen("Pharmacopoea Roterodamensis") == ["medical"]
    assert title_screen("De kleine Grandisson of De gehoorzaame zoon") == []
    assert title_screen("Bijbelsch magazijn voor alle standen") == []


def test_assertions_keep_every_scheme_separate() -> None:
    """The schemes disagree; the record must preserve the disagreement."""
    row = {"titel": "Huishoudelyk woordboek", "genre": "sec - taalkunde"}
    ggc = {"records": 3, "basisclassificatie": ["49.00 huishoudkunde: algemeen"],
           "subjects": ["Huishoudkunde"]}
    claims = assertions_for(row, ggc=ggc, ggc_query="Huishoudelyk woordboek",
                            text_regime="RECIPE_PRACTICE", retrieved="2026-10-22")
    by_scheme = {c.scheme: c.value for c in claims}
    assert by_scheme["text_regime"] == "RECIPE_PRACTICE"
    assert by_scheme["basisclassificatie"] == "49.00 huishoudkunde: algemeen"
    assert by_scheme["dbnl_genre"] == "sec - taalkunde"
    assert by_scheme["title_screen"] == "cookery"
    # Every claim must say where it came from, or the file is useless.
    assert all(c.source and c.method and c.retrieved for c in claims)


def test_build_records_reports_year_and_text_availability() -> None:
    rows = [
        {"ti_id": "chom003huis01", "titel": "Huishoudelyk woordboek",
         "jaar": "1743", "_jaar": "1743", "genre": "sec - taalkunde"},
        {"ti_id": "not001nota02", "titel": "Een notabel boecxken van cokeryen",
         "jaar": "1514", "_jaar": "1514", "genre": "non-fictie"},
    ]
    records = build_records(
        rows,
        ggc_lookup=lambda row: (None, None),
        regime_lookup=lambda row: "RECIPE_PRACTICE" if "woordboek" in row["titel"] else None,
        have_xml={work_stem("chom003huis01")},
        retrieved="2026-10-22",
    )
    assert [r["year"] for r in records] == [1743, 1514]
    # The 1514 cookbook is in the metadata but absent from the TEI zip.
    assert [r["has_xml"] for r in records] == [True, False]
    assert records[0]["ggc_records"] is None
    assert "text_regime" in records[0]["schemes"]
    assert "text_regime" not in records[1]["schemes"]


def test_work_stem_reconciles_the_two_id_spellings() -> None:
    """`_chom003huis01_01` in the corpus and `chom003huis01` in the dump are one work."""
    assert work_stem("_chom003huis01_01") == work_stem("chom003huis01")
    assert work_stem("_vol002volm01_01") == work_stem("vol002volm01")


def test_rows_without_ti_id_are_skipped() -> None:
    records = build_records(
        [{"ti_id": "", "titel": "x", "genre": "proza"}],
        ggc_lookup=lambda row: (None, None),
        regime_lookup=lambda row: None,
        have_xml=set(),
    )
    assert records == []


def test_parse_kb_basisclassificatie_splits_run_together_codes() -> None:
    """The KB cell concatenates codes and sometimes trails a stray label."""
    from trifecta_annotation.dbnl_genre import parse_kb_basisclassificatie

    value = ("44.38 farmacologie (geneeskunde) 49.40 lichaamsverzorging "
             "(huishoudkunde) Gegevens origineel")
    # "Gegevens origineel" is the next field's label bleeding in, not genre.
    assert parse_kb_basisclassificatie(value) == [
        "44.38 farmacologie (geneeskunde)",
        "49.40 lichaamsverzorging (huishoudkunde)",
    ]


def test_title_screen_claims_name_their_own_catalogue() -> None:
    claims = assertions_for({"titel": "Het Hollands kook-boek"}, ggc=None,
                            ggc_query=None, text_regime=None,
                            retrieved="2026-10-22",
                            title_source="kb_titles_parsed.csv")
    screen = [c for c in claims if c.scheme == "title_screen"]
    assert screen and all(c.source == "kb_titles_parsed.csv" for c in screen)


def test_catalogue_cells_tolerate_pandas_nan() -> None:
    """Empty catalogue cells arrive as float NaN, not None."""
    from trifecta_annotation.dbnl_genre import parse_kb_basisclassificatie, parse_kb_goo

    assert parse_kb_goo(float("nan")) == []
    assert parse_kb_basisclassificatie(float("nan")) == []


def test_parse_kb_goo_splits_topical_and_form_terms() -> None:
    from trifecta_annotation.dbnl_genre import parse_kb_goo

    assert parse_kb_goo("Geneesmiddelen, Cosmetica; Overzichten (vorm)") == [
        "Cosmetica", "Geneesmiddelen", "Overzichten (vorm)",
    ]


def test_parse_leiden_dc_prefers_description_years_over_dc_date() -> None:
    """dc:date is the digitisation year for these records; the real year hides
    in a description like "Afl. 1: 1894."."""
    from trifecta_annotation.dbnl_genre import parse_leiden_dc

    xml = """<oai_dc:dc xmlns:dc="x" xmlns:oai_dc="y">
    <dc:title>Nuttige Indische planten</dc:title>
    <dc:subject>Medicinal plants</dc:subject>
    <dc:subject>Botany, Economic</dc:subject>
    <dc:description>Afl. 1: 1894.</dc:description>
    <dc:description>Afl. 2: 1895.</dc:description>
    <dc:date>2010</dc:date>
    <dc:identifier>item:953710</dc:identifier>
    </oai_dc:dc>"""
    parsed = parse_leiden_dc(xml)
    assert parsed["title"] == "Nuttige Indische planten"
    assert parsed["subjects"] == ["Botany, Economic", "Medicinal plants"]
    assert parsed["dc_dates"] == ["2010"]
    assert parsed["years_in_description"] == ["1894", "1895"]
    assert "item:953710" in parsed["identifiers"]


def test_gutenberg_claims_carry_locc_and_subjects_separately() -> None:
    row = {
        "titel": "De Vegetarische Keuken",
        "gutenberg_locc": ["TX"],
        "gutenberg_subjects": ["Vegetarian cooking"],
    }
    claims = assertions_for(row, ggc=None, ggc_query=None, text_regime=None,
                            retrieved="2026-10-22")
    by_scheme = {c.scheme: c.value for c in claims}
    assert by_scheme["gutenberg_locc"] == "TX"
    assert by_scheme["gutenberg_subject"] == "Vegetarian cooking"


def test_every_record_is_keyed_the_same_way() -> None:
    """All sources share work_id/id_scheme so their records can be pooled."""
    records = build_records(
        [{"ti_id": "chom003huis01", "titel": "Huishoudelyk woordboek",
          "jaar": "1743", "_jaar": "1743", "genre": "sec - taalkunde"}],
        ggc_lookup=lambda row: (None, None),
        regime_lookup=lambda row: None,
        have_xml=set(),
    )
    assert records[0]["work_id"] == "chom003huis01"
    assert records[0]["id_scheme"] == "dbnl_ti_id"
    # The native DBNL identifier stays available under its own name.
    assert records[0]["ti_id"] == "chom003huis01"
