"""Weak-regime verb_food ingestion (PLAN.md §9i): the other genres, done properly.

The 2026 DBNL sweep took at most 10 rows/work, and about half were
noun-fallback picks (13% real frames vs 41% for verb_food). Production is
now verb-only, so this re-harvests every sweep work outside RECIPE/MEDICAL
with the verb route, drops contexts the sweep already annotated, and
keeps up to `--cap` (default 50) rows per work, evenly spaced in document
order. The per-work uncapped candidate count is recorded too (`counts`).

Writes its own logical names, never the canonical files.

    uv run python scripts/run_weak_regime_harvest.py harvest|annotate|report|all
"""

from __future__ import annotations

import argparse
import json
import time
import zipfile
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path

from data_io import resolve
from data_io.jsonl_io import save_semi_structured

from scripts.build_colonial_kwic import (
    AMBIGUOUS_FUNCTION_WORDS,
    ENTRY_SCOPE_REGIMES,
    build_term_pattern,
    capped_candidates,
    ingested_dbnl_stems,
    structural_units_for_document,
)
from trifecta_annotation.corpus_genre_join import load_genre_records
from trifecta_annotation.dbnl_genre import sweep_candidates, xml_filenames_by_stem
from trifecta_annotation.tei_segmentation import attach_tei_scope_to_rows, render_tei
from trifecta_annotation.text_regime import infer_text_regime
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

INPUTS = "weak_regime_verb_kwic_inputs"
ANNOTATIONS = "weak_regime_verb_annotations"
CORPUS = "dbnl_full_sweep_2026"  # same corpus tag as the sweep: same works, regime inference unchanged
SCRIPT = "scripts/run_weak_regime_harvest.py"
DEFAULT_CAP = 50
UNCAPPED = 10**9


def _counts_path() -> Path:
    return resolve(INPUTS).parent / "weak_regime_verb_counts.jsonl"


