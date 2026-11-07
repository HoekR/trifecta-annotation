"""Read the entry structure DBNL TEI *declares*, instead of detecting it.

Deliberately separate from `structural_parse.py`. That module detects unit
boundaries in flowing text with cue regexes and then has to decide whether to
trust what it found (per-cue-type checks plus a document density gate, PLAN.md
§9g). Here the boundaries are declared markup: a `div[@type="section"]` is an
entry because the encoder said so, so there is nothing to trust-gate and no
density to measure. Keeping the two apart stops the declared path inheriting
machinery built for a far less reliable signal.

CORRECTION (7 Nov 2026): "char offsets come free" was wrong as originally
written — this module's `_text()` rendering and `strip_tei`'s regex
stripping disagree at every tag boundary with no surrounding whitespace,
drifting ~5% over a full document. Fixed by `render_tei`, which produces the
harvester's text and every entry's offset in one structural walk, replacing
`strip_tei` for TEI sources.

Why this exists at all: the DBNL ingestion path reaches text through
`strip_tei()` in `scripts/build_colonial_kwic.py`, which is
`_WS.sub(" ", _TAG.sub(" ", xml))` — it deletes every tag with a regex and
never parses the XML. All of the structure below is destroyed at ingestion in
that one line, which is also why downstream code has only cue detection to work
with. See PLAN.md §9h.

Four levels, two of which hide in typographic markup rather than in the div
tree (`feedback_typography_hides_structure`):

1. `div[@type="chapter"]` — in the dictionaries and formularies these are
   alphabet dividers ("B.", "K."), carrying no scope.
2. `div[@type="section"]` + `<head>` — flat (depth 1) in every work inspected,
   and headed in ~100% of cases, but **not reliably one entry each**.
3. `<hi rend="b">` at paragraph start — `trefwoorden`/`subtrefwoorden` keyword
   anchors. Chomel only; position matters, since mid-paragraph bold is not this.

Levels 2 and 3 together make the entry boundary, because Chomel's sectioning is
uneven: 3,597 of its 4,795 sections are a single lemma ("Bye-Korf.",
"Bye-kruid. Zie Melisse."), but 799 run on past their head into further lemmas
marked *only* in bold — the first anchor sits at mean position 0.39 of those
sections' bodies, and anchors coincide with a section head only 28 times in
2,346. Attributing text to the nearest enclosing `div` alone therefore
misattributes it: a passage 8,127 chars into a section headed "Andere manier om
Aal te vangen." actually sits under the bold lemma `aamborstigheit` (asthma)
and is an asthma remedy, not an eel bait. `parse_entries` emits units at the
union of both boundaries for that reason, tagged by `unit_kind`.
4. `<hi rend="i">` matching `RUBRIC_LABELS` — a materia-medica field template.
   Chomel only, and only in ~7% of its entries.

Levels 1-2 generalise across every DBNL work checked; levels 3-4 do not, so
they are reported as observations rather than required fields — `Het
secreet-boek` has no bold at all and uses italic for authorities *and*
ingredients, while the Pharmacopoeas carry content in `<item>` and use italic
for Latin quantity units.

No LLM calls, no frame judgements, no writes to project data. This module
reports what the markup says; deciding what an entry *means* is a separate step.
"""

from __future__ import annotations

import re
import zipfile
from bisect import bisect_right

import lxml.etree as ET
from dataclasses import dataclass, field
from html.entities import name2codepoint
from pathlib import Path

__all__ = [
    "Anchor",
    "TeiEntry",
    "RUBRIC_LABELS",
    "editorial_heads",
    "parse_entries",
    "read_work_xml",
    "head_inventory",
    "render_tei",
    "RenderedTei",
    "entry_for_offset",
    "attach_tei_scope_to_rows",
]

# Observed as italic rubric labels in Chomel's herbal entries, validated by
# recurring order rather than by frequency: `Beschryving > Plaats >
# Eigenschappen` appears in that order 71 times, direction near-deterministic
# (Plaats before Eigenschappen 188 vs 8), and the template cycles per described
# item. Work-specific — do not assume these in other sources.
RUBRIC_LABELS = frozenset({
    "Beschryving", "Plaats", "Eigenschappen", "Krachten",
    "Dosis", "Gebruik", "Naam", "Keus", "Soorten",
})

