"""T1b (plans/steps/TRIANGULATION.md): passage-first triangulation on a frozen, stratified work sample.

No LLM calls. Three subcommands:

- `sample`: draw about 40 DBNL TEI works, stratified by DBNL genre plus a RECIPE/MEDICAL stratum, with a
  fixed seed. Writes `docs/evidence/triangulation_b/works.csv` and refuses to overwrite it (frozen).
- `harvest`: every food-noun occurrence in those works, uncapped (`scan_text`), plus the uncapped verb
  route (`verb_first_hits`). A noun occurrence is *verb-selected* when a verb hit's window contains it and
  the verb hit's target is the same word. Writes two input files:
  - `triangulation_b_kwic_inputs`: one food-anchored row per occurrence (noun-centred context);
  - `triangulation_b_verbctx_kwic_inputs`: the verb route's own row (verb-centred context) for each
    verb-selected occurrence. This tests whether the context centring alone changes the label.
- `estimate`: row counts per route and stratum, plus estimated LLM calls. This is gate G2/G2a.

Step A/B see only `target_word` + `context_text`. The verb (`discovery_verb`) reaches only the GloBERTise
sieve, as a marker. So the routes differ in *selection* and *context centring*, not in what the LLM is
told; verb-in-prompt is T5.

    uv run python scripts/triangulation_sample.py sample|harvest|estimate
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from data_io import resolve
from data_io.jsonl_io import save_semi_structured
from scripts.build_colonial_kwic import (
    AMBIGUOUS_FUNCTION_WORDS,
    build_term_pattern,
    scan_text,
    structural_units_for_document,
    verb_first_hits,
)
from trifecta_annotation.adapters.food_snippets import DEFAULT_KWIC_CONTEXT_RADIUS
from trifecta_annotation.clear_frame_examples import term_allowed
from trifecta_annotation.corpus_genre_join import load_genre_records
from trifecta_annotation.dbnl_genre import sweep_candidates, xml_filenames_by_stem
from trifecta_annotation.tei_segmentation import attach_tei_scope_to_rows, render_tei
from trifecta_annotation.text_regime import TextRegime, infer_text_regime
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "triangulation_b"
WORKS = OUT / "works.csv"
CORPUS = "dbnl_full_sweep_2026"
SCRIPT = "scripts/triangulation_sample.py"
FOOD_INPUTS = "triangulation_b_kwic_inputs"
VERB_INPUTS = "triangulation_b_verbctx_kwic_inputs"
RUN_INPUTS = "triangulation_b_run_kwic_inputs"
RUN_ANNOTATIONS = "triangulation_b_annotations"
RECIPE_VERB_CAP = 300               # G2 (12 Nov): RECIPE alone had 1,035 verb-selected occurrences
# G2 for the re-harvests (Rik, 16 Nov): with the reviewed list MEDICAL has 1,805 verb-selected occurrences, so it
# is capped like RECIPE. The untagged (12 Nov) selection keeps its RECIPE-only cap, so it stays reproducible.
VERB_CAPS_TAGGED = {"RECIPE": 300, "MEDICAL": 300}
PER_STRATUM_FOOD_ONLY = 200          # G2: random non-verb-selected occurrences per stratum
SEED = 20261112
# Works per stratum (40 total). Every genre gets at least 2 works, so no stratum is a single anecdote.
QUOTA = {"RECIPE": 5, "MEDICAL": 5, "non-fictie": 8, "poëzie": 6, "proza": 5, "jeugdliteratuur": 3,
         "drama": 3, "sec - taalkunde": 3, "sec - letterkunde": 2}
# Extended sample (Rik, 17 Nov: "up the cap a bit for the rest"): the same seed and pools, drawn further down,
# so the 39 frozen works stay in. Aim: ~100+ verb passages per genre (drama and youth literature had 13 each).
WORKS_EXT = OUT / "works_ext.csv"
QUOTA_EXT = {"RECIPE": 5, "MEDICAL": 9, "non-fictie": 10, "poëzie": 10, "proza": 8, "jeugdliteratuur": 20,
             "drama": 20, "sec - taalkunde": 8, "sec - letterkunde": 6}
EXT_TAGS = {"v3f"}  # tags that harvest the extended works list
MIN_VERB, MAX_VERB = 3, 100        # mid-sized: uncapped verb candidates per work (weak-regime counts)
MAX_BYTES = 3_000_000              # leave out dictionary-sized outliers (Chomel and the like)
CALLS_PER_ROW = 5.28               # project_pipeline_economics: LLM calls per annotated row
SIEVE_SAVING = 0.43                # Step A sieve on weak regimes (8 Nov shadow run)


def _genre(rec: dict) -> str:
    ga = rec.get("genre_assertions")
    ga = ast.literal_eval(ga) if isinstance(ga, str) else (ga or [])
    vals = sorted({a["value"] for a in ga if a.get("scheme") == "dbnl_genre"})
    return vals[0] if vals else "?"


def _pools() -> dict[str, list[dict]]:
    zip_path = resolve("dbnl_xml")
    recs = load_genre_records()
    by_id = {r["ti_id"]: r for r in recs if r.get("ti_id")}
    cands = sweep_candidates(recs, filenames_by_stem=xml_filenames_by_stem(zip_path), exclude_stems=set())
    counts = pd.read_json(resolve("weak_regime_verb_kwic_inputs").parent / "weak_regime_verb_counts.jsonl",
                          lines=True).set_index("source_path").verb_candidates
    with zipfile.ZipFile(zip_path) as archive:
        size = {i.filename: i.file_size for i in archive.infolist()}

    pools: dict[str, list[dict]] = defaultdict(list)
    for c in cands:
        fn = c["filename"]
        regime = infer_text_regime(corpus=CORPUS, title=c["titel"] or c["ti_id"], source_path=fn)
        if size.get(fn, 0) > MAX_BYTES:
            continue
        rec = {"filename": fn, "ti_id": c["ti_id"], "title": c["titel"], "year": c["year"],
               "genre": _genre(by_id.get(c["ti_id"], {})), "regime": regime.value,
               "bytes": size.get(fn), "verb_candidates": counts.get(fn)}
        if regime in (TextRegime.RECIPE_PRACTICE, TextRegime.MEDICAL):
            # Title-keyword regimes misfire (a wedding poem "... Medic: Doctor" came out MEDICAL), so poetry
            # and drama are kept out of these strata. Not in the weak-regime counts: no size-by-verb filter.
            if rec["genre"] not in ("poëzie", "drama"):
                pools["RECIPE" if regime is TextRegime.RECIPE_PRACTICE else "MEDICAL"].append(rec)
        elif rec["verb_candidates"] is not None and MIN_VERB <= rec["verb_candidates"] <= MAX_VERB:
            pools[rec["genre"]].append(rec)
    return pools


def _pick(pools: dict[str, list[dict]], quota: dict[str, int]) -> list[dict]:
    """Deterministic: a larger quota takes the same works first, then more from the same shuffled pool."""
    rng = random.Random(SEED)
    picked = []
    for stratum, n in quota.items():
        pool = sorted(pools[stratum], key=lambda r: r["filename"])
        rng.shuffle(pool)
        take, series = [], set()
        for r in pool:                       # one work per series: parts of one pharmacopoeia are not 3 works
            key = r["filename"].lstrip("_")[:7]
            if key not in series and len(take) < n:
                series.add(key)
                take.append(r)
        print(f"{stratum}: {len(take)} of {len(pool)} eligible", flush=True)
        picked += [{**r, "stratum": stratum} for r in take]
    return picked


def sample() -> None:
    if WORKS.exists():
        raise SystemExit(f"{WORKS} exists: the sample is frozen. Delete it deliberately to redraw.")
    picked = _pick(_pools(), QUOTA)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(picked).to_csv(WORKS, index=False)
    print(f"wrote {len(picked)} works -> {WORKS} (seed {SEED})")


def extend() -> None:
    """Write works_ext.csv: the frozen sample plus more works per genre (QUOTA_EXT). Refuses to overwrite."""
    if WORKS_EXT.exists():
        raise SystemExit(f"{WORKS_EXT} exists. Delete it deliberately to redraw.")
    picked = _pick(_pools(), QUOTA_EXT)
    frozen = set(pd.read_csv(WORKS).filename)
    missing = frozen - {r["filename"] for r in picked}
    if missing:
        raise SystemExit(f"extended draw lost frozen works: {sorted(missing)}")
    df = pd.DataFrame(picked).assign(in_frozen_sample=lambda d: d.filename.isin(frozen))
    df.to_csv(WORKS_EXT, index=False)
    print(f"wrote {len(df)} works -> {WORKS_EXT} ({int(df.in_frozen_sample.sum())} frozen + "
          f"{int((~df.in_frozen_sample).sum())} new)")


def harvest(tag: str = "") -> None:
    """`tag` writes to `triangulation_b_<tag>_…` instead of the original inputs, which stay for comparison
    (and are the parent of the C3 sample)."""
    food_name = FOOD_INPUTS.replace("triangulation_b_", f"triangulation_b_{tag}_") if tag else FOOD_INPUTS
    verb_name = VERB_INPUTS.replace("triangulation_b_", f"triangulation_b_{tag}_") if tag else VERB_INPUTS
    works = pd.read_csv(WORKS_EXT if tag in EXT_TAGS else WORKS)
    terms = load_food_terms()
    canonical = alt_label_index(terms)
    all_terms = (set(canonical) | {str(p).strip().lower() for p in terms["Pref_label"].dropna()}) - AMBIGUOUS_FUNCTION_WORDS
    pattern = build_term_pattern({t: t for t in all_terms})
    food_terms_list = sorted(all_terms)
    R = DEFAULT_KWIC_CONTEXT_RADIUS

    food_rows, verb_rows = [], []
    t0 = time.monotonic()
    with zipfile.ZipFile(resolve("dbnl_xml")) as archive:
        for i, w in enumerate(works.itertuples(), 1):
            fn, title = w.filename, (w.title if isinstance(w.title, str) else w.ti_id)
            date = str(int(w.year)) if pd.notna(w.year) else None
            rendered = render_tei(archive.read(fn).decode("utf-8", errors="replace"), work_id=fn)
            text = rendered.text
            regime = infer_text_regime(corpus=CORPUS, title=title, source_path=fn)
            units = structural_units_for_document(text, title=title, source_path=fn, corpus=CORPUS)
            common = dict(pattern=pattern, canonical=canonical, source_path=fn, title=title, corpus=CORPUS,
                          date=date, regime=regime, units=units)
            # restricted food terms (body parts, 'never' words) by regime, on the food route too (Rik, 17 Nov)
            nouns = [n for n in scan_text(text, **common) if term_allowed(n["target_word"], regime)]
            verbs = [row for _, row in verb_first_hits(text, food_terms_list=food_terms_list, **common)]
            # verb_first_hits' offset is the *verb*; its window is verb ± R. Index verb hits by target word.
            by_word = defaultdict(list)
            for v in verbs:
                by_word[v["target_word"].lower()].append(v)
            for n in nouns:
                off = n["target_char_offset"]
                match = next((v for v in by_word.get(n["target_word"].lower(), [])
                              if v["target_char_offset"] - R <= off <= v["target_char_offset"] + R), None)
                n["record_id"] = f"{fn}__tri__{off}__{n['target_word']}"
                n["stratum"] = w.stratum
                n["verb_selected"] = match is not None
                if match is not None:
                    n["verb_discovery_verb"] = match["discovery_verb"]
                    n["verb_frame_hint"] = match["frame_hint"]
                    v = {**match, "record_id": f"{fn}__triv__{off}__{n['target_word']}",
                         "stratum": w.stratum, "pair_record_id": n["record_id"]}
                    verb_rows.append(v)
                food_rows.append(n)
            attach_tei_scope_to_rows([r for r in food_rows if r["source_path"] == fn], located=rendered.located)
            el = time.monotonic() - t0
            print(f"  {i}/{len(works)} {fn}: {len(nouns)} nouns, {len(verbs)} verb hits "
                  f"({el / 60:.1f} min)", flush=True)

    # one verb row per verb hit, even if it contains several occurrences of its word
    seen, dedup = set(), []
    for v in verb_rows:
        key = (v["source_path"], v["target_char_offset"])
        if key not in seen:
            seen.add(key)
            dedup.append(v)
    for rows, name, desc in ((food_rows, food_name, "every food-noun occurrence, uncapped, noun-centred"),
                             (dedup, verb_name, "verb-route rows (verb-centred) for verb-selected occurrences")):
        out = save_semi_structured(rows, logical_name=name, parent_sources=["dbnl_xml"],
                                   description=f"T1b triangulation sample (40 works): {desc}", script=SCRIPT)
        print(f"wrote {len(rows)} rows -> {out}", flush=True)


def estimate(tag: str = "") -> None:
    def load(name):
        with open(resolve(name), encoding="utf-8") as fh:
            return pd.DataFrame([json.loads(l) for l in fh if l.strip()])
    food_name = FOOD_INPUTS.replace("triangulation_b_", f"triangulation_b_{tag}_") if tag else FOOD_INPUTS
    verb_name = VERB_INPUTS.replace("triangulation_b_", f"triangulation_b_{tag}_") if tag else VERB_INPUTS
    f, v = load(food_name), load(verb_name)
    weak = ~f.text_regime.isin(["RECIPE_PRACTICE", "MEDICAL"])
    per = f.groupby("stratum").agg(works=("source_path", "nunique"), occurrences=("record_id", "size"),
                                   verb_selected=("verb_selected", "sum"))
    per["verb_share"] = (per.verb_selected / per.occurrences).round(3)
    per["occ_per_work_median"] = f.groupby(["stratum", "source_path"]).size().groupby("stratum").median()
    calls_food = CALLS_PER_ROW * (weak.sum() * (1 - SIEVE_SAVING) + (~weak).sum())
    calls_verb = CALLS_PER_ROW * len(v) * (1 - SIEVE_SAVING)
    top = f.groupby("source_path").size().sort_values(ascending=False).head(5)
    lines = ["# T1b cost estimate (gate G2 / G2a)", "",
             f"Works: {f.source_path.nunique()}. Food-anchored occurrences: {len(f)}; verb-selected: "
             f"{int(f.verb_selected.sum())} ({f.verb_selected.mean():.1%}). Verb-centred rows: {len(v)}.", "",
             per.reset_index().to_markdown(index=False), "",
             "Largest works (occurrences):", "", top.to_frame("n").to_markdown(), "",
             f"Estimated LLM calls ({CALLS_PER_ROW}/row; Step A sieve saves ~{SIEVE_SAVING:.0%} outside RECIPE/MEDICAL, "
             "a rough figure since the sieve's saving was measured on verb rows):", "",
             f"- food-anchored: **~{calls_food:,.0f}**", f"- verb-centred: **~{calls_verb:,.0f}**", "",
             f"G2a (power): passages with both anchors = {int(f.verb_selected.sum())} (want ≥ ~100).", ""]
    (OUT / (f"estimate_{tag}.md" if tag else "estimate.md")).write_text("\n".join(lines))
    print("\n".join(lines))


def select(tag: str = "") -> None:
    """G2 decision (Rik, 12 Nov 2026): about 4k rows instead of 44k. Each row gets a `tri_set`:

    - `verb_noun`: verb-selected occurrence, noun-centred (RECIPE capped at RECIPE_VERB_CAP, evenly spaced);
    - `verb_verb`: the same occurrence's verb-centred row;
    - `food_only`: random non-verb-selected occurrence, PER_STRATUM_FOOD_ONLY per stratum; the weight is the
      stratum's non-verb-selected total divided by the sample size.
    """
    def load(name):
        with open(resolve(name), encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]
    t = (lambda n: n.replace("triangulation_b_", f"triangulation_b_{tag}_")) if tag else (lambda n: n)
    food_name, verb_name, run_name = t(FOOD_INPUTS), t(VERB_INPUTS), t(RUN_INPUTS)
    caps = VERB_CAPS_TAGGED if tag else {"RECIPE": RECIPE_VERB_CAP}
    food, verb = load(food_name), load(verb_name)
    verb_by_pair = {v["pair_record_id"]: v for v in verb}
    rng = random.Random(SEED)
    run, weights = [], {}
    by_stratum = defaultdict(lambda: {"verb": [], "food_only": []})
    for r in food:
        by_stratum[r["stratum"]]["verb" if r["verb_selected"] else "food_only"].append(r)
    for stratum, d in sorted(by_stratum.items()):
        vs = sorted(d["verb"], key=lambda r: (r["source_path"], r["target_char_offset"]))
        cap = caps.get(stratum)
        if cap and len(vs) > cap:
            vs = [vs[k * len(vs) // cap] for k in range(cap)]      # evenly spaced over the works
        for r in vs:
            run.append({**r, "tri_set": "verb_noun", "tri_weight": 1.0})
            v = verb_by_pair.get(r["record_id"])
            if v is not None:
                run.append({**v, "tri_set": "verb_verb", "tri_weight": 1.0})
        fo = d["food_only"]
        take = rng.sample(fo, min(PER_STRATUM_FOOD_ONLY, len(fo)))
        w = len(fo) / max(len(take), 1)
        weights[stratum] = {"food_only_total": len(fo), "sampled": len(take), "weight": round(w, 3),
                            "verb_selected_total": len(d["verb"]), "verb_selected_run": len(vs)}
        run += [{**r, "tri_set": "food_only", "tri_weight": w} for r in take]
    seen, dedup = set(), []
    for r in run:                      # a verb-centred row can serve two occurrences of the same word
        if r["record_id"] not in seen:
            seen.add(r["record_id"])
            dedup.append(r)
    (OUT / (f"weights_{tag}.json" if tag else "weights.json")).write_text(json.dumps(weights, indent=2, ensure_ascii=False))
    out = save_semi_structured(dedup, logical_name=run_name, parent_sources=[food_name, verb_name],
                               description="T1b annotation set (G2: verb-selected + verb-centred + 200 food-only/stratum)",
                               script=SCRIPT)
    print(json.dumps(weights, indent=1, ensure_ascii=False))
    print(f"wrote {len(dedup)} rows -> {out}; " + ", ".join(f"{k}: {v}" for k, v in Counter(r['tri_set'] for r in dedup).items()))


ROUTED_FROM = "v3f"  # the harvest the full routed run is drawn from


def routed() -> None:
    """Routing decision (Rik, 18 Nov 2026): every food word in recipe books, verb-selected occurrences elsewhere
    (medical books included), noun-centred only. Writes `triangulation_b_routed_run_kwic_inputs` and seeds
    `triangulation_b_routed_annotations` with the v3f annotations of the same record_id *and* context_text, so
    `annotate --tag routed` (resume on record_id) only runs the rest. Refuses to overwrite either file."""
    src = f"triangulation_b_{ROUTED_FROM}_"
    run_name, ann_name = "triangulation_b_routed_run_kwic_inputs", "triangulation_b_routed_annotations"
    if Path(resolve(run_name)).exists() or Path(resolve(ann_name)).exists():
        raise SystemExit(f"{run_name} or {ann_name} exists; move it aside to rebuild")
    with open(resolve(src + "kwic_inputs"), encoding="utf-8") as fh:
        food = [json.loads(l) for l in fh if l.strip()]
    run = [{**r, "tri_set": "routed_recipe" if r["stratum"] == "RECIPE" else "routed_verb", "tri_weight": 1.0}
           for r in food if r["stratum"] == "RECIPE" or r["verb_selected"]]
    out = save_semi_structured(run, logical_name=run_name, parent_sources=[src + "kwic_inputs"],
                               description="Full routed run: recipe books all food words, verb route elsewhere",
                               script=SCRIPT)
    ctx = {r["record_id"]: r["context_text"] for r in run}
    kept = 0
    with open(resolve(src + "annotations"), encoding="utf-8") as fh, \
            open(resolve(ann_name), "w", encoding="utf-8") as oh:
        for line in fh:
            if not line.strip():
                continue
            a = json.loads(line)
            p = a.get("provenance") or {}
            if not a.get("error") and ctx.get(p.get("record_id")) == p.get("context_text"):
                oh.write(line if line.endswith("\n") else line + "\n")
                kept += 1
    print(f"wrote {len(run)} rows -> {out}; " + ", ".join(f"{k}: {v}" for k, v in Counter(r['tri_set'] for r in run).items()))
    print(f"seeded {kept} annotations from {ROUTED_FROM}; {len(run) - kept} to annotate "
          f"(~{(len(run) - kept) * 3 / 3600:.1f} h at 3 s each)")


def annotate(tag: str = "", retry_errors: bool = True) -> None:
    from trifecta_annotation.batch import load_inputs, run_batch

    t = (lambda n: n.replace("triangulation_b_", f"triangulation_b_{tag}_")) if tag else (lambda n: n)
    run_inputs, run_annotations = t(RUN_INPUTS), t(RUN_ANNOTATIONS)
    model_dir = Path(resolve("trifecta_step_a_keepdrop_models")) / "globertise-keepdrop" / "model"
    run_batch(
        load_inputs(input_logical=run_inputs), output_logical=run_annotations, resume=True,
        parent_sources=[run_inputs], step_a_sieve_model=model_dir,
        description="A->B->C annotations for the T1b triangulation set (local Ollama, Step A sieve as routed)",
        script=SCRIPT, retry_errors=retry_errors,
    )


def report(tag: str = "") -> None:
    """Measures fixed before the labels were seen (12 Nov 2026):

    1. frame yield per set, with Wilson CI; food_only also weighted up to its stratum totals, giving the
       estimated frames the food route adds beyond the verb route;
    2. centring: verb_noun vs verb_verb label on the same occurrence (agreement, CI, crosstab);
    3. frame mix per set;
    4. reading lists for Rik: centring disagreements, and 100 random food_only frames (precision check).
    """
    from scripts.eval_gold_by_position import label, wilson

    t = (lambda n: n.replace("triangulation_b_", f"triangulation_b_{tag}_")) if tag else (lambda n: n)
    sfx = f"_{tag}" if tag else ""
    inputs = {}
    with open(resolve(t(RUN_INPUTS)), encoding="utf-8") as fh:
        for l in fh:
            if l.strip():
                r = json.loads(l)
                inputs[r["record_id"]] = r
    rows = []
    with open(resolve(t(RUN_ANNOTATIONS)), encoding="utf-8") as fh:
        for l in fh:
            if not l.strip():
                continue
            a = json.loads(l)
            inp = inputs.get(a["provenance"]["record_id"])
            if inp is None:
                continue
            rows.append({"record_id": inp["record_id"], "set": inp["tri_set"], "stratum": inp["stratum"],
                         "weight": inp["tri_weight"], "pair": inp.get("pair_record_id"),
                         "work": inp["source_path"], "target": inp["target_word"],
                         "verb": inp.get("discovery_verb") or inp.get("verb_discovery_verb"),
                         "label": label(a), "error": bool(a.get("error")),
                         "context": inp["context_text"][:300]})
    df = pd.DataFrame(rows)
    REAL = {"COOKING_CREATION", "INGESTION", "CURE", "PRESERVING"}
    df["frame"] = df.label.isin(REAL)
    df.to_csv(OUT / f"rows{sfx}.csv", index=False)

    def ci(k, n):
        lo, hi = wilson(int(k), int(n))
        return f"{k / max(n, 1):.0%} ({lo:.0%}–{hi:.0%})"

    weights = json.loads((OUT / f"weights{sfx}.json").read_text())
    ylines = []
    for st in sorted(df.stratum.unique()):
        d = df[df.stratum == st]
        vn, fo = d[d.set == "verb_noun"], d[d.set == "food_only"]
        w = weights[st]
        est_food = fo.frame.mean() * w["food_only_total"] if len(fo) else float("nan")
        est_verb = vn.frame.mean() * w["verb_selected_total"] if len(vn) else 0
        ylines.append({"stratum": st, "verb-selected yield": ci(vn.frame.sum(), len(vn)),
                       "food-only yield": ci(fo.frame.sum(), len(fo)),
                       "est. frames via verb route": round(est_verb), "est. frames food-only": round(est_food)})
    yt = pd.DataFrame(ylines)

    vn = df[df.set == "verb_noun"].set_index("record_id")
    vv = df[df.set == "verb_verb"].dropna(subset=["pair"]).set_index("pair")
    pairs = vn.join(vv[["label"]], rsuffix="_verbctx", how="inner")
    same = int((pairs.label == pairs.label_verbctx).sum())
    fo_frames = df[(df.set == "food_only") & df.frame].sample(frac=1, random_state=SEED).head(100)
    fo_frames[["work", "stratum", "target", "label", "context"]].assign(rik_correct="").to_csv(
        OUT / f"read_food_only_frames{sfx}.csv", index=False)
    dis = pairs[pairs.label != pairs.label_verbctx]
    dis[["work", "target", "verb", "label", "label_verbctx", "context"]].assign(rik_which="").to_csv(
        OUT / f"read_centring_disagreements{sfx}.csv")

    lines = [
        f"# T1b: passage-first triangulation ({df.work.nunique()} works){' — ' + tag if tag else ''}", "",
        f"Rows annotated: {len(df)} of {len(inputs)} ({int(df.error.sum())} errors). "
        "Yield = share of rows with a real frame (CC/ING/CURE/PRES), Wilson 95% CI.", "",
        "## 1. Yield per route, and frames the food route adds", "",
        yt.to_markdown(index=False), "",
        f"Totals: est. frames via verb route ≈ {int(yt['est. frames via verb route'].sum())}, "
        f"food-only ≈ {int(yt['est. frames food-only'].fillna(0).sum())} (weighted; precision unverified until "
        "`read_food_only_frames.csv` is read).", "",
        "## 2. Context centring: same occurrence, noun-centred vs verb-centred", "",
        f"Pairs: {len(pairs)}; same label: {ci(same, len(pairs))}.", "",
        pd.crosstab(pairs.label, pairs.label_verbctx).to_markdown(), "",
        "## 3. Frame mix per set", "",
        pd.crosstab(df.set, df.label).to_markdown(), "",
        "## 4. To read", "",
        f"- `read_food_only_frames.csv`: 100 random food-only frames; fill in `rik_correct` (gate G3 input).",
        f"- `read_centring_disagreements.csv`: {len(dis)} rows; fill in `rik_which` (noun / verb / neither).", "",
    ]
    (OUT / f"report{sfx}.md").write_text("\n".join(lines))
    print("\n".join(lines))


def routed_report() -> None:
    """Frames per genre in the full routed run. Descriptive only: recipe books went through the food route and
    the other genres through the verb route, and works were drawn per genre by quota, so shares of frames are
    not comparable across routes and counts are not corpus totals. Writes report_routed.md."""
    from scripts.eval_gold_by_position import label

    frames = ["COOKING_CREATION", "CURE", "INGESTION", "PRESERVING"]
    with open(resolve("triangulation_b_routed_run_kwic_inputs"), encoding="utf-8") as fh:
        inputs = {r["record_id"]: r for r in map(json.loads, filter(str.strip, fh))}
    rows = []
    with open(resolve("triangulation_b_routed_annotations"), encoding="utf-8") as fh:
        for a in map(json.loads, filter(str.strip, fh)):
            i = inputs[a["provenance"]["record_id"]]
            rows.append({"genre": i["stratum"], "route": "food" if i["tri_set"] == "routed_recipe" else "verb",
                         "work": i["source_path"], "label": "ERROR" if a.get("error") else label(a)})
    df = pd.DataFrame(rows)
    df["frame"] = df.label.isin(frames)
    ok = df[df.label != "ERROR"]
    table = []
    for genre, d in ok.groupby("genre"):
        f = d[d.frame]
        top = f.work.value_counts(normalize=True)
        table.append({"genre": genre, "route": d.route.iloc[0], "works": d.work.nunique(), "passages": len(d),
                      "frames": len(f), "frame share": f"{len(f) / len(d):.0%}",
                      "largest work's share of frames": f"{top.iloc[0]:.0%}" if len(top) else "-"})
    mix = pd.crosstab(ok[ok.frame].genre, ok[ok.frame].label)
    lines = [
        "# Full routed run: frames per genre", "",
        f"{len(df):,} passages from {df.work.nunique()} works; {int((df.label == 'ERROR').sum())} timed out and are "
        f"left out below; {int(ok.frame.sum()):,} frames.", "",
        "Recipe books: every food word. Other genres: food words with a reviewed verb nearby. Shares are not "
        "comparable across the two routes, and works were drawn per genre by quota, so counts are not corpus "
        "totals. Frames are model output; read precision outside recipe books was 72% (62-80%).", "",
        pd.DataFrame(table).to_markdown(index=False), "", "## Frame mix (counts)", "", mix.to_markdown(), "",
    ]
    (OUT / "report_routed.md").write_text("\n".join(lines))
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "extend", "harvest", "estimate", "select", "annotate", "report", "routed", "routed-report"])
    ap.add_argument("--tag", default="", help="harvest/estimate: write and read triangulation_b_<tag>_* (e.g. v3)")
    ap.add_argument("--skip-errors", action="store_true",
                    help="annotate: keep earlier error rows as they are instead of retrying them")
    a = ap.parse_args()
    if a.cmd == "annotate":
        annotate(a.tag, retry_errors=not a.skip_errors)
        return
    if a.cmd in ("harvest", "estimate", "select", "annotate", "report"):
        {"harvest": harvest, "estimate": estimate, "select": select, "annotate": annotate,
         "report": report}[a.cmd](a.tag)
        return
    {"sample": sample, "extend": extend, "routed": routed, "routed-report": routed_report}[a.cmd]()


if __name__ == "__main__":
    main()
