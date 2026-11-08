"""Entry-scope production harvest + annotation (PLAN.md §9i, selection v2).

Selection v2 showed that in structured RECIPE/MEDICAL works most real frames
lie on mentions with no qualifying verb, which the verb_food harvest never
selects. This collects exactly those rows through production's
`capped_candidates` routing (kwic_mode == "entry_scope", cap 500/work), over
every DBNL TEI work whose work regime is RECIPE_PRACTICE or MEDICAL.

Writes its own logical names (`entry_scope_kwic_inputs`,
`entry_scope_annotations`), never the canonical kwic/annotation files: TEI
re-harvests no longer resume-match old record_ids, so mixing would duplicate.

    uv run python scripts/run_entry_scope_harvest.py harvest|annotate|report|all

Extending one work past the cap (annotations resume, so rows already done are
reused; record_ids are offset-based and stable):

    uv run python scripts/run_entry_scope_harvest.py all --only chom003huis01_01.xml \
        --cap 0 --inputs entry_scope_kwic_inputs_chomel_full
"""

from __future__ import annotations

import argparse
import json
import time
import zipfile
from collections import Counter, defaultdict
from itertools import zip_longest

from data_io import resolve
from data_io.jsonl_io import save_semi_structured

from scripts.build_colonial_kwic import (
    AMBIGUOUS_FUNCTION_WORDS,
    DEFAULT_ENTRY_SCOPE_CAP,
    DEFAULT_SWEEP_CAP,
    ENTRY_SCOPE_REGIMES,
    NEW_DBNL_WORKS,
    build_term_pattern,
    capped_candidates,
    structural_units_for_document,
)
from trifecta_annotation.corpus_genre_join import load_genre_records
from trifecta_annotation.dbnl_genre import work_stem, xml_filenames_by_stem
from trifecta_annotation.tei_segmentation import attach_tei_scope_to_rows, render_tei
from trifecta_annotation.text_regime import infer_text_regime
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

INPUTS = "entry_scope_kwic_inputs"
ANNOTATIONS = "entry_scope_annotations"
CORPUS = "dbnl_entry_scope_2026"
SCRIPT = "scripts/run_entry_scope_harvest.py"


def _works(zip_path) -> list[tuple[str, str, str]]:
    """(filename, title, regime) for every DBNL TEI work in a structured regime."""
    by_stem = xml_filenames_by_stem(zip_path)
    titles: dict[str, str] = {}
    for rec in load_genre_records():
        if rec.get("id_scheme") == "dbnl_ti_id" and rec.get("titel"):
            titles.setdefault(work_stem(rec["ti_id"]), rec["titel"])
    for work_id, (title, _year) in NEW_DBNL_WORKS.items():
        titles[work_stem(work_id)] = title
    out = []
    for stem, fn in sorted(by_stem.items()):
        title = titles.get(stem, stem)
        regime = infer_text_regime(corpus="dbnl_full_sweep_2026", title=title, source_path=fn)
        if regime in ENTRY_SCOPE_REGIMES:
            out.append((fn, title, regime.value))
    return out


def harvest(*, cap: int | None, only: set[str] | None, inputs: str) -> None:
    terms = load_food_terms()
    canonical = alt_label_index(terms)
    all_terms = set(canonical) | {str(p).strip().lower() for p in terms["Pref_label"].dropna()}
    all_terms -= AMBIGUOUS_FUNCTION_WORDS
    pattern = build_term_pattern({t: t for t in all_terms})
    food_terms_list = sorted(all_terms)

    zip_path = resolve("dbnl_xml")
    works = _works(zip_path)
    if only:
        works = [w for w in works if w[0] in only]
    print(f"{len(works)} RECIPE/MEDICAL DBNL works", flush=True)
    per_work: dict[str, list[dict]] = {}
    t_all = time.monotonic()
    with zipfile.ZipFile(zip_path) as archive:
        for i, (fn, title, regime) in enumerate(works, 1):
            t0 = time.monotonic()
            rendered = render_tei(archive.read(fn).decode("utf-8", errors="replace"), work_id=fn)
            if not rendered.located:
                print(f"  [{i}/{len(works)}] {title[:60]!r}: no TEI entries, skipped", flush=True)
                continue
            units = structural_units_for_document(rendered.text, title=title, source_path=fn, corpus=CORPUS)
            hits = capped_candidates(
                rendered.text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
                source_path=fn, title=title, corpus=CORPUS, date=None, units=units,
                cap=DEFAULT_SWEEP_CAP, located=rendered.located,
                entry_scope_cap=cap,
            )
            scoped = [h for h in hits if h["kwic_mode"] == "entry_scope"]
            heads = {h.get("tei_scope_head") for h in attach_tei_scope_to_rows(list(scoped), located=rendered.located)}
            scoped = attach_tei_scope_to_rows(scoped, located=rendered.located)
            per_work[fn] = scoped
            print(f"  [{i}/{len(works)}] [{regime}] {title[:60]!r}: {len(scoped)} entry-scope rows, "
                  f"{len(heads)} distinct entry heads "
                  f"({time.monotonic() - t0:.0f}s, {time.monotonic() - t_all:.0f}s total)", flush=True)

    # Round-robin across works so a run stopped early still covers every work.
    rows = [r for group in zip_longest(*per_work.values()) for r in group if r is not None]
    out = save_semi_structured(
        rows, logical_name=inputs, parent_sources=["dbnl_xml", "dbnl_work_genre"],
        description=f"Entry-scope rows (cap {cap or 'none'}/work) from RECIPE/MEDICAL DBNL TEI works"
                    + (f", only {sorted(only)}" if only else ""),
        script=SCRIPT,
    )
    print(f"wrote {len(rows)} rows from {len(per_work)} works -> {out}", flush=True)


