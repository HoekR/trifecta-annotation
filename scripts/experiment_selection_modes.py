"""Controlled comparison of candidate-selection modes on identical material.

PLAN.md §9i could only compare selection modes observationally, and every
reading was confounded. This settles it by design: per work, one fixed random
pool of food-mention windows; each mode ranks that same pool; the union of each
mode's top N is annotated once by the normal A->B->C cascade.

Modes:
  verb_food        best `score_snippet_for_frame` confidence over the food
                   frames; mentions with no qualifying verb are not selectable
                   (as in production)
  embedding        best food-frame centroid cosine minus NONE cosine (GysBERT;
                   exemplars from the test works are excluded)
  noun             random order — the unscored baseline
  entry_scope      random among mentions whose governing TEI entry head names a
                   goal (`regime_from_tei_scope_head` -> MEDICAL/RECIPE), verb
                   or no verb: the route for structurally-evoked frames
  entry_scope_head the same mentions, with the entry head prepended to the
                   context ("[Kopje: ...]") — tests whether the cascade can use
                   intention that lives in the head rather than the sentence

The report gives Step A survival and real-frame yield per mode, plus how many
real frames each mode finds that `verb_food` can never reach (mention has no
qualifying verb) — the complementarity question.

v1 (commit 23a859d, results in experiments/selection_modes/) ran 3 works and the
first three modes; this is v2.

    uv run python scripts/experiment_selection_modes.py all
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

OUT_DIR = Path(resolve("trifecta_annotations")).parent / "experiments" / "selection_modes_v2"
SELECTION = OUT_DIR / "selection.jsonl"
META = OUT_DIR / "meta.json"
ANNOTATIONS = OUT_DIR / "annotations.jsonl"
REPORT = OUT_DIR / "report.md"

POOL_SIZE = 1500
TOP_N = 60
SEED = 0
WORKS_PER_SWEEP_REGIME = 3
FIXED_WORKS = [
    ("chom003huis01_01.xml", "Huishoudelyk woordboek", "RECIPE_PRACTICE"),
    ("bate002secr02_01.xml", "Het secreet-boek vol heerlijke konsten", "RECIPE_PRACTICE"),
    ("_vol002volm01_01.xml", "De volmaakte Hollandsche keuken-meid", "RECIPE_PRACTICE"),
    ("_pha001phar05_01.xml", "Pharmacopoea Amstelredamensis", "MEDICAL"),
]
import re

_BIBLE = re.compile(r"\b(biblia|bijbel|bible)\b", re.IGNORECASE)
MODES = ("verb_food", "embedding", "noun", "entry_scope", "entry_scope_head")


def _pick_works() -> list[tuple[str, str, str]]:
    """Fixed recipe/medical works plus the largest LITERARY / UNKNOWN sweep
    works, skipping near-duplicate titles (e.g. several Bible editions)."""
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
    by_regime: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for c in cands:
        title = c["titel"] or c["ti_id"]
        regime = infer_text_regime(corpus="dbnl_full_sweep_2026", title=title, source_path=c["filename"]).value
        if regime in ("LITERARY", "UNKNOWN"):
            by_regime[regime].append((sizes.get(c["filename"], 0), c["filename"], title))
    works = list(FIXED_WORKS)
    for regime in ("LITERARY", "UNKNOWN"):
        seen_prefixes: set[str] = set()
        for _, fn, title in sorted(by_regime[regime], reverse=True):
            prefix = "bible" if _BIBLE.search(title) else title[:12].lower()
            if prefix in seen_prefixes:
                continue
            seen_prefixes.add(prefix)
            works.append((fn, title, regime))
            if len(seen_prefixes) >= WORKS_PER_SWEEP_REGIME:
                break
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
    from trifecta_annotation.regime_routing import regime_from_tei_scope_head
    from trifecta_annotation.schemas import TrifectaFrame
    from trifecta_annotation.tei_segmentation import entry_for_offset, read_work_xml, render_tei
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
    meta: dict[str, dict] = {}
    pool_stats: dict[str, dict] = {}
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
        print(f"[{regime_name}] {title[:60]!r}: {len(hits)} mentions, pool {len(pool)}", flush=True)

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
            if (i + 1) % 500 == 0:
                print(f"   verb-scored {i + 1}/{len(pool)}", flush=True)

        scopes: list[str | None] = []
        for row in pool:
            entry = entry_for_offset(rendered.located, row["target_char_offset"]) if rendered.located else None
            scopes.append((entry.scope_head or entry.head) if entry is not None else None)
        goal = [s is not None and regime_from_tei_scope_head(s) is not None for s in scopes]

        vecs = embedder.encode([r["context_text"] for r in pool])
        none_sim = vecs @ centroids["NONE"]
        frame_sim = np.max(np.stack([vecs @ centroids[f] for f in FOOD_QUERY_FRAMES if f in centroids]), axis=0)
        emb_scores = (frame_sim - none_sim).tolist()

        idx = list(range(len(pool)))
        verb_ranked = sorted((i for i in idx if verb_scores[i] is not None), key=lambda i: -verb_scores[i])
        emb_ranked = sorted(idx, key=lambda i: -emb_scores[i])
        noun_ranked = idx[:]
        rng.shuffle(noun_ranked)
        scope_ranked = [i for i in idx if goal[i]]
        rng.shuffle(scope_ranked)
        pool_stats[fn] = {
            "title": title, "regime": regime_name, "mentions": len(hits), "pool": len(pool),
            "verb_selectable": len(verb_ranked), "scope_selectable": len(scope_ranked),
            "entries_located": len(rendered.located),
        }
        print(f"   verb-selectable {len(verb_ranked)}, scope-selectable {len(scope_ranked)} "
              f"({time.monotonic() - t0:.0f}s)", flush=True)

        chosen: dict[int, list[str]] = defaultdict(list)
        for mode, ranked in (("verb_food", verb_ranked), ("embedding", emb_ranked),
                             ("noun", noun_ranked), ("entry_scope", scope_ranked)):
            for i in ranked[:TOP_N]:
                chosen[i].append(mode)
        for i, mode_list in chosen.items():
            base = dict(pool[i])
            base_id = f"selexp2__{base['record_id']}"
            info = {"work": fn, "regime": regime_name, "verb_selectable": verb_scores[i] is not None,
                    "scope": scopes[i]}
            row = dict(base, record_id=base_id, kwic_mode="selection_experiment")
            selection.append(row)
            meta[base_id] = dict(info, modes=mode_list, base=base_id)
            if "entry_scope" in mode_list:
                head_id = f"selexp2__head__{base['record_id']}"
                head_row = dict(
                    base, record_id=head_id, kwic_mode="selection_experiment",
                    context_text=f"[Kopje: {scopes[i]}] {base['context_text']}",
                    structural_header=scopes[i],
                )
                selection.append(head_row)
                meta[head_id] = dict(info, modes=["entry_scope_head"], base=base_id)

    with SELECTION.open("w", encoding="utf-8") as h:
        for row in selection:
            h.write(json.dumps(row, ensure_ascii=False) + "\n")
    META.write_text(json.dumps({"works": works, "pool_stats": pool_stats, "records": meta},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(selection)} candidates -> {SELECTION}", flush=True)


def annotate() -> None:
    from trifecta_annotation.batch import load_inputs, run_batch

    run_batch(
        load_inputs(input_path=SELECTION),
        output_path=ANNOTATIONS,
        resume=True,
        description="Selection-mode experiment v2: same pool, five selection modes",
        script="scripts/experiment_selection_modes.py",
    )


def report() -> None:
    meta = json.loads(META.read_text(encoding="utf-8"))
    records, pool_stats = meta["records"], meta["pool_stats"]
    stats: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0, 0])  # n, A, frame, frame unreachable by verb
    errors = 0
    for line in ANNOTATIONS.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        info = records.get(r["provenance"]["record_id"])
        if info is None:
            continue
        if r.get("error"):
            errors += 1
            continue
        survived = not r.get("dropped")
        frame = (r.get("step_b") or {}).get("selected_frame")
        real = survived and frame not in (None, "NONE")
        unreachable = real and not info["verb_selectable"]
        for mode in info["modes"]:
            for key in ((info["regime"], mode), ("ALL", mode)):
                s = stats[key]
                s[0] += 1
                s[1] += survived
                s[2] += real
                s[3] += unreachable

    lines = [
        "# Selection-mode experiment v2", "",
        f"Pool {POOL_SIZE} mentions/work, top {TOP_N}/mode, seed {SEED}. Errors excluded: {errors}.", "",
        "## Works", "",
        "| regime | work | mentions | verb-selectable | scope-selectable | TEI entries |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for fn, ps in pool_stats.items():
        lines.append(f"| {ps['regime']} | {ps['title'][:50]} (`{fn}`) | {ps['mentions']} | "
                     f"{ps['verb_selectable']}/{ps['pool']} | {ps['scope_selectable']}/{ps['pool']} | "
                     f"{ps['entries_located']} |")
    lines += [
        "", "## Results", "",
        "`unreachable by verb` = real frames on mentions with no qualifying verb, which `verb_food` can never select.",
        "", "| regime | mode | n | survive Step A | real frame | unreachable by verb |",
        "|---|---|---:|---:|---:|---:|",
    ]
    order = {m: i for i, m in enumerate(MODES)}
    for (regime, mode), (n, a, f, u) in sorted(stats.items(), key=lambda kv: (kv[0][0], order.get(kv[0][1], 9))):
        lines.append(f"| {regime} | {mode} | {n} | {a / n:.0%} ({a}) | {f / n:.0%} ({f}) | {u} |")
    lines += ["", "Note: entry-scope selection uses production's `regime_from_tei_scope_head` cues, "
              "which have their own false positives (`manier om` matches 'Andere manier om Aal te vangen')."]
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
