"""Per-work genre assertions, each carrying its own provenance.

Genre for these works is contested, not unknown: the three schemes we have
disagree systematically, and merging them would destroy the information. The
clearest case is `Huishoudelyk woordboek` — DBNL files it as `sec - taalkunde`,
KB's GGC calls it `49.00 huishoudkunde: algemeen`, and the project's own
`text_regime` calls it `RECIPE_PRACTICE`. It is also 53% of the annotated
three-frame rows, so a filter built on DBNL's genre would discard the most
productive work in the corpus (measured: 64% of rows would go).

So this module records *assertions*, not a resolved label. Each assertion says
what was claimed, under which scheme, by which source, and how it was obtained.
Downstream code picks a scheme deliberately, or counts agreement across schemes
as votes; nothing here picks one for it, and nothing here weights the sources —
they differ in trustworthiness (see the per-scheme notes) and that judgement
belongs with whoever is using the result.

Schemes, in rough order of usefulness for TRIFECTA:

``text_regime``
    The project's own per-work overrides (`text_regime.py:_WORK_REGIME`). Hand
    assigned, so right by construction for the 61 works it covers.
``basisclassificatie``
    Nederlandse Basisclassificatie codes from GGC, e.g.
    `49.25 eetwaren naar bereiding`, `44.42 farmacie`. A real genre taxonomy.
``ggc_subject``
    GGC subject headings and form terms — `Kookkunst`, `Recepten (vorm)`.
``title_screen``
    Word-boundary keyword hit on the title. Cheap, and the only scheme that
    works before any text is read, but it only fires on works that announce
    their genre in the title, so absence means nothing.
``kb_goo`` / ``kb_basisclassificatie``
    Trefwoord GOO headings and Basisclassificatie codes from the earlier KB
    catalogue parse (`kb_titles_parsed`). The richest source we have: subjects
    on 100% of 7,545 rows, codes on 95%. It is a *culinary* bibliography —
    `49.25 eetwaren naar bereiding` carries 6,781 rows — so it is strong for the
    cookery side and thin for CURE (44.x codes total a few hundred).
``gutenberg_locc`` / ``gutenberg_subject``
    Library of Congress class codes and LCSH subjects from the Project Gutenberg
    catalogue feed. The most complete genre data of any source here — LoCC on
    100% of 79,634 records — and the only one that ships with free full text.
    But the Dutch holding is 1,114 records of which exactly **4** are classed
    `TX` (home economics/cookery), so it adds a few texts, not volume.

    Treat it as **one vote, not an authority**: Gutenberg's cataloguing is
    volunteer work of uneven depth, its `Issued` field is the posting date
    rather than the work's year, and a single LoCC letter pair is a much
    coarser claim than a Basisclassificatie code. Useful for corroborating
    another source, or for the handful of texts only it supplies; not for
    settling a genre on its own.

``leiden_dc_subject``
    LCSH-style `dc:subject` from the Leiden UB OAI-DC records shipped beside the
    colonial books ("Botany, Economic", "Medicinal plants").
``dbnl_genre``
    The dump's own `genre` column. Recorded for completeness; see the docstring
    above for why it must not be used as a filter.

**Dates from catalogue records are not safe by default.** A KB `Jaar` or a
Leiden `dc:date` is often the *digitisation* year, not the work's: the Digby
remedy book is dated `[2016]` and `[2011]`, and `Nuttige Indische planten`
carries `dc:date` 2010 with the real years (1894, 1895) only in `dc:description`.
Year provenance is therefore recorded per claim, like genre.

**Known gap, deliberately not solved here.** These are *work*-level assertions,
and periodicals break that: a `Vaderlandsche Letteroefeningen` jaargang mixes
reviews, travel writing and household notes under one genre, and 19th-century
travel/ethnographic description is similarly mixed. Work-level genre is the
wrong grain for them; resolving it needs unit-level classification, which is a
separate piece of work.
"""

from __future__ import annotations

import csv
import re
import zipfile
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

# Word boundaries are load-bearing. Without them "kok" matched
# "De kleine Grandisson" and "recept" matched "Bijbelsch magazijn".
TITLE_SCREEN: dict[str, str] = {
    "cookery": r"\b(kokery\w*|cokery\w*|kook\w*|kock\w*|keuken\w*|keucken\w*|banket\w*|"
               r"confitur\w*|spijs\w*|spys\w*|maaltijd\w*|huishoud\w*|huyshoud\w*|"
               r"menage\w*|gaare-keuken)\b",
    # Kept although it finds almost nothing: preserving is essentially never
    # named in a title, which is itself why PRESERVING cannot be grown by work
    # selection. The absence is the finding, so the screen stays in to record it.
    "preserving": r"\b(inmaak\w*|inmaken|bewaren|confyt\w*|confijt\w*|pekel\w*|azijn\w*)\b",
    "medical": r"\b(apothe\w*|apoteek\w*|pharmacop\w*|farmacop\w*|medicyn\w*|medicijn\w*|"
               r"artseny\w*|artsenij\w*|geneesm\w*|geneesk\w*|heelkund\w*|remedi\w*|"
               r"secreet\w*|secret\w*|chirurg\w*|kruid-boek|kruidboek|herbari\w*|"
               r"wondre|distill\w*)\b",
}

