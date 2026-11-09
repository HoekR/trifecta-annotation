"""Export every frame row that mentions a kg_mockup commodity, as FrameNetRecord JSONL.

One source for kg_mockup, all genres and all annotation sources together
(cookbooks, herbals, novels, periodicals, travel accounts...): the frame
(COOKING_CREATION / INGESTION / CURE / PRESERVING) is the context of each
mention, and genre / source_label are attributes, not separate sources.

Reads the hand-edited crosswalk `crosswalks/kg_mockup_commodities.xlsx`
(sheet `decisions`, rows with decision == "y") and matches on the vocabulary
Pref_label, not vocab_id: annotations keep only the word, which maps to a
label, and duplicate-label vocabulary entries are indistinguishable downstream.

One record per (work, context, commodity) with a real frame. Fields beyond
FrameNetRecord's own are optional extras kg_mockup accepts:
  influence_from / influence_to  edition year .. edition year + 20 (Rik's window)
  source_work, work_id, source_label, genre, target_word, record_id

Year = provenance.date, else the work's year from the genre records (the
edition year; no first-edition data, so first_edition_year is left unset).
Rows with no year are dropped and counted. A second file, <out>_works.jsonl,
lists every annotated work with a year (commodity or not): the coverage
kg_mockup shows so that absence of evidence reads as absence of material. kg_mockup assumes no relation
between its sources: this is a side-by-side source keyed on commodity + year.

    uv run python scripts/export_kg_mockup_frames.py [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from data_io import resolve
from openpyxl import load_workbook

from trifecta_annotation.corpus_genre_join import load_genre_records
from trifecta_annotation.dbnl_genre import work_stem
from trifecta_annotation.text_regime import infer_text_regime
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

ROOT = Path(__file__).resolve().parents[1]
CROSSWALK = ROOT / "crosswalks" / "kg_mockup_commodities.xlsx"
DEFAULT_OUT = Path.home() / "develop" / "kg_mockup" / "data" / "dbnl_food_frames.jsonl"
SOURCE_TYPE = "DBNL_FOOD_FRAMES"
INFLUENCE_YEARS = 20
SOURCES = {  # logical -> label (None: the early hand-picked batch)
    "trifecta_annotations": "Curated corpus",
    "colonial_annotations": "Initial exploration",
    "handdownload_annotations": "Initial exploration",
    "dbnl_sweep_annotations": "DBNL sweep",
    "entry_scope_annotations": "Entry scope",
    "weak_regime_verb_annotations": "Weak-regime verb",
}


def _jsonl(path: Path):
    for line in path.open(encoding="utf-8"):
        if line.strip() and not line.startswith("---"):
            yield json.loads(line)


def _year(value) -> int | None:
    m = re.search(r"\b(1[2-9]\d\d)\b", str(value or ""))
    return int(m.group(1)) if m else None


def load_crosswalk() -> dict[str, set[str]]:
    """pref_label -> commodity_ids, for rows decided 'y'."""
    ws = load_workbook(CROSSWALK, read_only=True)["decisions"]
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip() for h in next(rows)]
    out: dict[str, set[str]] = {}
    for values in rows:
        r = dict(zip(header, values))
        if str(r.get("decision") or "").strip().lower() != "y":
            continue
        label = str(r.get("pref_label") or "").strip().lower()
        cid = str(r.get("commodity_id") or "").strip().upper()
        if label and cid:
            out.setdefault(label, set()).add(cid)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    crosswalk = load_crosswalk()
    canonical = alt_label_index(load_food_terms())
    work_year: dict[str, int] = {}
    for rec in load_genre_records():
        y = _year(rec.get("year"))
        if y and rec.get("ti_id"):
            work_year.setdefault(work_stem(rec["ti_id"]), y)
    current_scope = {r["record_id"] for r in _jsonl(Path(resolve("entry_scope_kwic_inputs")))}

    seen: set[tuple] = set()
    stats: Counter = Counter()
    records: list[dict] = []
    # Coverage: every annotated work with a year, commodity or not, so kg_mockup can
    # show where material exists (an empty spot without a work there means "not searched").
    coverage: dict[str, dict] = {}
    for logical, label in SOURCES.items():
        path = Path(resolve(logical))
        if not path.exists():
            continue
        for r in _jsonl(path):
            pv = r["provenance"]
            if logical == "entry_scope_annotations" and pv["record_id"] not in current_scope:
                continue
            frame = (r.get("step_b") or {}).get("selected_frame")
            sp_c = pv.get("source_path") or ""
            year_c = _year(pv.get("date")) or work_year.get(work_stem(sp_c))
            if year_c is not None and not r.get("error"):
                w = coverage.setdefault(work_stem(sp_c), {
                    "work_id": sp_c, "year": year_c, "source_work": pv.get("title") or sp_c,
                    "genre": infer_text_regime(corpus=pv.get("corpus"), title=pv.get("title"), source_path=sp_c).value,
                    "rows": 0, "frames": 0})
                w["rows"] += 1
                w["frames"] += not r.get("dropped") and frame not in (None, "NONE")
            if r.get("error") or r.get("dropped") or frame in (None, "NONE"):
                continue
            word = (pv.get("target_word") or "").strip().lower()
            commodities = crosswalk.get(canonical.get(word, word))
            if not commodities:
                continue
            sp = pv.get("source_path") or ""
            year = _year(pv.get("date")) or work_year.get(work_stem(sp))
            for cid in sorted(commodities):
                key = (work_stem(sp), pv["context_text"], cid)
                if key in seen:
                    stats["duplicate across sources"] += 1
                    continue
                seen.add(key)
                if year is None:
                    stats["dropped: no year"] += 1
                    continue
                records.append({
                    "year": year,
                    "commodity_id": cid,
                    "source_type": SOURCE_TYPE,
                    "primary_frame": frame,
                    "text_evidence": re.sub(r"\s+", " ", pv["context_text"]).strip(),
                    "influence_from": year,
                    "influence_to": year + INFLUENCE_YEARS,
                    "source_work": pv.get("title") or sp,
                    "work_id": sp,
                    "source_label": label,
                    "genre": infer_text_regime(corpus=pv.get("corpus"), title=pv.get("title"), source_path=sp).value,
                    "target_word": pv.get("target_word"),
                    "record_id": pv["record_id"],
                })
                stats[f"exported from {label}"] += 1

    records.sort(key=lambda d: (d["commodity_id"], d["year"], d["work_id"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for d in records:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    works_out = args.out.with_name(args.out.stem + "_works.jsonl")
    with works_out.open("w", encoding="utf-8") as fh:
        for w in sorted(coverage.values(), key=lambda d: (d["year"], d["work_id"])):
            fh.write(json.dumps(w, ensure_ascii=False) + "\n")
    meta = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": "trifecta-annotation/scripts/export_kg_mockup_frames.py",
        "crosswalk": str(CROSSWALK),
        "sources": [k for k in SOURCES if Path(resolve(k)).exists()],
        "influence_years": INFLUENCE_YEARS,
        "records": len(records),
        "coverage_works": len(coverage),
        "stats": dict(stats),
    }
    args.out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"wrote {len(records)} records -> {args.out}; {len(coverage)} annotated works -> {works_out.name}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print("by commodity:", dict(Counter(d["commodity_id"] for d in records).most_common()))
    top = Counter(d["source_work"] for d in records).most_common(3)
    print("top works:", [(t[:40], n) for t, n in top])


if __name__ == "__main__":
    main()