def _already_annotated() -> set[tuple[str, str]]:
    """(source_path, context_text) of every sweep row; all were annotated."""
    out = set()
    for line in open(resolve("dbnl_sweep_kwic_inputs"), encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            out.add((r["source_path"], r["context_text"]))
    return out


def harvest(*, cap: int, limit: int | None) -> None:
    terms = load_food_terms()
    canonical = alt_label_index(terms)
    all_terms = set(canonical) | {str(p).strip().lower() for p in terms["Pref_label"].dropna()}
    all_terms -= AMBIGUOUS_FUNCTION_WORDS
    pattern = build_term_pattern({t: t for t in all_terms})
    food_terms_list = sorted(all_terms)

    zip_path = resolve("dbnl_xml")
    cands = sweep_candidates(load_genre_records(), filenames_by_stem=xml_filenames_by_stem(zip_path),
                             exclude_stems=ingested_dbnl_stems())
    done = _already_annotated()
    works = []
    for c in cands:
        title = c["titel"] or c["ti_id"]
        regime = infer_text_regime(corpus=CORPUS, title=title, source_path=c["filename"])
        if regime not in ENTRY_SCOPE_REGIMES:
            works.append((c, title, regime.value))
    if limit:
        works = works[:limit]
    print(f"{len(works)} non-RECIPE/MEDICAL sweep works; {len(done)} sweep contexts to skip", flush=True)

    per_work: dict[str, list[dict]] = {}
    counts = []
    t0 = time.monotonic()
    with zipfile.ZipFile(zip_path) as archive:
        for i, (c, title, regime) in enumerate(works, 1):
            fn = c["filename"]
            try:
                rendered = render_tei(archive.read(fn).decode("utf-8", errors="replace"), work_id=fn)
            except Exception as exc:  # one unparseable TEI file must not kill a 3 h scan
                print(f"  skipped {fn}: {type(exc).__name__}: {exc}", flush=True)
                continue
            units = structural_units_for_document(rendered.text, title=title, source_path=fn, corpus=CORPUS)
            pool = capped_candidates(
                rendered.text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
                source_path=fn, title=title, corpus=CORPUS,
                date=str(c["year"]) if c["year"] else None,
                units=units, cap=UNCAPPED, located=rendered.located, entry_scope=False,
            )
            new = [h for h in pool if (fn, h["context_text"]) not in done]
            new.sort(key=lambda h: h["target_char_offset"])
            if cap and len(new) > cap:
                new = [new[k * len(new) // cap] for k in range(cap)]
            for h in new:  # offset-based ids: stable across re-harvests, unique per work
                h["record_id"] = f"{fn}__weakverb__{h['target_char_offset']}__{h['target_word']}"
            per_work[fn] = attach_tei_scope_to_rows(new, located=rendered.located)
            counts.append({"source_path": fn, "title": title, "regime": regime, "year": c["year"],
                           "verb_candidates": len(pool), "already_annotated": len(pool) - len([h for h in pool if (fn, h["context_text"]) not in done]),
                           "selected": len(new)})
            if i % 50 == 0 or i == len(works):
                el = time.monotonic() - t0
                print(f"  {i}/{len(works)} works, {sum(map(len, per_work.values()))} rows "
                      f"({el / 60:.0f} min, ~{(len(works) - i) * el / i / 60:.0f} min left)", flush=True)

    rows = [r for group in zip_longest(*per_work.values()) for r in group if r is not None]
    ids = Counter(r["record_id"] for r in rows)
    dup = sum(n - 1 for n in ids.values() if n > 1)
    if dup:
        seen: set[str] = set()
        rows = [r for r in rows if not (r["record_id"] in seen or seen.add(r["record_id"]))]
        print(f"dropped {dup} duplicate record_ids", flush=True)
    with _counts_path().open("w", encoding="utf-8") as fh:
        for row in counts:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    out = save_semi_structured(
        rows, logical_name=INPUTS, parent_sources=["dbnl_xml", "dbnl_work_genre", "dbnl_sweep_kwic_inputs"],
        description=f"verb_food rows (cap {cap}/work) from non-RECIPE/MEDICAL sweep works, minus sweep contexts",
        script=SCRIPT,
    )
    summarize_counts()
    print(f"wrote {len(rows)} rows from {len(per_work)} works -> {out}", flush=True)


def summarize_counts() -> None:
    by = defaultdict(lambda: [0, 0, 0, 0, 0])  # works, works w/ new rows, candidates, already, selected
    for line in _counts_path().open(encoding="utf-8"):
        c = json.loads(line)
        for key in (c["regime"], "ALL"):
            s = by[key]
            s[0] += 1
            s[1] += c["selected"] > 0
            s[2] += c["verb_candidates"]
            s[3] += c["already_annotated"]
            s[4] += c["selected"]
    lines = ["| regime | works | works with new rows | verb candidates (uncapped) | already annotated | selected (capped) |",
             "|---|---:|---:|---:|---:|---:|"]
    lines += [f"| {k} | {w} | {wn} | {n} | {a} | {s} |" for k, (w, wn, n, a, s) in sorted(by.items())]
    out = _counts_path().with_suffix(".md")
    out.write_text("# Weak-regime verb_food harvest: counts\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def annotate() -> None:
    from trifecta_annotation.batch import load_inputs, run_batch

    model_dir = Path(resolve("trifecta_step_a_keepdrop_models")) / "globertise-keepdrop" / "model"
    run_batch(
        load_inputs(input_path=resolve(INPUTS)), output_logical=ANNOTATIONS, resume=True,
        parent_sources=[INPUTS], step_a_sieve_model=model_dir,
        description="A->B->C annotations for weak_regime_verb_kwic_inputs (local Ollama, Step A sieve 0.98)",
        script=SCRIPT,
    )


def report() -> None:
    inputs = {json.loads(l)["record_id"]: json.loads(l) for l in open(resolve(INPUTS), encoding="utf-8") if l.strip()}
    by = defaultdict(lambda: [0, 0, 0, 0])  # n, errors, sieved/dropped, real
    frames: Counter[str] = Counter()
    for line in open(resolve(ANNOTATIONS), encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        src = inputs.get(r["provenance"]["record_id"])
        if src is None:
            continue
        frame = (r.get("step_b") or {}).get("selected_frame")
        real = not r.get("error") and not r.get("dropped") and frame not in (None, "NONE")
        for key in (src.get("text_regime") or "?", "ALL"):
            s = by[key]
            s[0] += 1
            s[1] += bool(r.get("error"))
            s[2] += bool(r.get("dropped"))
            s[3] += real
        if real:
            frames[frame] += 1
    lines = ["# Weak-regime verb_food run", "", f"{sum(1 for _ in inputs)} rows harvested.", "",
             "| regime | annotated | errors | dropped (sieve or Step A) | real frame |", "|---|---:|---:|---:|---:|"]
    for k, (n, e, d, f) in sorted(by.items()):
        lines.append(f"| {k} | {n} | {e} | {d} | {f / max(n - e, 1):.0%} ({f}) |")
    lines += ["", "| frame | rows |", "|---|---:|", *[f"| {k} | {v} |" for k, v in frames.most_common()]]
    out = resolve(ANNOTATIONS).parent / "weak_regime_verb_report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=["harvest", "annotate", "report", "all"])
    p.add_argument("--cap", type=int, default=DEFAULT_CAP, help="rows per work (0 = uncapped)")
    p.add_argument("--limit", type=int, default=None, help="first N works only (smoke test)")
    a = p.parse_args()
    if a.phase in ("harvest", "all"):
        harvest(cap=a.cap, limit=a.limit)
    if a.phase in ("annotate", "all"):
        annotate()
    if a.phase in ("report", "all"):
        report()


if __name__ == "__main__":
    main()
