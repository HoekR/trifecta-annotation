"""Reporting genre: the text regime, filled in from catalogue data where it is UNKNOWN.

`infer_text_regime` (per-work overrides, corpus defaults, title keywords) leaves
most of the DBNL sweep as UNKNOWN. This module fills that gap for *reporting*
(overview, exports) from the local `dbnl_work_genre` sidecar, which already
holds GGC claims from the cache (`scripts/fetch_ggc_subjects.py`) and the DBNL
genre column. It never queries a catalogue and is **not** used by the
annotation pipeline: changing a row's regime there would change its prompts.

Order, first hit wins (each answer carries its source):

1. `infer_text_regime` when it is not UNKNOWN (curated overrides beat catalogues)
2. periodical: title words (jaargang, tijdschrift, almanak...); a jaargang mixes
   genres, so its format is the honest label (see `dbnl_genre` "Known gap")
3. DBNL genre poezie / drama / jeugdliteratuur -> LITERARY. DBNL classifies
   *this* work; GGC claims come from a title search that can hit another book,
   which filed children's books under HISTORY or ADMIN_TRADE
4. GGC Basisclassificatie (Rik's preferred scheme), by code prefix
5. DBNL proza / sec - letterkunde -> LITERARY, sec - taalkunde -> LANGUAGE
   (after GGC: DBNL "proza" also holds travel accounts and histories)
6. GGC subject headings, by keyword (noisiest, last)
   `non-fictie` is too coarse and stays UNKNOWN

Besides the `TextRegime` values this adds display-only genres the regime enum
does not have: PERIODICAL, RELIGION, HISTORY, LANGUAGE, OTHER_NONFICTION.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from data_io import resolve

from trifecta_annotation.dbnl_genre import work_stem
from trifecta_annotation.text_regime import infer_text_regime

EXTRA_GENRES = ("PERIODICAL", "RELIGION", "HISTORY", "LANGUAGE", "OTHER_NONFICTION")

_PERIODICAL = re.compile(r"\b(jaargang|jaarg\.|tijdschrift\w*|almana[ck]\w*|jaarboek\w*|maandschrift\w*|"
                         r"weekblad\w*|letteroefening\w*|magazijn)\b", re.I)

# Basisclassificatie main class (first two digits) or full code -> genre.
_BASIS_CODE = {"01.41": "PERIODICAL", "18.10": "LANGUAGE"}
_BASIS_CLASS = {
    "49": "RECIPE_PRACTICE",
    "44": "MEDICAL",
    "74": "TRAVEL",
    "55": "ADMIN_TRADE", "83": "ADMIN_TRADE", "85": "ADMIN_TRADE", "86": "ADMIN_TRADE", "89": "ADMIN_TRADE",
    **{c: "SCIENTIFIC" for c in ("30", "31", "33", "35", "38", "42", "43", "46", "48")},
    "15": "HISTORY",
    "11": "RELIGION",
    "17": "LANGUAGE",
    "18": "LITERARY", "24": "LITERARY",
}
# When a work has several codes, the food-relevant answer wins.
_PRIORITY = ("RECIPE_PRACTICE", "MEDICAL", "TRAVEL", "ADMIN_TRADE", "SCIENTIFIC", "PERIODICAL",
             "HISTORY", "RELIGION", "LANGUAGE", "LITERARY", "OTHER_NONFICTION")

_SUBJECT = [  # checked in order
    ("RECIPE_PRACTICE", r"kook|recept|huishoud|voedingsmiddel"),
    ("MEDICAL", r"genees|medisch|medicijn|artsen|apothe|farma|ziekte"),
    ("TRAVEL", r"\breis|geografie|aardrijks|land- en volkenkunde"),
    ("ADMIN_TRADE", r"handel|economie|scheepvaart|\brecht\b|staatkunde|politiek"),
    ("SCIENTIFIC", r"natuurlijke historie|natuurkunde|scheikunde|botan|plantkunde|dierkunde|landbouw"),
    ("RELIGION", r"godsdienst|godgeleerd|bijbel|preken|preek|kerk|theolog|liturg|stichtelijk"),
    ("HISTORY", r"geschiedenis|levensbeschrijving|kroniek|biografie"),
    ("LANGUAGE", r"taalkunde|woordenboek|grammatica|spraakkunst"),
    ("LITERARY", r"kinder|jeugd|prentenboek|strip|gedicht|lied|song|roman|novelle|verhal|proza|dicht|"
                 r"toneel|drama|\bfictie|rijm|emblem|letterkunde|samenspra"),
]
_SUBJECT = [(g, re.compile(p, re.I)) for g, p in _SUBJECT]

_DBNL_FIRST = {"poëzie": "LITERARY", "drama": "LITERARY", "jeugdliteratuur": "LITERARY"}
_DBNL_AFTER_GGC = {"proza": "LITERARY", "sec - letterkunde": "LITERARY", "sec - taalkunde": "LANGUAGE"}


@lru_cache(maxsize=1)
def _sidecar() -> dict[str, dict]:
    out: dict[str, dict] = {}
    path = Path(resolve("dbnl_work_genre"))
    if not path.exists():
        return out
    for line in path.open(encoding="utf-8"):
        if not line.strip() or line.startswith("---"):
            continue
        r = json.loads(line)
        if r.get("id_scheme") == "dbnl_ti_id":
            out.setdefault(work_stem(r["ti_id"]), r)
    return out


def _from_record(r: dict) -> tuple[str, str] | None:
    if _PERIODICAL.search(r.get("titel") or ""):
        return "PERIODICAL", "title"
    by_scheme: dict[str, list[str]] = {}
    for a in r.get("genre_assertions", []):
        by_scheme.setdefault(a["scheme"], []).append(a["value"])
    for v in by_scheme.get("dbnl_genre", []):
        if v in _DBNL_FIRST:
            return _DBNL_FIRST[v], "dbnl_genre"
    hits = []
    for v in by_scheme.get("basisclassificatie", []):
        code = v[:5]
        hits.append(_BASIS_CODE.get(code) or _BASIS_CLASS.get(code[:2]) or "OTHER_NONFICTION")
    if hits:
        return min(hits, key=_PRIORITY.index), "ggc_basisclassificatie"
    for v in by_scheme.get("dbnl_genre", []):
        if v in _DBNL_AFTER_GGC:
            return _DBNL_AFTER_GGC[v], "dbnl_genre"
    subjects = " | ".join(by_scheme.get("ggc_subject", []))
    for genre, rx in _SUBJECT:
        if subjects and rx.search(subjects):
            return genre, "ggc_subject"
    return None


def reporting_genre(*, corpus: str | None, title: str | None, source_path: str | None) -> tuple[str, str]:
    """(genre, where it came from) for one work."""
    regime = infer_text_regime(corpus=corpus, title=title, source_path=source_path).value
    if regime != "UNKNOWN":
        return regime, "text_regime"
    r = _sidecar().get(work_stem(source_path or ""))
    if r:
        hit = _from_record(r)
        if hit:
            return hit
    if _PERIODICAL.search(title or ""):
        return "PERIODICAL", "title"
    return "UNKNOWN", "none"
