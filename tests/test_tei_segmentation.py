"""Tests for reading declared entry structure out of DBNL TEI."""

from __future__ import annotations

from trifecta_annotation.tei_segmentation import (
    RUBRIC_LABELS,
    head_inventory,
    parse_entries,
)

CHOMEL_LIKE = """<TEI.2><text><body>
<div type="chapter"><head>B.</head>
  <div type="section"><head>Middel om een meenigte Aal te vangen.</head>
    <p><hi rend="b">aal</hi> Neemt wyn ende honig&nbsp;met snuiftabak.</p>
    <p><hi rend="b">aas</hi> Een pier is het beste aas.</p>
  </div>
  <div type="section"><head>Andere manier om Aal te vangen.</head>
    <p>Men neemt een zetangel.</p>
  </div>
</div>
<div type="chapter"><head>K.</head>
  <div type="section"><head>Van de Kruiden.</head>
    <p><hi rend="i">Beschryving</hi> De plant is groen.</p>
    <p><hi rend="i">Plaats</hi> Zy wast in Vrankryk.</p>
    <p><hi rend="i">Eigenschappen</hi> Zy zuiveren het Bloed.</p>
  </div>
</div>
</body></text></TEI.2>"""

SECREET_LIKE = """<TEI.2><text><body>
<div type="chapter"><head>De Secreten des Vyers.</head>
  <div type="section"><head>Om te maken een Keersse die niet uyt te blasen en is.</head>
    <p>Neemt was ende olie.</p></div>
  <div type="section"><head>Een ander.</head><p>Neemt terpentijn.</p></div>
  <div type="section"><head>Een ander.</head><p>Neemt savel.</p></div>
</div>
</body></text></TEI.2>"""


RUN_ON_SECTION = """<TEI.2><text><body>
<div type="chapter"><head>A.</head>
  <div type="section"><head>Andere manier om Aal te vangen.</head>
    <p>Men neemt een zetangel met een pier.</p>
    <p><hi rend="b">aamborstigheit</hi> Hier volgen middelen voor de borst.</p>
    <p>In vyf pinten wyns doet honig, snuiftabak en boomvaren.</p>
  </div>
</div>
</body></text></TEI.2>"""


def test_units_come_from_declared_sections_not_chapters():
    entries = parse_entries(CHOMEL_LIKE, work_id="w.xml")
    # 3 sections, but the first runs on into the `aas` lemma -> 4 units.
    assert len(entries) == 4
    assert [e.chapter_head for e in entries] == ["B.", "B.", "B.", "K."]
    assert entries[0].entry_id == "w.xml__u0"
    assert [e.unit_kind for e in entries] == [
        "section_head", "keyword_anchor", "section_head", "section_head"
    ]


def test_bold_lemma_opens_a_new_unit_inside_a_run_on_section():
    """Regression: attributing by nearest enclosing div misreads these.

    A section headed "Andere manier om Aal te vangen." runs on into the lemma
    `aamborstigheit`, so the wine/honey/tobacco passage belongs to the asthma
    remedy, not to the eel-catching entry. Resolving by section alone put it
    under the eel head and produced a confidently wrong reading (PLAN.md §9h).
    """
    entries = parse_entries(RUN_ON_SECTION, work_id="w.xml")
    assert [e.unit_kind for e in entries] == ["section_head", "keyword_anchor"]
    assert entries[0].head == "Andere manier om Aal te vangen."
    assert "zetangel" in entries[0].text
    assert "snuiftabak" not in entries[0].text

    assert entries[1].head == "aamborstigheit"
    assert "snuiftabak" in entries[1].text
    assert entries[1].scope_head == "aamborstigheit"
    assert entries[1].section_index == entries[0].section_index


