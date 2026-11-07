"""Controlled comparison of candidate-selection modes on identical material.

PLAN.md §9i could only compare selection modes observationally, and every
reading was confounded (corpus era, work selection, noun-fallback filling only
bins where no verb fired). This settles it by design:

1. For each of a few works (one per regime), take a fixed random pool of food
   mention windows (the plain `scan_text` hits, i.e. every mention).
2. Each mode ranks that same pool:
   - verb_food: best `score_snippet_for_frame` confidence over the four food
     frames (windows with no qualifying verb are not selectable by this mode,
     as in production);
   - embedding: best food-frame centroid cosine minus NONE-centroid cosine
     (GysBERT, centroids from gold exemplars, excluding exemplars from the
     test works themselves to avoid near-duplicate matching);
   - noun: random order (the unscored baseline).
3. Top-N per mode; the union is annotated once by the normal A->B->C cascade.
4. Report Step A survival and real-frame yield per mode and work.

Phases (each skips work already done, so it is safe to re-run):
    uv run python scripts/experiment_selection_modes.py select
    uv run python scripts/experiment_selection_modes.py annotate   # local Ollama
    uv run python scripts/experiment_selection_modes.py report
"""
from __future__ import annotations

import argparse
import json
import random
import time
import zipfile
from collections import defaultdict
from pathlib import Path

from data_io import resolve

OUT_DIR = Path(resolve("trifecta_annotations")).parent / "experiments" / "selection_modes"
SELECTION = OUT_DIR / "selection.jsonl"   # KwicInput rows to annotate
MODES = OUT_DIR / "modes.json"            # record_id -> [modes that selected it]
ANNOTATIONS = OUT_DIR / "annotations.jsonl"
REPORT = OUT_DIR / "report.md"

POOL_SIZE = 1500
TOP_N = 40
SEED = 0
RECIPE_WORK = ("chom003huis01_01.xml", "Huishoudelyk woordboek")


def _pick_works() -> list[tuple[str, str, str]]:
    """(filename, title, regime): Chomel for RECIPE_PRACTICE, and the largest
    sweep work whose inferred regime is LITERARY / UNKNOWN."""
    from scripts.build_colonial_kwic import ingested_dbnl_stems
    from trifecta_annotation.corpus_genre_join import load_genre_records
    from trifecta_annotation.dbnl_genre import sweep_candidates, xml_filenames_by_stem
    from trifecta_annotation.text_regime import infer_text_regime

    zip_path = resolve("dbnl_xml")
    cands = sweep_candidates(
        load_genre_records(),
        filenames_by_stem=xml_filenames_by_stem(zip_path),
        exclude_stems=ingested_dbnl_stems(),
    )
    with zipfile.ZipFile(zip_path) as archive:
        sizes = {i.filename: i.file_size for i in archive.infolist()}
    best: dict[str, tuple[int, str, str]] = {}
    for c in cands:
        title = c["titel"] or c["ti_id"]
        regime = infer_text_regime(corpus="dbnl_full_sweep_2026", title=title, source_path=c["filename"]).value
        if regime not in ("LITERARY", "UNKNOWN"):
            continue
        size = sizes.get(c["filename"], 0)
        if size > best.get(regime, (0, "", ""))[0]:
            best[regime] = (size, c["filename"], title)
    works = [(RECIPE_WORK[0], RECIPE_WORK[1], "RECIPE_PRACTICE")]
    for regime in ("LITERARY", "UNKNOWN"):
        _, fn, title = best[regime]
        works.append((fn, title, regime))
    return works