# A head that refers back instead of restating its scope. Chomel's are mostly
# harmless ("Andere manier om Aal te vangen." still names the scope); `Het
# secreet-boek` has 112 of the bare kind, which carry no scope at all and need
# carry-forward from the preceding sibling.
_ANAPHORIC = re.compile(r"^\s*(ander|andere|anders|nog|noch)\b", re.I)
_BARE = re.compile(r"^\s*(een\s+ander|ander|andere|anders|noch\s+een\s+ander)\s*\.?\s*$", re.I)

# A head that is just an alphabet letter. Head *presence* is ~100% across these
# works but informativeness is not: both Pharmacopoeas head sections with bare
# letters, which separate entries without describing them. Distinguished from
# `bare` because a divider supplies no scope to carry forward either — unlike
# "Een ander.", which means "another one of the preceding kind".
_DIVIDER = re.compile(r"^\s*[A-Z]\s*\.?\s*$")

# DBNL's own modern editorial apparatus, carried as a chapter in some editions:
# "Achtergrondinformatie", "Gevolgde werkwijze bij het digitaliseren",
# "Zetfouten", "Medewerkers" and so on. It documents the digitisation rather
# than belonging to the work, so it is excluded by default (operator decision,
# 30 Oct 2026).
#
# Deliberately matches only this phrase. Historical front matter is *not*
# editorial apparatus and must survive: `Het secreet-boek` opens with
# "Voor-Reden des Autheurs." and the Roterodamensis with "Extract uit het
# Previlegie.", both genuine period text. Rare in this dump — 0 of 60 sampled
# works contain the phrase at all — so this is a narrow safety net, not a
# general front-matter filter.
_EDITORIAL_HEAD = re.compile(r"^\s*Verantwoording van de digitale uitgave", re.I)

_UNDEFINED_ENTITY = re.compile(r"&([A-Za-z][A-Za-z0-9]*);")
_XML_BUILTIN = frozenset({"amp", "lt", "gt", "quot", "apos"})
_WS = re.compile(r"\s+")


def _sanitize_entities(xml: str) -> str:
    """Resolve HTML entities the TEI uses but never declares.

    These files carry `&nbsp;` (and friends) with no DTD, so a strict parser
    stops at the first one. Left unhandled upstream, they also leak into
    exports as the literal text "&nbsp;".
    """
    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in _XML_BUILTIN:
            return match.group(0)
        codepoint = name2codepoint.get(name)
        return chr(codepoint) if codepoint is not None else " "

    return _UNDEFINED_ENTITY.sub(repl, xml)


_PARSER = ET.XMLParser(
    recover=True, resolve_entities=False, load_dtd=False, no_network=True
)


def _parse_xml(xml: str) -> ET._Element:
    """Parse sanitized TEI source. Encodes to bytes first: lxml refuses a
    `str` containing an XML declaration with an `encoding` attribute, which
    every one of these files has. `no_network`/`load_dtd=False` stop it
    trying to fetch the DOCTYPE's PUBLIC identifier over the network."""
    return ET.fromstring(_sanitize_entities(xml).encode("utf-8"), parser=_PARSER)


def _text(element: ET.Element) -> str:
    return _WS.sub(" ", "".join(element.itertext())).strip()


@dataclass(frozen=True)
class Anchor:
    """A level-3 keyword anchor and where it sits in the entry's text."""

    term: str
    offset: int


@dataclass(frozen=True)
class TeiEntry:
    """One declared entry, with its governing head and observed sub-structure.

    `head` is what the markup says; `scope_head` is what governs this entry
    after carry-forward, which differs only when the head is anaphoric and
    bare. `scope_inherited` says which case applies — callers must keep that
    distinction when anything derived from `scope_head` reaches analysis, or a
    40-entry run under one head over-counts it 40-fold (PLAN.md §9e).
    """

    work_id: str
    entry_index: int
    entry_id: str
    chapter_index: int | None
    chapter_head: str | None
    head: str | None
    head_kind: str  # descriptive | anaphoric | bare | divider | absent
    unit_kind: str  # section_head | keyword_anchor
    section_index: int
    scope_head: str | None
    scope_inherited: bool
    carriers: tuple[str, ...]
    keyword_anchors: tuple[Anchor, ...] = field(default=())
    rubrics: tuple[str, ...] = field(default=())
    text: str = ""

    @property
    def char_len(self) -> int:
        return len(self.text)


