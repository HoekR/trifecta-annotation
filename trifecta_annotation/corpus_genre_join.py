"""Join corpus source files to `dbnl_work_genre` for a year and a category.

`corpus_overview.py` groups `food_snippets` by `filename` (a DBNL XML name like
`_pha001phar05_01.xml`); this module resolves each filename's year and a single
display category out of the sidecar built by `scripts/build_dbnl_genre.py`.

Two sources, because one alone does not cover the corpus:

- **DBNL (`dbnl_ti_id` records)** — the primary source. `_jaar`/`jaar` is the
  catalogued year of *that edition*, joined by `work_stem`.
- **KB (`kb_row` records), by title** — fills gaps DBNL leaves. Restricted to
  years below 1900: KB's `Jaar` is the *catalogue record's* year, and 97% of KB
  rows are dated 1900+ because they are modern reprints/digitisations, not the
  underlying work's own era (the Digby remedy book's KB row is dated `[2016]`
  despite the work being from 1680). Below 1900 that risk mostly disappears, but
  it is still an edition year — e.g. a 19th-century edition of a 15th-century
  manuscript collection is dated by its own printing, not by the manuscript.
  Where a title has several KB rows (reprints — e.g. `Aaltje` genuinely
  evolved across editions from 1803 to 1891), the earliest is kept. This is
  deliberately not an attempt to identify "the" edition: KB gives only
  catalogue metadata, never the edition's text, so there is nothing here to
  select a specific printing *for* — the date is used only to place the work
  in time. Chasing which edition is "true" would be solving a problem this
  data cannot answer; the earliest known date is the right anchor for that
  weaker question.

Category prefers **Basisclassificatie** (Rik, 22 Oct 2026 — "I like
`49.00 huishoudkunde` best"): stable numeric codes, a real taxonomy, unlike the
free-text subject headings. Preference order, first match wins:
`kb_basisclassificatie` > `basisclassificatie` (GGC) > `text_regime` >
`ggc_subject` > `title_screen` > `dbnl_genre`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

from data_io import resolve

from trifecta_annotation.dbnl_genre import work_stem

_CATEGORY_SCHEME_ORDER = (
    "kb_basisclassificatie",
    "basisclassificatie",
    "text_regime",
    "ggc_subject",
    "title_screen",
    "dbnl_genre",
)


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (title or "").lower()).strip()[:40]


class GenreLookup(NamedTuple):
    year: int | None
    year_source: str
    category: str | None
    category_scheme: str | None


_EMPTY = GenreLookup(year=None, year_source="", category=None, category_scheme=None)


def load_genre_records(path: str | Path | None = None) -> list[dict]:
    path = Path(path or resolve("dbnl_work_genre"))
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _best_category(assertions: list[dict]) -> tuple[str | None, str | None]:
    by_scheme = {a["scheme"]: a["value"] for a in reversed(assertions)}
    for scheme in _CATEGORY_SCHEME_ORDER:
        if scheme in by_scheme:
            return by_scheme[scheme], scheme
    return None, None


def build_genre_index(records: list[dict] | None = None) -> dict[str, GenreLookup]:
    """filename work-stem -> best (year, category) available for it."""
    records = records if records is not None else load_genre_records()

    by_stem: dict[str, dict] = {
        work_stem(r["work_id"]): r for r in records if r["id_scheme"] == "dbnl_ti_id"
    }
    # Earliest in-period KB row per normalised title, for the title fallback.
    kb_by_title: dict[str, dict] = {}
    for r in records:
        if r["id_scheme"] != "kb_row" or not r["year"] or r["year"] >= 1900:
            continue
        key = _title_key(r["titel"])
        if not key:
            continue
        prior = kb_by_title.get(key)
        if prior is None or r["year"] < prior["year"]:
            kb_by_title[key] = r

    index: dict[str, GenreLookup] = {}
    for stem, record in by_stem.items():
        year = record["year"]
        year_source = record["year_provenance"] if year else ""
        category, scheme = _best_category(record["genre_assertions"])
        if year is None:
            fallback = kb_by_title.get(_title_key(record["titel"]))
            if fallback is not None:
                year = fallback["year"]
                year_source = "kb_titles_parsed.csv:Jaar (title match, earliest edition)"
        index[stem] = GenreLookup(year=year, year_source=year_source,
                                  category=category, category_scheme=scheme)
    return index


def lookup_for_filename(index: dict[str, GenreLookup], filename: str) -> GenreLookup:
    stem = work_stem(Path(filename).stem)
    return index.get(stem, _EMPTY)
