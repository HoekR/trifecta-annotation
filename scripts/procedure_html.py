"""One-page overview of the whole procedure, for keeping control (Rik, 17 Nov 2026).

Shows, in plain names (no plan codes in the headings): what is waiting on Rik, each stage of the procedure
from corpus to export with its state, the latest result (frames per genre), and what is parked or closed.
Live parts are read when the page is generated: reading-sheet progress, branch state, uncommitted notes,
and the per-genre frame shares from the latest annotated set.

    uv run python scripts/procedure_html.py   # -> docs/evidence/procedure_overview.html

Re-run after any reading session, run or decision. Stage texts live in STAGES / WAITING below; edit them
when a decision changes the procedure.
"""

from __future__ import annotations

import html
import math
import subprocess
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "docs" / "evidence"
TRI = EVID / "triangulation_b"
TAG = "v3d"  # latest annotated set
TEMPLATE = ROOT.parent / "dighum_template"

RECIPE = {"RECIPE": "recipe books", "MEDICAL": "medical books"}
GENRE_NAMES = {
    "RECIPE": "recipe books", "MEDICAL": "medical books", "proza": "prose", "drama": "drama",
    "poëzie": "poetry", "non-fictie": "non-fiction", "jeugdliteratuur": "youth literature",
    "sec - letterkunde": "studies of literature", "sec - taalkunde": "studies of language",
}

CLOSED_SHEETS = {"2 Disagreements"}  # stopped by Rik 17 Nov: window effects, not contradictions

# state: done | working | question | parked | out
STAGES = [
    ("Corpus", "done",
     "DBNL works with TEI structure (on the 2 TB disk). The current sample: 39 works, 44,372 food-word occurrences.",
     "OCR cookbooks without TEI and Delpher newspapers are outside this procedure until their structure is read.",
     "plans/steps/DELPHER_KRANTEN.md"),
    ("Structure: entries and headings", "question",
     "TEI entries and headings are read (segmenter shipped); a recipe or remedy inherits its heading's purpose.",
     "The heading cue is narrow and unvalidated. Frames live at two levels: the heading gives the purpose, "
     "the sentence the procedure.",
     "plans/steps/TRIANGULATION.md"),
    ("Finding passages: two routes", "working",
     "Food route: every food word from the vocabulary. Verb route: a food word with a reviewed verb nearby "
     "(321 lemmas, 1,771 forms, three review rounds).",
     "Which route per genre. First result: recipe books need no verb filter; literary works do; medical "
     "books are unclear.",
     "plans/steps/VERB_LEXICON.md"),
    ("Cheap filter before the language model", "done",
     "A small trained model (GloBERTise) drops clear non-food passages at threshold 0.98; saves about 43% "
     "of calls outside recipe and medical books.",
     "", "PLAN.md"),
    ("Step A: is this food?", "done",
     "The language model drops metaphors and non-food senses. 92% right on the old gold.",
     "", "PLAN.md"),
    ("Step B: which frame?", "question",
     "Cooking, eating, cure, preserving or none, one label per passage.",
     "Agreement with gold on DBNL texts is 0.48, not the 75% measured on the old gold. One label per "
     "sentence is the shared assumption behind the failed fixes; the two-level design addresses it.",
     "plans/steps/TRIANGULATION.md"),
    ("Step C: the details (qualia)", "parked",
     "Ingredients, tools, ailments and so on per frame. Treated as hypotheses, not as counts.",
     "Six attempts failed for the same reason: the goal is in the title, not in the sentence. Waits for "
     "the two-level design.",
     "PLAN.md"),
    ("Checking without new random gold", "working",
     "Compare the two routes on the same passages; read where they disagree; measure per genre.",
     "Read 17 Nov: food-only frames are right in recipe books (93%), mostly wrong elsewhere (33%) and in "
     "medical books (25%, body parts). Centring disagreements are window effects, not contradictions.",
     "plans/steps/TRIANGULATION.md"),
    ("Outputs", "working",
     "Analysis export; food harvest shared with colleagues (10 Nov); knowledge-graph mock-up on SURF.",
     "Annotations have no date, so nothing per year yet. The latest results go to the knowledge-graph "
     "mock-up only after the full run with per-genre routing (17 Nov): the test sample is quota-drawn, "
     "counts verb passages twice and is not yet checked.",
     "plans/steps/FOOD_HARVEST_SHARING.md"),
]