def _head_kind(head: str | None) -> str:
    if head is None or not head.strip():
        return "absent"
    if _DIVIDER.match(head):
        return "divider"
    if _BARE.match(head):
        return "bare"
    if _ANAPHORIC.match(head):
        return "anaphoric"
    return "descriptive"


def _carriers(section: ET.Element) -> tuple[str, ...]:
    """Which elements actually hold this entry's content.

    Worth reporting because assuming `<p>` produces false negatives: the
    Pharmacopoeas keep 846 and 2,501 of their `hi` inside `<item>`, so a
    p-centric reading calls the most densely marked works the sparsest.
    """
    counts: dict[str, int] = {}
    for tag in ("p", "item", "cell", "q"):
        found = [e for e in section.iter(tag) if _text(e)]
        if found:
            counts[tag] = len(found)
    return tuple(tag for tag, _ in sorted(counts.items(), key=lambda kv: -kv[1]))


def _section_body(
    section: ET.Element,
) -> tuple[str, tuple[Anchor, ...], tuple[ET._Element, ...]]:
    """Render a section's text once, recording exact anchor offsets as it goes.

    Offsets must come from the walk, not from searching the rendered string: a
    term can recur within one section (`argemone` appears twice in the worst
    case), so `str.find` would collapse distinct lemmas onto one position.

    An anchor is bold at the *start* of a content element — mid-element bold is
    emphasis, not a lemma boundary.
    """
    parts: list[str] = []
    anchors: list[Anchor] = []
    anchor_elements: list[ET._Element] = []
    length = 0

    for element in section.iter():
        if element.tag not in ("p", "item", "cell"):
            continue
        rendered = _text(element)
        if not rendered:
            continue
        children = list(element)
        leading_text = element.text and element.text.strip()
        if children and not leading_text:
            first = children[0]
            if first.tag == "hi" and first.get("rend") == "b":
                term = _text(first)
                if term:
                    anchors.append(Anchor(term=term, offset=length))
                    anchor_elements.append(element)
        parts.append(rendered)
        length += len(rendered) + 1

    return " ".join(parts), tuple(anchors), tuple(anchor_elements)


def _rubrics(section: ET.Element) -> tuple[str, ...]:
    """Level 4 in document order, so a caller can check the template's sequence.

    Immediate repeats are collapsed; genuine cycles are preserved, because
    `(Beschryving Plaats Eigenschappen)+` repeating per described item is the
    evidence that this is a template and not a word list.
    """
    seen: list[str] = []
    for hi in section.iter("hi"):
        if hi.get("rend") != "i":
            continue
        label = _text(hi).rstrip(".:")
        if label in RUBRIC_LABELS and (not seen or seen[-1] != label):
            seen.append(label)
    return tuple(seen)


def read_work_xml(zip_path: str | Path, xml_name: str) -> str:
    """Read one TEI file out of the DBNL zip without extracting it."""
    with zipfile.ZipFile(zip_path) as archive:
        return archive.read(xml_name).decode("utf-8", errors="replace")


def editorial_heads(xml: str) -> list[str]:
    """Heads of the sections `parse_entries` drops as DBNL editorial apparatus.

    Provided so the exclusion can be inspected rather than taken on trust —
    silent dropping is how this project lost provenance before.
    """
    root = _parse_xml(xml)
    heads: list[str] = []
    for chapter in root.iter("div"):
        if chapter.get("type") != "chapter":
            continue
        head = chapter.find("head")
        if head is None or not _EDITORIAL_HEAD.match(_text(head)):
            continue
        for section in chapter.iter("div"):
            if section.get("type") == "section":
                section_head = section.find("head")
                heads.append(_text(section_head) if section_head is not None else "")
    return heads


def parse_entries(
    xml: str, *, work_id: str, drop_editorial: bool = True
) -> list[TeiEntry]:
    """Parse declared entries. Levels 3-4 are reported when present, else empty.

    Sections are read in document order. A section outside any chapter still
    yields an entry, with `chapter_index`/`chapter_head` as None.

    `drop_editorial` excludes DBNL's digitisation documentation (see
    `_EDITORIAL_HEAD`); pass False to see what is being dropped, or use
    `editorial_heads`.
    """
    return [entry for entry, _ in _build_entries(_parse_xml(xml), work_id, drop_editorial)]