def test_repeated_anchor_terms_get_distinct_offsets():
    xml = """<TEI.2><text><body><div type="section"><head>A.</head>
    <p>Opening tekst.</p>
    <p><hi rend="b">argemone</hi> Eerste vermelding.</p>
    <p><hi rend="b">argemone</hi> Tweede vermelding.</p>
    </div></body></text></TEI.2>"""
    entries = parse_entries(xml, work_id="w.xml")
    offsets = [a.offset for a in entries[0].keyword_anchors]
    assert len(offsets) == 2
    assert offsets[0] != offsets[1]
    assert "Eerste" in entries[1].text and "Tweede" not in entries[1].text
    assert "Tweede" in entries[2].text


def test_undefined_entities_do_not_break_parsing_or_leak_as_text():
    entries = parse_entries(CHOMEL_LIKE, work_id="w.xml")
    assert "&nbsp;" not in entries[0].text
    assert "honig" in entries[0].text


def test_paragraph_initial_bold_is_a_keyword_anchor():
    entries = parse_entries(CHOMEL_LIKE, work_id="w.xml")
    # Anchors are reported on the unit that opens the section, so the whole
    # lemma run stays visible even though `aas` also opens a unit of its own.
    assert [a.term for a in entries[0].keyword_anchors] == ["aal", "aas"]
    assert entries[0].text[entries[0].keyword_anchors[0].offset:].startswith("aal")


def test_mid_paragraph_bold_is_not_an_anchor():
    xml = """<TEI.2><text><body><div type="section"><head>H.</head>
    <p>Neemt <hi rend="b">zout</hi> ende peper.</p></div></body></text></TEI.2>"""
    assert parse_entries(xml, work_id="w.xml")[0].keyword_anchors == ()


def test_rubric_sequence_is_reported_in_document_order():
    entries = parse_entries(CHOMEL_LIKE, work_id="w.xml")
    kruiden = entries[3]
    assert kruiden.head == "Van de Kruiden."
    assert kruiden.rubrics == ("Beschryving", "Plaats", "Eigenschappen")
    assert set(kruiden.rubrics) <= RUBRIC_LABELS


def test_anaphoric_head_that_restates_its_scope_is_not_inherited():
    entries = parse_entries(CHOMEL_LIKE, work_id="w.xml")
    second = entries[2]
    assert second.head_kind == "anaphoric"
    assert second.scope_inherited is False
    assert second.scope_head == "Andere manier om Aal te vangen."


def test_bare_head_carries_scope_forward_from_preceding_sibling():
    entries = parse_entries(SECREET_LIKE, work_id="s.xml")
    assert [e.head_kind for e in entries] == ["descriptive", "bare", "bare"]
    assert all(e.scope_inherited for e in entries[1:])
    assert all(
        e.scope_head == "Om te maken een Keersse die niet uyt te blasen en is."
        for e in entries[1:]
    )


def test_divider_head_supplies_no_scope_and_is_not_carried_forward():
    xml = """<TEI.2><text><body>
    <div type="section"><head>Van de Kruiden.</head><p>Groen.</p></div>
    <div type="section"><head>B.</head><p>Bardanae, klissen.</p></div>
    <div type="section"><head>Een ander.</head><p>Nog een.</p></div>
    </body></text></TEI.2>"""
    entries = parse_entries(xml, work_id="w.xml")
    assert entries[1].head_kind == "divider"
    assert entries[1].scope_head is None
    # Must not resurrect the scope from before the divider.
    assert entries[2].scope_head is None


def test_content_carriers_are_reported_not_assumed_to_be_p():
    xml = """<TEI.2><text><body><div type="section"><head>B.</head>
    <list><item>Bardanae, klissen.</item><item>Bistortae, Herts-tong.</item></list>
    </div></body></text></TEI.2>"""
    assert parse_entries(xml, work_id="w.xml")[0].carriers == ("item",)


def test_head_inventory_is_flat_and_unclassified():
    rows = head_inventory(parse_entries(CHOMEL_LIKE, work_id="w.xml"))
    assert len(rows) == 4
    assert rows[0]["anchors"] == "aal|aas"
    assert rows[3]["rubrics"] == "Beschryving>Plaats>Eigenschappen"
    assert "frame" not in rows[0]
