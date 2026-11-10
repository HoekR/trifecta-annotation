"""Targeted harvest of Indies-cuisine terms in the cookbooks (and the rest of the 2026 batches).

Uses only the terms of the in-repo vocabulary extension
(`vocabulary/Food_terms_indies.csv`), which the earlier harvests could not see.
Sources: the KB cookbooks 1900-1913 (re-OCR text), the LDK2025 cookbooks
1910-1940 and the Google Books batch of 9 Nov 2026 (GOOGLE_BOOKS_2026_11).
Every mention is written (`indies_kwic_inputs_all`); for annotation, at most
`--cap` per book, evenly spaced (`indies_kwic_inputs`). Writes only its own
logical names.

    uv run python scripts/run_indies_harvest.py harvest [--cap 80]
    uv run python scripts/run_indies_harvest.py annotate [--until 17:15]
    uv run python scripts/run_indies_harvest.py report
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from data_io import resolve
from data_io.jsonl_io import save_semi_structured

from scripts.build_colonial_kwic import (
    GOOGLE_BOOKS_2026_11,
    GOOGLE_BOOKS_2026_11_DIR,
    KB_COOKBOOKS_2026,
    KB_COOKBOOKS_REOCR,
    PLACE_OF_PRINT,
    WANNEE_2026_11,
    WANNEE_2026_11_DIR,
    build_term_pattern,
    scan_text,
    structural_units_for_document,
)
from trifecta_annotation.text_regime import TextRegime
from trifecta_annotation.vocabulary import VOCABULARY_EXTENSIONS, alt_label_index

SCRIPT = "scripts/run_indies_harvest.py"
INPUTS_ALL = "indies_kwic_inputs_all"
INPUTS = "indies_kwic_inputs"
ANNOTATIONS = "indies_annotations"
REGIME = {  # explicit, these are known works
    "Medische verhandelingen (Allinson)": TextRegime.MEDICAL,
    "De nieuwe geneeskunde zonder medicijnen (Kuhne)": TextRegime.MEDICAL,
    "Algemeene orders, reglementen en instructiën": TextRegime.ADMIN_TRADE,
}


def sources() -> list[tuple[str, str, int | None, str, str]]:
    """(source_path, title, year, corpus, text) for every text in scope."""
    ocr = Path(resolve("colonial_books_ocr"))
    out = []
    for filename, (title, year) in KB_COOKBOOKS_2026.items():
        slug = KB_COOKBOOKS_REOCR.get(filename)
        p = ocr / f"{slug}_nld.txt" if slug else None
        if p and p.exists():
            out.append((filename, title, year, "kb_cookbooks_2026", p.read_text(encoding="utf-8", errors="replace")))
    for p in sorted(Path(resolve("ldk2025_cookbooks")).glob("cookbook_*.txt")):
        year = int(p.stem.split("_")[1])
        out.append((p.name, f"LDK kookboek {year}", year, "ldk2025_cookbooks", p.read_text(encoding="utf-8", errors="replace")))
    for filename, (title, year) in GOOGLE_BOOKS_2026_11.items():
        p = (ocr / GOOGLE_BOOKS_2026_11_DIR / filename).with_suffix(".txt")
        if p.exists():
            out.append((filename, title, year, "google_books_2026_11", p.read_text(encoding="utf-8", errors="replace")))
    for filename, (title, year) in WANNEE_2026_11.items():
        p = ocr / WANNEE_2026_11_DIR / filename
        if p.exists():
            out.append((f"wannee_{filename}", title, year, "wannee_2026_11", p.read_text(encoding="utf-8", errors="replace")))
    return out


def harvest(cap: int) -> None:
    indies = pd.concat([pd.read_csv(p) for p in VOCABULARY_EXTENSIONS if p.exists()], ignore_index=True)
    canonical = alt_label_index(indies)
    pattern = build_term_pattern({t: t for t in canonical})
    all_rows, capped, per_book = [], [], Counter()
    for sp, title, year, corpus, text in sources():
        regime = REGIME.get(title, TextRegime.RECIPE_PRACTICE)
        units = structural_units_for_document(text, title=title, source_path=sp, corpus=corpus)
        hits = scan_text(text, pattern=pattern, canonical=canonical, source_path=sp, title=title, corpus=corpus,
                         date=str(year) if year else None, regime=regime, units=units)
        for h in hits:
            h["record_id"] = f"{sp}__indies__{h['target_char_offset']}__{h['target_word']}"
            h["kwic_mode"] = "indies_term"
            h["text_regime"] = regime.value
            h["place_of_print"] = PLACE_OF_PRINT.get(title, "")
        hits.sort(key=lambda h: h["target_char_offset"])
        all_rows += hits
        pick = hits if len(hits) <= cap else [hits[k * len(hits) // cap] for k in range(cap)]
        capped.append(pick)
        per_book[f"{year} {title[:48]}"] = len(hits)
        print(f"  {year} {title[:55]!r}: {len(hits)} Indies mentions, {len(pick)} for annotation", flush=True)
    # round-robin over books, so an early stop still covers every book
    from itertools import zip_longest
    rr = [r for group in zip_longest(*capped) for r in group if r is not None]
    save_semi_structured(all_rows, logical_name=INPUTS_ALL, parent_sources=["kb_cookbooks_2026", "ldk2025_cookbooks"],
                         description="Every Indies-term mention in the 2026 cookbook batches", script=SCRIPT)
    out = save_semi_structured(rr, logical_name=INPUTS, parent_sources=[INPUTS_ALL],
                               description=f"Indies-term mentions, at most {cap} per book, round-robin", script=SCRIPT)
    terms = Counter(canonical.get(r["target_word"].lower(), r["target_word"]) for r in all_rows)
    print(f"wrote {len(all_rows)} mentions ({len(rr)} for annotation) -> {out}")
    print("top terms:", ", ".join(f"{t} {n}" for t, n in terms.most_common(20)))


def annotate(until: str | None) -> None:
    from trifecta_annotation.batch import load_inputs, run_batch

    rows = load_inputs(input_path=resolve(INPUTS))
    if until:
        # resumable: stop cleanly at the deadline by annotating in chunks
        hh, mm = map(int, until.split(":"))
        deadline = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
        done = {json.loads(l)["provenance"]["record_id"] for l in open(resolve(ANNOTATIONS), encoding="utf-8")
                if l.strip() and not l.startswith("---")} if Path(resolve(ANNOTATIONS)).exists() else set()
        todo = [r for r in rows if r["record_id"] not in done]
        for start in range(0, len(todo), 25):
            if datetime.now() >= deadline:
                print(f"deadline {until} reached; {start} of {len(todo)} done this session (resume later)", flush=True)
                return
            run_batch(todo[start:start + 25], output_logical=ANNOTATIONS, resume=True, parent_sources=[INPUTS],
                      description="A->B->C annotations for indies_kwic_inputs (local Ollama)", script=SCRIPT)
        return
    run_batch(rows, output_logical=ANNOTATIONS, resume=True, parent_sources=[INPUTS],
              description="A->B->C annotations for indies_kwic_inputs (local Ollama)", script=SCRIPT)


def report() -> None:
    inputs = {json.loads(l)["record_id"]: json.loads(l) for l in open(resolve(INPUTS), encoding="utf-8") if l.strip()}
    by = defaultdict(Counter)
    for l in open(resolve(ANNOTATIONS), encoding="utf-8"):
        if not l.strip() or l.startswith("---"):
            continue
        r = json.loads(l)
        src = inputs.get(r["provenance"]["record_id"])
        if not src:
            continue
        frame = (r.get("step_b") or {}).get("selected_frame")
        out = "error" if r.get("error") else "dropped" if r.get("dropped") else (frame or "NONE")
        by[f"{src.get('date')} {src['title'][:45]}"][out] += 1
    df = pd.DataFrame(by).T.fillna(0).astype(int).sort_index()
    print(df.to_string())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("phase", choices=["harvest", "annotate", "report"])
    ap.add_argument("--cap", type=int, default=80)
    ap.add_argument("--until", default=None, help="HH:MM: stop annotating at this time (resumable)")
    a = ap.parse_args()
    {"harvest": lambda: harvest(a.cap), "annotate": lambda: annotate(a.until), "report": report}[a.phase]()


if __name__ == "__main__":
    main()