def annotate(*, inputs: str) -> None:
    from trifecta_annotation.batch import load_inputs, run_batch

    run_batch(
        load_inputs(input_path=resolve(inputs)),
        output_logical=ANNOTATIONS,
        resume=True,
        parent_sources=[inputs],
        description="A->B->C annotations for entry_scope_kwic_inputs (local Ollama)",
        script=SCRIPT,
    )


def report(*, inputs_logical: str, cap: int | None) -> None:
    inputs = {json.loads(l)["record_id"]: json.loads(l) for l in open(resolve(inputs_logical), encoding="utf-8") if l.strip()}
    by_work: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])  # n, errors, survive A, real
    by_regime: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    frames: Counter[str] = Counter()
    titles: dict[str, str] = {}
    for line in open(resolve(ANNOTATIONS), encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        rid = r["provenance"]["record_id"]
        if rid not in inputs:
            continue
        src = inputs[rid]
        fn, regime = src["source_path"], src.get("text_regime") or "?"
        titles[fn] = src.get("title") or fn
        for key, table in ((fn, by_work), (regime, by_regime)):
            s = table[key]
            s[0] += 1
            if r.get("error"):
                s[1] += 1
                continue
            survived = not r.get("dropped")
            frame = (r.get("step_b") or {}).get("selected_frame")
            s[2] += survived
            s[3] += survived and frame not in (None, "NONE")
        frame = (r.get("step_b") or {}).get("selected_frame")
        if not r.get("error") and not r.get("dropped") and frame not in (None, "NONE"):
            frames[frame] += 1

    def pct(a: int, n: int) -> str:
        return f"{a / n:.0%} ({a})" if n else "-"

    total = [sum(v[i] for v in by_regime.values()) for i in range(4)]
    lines = [
        "# Entry-scope production run",
        "",
        f"Rows annotated: {total[0]} of {len(inputs)} harvested ({total[1]} errors). "
        f"Works: {len(by_work)}. Cap {cap or 'none'}/work, round-robin order. Inputs: `{inputs_logical}`.",
        "Yield = real frame / non-error rows. Every row here is unreachable by the verb_food harvest.",
        "",
        "| regime | n | survive Step A | real frame |",
        "|---|---:|---:|---:|",
    ]
    for regime, (n, e, a, f) in sorted(by_regime.items()):
        lines.append(f"| {regime} | {n} | {pct(a, n - e)} | {pct(f, n - e)} |")
    lines += ["", "## Frames found", "", "| frame | rows |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in frames.most_common()]
    lines += ["", "## Per work (by rows annotated)", "", "| work | n | survive Step A | real frame |",
              "|---|---:|---:|---:|"]
    for fn, (n, e, a, f) in sorted(by_work.items(), key=lambda kv: -kv[1][0]):
        lines.append(f"| {titles[fn][:60]} (`{fn}`) | {n} | {pct(a, n - e)} | {pct(f, n - e)} |")
    suffix = "" if inputs_logical == INPUTS else "_" + inputs_logical.removeprefix(INPUTS + "_")
    out = resolve(ANNOTATIONS).parent / f"entry_scope_report{suffix}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))
    print(f"wrote {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["harvest", "annotate", "report", "all"])
    parser.add_argument("--cap", type=int, default=DEFAULT_ENTRY_SCOPE_CAP,
                        help=f"entry-scope rows per work (default {DEFAULT_ENTRY_SCOPE_CAP}; 0 = uncapped)")
    parser.add_argument("--only", nargs="*", default=None, metavar="FILE", help="restrict to these DBNL filenames")
    parser.add_argument("--inputs", default=INPUTS, help=f"inputs logical name (default {INPUTS})")
    args = parser.parse_args()
    cap = args.cap or None
    if args.phase in ("harvest", "all"):
        harvest(cap=cap, only=set(args.only) if args.only else None, inputs=args.inputs)
    if args.phase in ("annotate", "all"):
        annotate(inputs=args.inputs)
    if args.phase in ("report", "all"):
        report(inputs_logical=args.inputs, cap=cap)


if __name__ == "__main__":
    main()
