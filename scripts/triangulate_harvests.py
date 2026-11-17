"""Triangulate the food-first and verb-first harvests over the same DBNL works (read-only).

Food-first = the 2026 sweep's noun-fallback rows (`kwic_mode` None). Verb-first = the sweep's `verb_food`
rows plus the weak-regime verb harvest. The weak-regime harvest dropped contexts the sweep already had,
so the two never share an exact row; they meet as *neighbours* (target offsets within `--window` chars).

Per food-first row:

- reachability: does the verb route, uncapped (the full candidate pool `capped_candidates` would draw
  from), have a hit within the window? If not, the frame is unreachable by verb;
- cross-check: the labels of annotated verb-first rows within the window, against the food-first label.

Offsets live in `render_tei` text. Weak-regime rows carry them; sweep rows are located by context
(`locate` from eval_gold_by_position). Unlocated rows are counted.

    uv run python scripts/triangulate_harvests.py [--limit N] [--window 150]
    # -> docs/evidence/triangulation/{rows.csv,report.md}
"""

from __future__ import annotations

import argparse
import bisect
import json
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from data_io import resolve
from scripts.build_colonial_kwic import (
    AMBIGUOUS_FUNCTION_WORDS,
    build_term_pattern,
    capped_candidates,
)
from scripts.eval_gold_by_position import label, locate, wilson
from trifecta_annotation.tei_segmentation import render_tei
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "triangulation"
CORPUS = "dbnl_full_sweep_2026"
REAL = {"COOKING_CREATION", "INGESTION", "CURE", "PRESERVING"}


