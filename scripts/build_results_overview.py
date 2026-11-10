"""Aggregate every annotation source into small tables for the results dashboard.

Read-only. Writes two CSVs to experiments/results_overview/:

  cells.csv  source, genre, outcome, decade, n
             outcome = frame name, NONE (no frame), DROPPED (Step A or sieve),
             ERROR, or PENDING (harvested weak-regime rows not yet annotated)
  works.csv  work, wid, title, year, genre, source, rows, frames, pending, fb (frames by type)
  index.html self-contained page (template: results_overview.template.html)

Real frame = not error, not dropped, step_b.selected_frame not in (None, NONE),
the same rule as the per-run reports. Year: provenance.date where present,
else the work's year from the genre records (joined on work stem).
Genre: work-level `reporting_genre` (text regime, filled in from catalogue data;
trifecta_annotation/catalogue_genre.py), not the stored row label. On the page,
HISTORY / RELIGION / LANGUAGE fold into OTHER_NONFICTION (8 colours + grey Unknown).

    uv run python scripts/build_results_overview.py
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from data_io import resolve

from trifecta_annotation.corpus_genre_join import load_genre_records
from trifecta_annotation.dbnl_genre import work_stem
from trifecta_annotation.catalogue_genre import reporting_genre

TEMPLATE = Path(__file__).with_name("results_overview.template.html")
GENRE_ORDER = ["RECIPE_PRACTICE", "MEDICAL", "LITERARY", "TRAVEL", "ADMIN_TRADE", "SCIENTIFIC", "PERIODICAL",
               "OTHER_NONFICTION", "UNKNOWN"]
PAGE_FOLD = {"HISTORY": "OTHER_NONFICTION", "RELIGION": "OTHER_NONFICTION", "LANGUAGE": "OTHER_NONFICTION"}
OUT = Path("/Volumes/Extreme SSD/scratch/trifecta/experiments/results_overview")
SOURCES = {  # logical name -> label shown on the page
    "trifecta_annotations": "Curated corpus",
    "colonial_annotations": None,      # mixed batch: labelled per provenance.corpus below
    "handdownload_annotations": None,
    "dbnl_sweep_annotations": "DBNL sweep",
    "entry_scope_annotations": "Entry scope",
    "weak_regime_verb_annotations": "Weak-regime verb",
}
# "colonial" is a misnomer: the colonial_* and handdownload_* files are the early hand-picked
# batch (extra DBNL works, Leiden colonial books, KB cookbooks, Google Books, two 1513/14 editions).
# The per-origin corpus stays visible in works.csv / the works table via the title.
CORPUS_LABELS = {c: "Initial exploration" for c in (
    "dbnl_new_2026", "dbnl_hand_download_2026", "colonial_books_2026", "kb_cookbooks_2026", "google_books_2026")}
LABEL_ORDER = ["Curated corpus", "Initial exploration", "DBNL sweep", "Entry scope", "Weak-regime verb"]


def _jsonl(path: Path):
    for line in path.open(encoding="utf-8"):
        if line.strip() and not line.startswith("---"):
            yield json.loads(line)


def _year(value) -> int | None:
    m = re.search(r"\b(1[2-9]\d\d)\b", str(value or ""))
    return int(m.group(1)) if m else None


def main() -> None:
    work_year: dict[str, int] = {}
    for rec in load_genre_records():
        y = _year(rec.get("year"))
        if y and rec.get("ti_id"):
            work_year.setdefault(work_stem(rec["ti_id"]), y)

    cells: Counter = Counter()
    works: dict[tuple[str, str], dict] = {}
    dated = defaultdict(lambda: [0, 0])

    def add(label, src_path, title, genre, year, outcome):
        decade = f"{year // 10 * 10}s" if year else "undated"
        cells[(label, genre, outcome, decade)] += 1
        w = works.setdefault((label, src_path), {"work": src_path, "wid": work_stem(src_path), "title": title,
                                                 "year": year or "", "genre": genre, "source": label,
                                                 "rows": 0, "frames": 0, "pending": 0, "fb": {}})
        if outcome == "PENDING":
            w["pending"] += 1
        else:
            w["rows"] += 1
            if outcome not in ("NONE", "DROPPED", "ERROR"):
                w["frames"] += 1
                w["fb"][outcome] = w["fb"].get(outcome, 0) + 1
        dated[label][0] += 1
        dated[label][1] += year is not None

    # Genre = the CURRENT work-level inference, not the stored provenance.text_regime:
    # 2,274 curated rows still carry the UNKNOWN stamped before the per-work overrides
    # existed (audit 2026-11-09), and a few sweep works have mixed row-level labels.
    regime_cache: dict[tuple, str] = {}

    def genre_of(corpus, title, src_path):
        key = (corpus, work_stem(src_path or ""))
        if key not in regime_cache:
            g = reporting_genre(corpus=corpus, title=title, source_path=src_path)[0]
            regime_cache[key] = PAGE_FOLD.get(g, g)
        return regime_cache[key]

    def year_for(pv_date, src_path):
        return _year(pv_date) or work_year.get(work_stem(src_path or ""))

    current_scope = {r["record_id"] for r in _jsonl(Path(resolve("entry_scope_kwic_inputs")))}
    annotated_weak: set[str] = set()
    for logical, label in SOURCES.items():
        path = Path(resolve(logical))
        if not path.exists():
            continue
        for r in _jsonl(path):
            pv = r["provenance"]
            if logical == "entry_scope_annotations" and pv["record_id"] not in current_scope:
                continue
            if logical == "weak_regime_verb_annotations":
                annotated_weak.add(pv["record_id"])
            sp = pv.get("source_path") or ""
            genre = genre_of(pv.get("corpus"), pv.get("title"), sp)
            frame = (r.get("step_b") or {}).get("selected_frame")
            outcome = ("ERROR" if r.get("error") else "DROPPED" if r.get("dropped")
                       else frame if frame not in (None, "NONE") else "NONE")
            src_label = label or CORPUS_LABELS.get(pv.get("corpus"), pv.get("corpus") or logical)
            add(src_label, sp, pv.get("title") or sp, genre, year_for(pv.get("date"), sp), outcome)

    weak_inputs = Path(resolve("weak_regime_verb_kwic_inputs"))
    if weak_inputs.exists():
        for r in _jsonl(weak_inputs):
            if r["record_id"] not in annotated_weak:
                sp = r["source_path"]
                add(SOURCES["weak_regime_verb_annotations"], sp, r.get("title") or sp,
                    genre_of(r.get("corpus"), r.get("title"), sp), year_for(r.get("date"), sp), "PENDING")

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "cells.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "genre", "outcome", "decade", "n"])
        for key, n in sorted(cells.items()):
            w.writerow([*key, n])
    with (OUT / "works.csv").open("w", newline="", encoding="utf-8") as fh:
        rows = sorted(works.values(), key=lambda x: -(x["frames"] + x["pending"]))
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    real = sum(n for (s, g, o, d), n in cells.items() if o not in ("NONE", "DROPPED", "ERROR", "PENDING"))
    annotated = sum(n for (s, g, o, d), n in cells.items() if o != "PENDING")
    pending = sum(n for (s, g, o, d), n in cells.items() if o == "PENDING")
    print(f"annotated rows {annotated}, real frames {real}, pending {pending}; "
          f"{len(cells)} cells, {len(works)} source-work rows")
    by_frame: Counter = Counter()
    for (s, g, o, d), n in cells.items():
        if o not in ("NONE", "DROPPED", "ERROR", "PENDING"):
            by_frame[o] += n
    print("frames:", dict(by_frame.most_common()))
    for label, (n, d) in dated.items():
        print(f"  {label}: {n} rows, {d / n:.0%} dated")

    genres_present = {g for (s, g, o, d) in cells}
    genres = [g for g in GENRE_ORDER if g in genres_present] + sorted(genres_present - set(GENRE_ORDER))
    payload = {
        "built": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sources": [l for l in LABEL_ORDER if any(s == l for (s, *_) in cells)]
                   + sorted({s for (s, *_) in cells} - set(LABEL_ORDER)),
        "genres": genres,
        "frames": [f for f, _ in by_frame.most_common()],
        "cells": [[*k, n] for k, n in sorted(cells.items())],
        "works": rows,
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", blob)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print(f"wrote {OUT}/index.html ({len(html) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