STATE = {
    "done": ("✓", "done"), "working": ("●", "in progress"), "question": ("?", "open question"),
    "parked": ("‖", "parked"), "out": ("–", "not started"),
}

SIDE = [
    ("Indies food names (Malay vs Dutch)", "working", "first step done; next step waits on your downloads",
     "plans/steps/INDIES_NAMES.md"),
    ("Cooking times", "parked", "extraction works, attribution to the right food doesn't; needs recipe as unit",
     "plans/steps/COOKING_TIMES.md"),
    ("Cookbook lineage (Chomel vs. Huishoudelyk woordboek)", "out", "planned; why the harvest runs to 1920",
     "plans/steps/SENTENCE_HARVEST.md"),
    ("Newspapers (Delpher)", "out", "deferred; needs the external disk and article structure",
     "plans/steps/DELPHER_KRANTEN.md"),
    ("Grounding Step C in literal text", "parked", "closed 16 Oct: no gain, misses are substitutions",
     "plans/steps/STEPC_GROUNDING.md"),
]

DECISIONS = [
    ("13 Nov", "Verb list: first two review rounds", "349 lemmas; 'keep unless'"),
    ("16 Nov", "Verb list wired in", "word forms, enclitics (kooktse), separable verbs (legt … in)"),
    ("16 Nov", "Reachability rule retracted", "a verb nearby measures proximity, not evocation; moved to the genre question"),
    ("16 Nov", "Gate narrowed, body parts recipe-only", "non-food selected 17 of 51 → 1 of 51"),
    ("16 Nov", "Third review round", "24 verbs dropped, 27 weak, 8 full; 25 nouns restricted"),
    ("16 Nov", "Same-sentence rule rejected", "historical punctuation is no sentence marker"),
    ("16 Nov", "Annotation set chosen", "4,045 passages; recipe and medical capped at 300"),
    ("17 Nov", "Annotation run done", "3 h 26 min, 0 errors"),
    ("17 Nov", "Recipe books need no verb filter", "94% of food-only passages are frames (Rik: 'to be expected')"),
    ("17 Nov", "Food-only frames read", "right: recipe 93%, medical 25%, other genres 33%"),
    ("17 Nov", "Body parts: food in recipe books only", "scopes now on both routes; food-only rows outside recipe books halve"),
    ("17 Nov", "New harvest with the word restrictions", "44,372 → 26,994 occurrences; medical: verb 84% vs food-only 63%"),
    ("17 Nov", "Centring disagreements dropped", "not contradictions: the two windows read different sentences"),
]


def esc(s) -> str:
    return html.escape(str(s))


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def git(*args, cwd=ROOT) -> str:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def sheet_progress(name: str, col: str) -> tuple[int, int] | None:
    f = TRI / name
    if not f.exists():
        return None
    d = pd.read_csv(f, dtype=str)
    return int(d[col].fillna("").str.strip().ne("").sum()), len(d)