def load(name: str) -> list[dict]:
    with open(resolve(name), encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def kind(lab: str) -> str:
    return "frame" if lab in REAL else "no frame"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--window", type=int, default=150)
    ap.add_argument("--out", default=str(OUT), help="evidence folder (keep earlier runs as baselines)")
    args = ap.parse_args()
    W = args.window
    out = Path(args.out)

    food, verb = defaultdict(list), defaultdict(list)
    for r in load("dbnl_sweep_annotations"):
        pv = r["provenance"]
        (verb if pv.get("kwic_mode") == "verb_food" else food)[pv["source_path"]].append(r)
    for r in load("weak_regime_verb_annotations"):
        pv = r["provenance"]
        if pv.get("kwic_mode") == "verb_food":
            verb[pv["source_path"]].append(r)
    works = sorted(w for w in food if w in verb)
    if args.limit:
        works = works[:args.limit]
    print(f"{len(works)} works with both food-first and verb-first rows", flush=True)

    terms = load_food_terms()
    canonical = alt_label_index(terms)
    all_terms = (set(canonical) | {str(p).strip().lower() for p in terms["Pref_label"].dropna()}) - AMBIGUOUS_FUNCTION_WORDS
    pattern = build_term_pattern({t: t for t in all_terms})
    food_terms_list = sorted(all_terms)

    rows, status = [], Counter()
    t0 = time.monotonic()
    with zipfile.ZipFile(resolve("dbnl_xml")) as archive:
        for i, fn in enumerate(works, 1):
            try:
                rendered = render_tei(archive.read(fn).decode("utf-8", errors="replace"), work_id=fn)
            except Exception as exc:
                status["work unreadable"] += len(food[fn])
                print(f"  skipped {fn}: {type(exc).__name__}", flush=True)
                continue
            text = rendered.text
            low = text.lower()
            pool = capped_candidates(
                text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
                source_path=fn, title=fn, corpus=CORPUS, date=None, units=None, cap=10**9,
                located=rendered.located, entry_scope=False,
            )
            pool_sorted = sorted((int(h["target_char_offset"]), str(h.get("discovery_verb") or "")) for h in pool)
            pool_offs = [o for o, _ in pool_sorted]
            vrows = []
            for v in verb[fn]:
                pv = v["provenance"]
                off = pv.get("target_char_offset")
                off = int(off) if off not in (None, "None") else locate(low, pv.get("context_text", ""), pv.get("target_word", ""))
                if off is None:
                    status["verb row not located"] += 1
                    continue
                vrows.append((off, label(v), pv.get("discovery_verb")))
            vrows.sort()
            v_offs = [o for o, _, _ in vrows]
            for f in food[fn]:
                pv = f["provenance"]
                off = locate(low, pv.get("context_text", ""), pv.get("target_word", ""))
                if off is None:
                    status["food row not located"] += 1
                    continue
                status["food row located"] += 1
                lo_i, hi_i = bisect.bisect_left(pool_offs, off - W), bisect.bisect_right(pool_offs, off + W)
                reach = lo_i < hi_i
                pool_verbs = sorted({v for _, v in pool_sorted[lo_i:hi_i] if v})
                near = vrows[bisect.bisect_left(v_offs, off - W):bisect.bisect_right(v_offs, off + W)]
                vl = [lab for _, lab, _ in near]
                # one verb-side verdict per food row: a real frame if any neighbour has one
                v_frames = [l for l in vl if l in REAL]
                rows.append({
                    "work": fn, "record_id": pv["record_id"], "target": pv.get("target_word"), "offset": off,
                    "food_label": label(f), "verb_reachable": reach, "n_verb_neighbours": len(near),
                    "verb_label": (Counter(v_frames).most_common(1)[0][0] if v_frames else (vl[0] if vl else None)),
                    "verb_verbs": ";".join(sorted({str(d) for _, _, d in near})),
                    # which verbs made the row reachable (C5: a large list can make reach trivial)
                    "pool_verbs": ";".join(pool_verbs),
                    "context": pv.get("context_text", "")[:300],
                })
            if i % 50 == 0 or i == len(works):
                el = time.monotonic() - t0
                print(f"  {i}/{len(works)} works, {len(rows)} food rows located "
                      f"({el / 60:.0f} min, ~{(len(works) - i) * el / i / 60:.0f} min left)", flush=True)

    df = pd.DataFrame(rows)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "rows.csv", index=False)

    df["food_kind"] = df.food_label.map(kind)
    paired = df[df.verb_label.notna()].copy()
    paired["verb_kind"] = paired.verb_label.map(kind)
    frames = df[df.food_kind == "frame"]
    k = int((~frames.verb_reachable).sum())
    lo, hi = wilson(k, len(frames))
    same = int((paired.food_label == paired.verb_label).sum())
    slo, shi = wilson(same, len(paired))

    lines = [
        "# Triangulation: food-first vs verb-first harvests", "",
        f"Works with both: {len(works)}. Window: ±{W} chars around the food-first target. "
        + ", ".join(f"{a}: {b}" for a, b in status.items()) + ".", "",
        "## 1. Reachability: would the verb route have found the food-first row?", "",
        "Verb route uncapped (full candidate pool). Rows by food-first label:", "",
        pd.crosstab(df.food_label, df.verb_reachable, margins=True).to_markdown(), "",
        f"Food-first real frames unreachable by verb: **{k} of {len(frames)}** "
        f"({k / max(len(frames), 1):.0%}, 95% CI {lo:.0%}–{hi:.0%}).", "",
        "## 2. Cross-check: food-first rows with an annotated verb-first neighbour", "",
        f"Paired rows: {len(paired)}. Same label: {same} ({same / max(len(paired), 1):.0%}, 95% CI {slo:.0%}–{shi:.0%}).", "",
        "Frame vs no frame:", "",
        pd.crosstab(paired.food_kind, paired.verb_kind, margins=True).to_markdown(), "",
        "Full labels (rows = food-first, columns = verb-first):", "",
        pd.crosstab(paired.food_label, paired.verb_label).to_markdown(), "",
        "## 3. The disagreement to read: food-first no frame, verb-first neighbour has a frame", "",
        f"{int(((paired.food_kind == 'no frame') & (paired.verb_kind == 'frame')).sum())} rows; "
        "sample (first 25):", "",
    ]
    dis = paired[(paired.food_kind == "no frame") & (paired.verb_kind == "frame")]
    for _, r in dis.head(25).iterrows():
        lines.append(f"- `{r.work}` [{r.target}] food={r.food_label}, verb={r.verb_label} ({r.verb_verbs}): "
                     f"{r.context[:200]!r}")
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