def _editorial_chapters(root: ET._Element) -> set[ET._Element]:
    out: set[ET._Element] = set()
    for chapter in root.iter("div"):
        if chapter.get("type") != "chapter":
            continue
        head = chapter.find("head")
        if head is not None and _EDITORIAL_HEAD.match(_text(head)):
            out.add(chapter)
    return out


def _build_entries(
    root: ET._Element, work_id: str, drop_editorial: bool
) -> list[tuple[TeiEntry, ET._Element]]:
    """Entries plus the element each one starts at (section div or anchor
    element), so a caller walking the same tree can place them exactly."""
    chapter_of: dict[ET.Element, tuple[int, str | None]] = {}
    editorial: set[ET.Element] = set()
    for index, chapter in enumerate(root.iter("div")):
        if chapter.get("type") != "chapter":
            continue
        head = chapter.find("head")
        label = _text(head) if head is not None else None
        is_editorial = label is not None and bool(_EDITORIAL_HEAD.match(label))
        for section in chapter.iter("div"):
            if section.get("type") == "section":
                chapter_of[section] = (index, label)
                if is_editorial:
                    editorial.add(section)

    entries: list[tuple[TeiEntry, ET._Element]] = []
    last_scope: str | None = None
    position = 0

    for section_index, section in enumerate(
        s for s in root.iter("div") if s.get("type") == "section"
    ):
        if drop_editorial and section in editorial:
            continue
        head_element = section.find("head")
        section_head = _text(head_element) if head_element is not None else None
        body, anchors, anchor_elements = _section_body(section)
        carriers = _carriers(section)
        rubrics = _rubrics(section)
        chapter_index, chapter_head = chapter_of.get(section, (None, None))

        # Unit boundaries: the section head opens one, every anchor opens another.
        starts: list[tuple[int, str | None, str, ET._Element]] = [
            (0, section_head, "section_head", section)
        ]
        starts += [
            (a.offset, a.term, "keyword_anchor", el)
            for a, el in zip(anchors, anchor_elements)
            if a.offset > 0
        ]
        starts.sort(key=lambda s: s[0])

        for order, (start, head, unit_kind, start_element) in enumerate(starts):
            end = starts[order + 1][0] if order + 1 < len(starts) else len(body)
            kind = _head_kind(head)

            if kind == "divider":
                # Supplies no scope and must not become one, or every entry
                # after a letter heading would inherit "B.".
                scope_head, inherited = None, False
                last_scope = None
            elif kind in ("bare", "absent"):
                scope_head, inherited = last_scope, last_scope is not None
            else:
                scope_head, inherited = head, False
                last_scope = head

            entries.append((
                TeiEntry(
                    work_id=work_id,
                    entry_index=position,
                    entry_id=f"{work_id}__u{position}",
                    chapter_index=chapter_index,
                    chapter_head=chapter_head,
                    head=head,
                    head_kind=kind,
                    unit_kind=unit_kind,
                    section_index=section_index,
                    scope_head=scope_head,
                    scope_inherited=inherited,
                    carriers=carriers,
                    # Reported on the unit that opens the section, so the full
                    # anchor list stays visible without duplicating it per unit.
                    keyword_anchors=anchors if unit_kind == "section_head" else (),
                    rubrics=rubrics if unit_kind == "section_head" else (),
                    text=body[start:end].strip(),
                ),
                start_element,
            ))
            position += 1

    return entries


@dataclass(frozen=True)
class RenderedTei:
    """Plain text of a TEI work plus each entry's exact start offset in it."""

    text: str
    located: tuple[tuple[int, TeiEntry], ...]