_BASISCLASSIFICATIE = re.compile(r"^\d\d\.\d\d\s")
_YEAR = re.compile(r"1[0-9]{3}")
_TITELS_SOURCE = "dbnl_titels_pd.csv"
_GGC_SOURCE = "KB GGC (jsru.kb.nl SRU, x-collection=GGC)"
_KB_SOURCE = "kb_titles_parsed.csv"
_LEIDEN_SOURCE = "Leiden UB OAI-DC record (handle.net/1887.1)"
_PG_SOURCE = "Project Gutenberg catalogue feed (pg_catalog.csv)"

# GOO headings arrive as one string mixing topical and form terms, comma- and
# semicolon-separated: "Geneesmiddelen, Cosmetica; Overzichten (vorm)".
_GOO_SPLIT = re.compile(r"[;,]")
_BC_CODE = re.compile(r"\d\d\.\d\d [^\d]+?(?=\s*\d\d\.\d\d |\s*$)")
# The Basisclassificatie cell sometimes runs on into the next field's label
# ("49.25 eetwaren naar bereiding Gegevens origineel"), which would otherwise be
# captured as part of the classification value.
_BC_TRAILING = re.compile(
    r"\s+(?:Gegevens origineel|Gegevens gedigitaliseerde reproductie|"
    r"Aanvraagnummer:?|Toegang:?|Locatie origineel:?|Fysieke informatie:?)\s*$",
    re.I,
)


@dataclass(frozen=True)
class GenreAssertion:
    """One claim about a work's genre, with where it came from."""

    value: str
    scheme: str
    source: str
    method: str
    retrieved: str


def work_stem(ti_id: str) -> str:
    """Join key between a ti_id and a TEI filename.

    The two spellings differ: the annotation corpus and some zip entries carry a
    leading underscore and a ``_01`` volume suffix that the titles dump omits.
    Both sides must be reduced the same way, so this is the single definition —
    doing it inline in two places produced an off-by-one that silently reported
    every work as having no text.
    """
    return ti_id.strip().lstrip("_")[:12]


def _year(row: dict[str, str]) -> int | None:
    match = _YEAR.search((row.get("_jaar") or "") + " " + (row.get("jaar") or ""))
    return int(match.group(0)) if match else None


def xml_stems(zip_path: str | Path) -> set[str]:
    """ti_id stems that have TEI text in the DBNL zip.

    The dump's metadata is much wider than its text — 3,655 XML files against
    8,896 works dated 1500-1899 — so this is the difference between a work we
    can process and one we can only cite.
    """
    with zipfile.ZipFile(zip_path) as archive:
        return {
            work_stem(Path(name).stem)
            for name in archive.namelist()
            if name.endswith(".xml")
        }


def parse_ggc(xml: str) -> dict[str, Any]:
    """Subject terms and record count out of a cached GGC SRU response."""
    count = re.search(r"numberOfRecords>(\d+)", xml)
    subjects = re.findall(r"<dc:subject[^>]*>(.*?)</dc:subject>", xml, re.S)
    stripped = {s.strip() for s in subjects if s.strip()}
    return {
        "records": int(count.group(1)) if count else 0,
        "basisclassificatie": sorted(s for s in stripped if _BASISCLASSIFICATIE.match(s)),
        "subjects": sorted(s for s in stripped if not _BASISCLASSIFICATIE.match(s)),
    }


def title_screen(titel: str) -> list[str]:
    """Which title-keyword screens fire for *titel*."""
    low = (titel or "").lower()
    return [name for name, pattern in TITLE_SCREEN.items() if re.search(pattern, low)]


