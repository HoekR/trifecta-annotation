"""Build the per-work genre sidecar (logical `dbnl_work_genre`).

Reads only local, already-cached material — it **never queries the catalogue**,
since Rik's standing instruction is not to hammer it. GGC coverage grows only as
the cache does (see `scripts/fetch_ggc_subjects.py`).

Three record sources, kept separate by `id_scheme` rather than merged, because
they overlap partially and disagree about genre and about dates:

- `dbnl_ti_id`  — the DBNL PD titles dump, plus TEI availability from the zip
- `kb_row`      — the earlier KB catalogue parse (`kb_titles_parsed`), which has
                  the richest genre data and holds titles the corpus does not
- `leiden_item` — Leiden UB OAI-DC records beside the colonial books

    uv run python scripts/build_dbnl_genre.py --summary
"""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path

from data_io import resolve
from data_io.jsonl_io import save_semi_structured

from trifecta_annotation.dbnl_genre import (
    _cell,
    assertions_for,
    build_records,
    parse_ggc,
    parse_leiden_dc,
    read_titels,
    xml_stems,
)
from trifecta_annotation.text_regime import _WORK_REGIME

# GGC is cached per *queried title*, because the query is by title, not by id.
_SPLIT = re.compile(r"[,.]| of | ofte | Deel | Jaargang ")


def short_title(titel: str) -> str:
    """The form actually sent to GGC: a long DBNL title returns 0 records."""
    return _SPLIT.split(titel or "")[0].strip()


def _cache_slug(titel: str) -> str:
    return hashlib.sha1((titel or "").encode("utf-8")).hexdigest()[:16]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true", help="Print coverage counts")
    args = parser.parse_args()

    rows = read_titels(resolve("dbnl_titels"))
    have_xml = xml_stems(resolve("dbnl_xml"))
    cache_dir = Path(resolve("ggc_cache"))

    def ggc_lookup(row):
        path = cache_dir / (_cache_slug(row.get("titel", "")) + ".xml")
        if not path.exists():
            return None, None
        xml = path.read_text(encoding="utf-8", errors="replace")
        return parse_ggc(xml), short_title(row.get("titel", ""))

    def regime_lookup(row):
        # _WORK_REGIME is keyed by DBNL text id including the volume suffix,
        # while the titles dump carries the work-level ti_id, so try both.
        ti = (row.get("ti_id") or "").strip()
        for key in (ti, f"_{ti}", f"{ti}_01", f"_{ti}_01"):
            if key in _WORK_REGIME:
                return _WORK_REGIME[key].value
        return None

    records = build_records(rows, ggc_lookup=ggc_lookup, regime_lookup=regime_lookup,
                            have_xml=have_xml)
    records.extend(_kb_records())
    records.extend(_leiden_records())
    records.extend(_gutenberg_records())
    out = save_semi_structured(
        records,
        logical_name="dbnl_work_genre",
        parent_sources=["dbnl_titels", "dbnl_xml", "ggc_cache"],
        description="Per-work DBNL genre assertions with provenance per claim",
        script="scripts/build_dbnl_genre.py",
    )
    print(f"wrote {len(records)} records -> {out}")

    if args.summary:
        import collections
        scheme = collections.Counter()
        for rec in records:
            for s in rec["schemes"]:
                scheme[s] += 1
        print("\nworks carrying each scheme:")
        for name, n in scheme.most_common():
            print(f"  {name:20s} {n}")
        dated = [r for r in records if r["year"] and 1500 <= r["year"] < 1900]
        print(f"\nworks dated 1500-1899: {len(dated)}"
              f"  with TEI text: {sum(1 for r in dated if r['has_xml'])}")
        print(f"works with a cached GGC response: "
              f"{sum(1 for r in records if r['ggc_records'] is not None)}")