def waiting() -> list[tuple[str, str, str]]:
    """(what, detail, where); live parts first."""
    items = []
    from scripts.reading_sheet import WORKBOOK, progress
    prog = progress()
    if prog:
        for sheet, what in [("1 Food-only frames", "Read 100 food-only frames: right or wrong?"),
                            ("2 Disagreements", "Read the passages where the two routes disagree")]:
            n, t = prog.get(sheet, (0, 0))
            if n < t and sheet not in CLOSED_SHEETS:
                items.append((what, f"{n} of {t} done · sheet '{sheet}'", str(WORKBOOK.relative_to(ROOT))))
    for name, col, what in [] if prog else [
        (f"read_food_only_frames_{TAG}.csv", "rik_correct", "Read 100 food-only frames: right or wrong?"),
        (f"read_centring_disagreements_{TAG}.csv", "rik_which", "Read the passages where the two routes disagree"),
    ]:
        p = sheet_progress(name, col)
        if p and p[0] < p[1]:
            items.append((what, f"{p[0]} of {p[1]} done", f"docs/evidence/triangulation_b/{name}"))
    items += [
        ("Decide: which route for medical books?", "after the filter a verb clearly helps (84% vs 63%); "
         "proposal: verb route, food route in recipe books only", "docs/evidence/triangulation_b/reharvest_v3.md"),
        ("Decide: the verb bestellen", "no decision yet", "docs/evidence/verb_lexicon/"),
        ("Label about 150 entry headings with their purpose", "about an afternoon; the reference for two levels",
         "plans/steps/TRIANGULATION.md"),
        ("When: the full run", "with routing (all food words in recipe books, verb route elsewhere) about "
         "19k passages, ~16 h at the measured 3 s each; unrouted ~32k, ~1–2 days", ""),
    ]
    ahead = git("rev-list", "--count", "main..verb-lexicon-v3")
    if ahead and ahead != "0":
        items.append(("Merge the verb-lexicon branch into main", f"{ahead} commits ahead", ""))
    dirty = git("status", "--porcelain", cwd=TEMPLATE) if TEMPLATE.exists() else ""
    if dirty:
        items.append(("Commit the step-back notes in dighum_template", f"{len(dirty.splitlines())} files changed",
                      "../dighum_template/wisdom/"))
    return items


def genre_chart() -> tuple[str, str, int]:
    f = TRI / f"rows_{TAG}.csv"
    if not f.exists():
        return "<p class='sub'>No annotated set yet.</p>", "", 0
    df = pd.read_csv(f)
    rows = []
    for st, d in df.groupby("stratum"):
        vn, fo = d[d.set == "verb_noun"], d[d.set == "food_only"]
        rows.append((st, vn.frame.sum(), len(vn), fo.frame.sum(), len(fo)))
    rows.sort(key=lambda r: (r[0] not in RECIPE, list(RECIPE).index(r[0]) if r[0] in RECIPE else -r[1] / max(r[2], 1)))
    W, L, R, rowh, T = 560, 150, 44, 40, 22
    H = T + rowh * len(rows) + 26
    x = lambda v: L + (W - L - R) * v
    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Share of passages with a real frame per genre">']
    for t in [0, .25, .5, .75, 1]:
        p.append(f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{T - 6}" y2="{H - 24}"/>'
                 f'<text class="axis" x="{x(t):.1f}" y="{H - 8}" text-anchor="middle">{t:.0%}</text>')
    table = []
    for i, (st, kv, nv, kf, nf) in enumerate(rows):
        y0 = T + i * rowh
        name = GENRE_NAMES.get(st, st)
        p.append(f'<text class="lab{" strong" if st in RECIPE else ""}" x="{L - 10}" y="{y0 + 19}" text-anchor="end">{esc(name)}</text>')
        for j, (k, n, cls, what) in enumerate([(kv, nv, "s1", "food word + verb nearby"), (kf, nf, "s2", "food word only")]):
            if not n:
                continue
            v = k / n
            lo, hi = wilson(int(k), int(n))
            yy = y0 + 4 + j * 15
            p.append(f'<g class="mark"><rect class="bar {cls}" x="{L}" y="{yy}" width="{max(x(v) - L, 1):.1f}" height="12" rx="2"/>'
                     f'<line class="ci" x1="{x(lo):.1f}" x2="{x(hi):.1f}" y1="{yy + 6}" y2="{yy + 6}"/>'
                     f'<rect class="hit" x="{L}" y="{yy - 1}" width="{W - L - R}" height="14"/>'
                     f'<title>{esc(name)}, {what}: {v:.0%} ({lo:.0%}–{hi:.0%}), {int(k)} of {int(n)}</title></g>'
                     f'<text class="val" x="{max(x(hi), x(v)) + 6:.1f}" y="{yy + 10.5}">{v:.0%}</text>')
        table.append(f"<tr><th>{esc(name)}</th><td>{kv / nv:.0%} ({int(kv)}/{int(nv)})</td>"
                     f"<td>{kf / nf:.0%} ({int(kf)}/{int(nf)})</td></tr>" if nv and nf else "")
    p.append("</svg>")
    tbl = ("<table><tr><th>genre</th><th>food word + verb nearby</th><th>food word only</th></tr>"
           + "".join(table) + "</table>")
    return "".join(p), tbl, len(df)