def assertions_for(
    row: dict[str, str],
    *,
    ggc: dict[str, Any] | None,
    ggc_query: str | None,
    text_regime: str | None,
    retrieved: str,
    title_source: str = _TITELS_SOURCE,
) -> list[GenreAssertion]:
    """Every genre claim available for one title row, each tagged with its source."""
    out: list[GenreAssertion] = []
    if text_regime:
        out.append(GenreAssertion(
            value=text_regime, scheme="text_regime",
            source="trifecta_annotation/text_regime.py:_WORK_REGIME",
            method="per_work_override", retrieved=retrieved))
    if ggc:
        for value in ggc["basisclassificatie"]:
            out.append(GenreAssertion(
                value=value, scheme="basisclassificatie", source=_GGC_SOURCE,
                method=f'dc.title="{ggc_query}" -> dc:subject', retrieved=retrieved))
        for value in ggc["subjects"]:
            out.append(GenreAssertion(
                value=value, scheme="ggc_subject", source=_GGC_SOURCE,
                method=f'dc.title="{ggc_query}" -> dc:subject', retrieved=retrieved))
    for tag in title_screen(row.get("titel", "")):
        out.append(GenreAssertion(
            value=tag, scheme="title_screen", source=title_source,
            method="word-boundary regex on titel", retrieved=retrieved))
    for value in parse_kb_basisclassificatie(row.get("kb_basisclassificatie")):
        out.append(GenreAssertion(
            value=value, scheme="kb_basisclassificatie", source=_KB_SOURCE,
            method="Basisclassificatie column", retrieved=retrieved))
    for value in parse_kb_goo(row.get("kb_goo")):
        out.append(GenreAssertion(
            value=value, scheme="kb_goo", source=_KB_SOURCE,
            method="Trefwoord GOO column", retrieved=retrieved))
    for value in row.get("gutenberg_locc") or []:
        out.append(GenreAssertion(
            value=value, scheme="gutenberg_locc", source=_PG_SOURCE,
            method="LoCC column", retrieved=retrieved))
    for value in row.get("gutenberg_subjects") or []:
        out.append(GenreAssertion(
            value=value, scheme="gutenberg_subject", source=_PG_SOURCE,
            method="Subjects column (LCSH)", retrieved=retrieved))
    for value in row.get("leiden_subjects") or []:
        out.append(GenreAssertion(
            value=value, scheme="leiden_dc_subject", source=_LEIDEN_SOURCE,
            method="dc:subject", retrieved=retrieved))
    if (row.get("genre") or "").strip():
        out.append(GenreAssertion(
            value=row["genre"].strip(), scheme="dbnl_genre", source=_TITELS_SOURCE,
            method="genre column, verbatim", retrieved=retrieved))
    return out


def _cell(value: Any) -> str:
    """A catalogue cell as text. Pandas hands back float NaN for empties."""
    if value is None or isinstance(value, float):
        return ""
    return str(value)


def parse_kb_goo(value: Any) -> list[str]:
    """Split a Trefwoord GOO cell into individual headings."""
    value = _cell(value)
    if not value:
        return []
    return sorted({p.strip() for p in _GOO_SPLIT.split(value) if p.strip()})


def parse_kb_basisclassificatie(value: Any) -> list[str]:
    """Pull the Basisclassificatie codes out of a run-together cell.

    The cell concatenates codes without a separator and sometimes trails a
    stray label ("... 49.40 lichaamsverzorging (huishoudkunde) Gegevens
    origineel"), so codes are matched rather than split.
    """
    value = _cell(value)
    if not value:
        return []
    return sorted({
        _BC_TRAILING.sub("", m.group(0).strip()).strip()
        for m in _BC_CODE.finditer(value)
    })


def parse_leiden_dc(xml: str) -> dict[str, Any]:
    """Subjects, title and dates out of a Leiden UB OAI-DC record."""
    def tags(name: str) -> list[str]:
        return [t.strip() for t in re.findall(rf"<dc:{name}>(.*?)</dc:{name}>", xml, re.S) if t.strip()]
    descriptions = tags("description")
    # dc:date is frequently the digitisation year; a real year often survives
    # only in a description like "Afl. 1: 1894."
    in_desc = sorted({m.group(0) for d in descriptions for m in _YEAR.finditer(d)})
    return {
        "title": (tags("title") or [""])[0],
        "subjects": sorted(set(tags("subject"))),
        "dc_dates": sorted(set(tags("date"))),
        "years_in_description": in_desc,
        "identifiers": tags("identifier"),
    }


def read_titels(path: str | Path) -> list[dict[str, str]]:
    """Rows of dbnl_titels_pd.csv, skipping its leading ``sep=|`` line."""
    with Path(path).open(encoding="utf-8", errors="replace") as handle:
        handle.readline()
        return list(csv.DictReader(handle, delimiter="|"))


def build_records(
    rows: Iterable[dict[str, str]],
    *,
    ggc_lookup,
    regime_lookup,
    have_xml: set[str],
    retrieved: str | None = None,
) -> list[dict[str, Any]]:
    """One record per title row: identity, year, text availability, assertions.

    `ggc_lookup` and `regime_lookup` are callables so this stays testable and so
    GGC is only ever read from cache here — nothing in this module queries the
    catalogue.
    """
    retrieved = retrieved or date.today().isoformat()
    records: list[dict[str, Any]] = []
    for row in rows:
        ti_id = (row.get("ti_id") or "").strip()
        if not ti_id:
            continue
        ggc, query = ggc_lookup(row)
        regime = regime_lookup(row)
        claims = assertions_for(row, ggc=ggc, ggc_query=query,
                                text_regime=regime, retrieved=retrieved)
        records.append({
            # Every source in this file uses work_id/id_scheme as the key, so
            # that records from different catalogues can sit side by side.
            # ti_id is kept as well because it is the native DBNL identifier.
            "work_id": ti_id,
            "id_scheme": "dbnl_ti_id",
            "ti_id": ti_id,
            "titel": (row.get("titel") or "").strip(),
            "year": _year(row),
            "year_provenance": f"{_TITELS_SOURCE}:_jaar|jaar",
            "has_xml": work_stem(ti_id) in have_xml,
            "ggc_records": (ggc or {}).get("records"),
            "genre_assertions": [asdict(c) for c in claims],
            "schemes": sorted({c.scheme for c in claims}),
        })
    return records