def _kb_records() -> list[dict]:
    """Records from the earlier KB parse.

    The file is a messy export: a quoting bug pulled ~90 data fragments into the
    header row, so only the named columns are trusted and the rest ignored.
    `Jaar` is kept as-is and flagged, because for this source it is often the
    digitisation year rather than the work's.
    """
    import pandas as pd

    frame = pd.read_csv(resolve("kb_titles_parsed"), sep="\t", dtype=str, low_memory=False)
    out: list[dict] = []
    for i, row in enumerate(frame.to_dict(orient="records")):
        titel = _cell(row.get("Titel")).strip()
        if not titel:
            continue
        year = re.search(r"1[5-9]\d\d", _cell(row.get("Jaar")))
        out.append({
            "work_id": f"kb:{i}",
            "id_scheme": "kb_row",
            "titel": titel,
            "year": int(year.group(0)) if year else None,
            "year_provenance": "kb_titles_parsed.csv:Jaar (may be the digitisation year)",
            "has_xml": False,
            "ggc_records": None,
            "auteur": _cell(row.get("Auteur")).strip() or None,
            "genre_assertions": [
                asdict(c) for c in assertions_for(
                    {"titel": titel,
                     "kb_goo": row.get("Trefwoord GOO"),
                     "kb_basisclassificatie": row.get("Basisclassificatie")},
                    ggc=None, ggc_query=None, text_regime=None,
                    retrieved=date.today().isoformat(),
                    title_source="kb_titles_parsed.csv")
            ],
        })
    for rec in out:
        rec["schemes"] = sorted({c["scheme"] for c in rec["genre_assertions"]})
    return out


def _gutenberg_records() -> list[dict]:
    """Dutch Project Gutenberg records.

    Restricted to `Language == "nl"` on purpose: the full feed is 79,634 records
    and the other 78,520 would swamp the sidecar without being candidates. Note
    `Issued` is the date Gutenberg posted the text, never the work's own year,
    so no year is claimed here — it has to come from a catalogue.
    """
    import csv as _csv

    out: list[dict] = []
    with Path(resolve("gutenberg_catalog")).open(encoding="utf-8", errors="replace") as fh:
        for row in _csv.DictReader(fh):
            if (row.get("Language") or "").strip() != "nl":
                continue
            title = " / ".join(t.strip() for t in (row.get("Title") or "").splitlines() if t.strip())
            locc = [c.strip() for c in (row.get("LoCC") or "").split(";") if c.strip()]
            subs = [s.strip() for s in (row.get("Subjects") or "").split(";") if s.strip()]
            out.append({
                "work_id": f"gutenberg:{row['Text#']}",
                "id_scheme": "gutenberg_id",
                "titel": title,
                "year": None,
                "year_provenance": "none — PG 'Issued' is the posting date, not the work's year",
                "has_xml": False,
                "has_ocr_text": True,
                "ggc_records": None,
                "pg_issued": (row.get("Issued") or "").strip(),
                "genre_assertions": [
                    asdict(c) for c in assertions_for(
                        {"titel": title, "gutenberg_locc": locc, "gutenberg_subjects": subs},
                        ggc=None, ggc_query=None, text_regime=None,
                        retrieved=date.today().isoformat(),
                        title_source="pg_catalog.csv")
                ],
            })
    for rec in out:
        rec["schemes"] = sorted({c["scheme"] for c in rec["genre_assertions"]})
    return out


def _leiden_records() -> list[dict]:
    """Records from the OAI-DC files shipped beside the Leiden colonial books."""
    out: list[dict] = []
    book_dir = Path(resolve("colonial_books"))
    for path in sorted(book_dir.glob("*.xml")):
        if path.name.startswith("._"):
            continue
        meta = parse_leiden_dc(path.read_text(encoding="utf-8", errors="replace"))
        item = next((i for i in meta["identifiers"] if i.startswith("item:")), path.stem)
        # Prefer a year found in a description over dc:date, which is usually
        # the year of digitisation for these records.
        year = meta["years_in_description"] or [y for y in meta["dc_dates"] if re.fullmatch(r"1[5-9]\d\d", y)]
        # OCR text is what makes a book processable; the PDFs alone are not.
        stem = path.stem.replace("DC Record", "").replace("_DC Record", "").strip()
        has_text = any(book_dir.glob(f"{stem.split('_')[0]}*.txt")) or any(
            book_dir.glob(f"*{item.split(':')[-1]}*.txt"))
        out.append({
            "work_id": f"leiden:{item}",
            "id_scheme": "leiden_item",
            "titel": meta["title"] or stem,
            "year": int(year[0]) if year else None,
            "year_provenance": ("dc:description" if meta["years_in_description"]
                                else "dc:date (may be the digitisation year)"),
            "has_xml": False,
            "has_ocr_text": has_text,
            "ggc_records": None,
            "genre_assertions": [
                asdict(c) for c in assertions_for(
                    {"titel": meta["title"], "leiden_subjects": meta["subjects"]},
                    ggc=None, ggc_query=None, text_regime=None,
                    retrieved=date.today().isoformat(),
                    title_source="Leiden UB OAI-DC record (handle.net/1887.1)")
            ],
        })
    for rec in out:
        rec["schemes"] = sorted({c["scheme"] for c in rec["genre_assertions"]})
    return out


if __name__ == "__main__":
    main()