def select() -> None:
    import numpy as np

    from scripts.build_colonial_kwic import build_term_pattern, scan_text
    from trifecta_annotation.clear_frame_examples import score_snippet_for_frame
    from trifecta_annotation.embedding_candidates import (
        FOOD_QUERY_FRAMES,
        GysbertEmbedder,
        frame_centroids_from_embeddings,
        load_exemplars_jsonl,
    )
    from trifecta_annotation.schemas import TrifectaFrame
    from trifecta_annotation.tei_segmentation import read_work_xml, render_tei
    from trifecta_annotation.text_regime import TextRegime
    from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    works = _pick_works()
    print("works:", works, flush=True)
    test_files = {fn for fn, _, _ in works}

    terms = load_food_terms()
    canonical = alt_label_index(terms)
    all_terms = set(canonical) | {str(p).strip().lower() for p in terms["Pref_label"].dropna()}
    pattern = build_term_pattern({t: t for t in all_terms})
    food_terms_list = sorted(all_terms)

    exemplars = load_exemplars_jsonl(resolve("embedding_exemplars"))
    excluded = 0
    for frame, rows in exemplars.items():
        kept = [r for r in rows if str(r.get("record_id", "")).split("__")[0] not in test_files]
        excluded += len(rows) - len(kept)
        exemplars[frame] = kept
    print(f"exemplars: excluded {excluded} from test works", flush=True)

    embedder = GysbertEmbedder()
    centroids = frame_centroids_from_embeddings(exemplars, lambda t: embedder.encode(t))
    rng = random.Random(SEED)

    selection: list[dict] = []
    modes: dict[str, list[str]] = defaultdict(list)
    for fn, title, regime_name in works:
        t0 = time.monotonic()
        rendered = render_tei(read_work_xml(resolve("dbnl_xml"), fn), work_id=fn)
        regime = TextRegime(regime_name)
        hits = scan_text(
            rendered.text, pattern=pattern, canonical=canonical,
            source_path=fn, title=title, corpus="selection_mode_experiment",
            date=None, regime=regime,
        )
        pool = rng.sample(hits, min(POOL_SIZE, len(hits)))
        print(f"[{regime_name}] {title!r}: {len(hits)} mentions, pool {len(pool)}", flush=True)

        verb_scores: list[float | None] = []
        for i, row in enumerate(pool):
            best = None
            for frame_name in FOOD_QUERY_FRAMES:
                cand = score_snippet_for_frame(
                    row["context_text"], food_terms_list, TrifectaFrame(frame_name), regime=regime,
                )
                if cand is not None and (best is None or cand.confidence_score > best):
                    best = cand.confidence_score
            verb_scores.append(best)
            if (i + 1) % 250 == 0:
                print(f"   verb-scored {i + 1}/{len(pool)}", flush=True)

        vecs = embedder.encode([r["context_text"] for r in pool])
        none_sim = vecs @ centroids["NONE"]
        frame_sim = np.max(np.stack([vecs @ centroids[f] for f in FOOD_QUERY_FRAMES if f in centroids]), axis=0)
        emb_scores = (frame_sim - none_sim).tolist()

        idx = list(range(len(pool)))
        verb_ranked = sorted((i for i in idx if verb_scores[i] is not None), key=lambda i: -verb_scores[i])
        emb_ranked = sorted(idx, key=lambda i: -emb_scores[i])
        noun_ranked = idx[:]
        rng.shuffle(noun_ranked)
        print(f"   verb-selectable: {len(verb_ranked)}  ({time.monotonic() - t0:.0f}s)", flush=True)

        chosen: dict[int, list[str]] = defaultdict(list)
        for mode, ranked in (("verb_food", verb_ranked), ("embedding", emb_ranked), ("noun", noun_ranked)):
            for i in ranked[:TOP_N]:
                chosen[i].append(mode)
        for i, mode_list in chosen.items():
            row = dict(pool[i])
            row["record_id"] = f"selexp__{row['record_id']}"
            row["kwic_mode"] = "selection_experiment"
            selection.append(row)
            modes[row["record_id"]] = mode_list

    with SELECTION.open("w", encoding="utf-8") as h:
        for row in selection:
            h.write(json.dumps(row, ensure_ascii=False) + "\n")
    MODES.write_text(json.dumps({"works": works, "modes": modes}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(selection)} unique candidates -> {SELECTION}", flush=True)


def annotate() -> None:
    from trifecta_annotation.batch import load_inputs, run_batch

    run_batch(
        load_inputs(input_path=SELECTION),
        output_path=ANNOTATIONS,
        resume=True,
        description="Selection-mode experiment: same pool, three selection modes",
        script="scripts/experiment_selection_modes.py",
    )


def report() -> None:
    meta = json.loads(MODES.read_text(encoding="utf-8"))
    modes, works = meta["modes"], meta["works"]
    regime_of = {fn: regime for fn, _, regime in works}
    stats: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])  # n, survived A, real frame
    errors = 0
    for line in ANNOTATIONS.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("error"):
            errors += 1
            continue
        prov = r["provenance"]
        regime = regime_of.get(prov["source_path"], "?")
        survived = not r.get("dropped")
        frame = (r.get("step_b") or {}).get("selected_frame")
        real = survived and frame not in (None, "NONE")
        for mode in modes.get(prov["record_id"], []):
            for key in ((regime, mode), ("ALL", mode)):
                s = stats[key]
                s[0] += 1
                s[1] += survived
                s[2] += real

    lines = ["# Selection-mode experiment", "",
             f"Pool {POOL_SIZE} mentions/work, top {TOP_N}/mode, seed {SEED}. Errors excluded: {errors}.", "",
             "Works: " + "; ".join(f"{r}: {t} ({f})" for f, t, r in works), "",
             "| regime | mode | n | survive Step A | real frame |", "|---|---|---:|---:|---:|"]
    for (regime, mode), (n, a, f) in sorted(stats.items()):
        lines.append(f"| {regime} | {mode} | {n} | {a / n:.0%} ({a}) | {f / n:.0%} ({f}) |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phase", choices=["select", "annotate", "report", "all"])
    args = parser.parse_args()
    if args.phase in ("select", "all") and not SELECTION.exists():
        select()
    if args.phase in ("annotate", "all"):
        annotate()
    if args.phase in ("report", "all"):
        report()


if __name__ == "__main__":
    main()
