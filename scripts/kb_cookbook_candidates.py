"""Candidate list of KB cookbooks to download by hand (Indies names, N3).

Source: the KB culinary bibliography (`kb_titles_parsed`, a scrape of the KB
cookbook collection catalogue) via its rows in `dbnl_work_genre`. Writes
`<acquisitions>/kb_cookbook_candidates_<from>_<to>.xlsx` for Rik to tick
`decision` in. Read-only on everything else; no network.

The raw catalogue file is a messy scrape: records run into each other, and a
digitised copy is a *separate* record dated by its digitisation year ([2015],
"Bibliotheca Gastronomica"). So digital-copy links (KB resolver MMKB = Delpher
book, or Google Books KBNL) are attached to the record that precedes them in
the text and matched to candidates by **title only**: the copy may be another
edition. MMKB ids also mark what we already have (our KB files are named by it).

    uv run python scripts/kb_cookbook_candidates.py [--from 1889 --to 1949]
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import urllib.parse
from pathlib import Path

import pandas as pd
from data_io import resolve

from scripts.build_colonial_kwic import GOOGLE_BOOKS_2026_11, KB_COOKBOOKS_2026

OUT_DIR = Path("/Volumes/Extreme SSD/scratch/trifecta/colonial_ocr/acquisitions")
INDIES = re.compile(r"indi[së]|oost-?ind|rijsttafel|rystafel|java|indonesi|sambal|tropen|tropisch|batavia|"
                    r"soerabaja|samarang|semarang|chinee|maleis|koloni|suriname|cura[cç]ao", re.I)
LINK = re.compile(r'(?:https?://)?(?:resolver\.kb\.nl/resolve\?urn=(?:MMKB[0-9A-Z]*:\d+|dts:[^\s\t"]+)'
                  r'|books\.google\.com/books\?vid=KBNL:?\s?[A-Z0-9]+)')
RECORD = re.compile(r'(?:^|[\s"])(\d{1,4})\t([^\t\n]{3,})\t', re.M)
COLS = ["indies_title", "already_have", "year", "title", "author", "basisclassificatie",
        "delpher_search", "digital_copy", "decision", "note"]


def _key(title: str) -> str:
    return re.sub(r"[^a-z]", "", (title or "").lower().split(" / ")[0])[:40]


def digital_copies() -> dict[str, str]:
    """title key -> first digital-copy URL found for a record with that title."""
    text = Path(resolve("kb_titles_parsed")).read_text(encoding="utf-8", errors="replace")
    starts = [(m.start(), m.group(2)) for m in RECORD.finditer(text)]
    pos = [s for s, _ in starts]
    out: dict[str, str] = {}
    for m in LINK.finditer(text):
        i = bisect.bisect_right(pos, m.start()) - 1
        if i >= 0:
            url = m.group(0).replace(" ", "")
            out.setdefault(_key(starts[i][1]), url if url.startswith("http") else "https://" + url)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="y0", type=int, default=1889)
    ap.add_argument("--to", dest="y1", type=int, default=1949)
    a = ap.parse_args()

    have_titles = {_key(t) for t, _ in [*KB_COOKBOOKS_2026.values(), *GOOGLE_BOOKS_2026_11.values()]}
    have_mmkb = {re.sub(r"_pdf.*", "", f).lower() for f in KB_COOKBOOKS_2026}
    copies = digital_copies()
    rows = []
    for line in open(resolve("dbnl_work_genre"), encoding="utf-8"):
        r = json.loads(line)
        if r.get("id_scheme") != "kb_row" or not r.get("year") or not a.y0 <= r["year"] <= a.y1:
            continue
        title = r["titel"].split(" / ")[0].strip()
        url = copies.get(_key(title), "")
        mm = re.search(r"urn=(MMKB[0-9A-Z]*):(\d+)", url)
        rows.append({
            "indies_title": bool(INDIES.search(r["titel"])),
            "already_have": _key(title) in have_titles or bool(mm and f"{mm[1].lower()}_{mm[2]}" in have_mmkb),
            "year": r["year"], "title": title, "author": (r.get("auteur") or "")[:80],
            "basisclassificatie": "; ".join(x["value"] for x in r["genre_assertions"]
                                            if x["scheme"] == "kb_basisclassificatie"),
            "delpher_search": f"https://www.delpher.nl/nl/boeken/results?query={urllib.parse.quote(title[:80])}&coll=boeken",
            "digital_copy": url, "decision": "", "note": "",
        })
    df = (pd.DataFrame(rows).drop_duplicates(["title", "year"])
          .sort_values(["indies_title", "year"], ascending=[False, True]))
    path = OUT_DIR / f"kb_cookbook_candidates_{a.y0}_{a.y1}.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        df[COLS].to_excel(xw, index=False, sheet_name="candidates")
        ws = xw.sheets["candidates"]
        for i, row in enumerate(df.itertuples(), start=2):  # URLs stay as cell text; hyperlink on top
            for col, url in ((7, row.delpher_search), (8, row.digital_copy)):
                if url:
                    ws.cell(row=i, column=col).hyperlink = url
                    ws.cell(row=i, column=col).style = "Hyperlink"
        for col, w in zip("ABCDEFGHIJ", [8, 8, 6, 70, 35, 35, 20, 20, 10, 30]):
            ws.column_dimensions[col].width = w
        ws.freeze_panes, ws.auto_filter.ref = "A2", ws.dimensions
        rm = xw.book.create_sheet("read me")
        for n, text in enumerate([
            f"KB culinary bibliography (kb_titles_parsed), {a.y0}-{a.y1} by catalogue year (may be a reprint year).",
            "indies_title: rough title-word flag (Indisch, rijsttafel, Java, tropen ...); false hits possible.",
            "already_have: matched on title or on the MMKB id of our KB cookbook files.",
            "digital_copy: KB resolver (MMKB = Delpher book) or Google Books, matched by TITLE: may be another edition.",
            "delpher_search: title search, for titles without a digital_copy.",
            "decision / note: yours. Downloaded cookbooks -> acquisitions/delpher_2026_11/ (+ year); Claude registers them.",
            "Rebuild: uv run python scripts/kb_cookbook_candidates.py (overwrites this file: copy your decisions first).",
        ], 1):
            rm.cell(row=n, column=1, value=text)
        rm.column_dimensions["A"].width = 110
    print(f"{len(df)} candidates, {df.indies_title.sum()} Indies titles, "
          f"{(df.digital_copy != '').sum()} with a digital copy, {df.already_have.sum()} already have -> {path}")


if __name__ == "__main__":
    main()