def centring() -> tuple[int, int]:
    f = TRI / f"rows_{TAG}.csv"
    if not f.exists():
        return 0, 0
    df = pd.read_csv(f)
    vn = df[df.set == "verb_noun"].set_index("record_id")
    vv = df[df.set == "verb_verb"].dropna(subset=["pair"]).set_index("pair")
    j = vn.join(vv[["label"]], rsuffix="_v", how="inner")
    return int((j.label == j.label_v).sum()), len(j)


def badge(state: str) -> str:
    icon, label = STATE[state]
    return f'<span class="badge {state}"><span aria-hidden="true">{icon}</span> {label}</span>'


def link(path: str) -> str:
    return f'<a href="{esc(Path("../..") / path if not path.startswith("..") else Path("../../..") / path[3:])}">{esc(path)}</a>' if path else ""


def main() -> None:
    chart, tbl, n_rows = genre_chart()
    same, pairs = centring()
    wait = waiting()
    stage_html = []
    for i, (name, state, what, issue, where) in enumerate(STAGES, 1):
        stage_html.append(
            f'<li class="stage {state}"><div class="num">{i}</div><div class="body">'
            f'<div class="head"><b>{esc(name)}</b>{badge(state)}</div><p>{esc(what)}</p>'
            + (f'<p class="issue">{esc(issue)}</p>' if issue else "")
            + (f'<p class="where">{link(where)}</p>' if where else "") + "</div></li>")
    side = "".join(f"<tr><td>{esc(a)}</td><td>{badge(s)}</td><td>{esc(b)}</td><td>{link(w)}</td></tr>" for a, s, b, w in SIDE)
    wait_html = "".join(f"<li><b>{esc(a)}</b><span class='det'>{esc(b)}</span>"
                        + (f"<span class='where'>{link(w)}</span>" if w else "") + "</li>" for a, b, w in wait)
    log = "".join(f"<tr><td>{esc(d)}</td><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for d, a, b in DECISIONS)
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    head = git("log", "-1", "--format=%h, %cd", "--date=format:%d %b")

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Procedure overview</title>
<style>
:root {{ color-scheme: light;
  --surface:#fcfcfb; --card:#ffffff; --border:#e4e3df; --text:#0b0b0b; --text2:#52514e; --muted:#8a8984;
  --grid:#ecebe7; --s1:#2a78d6; --s2:#eb6834; --accent:#2a78d6;
  --good:#0c8a0c; --warn:#b86e00; --serious:#c2410c; --neutral:#8a8984; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme: dark;
  --surface:#1a1a19; --card:#222220; --border:#383835; --text:#f0efec; --text2:#c3c2b7; --muted:#8f8e86;
  --grid:#2c2c2a; --s1:#3987e5; --s2:#d95926; --accent:#3987e5;
  --good:#3fb93f; --warn:#e3a02f; --serious:#f07a45; --neutral:#8f8e86; }} }}
:root[data-theme="dark"] {{ color-scheme: dark;
  --surface:#1a1a19; --card:#222220; --border:#383835; --text:#f0efec; --text2:#c3c2b7; --muted:#8f8e86;
  --grid:#2c2c2a; --s1:#3987e5; --s2:#d95926; --accent:#3987e5;
  --good:#3fb93f; --warn:#e3a02f; --serious:#f07a45; --neutral:#8f8e86; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--surface); color:var(--text); font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:22px; margin:0 0 4px; }} h2 {{ font-size:16px; margin:0 0 10px; }}
.sub {{ color:var(--text2); margin:0 0 16px; }}
a {{ color:var(--accent); }}
.where a, .sub code, a {{ overflow-wrap:anywhere; }} .cols > * {{ min-width:0; }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; margin-bottom:14px; }}
.cols {{ display:grid; grid-template-columns:minmax(0,1.15fr) minmax(0,1fr); gap:14px; }}
@media (max-width:820px) {{ .cols {{ grid-template-columns:1fr; }} }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-bottom:14px; }}
.tile {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px 14px; }}
.tile .k {{ color:var(--text2); font-size:12px; }} .tile .v {{ font-size:26px; font-weight:600; }}
.tile .was {{ color:var(--muted); font-size:12px; }}
ul.wait {{ list-style:none; margin:0; padding:0; }}
ul.wait li {{ padding:8px 0 8px 26px; border-bottom:1px solid var(--border); position:relative; }}
ul.wait li::before {{ content:"☐"; position:absolute; left:2px; top:7px; color:var(--serious); font-size:15px; }}
ul.wait li b {{ display:block; font-weight:600; }}
.det {{ color:var(--text2); font-size:12px; margin-right:8px; }} .where {{ font-size:12px; }}
ol.flow {{ list-style:none; margin:0; padding:0; }}
.stage {{ display:flex; gap:12px; position:relative; padding-bottom:14px; }}
.stage:not(:last-child)::after {{ content:""; position:absolute; left:14px; top:30px; bottom:0; width:2px; background:var(--border); }}
.num {{ flex:0 0 30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-weight:600; font-size:13px; background:var(--surface); border:2px solid var(--neutral); color:var(--text); z-index:1; }}
.stage.done .num {{ border-color:var(--good); }} .stage.working .num {{ border-color:var(--accent); }}
.stage.question .num {{ border-color:var(--warn); }}
.body {{ flex:1; min-width:0; }} .body p {{ margin:3px 0; color:var(--text2); }}
.body .head {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
.body .issue {{ color:var(--text); border-left:3px solid var(--warn); padding-left:8px; }}
.stage.parked .issue, .stage.done .issue {{ border-left-color:var(--neutral); }}
.badge {{ font-size:11px; padding:1px 7px; border-radius:10px; border:1px solid currentColor; white-space:nowrap; }}
.badge.done {{ color:var(--good); }} .badge.working {{ color:var(--accent); }} .badge.question {{ color:var(--warn); }}
.badge.parked, .badge.out {{ color:var(--neutral); }}
svg {{ width:100%; height:auto; display:block; }}
.grid {{ stroke:var(--grid); stroke-width:1; }} .axis {{ fill:var(--text2); font-size:12px; }}
.lab {{ fill:var(--text2); font-size:14px; }} .lab.strong {{ fill:var(--text); font-weight:600; }}
.val {{ fill:var(--text); font-size:12px; }}
.bar.s1 {{ fill:var(--s1); }} .bar.s2 {{ fill:var(--s2); }}
.ci {{ stroke:var(--text); stroke-width:1.2; opacity:.55; }}
.hit {{ fill:transparent; }} .mark:hover .bar {{ opacity:.8; }}
.legend {{ display:flex; gap:16px; color:var(--text2); font-size:12px; margin-top:6px; flex-wrap:wrap; }}
.sw {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; vertical-align:-1px; }}
.finding {{ margin:10px 0 0; padding-left:18px; }} .finding li {{ margin:3px 0; }}
table {{ border-collapse:collapse; width:100%; font-size:12px; }}
th, td {{ text-align:left; padding:5px 6px; border-bottom:1px solid var(--border); vertical-align:top; }}
.log td:first-child {{ white-space:nowrap; color:var(--text2); }}
details summary {{ cursor:pointer; color:var(--text2); margin-top:8px; }}
.scroll {{ overflow-x:auto; }}
code {{ font-size:12px; }}
</style></head><body><main>
<h1>Procedure overview</h1>
<p class="sub">Food frames in historical Dutch texts: from corpus to export. Generated {date.today():%d %b %Y} by
<code>scripts/procedure_html.py</code> · branch <code>{esc(branch)}</code> · last commit <code>{esc(head)}</code>.
Verb-list history: <a href="triangulation_b/overview.html">verb lexicon overview</a>.</p>

<div class="tiles">
 <div class="tile"><div class="k">Waiting on you</div><div class="v">{len(wait)}</div><div class="was">items, list on the left</div></div>
 <div class="tile"><div class="k">Latest annotation run</div><div class="v">{n_rows:,}</div><div class="was">passages, 0 errors (17 Nov)</div></div>
 <div class="tile"><div class="k">Frame agreement with gold, DBNL texts</div><div class="v">0.48</div><div class="was">not the 75% of the old gold</div></div>
 <div class="tile"><div class="k">Same label, noun- or verb-centred</div><div class="v">{same / max(pairs, 1):.0%}</div><div class="was">{same} of {pairs} pairs</div></div>
</div>

<div class="cols">
 <div>
  <div class="card"><h2>Waiting on you</h2><ul class="wait">{wait_html}</ul></div>
  <div class="card"><h2>Latest result: where a verb helps</h2>
   <p class="sub" style="margin:0 0 8px">Share of passages that get a real frame (cooking, eating, cure, preserving). Line = 95% interval.</p>
   {chart}
   <div class="legend"><span><span class="sw" style="background:var(--s1)"></span>food word + verb nearby</span>
   <span><span class="sw" style="background:var(--s2)"></span>food word only</span></div>
   <ul class="finding">
    <li><b>Recipe books:</b> every food word is in a frame; the genre evokes it. No verb filter needed.</li>
    <li><b>Other genres:</b> a verb nearby raises the share 4–10×. Keep the verb filter.</li>
    <li><b>Medical books:</b> a verb barely helps. Open.</li>
    <li><b>Your reading:</b> food-only frames right in recipe books 93%, medical 25% (body parts), other genres 33%.</li>
   </ul>
   <details><summary>Table</summary><div class="scroll">{tbl}</div></details>
  </div>
 </div>
 <div class="card"><h2>The procedure, stage by stage</h2>
  <ol class="flow">{''.join(stage_html)}</ol>
  <div class="legend">{badge('done')} {badge('working')} {badge('question')} {badge('parked')}</div>
 </div>
</div>

<div class="card"><h2>The common thread</h2>
 <p>Different fixes for Step B and Step C failed in the same way. What they shared is the unit: one label per
 sentence-sized window. Frames often live a level higher, in the heading (71% of 3,326 recipes name their goal
 only in the title). The two-level design (heading gives purpose, sentence gives procedure) is the answer under
 test; the genre question decides where each level and route applies.</p>
</div>

<div class="cols">
 <div class="card"><h2>Side tracks</h2><div class="scroll"><table>{side}</table></div></div>
 <div class="card"><h2>Recent decisions</h2><div class="scroll"><table class="log">{log}</table></div></div>
</div>
</main></body></html>"""
    out = EVID / "procedure_overview.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({len(wait)} waiting, {n_rows} rows)")


if __name__ == "__main__":
    main()