def render_tei(xml: str, *, work_id: str) -> RenderedTei:
    """Render the work's `<text>` body and place every entry in one walk.

    Replaces `strip_tei` for TEI sources. `strip_tei` deletes tags with a regex
    while this module rendered entries via `itertext()`; the two disagree at
    every tag boundary that has no whitespace in the source (e.g.
    `aamborstigheit</hi>, Kortademigheit`), drifting ~5% over Chomel, and the
    substring-anchoring workaround that bridged them only placed ~63% of
    entries. Here the harvester's text and the entry offsets come from the
    same pass, so they agree by construction.

    Rendering: every tag boundary becomes one space and whitespace runs
    collapse, matching `strip_tei`'s word separation. Unlike `strip_tei` it
    leaves out the `teiHeader` and DBNL's digitisation apparatus, and entities
    are resolved rather than leaking as literal `&nbsp;`.
    """
    root = _parse_xml(xml)
    body = root.find(".//text")
    if body is None:
        body = root
    skip = _editorial_chapters(root)

    parts: list[str] = []
    length = 0
    last_space = True
    offsets: dict[ET._Element, int] = {}

    def emit(s: str | None) -> None:
        nonlocal length, last_space
        if not s:
            return
        s = _WS.sub(" ", s)
        if last_space and s.startswith(" "):
            s = s[1:]
        if not s:
            return
        parts.append(s)
        length += len(s)
        last_space = s.endswith(" ")

    def walk(el: ET._Element) -> None:
        if not isinstance(el.tag, str) or el in skip:
            emit(" ")
            emit(el.tail)
            return
        emit(" ")
        offsets[el] = length
        emit(el.text)
        for child in el:
            walk(child)
        emit(" ")
        emit(el.tail)

    walk(body)
    text = "".join(parts).rstrip()

    located = sorted(
        ((offsets[el], entry) for entry, el in _build_entries(root, work_id, True) if el in offsets),
        key=lambda pair: pair[0],
    )
    return RenderedTei(text=text, located=tuple(located))


def entry_for_offset(
    located: tuple[tuple[int, TeiEntry], ...] | list[tuple[int, TeiEntry]], offset: int
) -> TeiEntry | None:
    """The entry governing `offset` in `render_tei`'s text."""
    index = bisect_right([pos for pos, _ in located], offset) - 1
    return located[index][1] if index >= 0 else None


def attach_tei_scope_to_rows(
    rows: list[dict],
    *,
    located: tuple[tuple[int, TeiEntry], ...] | list[tuple[int, TeiEntry]],
) -> list[dict]:
    """Stamp ``tei_scope_head`` (and upgrade UNKNOWN ``text_regime``) on harvest rows.

    `located` must come from `render_tei` on the same text the rows were
    harvested from, so `target_char_offset` lands in the right entry.
    Pre-LLM route for works whose work-level regime is UNKNOWN (PLAN.md §9i):
    an entry headed like a remedy/recipe is treated as MEDICAL/RECIPE_PRACTICE
    for sieve routing without rewriting the cascade.
    """
    from trifecta_annotation.regime_routing import regime_from_tei_scope_head
    from trifecta_annotation.text_regime import TextRegime

    if not located:
        return rows
    positions = [pos for pos, _ in located]
    out: list[dict] = []
    for row in rows:
        updated = dict(row)
        offset = updated.get("target_char_offset")
        index = bisect_right(positions, int(offset)) - 1 if offset is not None else -1
        if index < 0:
            out.append(updated)
            continue
        entry = located[index][1]
        scope = entry.scope_head or entry.head
        if scope:
            updated["tei_scope_head"] = scope
            regime = updated.get("text_regime")
            if regime in (None, "", TextRegime.UNKNOWN.value):
                upgraded = regime_from_tei_scope_head(scope)
                if upgraded is not None:
                    updated["text_regime"] = upgraded.value
        out.append(updated)
    return out


def head_inventory(entries: list[TeiEntry]) -> list[dict[str, object]]:
    """Flat rows for human review of the head list — the point of this module.

    Nothing here is classified. The inventory exists so the head list can be
    read by eye before anything downstream assigns meaning to it.
    """
    return [
        {
            "entry_id": e.entry_id,
            "chapter_head": e.chapter_head or "",
            "head": e.head or "",
            "head_kind": e.head_kind,
            "unit_kind": e.unit_kind,
            "scope_head": e.scope_head or "",
            "scope_inherited": e.scope_inherited,
            "carriers": "|".join(e.carriers),
            "anchors": "|".join(a.term for a in e.keyword_anchors),
            "rubrics": ">".join(e.rubrics),
            "char_len": e.char_len,
        }
        for e in entries
    ]
