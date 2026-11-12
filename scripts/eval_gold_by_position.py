"""Gold accuracy by position in the document: does the cascade fail where the purpose sits in a heading?

Read-only. For every gold row from a DBNL TEI work, find its passage in `render_tei`'s text, look up the
governing entry (`entry_for_offset`), and classify where the target word sits:

- `head`: inside the entry's head;
- `near_head`: in the first 200 characters after it;
- `body`: further down the entry.

Plus two facts about the entry: whether its (scope) head carries a recipe/remedy cue
(`regime_from_tei_scope_head`), and whether the head text is inside the row's `context_text`, i.e.
whether the model could see it. Then Step B agreement (gold vs `gold_predictions`) per class, with
Wilson 95% intervals and n.

Rows are located by text, since gold carries no offsets: exact match of the normalised context, else a
60-character window around the target word. Unlocated rows are counted, not dropped silently.

    uv run python scripts/eval_gold_by_position.py
    # -> docs/evidence/gold_by_position/report.md, rows.csv
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from data_io.manifest import DataManager
from trifecta_annotation.regime_routing import regime_from_tei_scope_head
from trifecta_annotation.tei_segmentation import read_work_xml, render_tei

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "gold_by_position"
resolve = DataManager(ROOT / "data_manifest.toml").resolve
NEAR = 200
_WS = re.compile(r"\s+")
# Broader than `regime_from_tei_scope_head` (which misses e.g. "Koors", "om ... te geven", "Zwelling der
# Koejen"): the frame a head *implies*, for this analysis only. Order matters: preserving before cooking.
HEAD_FRAME = [
    ("CURE", re.compile(r"\b(tegen|tegens|voor (de |den |het )?(koo?rts|zwelling|pijn|hoest|kwaal)|koo?rts|zwelling|"
                        r"krankhe|ziekte|pyn|pijn|remedie|middel|genees|geneez|afziedsel|julep|drankje|hartsterk|"
                        r"aamborst|kwalen|heelen)", re.I)),
    ("PRESERVING", re.compile(r"\b(bewaren|bewaart|bewaard|zonder bederf|lang goed|konfy|confy|gekonfyt|inleggen|"
                              r"inmaken|inmaeken|pekel|zouten|rooken|droogen|in te leggen)", re.I)),
    ("COOKING_CREATION", re.compile(r"\b(om\b.{0,60}\bte\b|hoe ?men|manier|bereid|toebereid|te maken|maeken|"
                                    r"braden|koken|kooken|bakken|recept)", re.I)),
]


def head_frame(head: str | None) -> str:
    for frame, rx in HEAD_FRAME:
        if head and rx.search(head):
            return frame
    return ""


def norm(s: str) -> str:
    return _WS.sub(" ", str(s)).strip().lower()


def label(rec: dict) -> str:
    if rec.get("dropped"):
        return "DROPPED"
    f = (rec.get("step_b") or {}).get("selected_frame")
    return f if f else "NONE"


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def locate(text: str, ctx: str, target: str) -> int | None:
    """Offset of the target word in `text` (already normalised), or None."""
    c = norm(ctx)
    t = norm(target)
    ti = c.find(t)
    i = text.find(c)
    if i >= 0:
        return i + max(ti, 0)
    if ti < 0:
        return None
    for w in (60, 40, 25):
        a = max(0, ti - w // 2)
        win = c[a:a + w]
        if len(win) < 15:
            continue
        j = text.find(win)
        if j >= 0 and text.find(win, j + 1) < 0:      # unique only
            return j + (ti - a)
    return None


def main() -> None:
    gold = [json.loads(s) for s in pd.read_parquet(resolve("trifecta_gold"))["annotation_json"]]
    gold = [g for g in gold if str(g["provenance"].get("source_path", "")).endswith(".xml")]
    pred = {}
    with open(resolve("gold_predictions")) as fh:
        for line in fh:
            r = json.loads(line)
            pred[r["provenance"]["record_id"]] = r

    zip_path = resolve("dbnl_xml")
    rows, status = [], Counter()
    by_work: dict[str, list[dict]] = {}
    for g in gold:
        by_work.setdefault(g["provenance"]["source_path"], []).append(g)
    for fn, recs in sorted(by_work.items()):
        try:
            rendered = render_tei(read_work_xml(zip_path, fn), work_id=fn)
        except KeyError:
            status["work not in zip"] += len(recs)
            continue
        text = rendered.text.lower()            # render_tei already collapses whitespace
        located = rendered.located
        starts = [p for p, _ in located]
        for g in recs:
            pv = g["provenance"]
            off = locate(text, pv.get("context_text", ""), pv.get("target_word", ""))
            if off is None:
                status["not located"] += 1
                continue
            import bisect
            k = bisect.bisect_right(starts, off) - 1
            if k < 0:
                status["before first entry"] += 1
                continue
            e_start, entry = located[k]
            head = entry.head or ""
            head_end = e_start + len(head) + 2
            rel = off - head_end
            position = "head" if off < head_end else ("near_head" if rel <= NEAR else "body")
            scope = entry.scope_head or entry.head
            cue = regime_from_tei_scope_head(scope)
            head_seen = bool(head) and norm(head)[:30] in norm(pv.get("context_text", ""))
            p = pred.get(pv["record_id"])
            status["located"] += 1
            rows.append({
                "record_id": pv["record_id"], "work": fn, "target": pv.get("target_word"),
                "position": position, "chars_after_head": max(rel, 0),
                "purpose_head": cue.value if cue else "", "head_frame": head_frame(scope), "head_seen": head_seen,
                "head_kind": entry.head_kind, "scope_inherited": entry.scope_inherited,
                "scope_head": (scope or "")[:80], "gold": label(g),
                "pred": label(p) if p else None,
            })
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "rows.csv", index=False)

    def table(by: list[str]) -> pd.DataFrame:
        d = df.dropna(subset=["pred"])
        out = []
        for key, grp in d.groupby(by):
            k, n = int((grp.gold == grp.pred).sum()), len(grp)
            lo, hi = wilson(k, n)
            key = key if isinstance(key, tuple) else (key,)
            out.append({**dict(zip(by, key)), "n": n, "agree": k, "accuracy": round(k / n, 2),
                        "95% CI": f"{lo:.2f}–{hi:.2f}"})
        return pd.DataFrame(out)

    df["purpose_head"] = df["purpose_head"].fillna("")
    df["head_frame"] = df["head_frame"].fillna("")
    d = df.dropna(subset=["pred"]).assign(purpose=lambda x: x.purpose_head.ne(""))
    lines = ["# Gold accuracy by position in the document", "",
             f"Gold rows from DBNL TEI works: {len(gold)}. " + ", ".join(f"{k}: {v}" for k, v in status.items()) +
             f". With a prediction (`gold_predictions`): {len(d)}.", "",
             "Step B agreement = gold label == predicted label (frame, NONE or DROPPED). Wilson 95% intervals.", "",
             "## By position of the target word", "", table(["position"]).to_markdown(index=False), "",
             "## By whether the entry's head names a purpose (recipe/remedy cue)", "",
             table(["purpose_head"]).to_markdown(index=False), "",
             "## Purpose head × could the model see the head (head text inside the context)?", "",
             d.assign(purpose=d.purpose.map({True: "purpose head", False: "no purpose head"}))
              .pipe(lambda x: x).groupby(["purpose", "head_seen"]).apply(
                  lambda grp: pd.Series({"n": len(grp), "accuracy": round((grp.gold == grp.pred).mean(), 2),
                                         "95% CI": "{:.2f}–{:.2f}".format(*wilson(int((grp.gold == grp.pred).sum()), len(grp)))}),
                  include_groups=False).reset_index().to_markdown(index=False), "",
             "## Gold vs predicted labels where the head names a purpose and the model could not see it", "",
             pd.crosstab(d[d.purpose & ~d.head_seen].gold, d[d.purpose & ~d.head_seen].pred).to_markdown(), "",
             "## Broader head reading: the frame the head implies (`HEAD_FRAME`)", "",
             "Does the production cue (`regime_from_tei_scope_head`) see these heads? Rows per implied frame, and how many"
             " of them the production cue flags:", "",
             d.groupby(d.head_frame.fillna("").replace("", "(none)")).apply(lambda g: pd.Series({"n": len(g),
                 "flagged by production cue": int(g.purpose_head.fillna("").ne("").sum())}), include_groups=False)
              .reset_index().to_markdown(index=False), "",
             "Agreement by implied head frame × head visible to the model:", "",
             table(["head_frame", "head_seen"]).to_markdown(index=False), "",
             "## Where the head implies a frame: is gold that frame, and does the model get it?", "",
             (lambda h: pd.DataFrame({"n": [len(h)], "gold = head frame": [int((h.gold == h.head_frame).sum())],
                 "pred = head frame": [int((h.pred == h.head_frame).sum())],
                 "pred = head frame, head NOT visible": [f"{int(((h.pred == h.head_frame) & ~h.head_seen).sum())} of {int((~h.head_seen).sum())}"],
                 "pred = head frame, head visible": [f"{int(((h.pred == h.head_frame) & h.head_seen).sum())} of {int(h.head_seen.sum())}"]}))(
                 d[d.head_frame.fillna("").ne("") & (d.gold == d.head_frame)]).to_markdown(index=False), "",
             "(Only rows whose gold equals the head's implied frame, i.e. where the head was right.)", "",
             "## Rows where gold has a real frame (not NONE / DROPPED)", "",
             table(["position"]).pipe(lambda t: t).to_markdown(index=False) if False else
             (lambda f: pd.DataFrame([{"rows": len(f), "accuracy": round((f.gold == f.pred).mean(), 2),
                 "95% CI": "{:.2f}–{:.2f}".format(*wilson(int((f.gold == f.pred).sum()), len(f)))}]))(
                 d[~d.gold.isin(["NONE", "DROPPED"])]).to_markdown(index=False), "",
             "## Confusion (all rows with a prediction)", "", pd.crosstab(d.gold, d.pred).to_markdown(), "",
             "## By work", "", table(["work"]).to_markdown(index=False), ""]
    (OUT / "report.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
