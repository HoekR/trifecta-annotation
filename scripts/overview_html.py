"""One-page overview of the verb-lexicon / T1b re-harvest work (Rik, 16 Nov: "a visual overview at a glance").

Reads the T1b harvest inputs per run (old, v3, v3b, v3c, v3d; missing runs are skipped), Rik's C3 labels and the
cost estimates, and writes a self-contained HTML page (no external assets, light and dark mode):

    uv run python scripts/overview_html.py   # -> docs/evidence/triangulation_b/overview.html

Re-run after every re-harvest.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd

from data_io import resolve

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence" / "triangulation_b"
RUNS = [  # tag, label, what changed
    ("", "old", "infinitive-only list (July POC)"),
    ("v3", "v3", "reviewed list, everything through the gate"),
    ("v3b", "v3b", "gate narrowed, body parts recipe-only, list fixes"),
    ("v3c", "v3c", "round 3: verbs drop/light/keep, nouns recipe-only/never"),
    ("v3d", "v3d", "keep-verb reading: gebruiken/suikeren light, noun stems gated"),
]
RECIPE = {"RECIPE", "MEDICAL"}
DECISIONS = [
    ("13 Nov", "Round 1–2 lemma review", "349 lemmas, 1,966 forms; 'keep unless'"),
    ("16 Nov", "V3 wired in", "paradigms, enclitics (kooktse), separable verbs (legt … in), word lookup ×56"),
    ("16 Nov", "C5 rule retracted", "verb reachability measures proximity, not evocation → T8 (genre)"),
    ("16 Nov", "v3: precision collapsed", "C3: 17 of 51 non-food selected; light verbs and body parts"),
    ("16 Nov", "v3b: options a–c", "gate narrowed, body parts recipe-only, sta[ae]n/tap/verlost"),
    ("16 Nov", "v3c: round 3", "24 verbs dropped, 27 light, 8 full; 16 nouns recipe-only, 9 never"),
    ("16 Nov", "Keep verbs read", "gebruiken, suikeren light; same-sentence rule tested and rejected"),
    ("16 Nov", "v3d", "re-harvest with the keep-verb decisions"),
]


def load_run(tag: str) -> pd.DataFrame | None:
    name = f"triangulation_b_{tag}_kwic_inputs" if tag else "triangulation_b_kwic_inputs"
    try:
        path = resolve(name)
    except Exception:
        return None
    if not Path(path).exists():
        return None
    with open(path, encoding="utf-8") as fh:
        return pd.DataFrame([json.loads(line) for line in fh if line.strip()])


def cost(tag: str) -> int | None:
    f = OUT / (f"estimate_{tag}.md" if tag else "estimate.md")
    if not f.exists():
        return None
    m = re.search(r"verb-centred: \*\*~([\d,]+)\*\*", f.read_text())
    return int(m.group(1).replace(",", "")) if m else None


def c3_labels() -> pd.DataFrame:
    x = pd.read_excel(ROOT / "docs/evidence/verb_lexicon/verb_lexicon_review_2.xlsx", sheet_name=None)
    c = list(x.values())[3].rename(columns={" ": "id"})
    return c[c.is_food.notna()][["id", "is_food"]]


def esc(s) -> str:
    return html.escape(str(s))


def line_chart(share: pd.DataFrame, labels: list[str]) -> str:
    """Verb share per stratum (lines) over runs (x). Two series groups: recipe/medical vs other genres."""
    W, H, L, R, T, B = 760, 340, 48, 150, 16, 34
    ymax = max(0.4, float(share.max().max()) * 1.05)
    xs = {lab: L + i * (W - L - R) / max(1, len(labels) - 1) for i, lab in enumerate(labels)}
    y = lambda v: T + (H - T - B) * (1 - v / ymax)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Verb-selected share per genre over runs">']
    for t in [0, 0.1, 0.2, 0.3, 0.4]:
        if t <= ymax:
            parts.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                         f'<text class="axis" x="{L - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{t:.0%}</text>')
    for lab in labels:
        parts.append(f'<text class="axis" x="{xs[lab]:.1f}" y="{H - 10}" text-anchor="middle">{esc(lab)}</text>')
    # other genres first (behind), recipe/medical on top
    order = sorted(share.index, key=lambda s: s in RECIPE)
    end_labels = []
    for s in order:
        row = share.loc[s, labels]
        cls = "s1" if s in RECIPE else "s2"
        pts = [(xs[lab], y(v)) for lab, v in row.items() if pd.notna(v)]
        d = " ".join(f"{'M' if i == 0 else 'L'}{px:.1f},{py:.1f}" for i, (px, py) in enumerate(pts))
        parts.append(f'<path class="line {cls}" d="{d}"><title>{esc(s)}</title></path>')
        for (lab, v), (px, py) in zip([(lab, v) for lab, v in row.items() if pd.notna(v)], pts):
            parts.append(f'<circle class="dot {cls}" cx="{px:.1f}" cy="{py:.1f}" r="4">'
                         f'<title>{esc(s)} · {esc(lab)}: {v:.1%}</title></circle>')
        if pts:
            end_labels.append((pts[-1][1], s, row.dropna().iloc[-1], cls))
    # direct end labels for the two recipe strata only; the rest via legend + table
    last_y = -1e9
    for py, s, v, cls in sorted(end_labels):
        if s in RECIPE:
            ly = max(py, last_y + 14)                 # keep end labels apart (recipe 27% / medical 26%)
            last_y = ly
            parts.append(f'<text class="lab" x="{W - R + 8}" y="{ly + 4:.1f}">{esc(s.lower())} {v:.0%}</text>')
    lit = [e for e in end_labels if e[1] not in RECIPE]
    if lit:
        lo, hi = min(e[2] for e in lit), max(e[2] for e in lit)
        mid = sum(e[0] for e in lit) / len(lit)
        parts.append(f'<text class="lab muted" x="{W - R + 8}" y="{mid + 4:.1f}">7 other genres {lo:.0%}–{hi:.0%}</text>')
    parts.append("</svg>")
    return "".join(parts)


def bar_chart(values: list[tuple[str, float | None]], fmt, cls="s1", label="") -> str:
    W, H, L, T, B = 360, 190, 8, 18, 30
    vmax = max((v for _, v in values if v), default=1) * 1.15
    n = len(values)
    bw = (W - 2 * L) / n * 0.55
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(label)}">',
             f'<line class="base" x1="{L}" x2="{W - L}" y1="{H - B}" y2="{H - B}"/>']
    for i, (lab, v) in enumerate(values):
        cx = L + (i + 0.5) * (W - 2 * L) / n
        parts.append(f'<text class="axis" x="{cx:.1f}" y="{H - 10}" text-anchor="middle">{esc(lab)}</text>')
        if v is None:
            parts.append(f'<text class="axis muted" x="{cx:.1f}" y="{H - B - 6}" text-anchor="middle">–</text>')
            continue
        h = (H - T - B) * v / vmax
        x0, y0 = cx - bw / 2, H - B - h
        parts.append(f'<path class="bar {cls}" d="M{x0:.1f},{H - B} V{y0 + 4:.1f} Q{x0:.1f},{y0:.1f} {x0 + 4:.1f},{y0:.1f} '
                     f'H{x0 + bw - 4:.1f} Q{x0 + bw:.1f},{y0:.1f} {x0 + bw:.1f},{y0 + 4:.1f} V{H - B} Z">'
                     f'<title>{esc(lab)}: {fmt(v)}</title></path>'
                     f'<text class="val" x="{cx:.1f}" y="{y0 - 5:.1f}" text-anchor="middle">{fmt(v)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def pair_chart(rows: list[tuple[str, int | None, int | None]]) -> str:
    """C3: food (of 18) and non-food (of 51) selected per run, side by side."""
    W, H, L, T, B = 360, 190, 8, 18, 30
    vmax = 20
    n = len(rows)
    gw = (W - 2 * L) / n
    bw = gw * 0.3
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="C3 selection per run">',
             f'<line class="base" x1="{L}" x2="{W - L}" y1="{H - B}" y2="{H - B}"/>']
    for i, (lab, y_, n_) in enumerate(rows):
        cx = L + (i + 0.5) * gw
        parts.append(f'<text class="axis" x="{cx:.1f}" y="{H - 10}" text-anchor="middle">{esc(lab)}</text>')
        for j, (v, cls, what) in enumerate([(y_, "s1", "food of 18"), (n_, "s3", "non-food of 51")]):
            if v is None:
                continue
            x0 = cx - bw - 1 + j * (bw + 2)
            h = (H - T - B) * v / vmax
            y0 = H - B - h
            parts.append(f'<rect class="bar {cls}" x="{x0:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{max(h, 0.5):.1f}" rx="2">'
                         f'<title>{esc(lab)}: {v} {what}</title></rect>'
                         f'<text class="val" x="{x0 + bw / 2:.1f}" y="{y0 - 4:.1f}" text-anchor="middle">{v}</text>')
    parts.append("</svg>")
    return "".join(parts)


def main() -> None:
    runs = [(tag, lab, what, load_run(tag)) for tag, lab, what in RUNS]
    runs = [r for r in runs if r[3] is not None]
    labels = [lab for _, lab, _, _ in runs]
    share = pd.DataFrame({lab: d.groupby("stratum").verb_selected.mean() for _, lab, _, d in runs})
    total = {lab: float(d.verb_selected.mean()) for _, lab, _, d in runs}
    c3 = c3_labels()
    c3rows = []
    for _, lab, _, d in runs:
        m = c3.merge(d[["record_id", "verb_selected"]], left_on="id", right_on="record_id", how="left")
        c3rows.append((lab, int(m[m.is_food == "y"].verb_selected.sum()), int(m[m.is_food == "n"].verb_selected.sum())))
    costs = [(lab, cost(tag)) for tag, lab, _, _ in runs]
    first, last = labels[0], labels[-1]
    y0, n0 = c3rows[0][1:], None
    yl, nl = c3rows[-1][1], c3rows[-1][2]
    prec = lambda y, n: f"{y}/{y + n}" if y + n else "–"

    table_rows = "".join(
        f"<tr><th>{esc(s)}</th>" + "".join(f"<td>{share.loc[s, lab]:.1%}</td>" for lab in labels) + "</tr>"
        for s in sorted(share.index, key=lambda s: (s not in RECIPE, s)))
    table_rows += "<tr class='tot'><th>total</th>" + "".join(f"<td>{total[lab]:.1%}</td>" for lab in labels) + "</tr>"
    runs_list = "".join(f"<li><b>{esc(lab)}</b> {esc(what)}</li>" for _, lab, what, _ in runs)
    log = "".join(f"<tr><td>{esc(d)}</td><td>{esc(a)}</td><td>{esc(b)}</td></tr>" for d, a, b in DECISIONS)

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Verb lexicon overview</title>
<style>
:root {{ color-scheme: light;
  --surface:#fcfcfb; --card:#ffffff; --border:#e4e3df; --text:#0b0b0b; --text2:#52514e; --muted:#8a8984;
  --grid:#ecebe7; --s1:#2a78d6; --s2:#eb6834; --s3:#e34948; --good:#0ca30c; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme: dark;
  --surface:#1a1a19; --card:#222220; --border:#383835; --text:#f0efec; --text2:#c3c2b7; --muted:#8f8e86;
  --grid:#2c2c2a; --s1:#3987e5; --s2:#d95926; --s3:#e66767; }} }}
:root[data-theme="dark"] {{ color-scheme: dark;
  --surface:#1a1a19; --card:#222220; --border:#383835; --text:#f0efec; --text2:#c3c2b7; --muted:#8f8e86;
  --grid:#2c2c2a; --s1:#3987e5; --s2:#d95926; --s3:#e66767; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--surface); color:var(--text); font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:22px; margin:0 0 4px; }} h2 {{ font-size:15px; margin:0 0 10px; }}
.sub {{ color:var(--text2); margin:0 0 18px; }}
.status {{ border-left:4px solid var(--s1); background:var(--card); padding:10px 14px; border-radius:6px; margin-bottom:18px; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-bottom:18px; }}
.tile, .card {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:14px; }}
.tile .k {{ color:var(--text2); font-size:12px; }} .tile .v {{ font-size:28px; font-weight:600; margin:2px 0; }}
.tile .was {{ color:var(--muted); font-size:12px; }}
.grid2 {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:12px; margin-bottom:12px; }}
svg {{ width:100%; height:auto; display:block; }}
.grid {{ stroke:var(--grid); stroke-width:1; }} .base {{ stroke:var(--muted); stroke-width:1; }}
.axis {{ fill:var(--text2); font-size:11px; }} .val, .lab {{ fill:var(--text); font-size:11px; }} .muted {{ fill:var(--muted); }}
.line {{ fill:none; stroke-width:2; }} .line.s1 {{ stroke:var(--s1); }} .line.s2 {{ stroke:var(--s2); opacity:.55; }}
.dot {{ stroke:var(--card); stroke-width:2; }} .dot.s1, .bar.s1 {{ fill:var(--s1); }} .dot.s2 {{ fill:var(--s2); }} .bar.s3 {{ fill:var(--s3); }}
.dot:hover, .bar:hover {{ opacity:.8; }}
.legend {{ display:flex; gap:16px; color:var(--text2); font-size:12px; margin-top:6px; flex-wrap:wrap; }}
.sw {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:5px; vertical-align:-1px; }}
table {{ border-collapse:collapse; width:100%; font-size:12px; }} th, td {{ text-align:right; padding:4px 6px; border-bottom:1px solid var(--border); }}
th:first-child, td:first-child {{ text-align:left; }} tr.tot th, tr.tot td {{ font-weight:600; }}
.log td {{ text-align:left; vertical-align:top; }} .log td:first-child {{ white-space:nowrap; color:var(--text2); }}
details summary {{ cursor:pointer; color:var(--text2); margin-top:8px; }}
ul.runs {{ margin:6px 0 0; padding-left:18px; color:var(--text2); }}
.scroll {{ overflow-x:auto; }}
</style></head><body><main>
<h1>Verb lexicon: where we are</h1>
<p class="sub">T1b sample: 39 frozen DBNL works, 44,372 food-noun occurrences. Selection only, no frames yet. Generated by <code>scripts/overview_html.py</code>.</p>
<div class="status"><b>Now:</b> {esc(last)} is the current list. <b>Next decision (Rik):</b> select the annotation set, then G2, the LLM run (cost below). Recipe/medical gain kept; literary noise back near the old level.</div>
<div class="tiles">
 <div class="tile"><div class="k">Food nouns selected by the verb route</div><div class="v">{total[last]:.1%}</div><div class="was">was {total[first]:.1%} ({esc(first)})</div></div>
 <div class="tile"><div class="k">C3 precision of selection (Rik's labels)</div><div class="v">{prec(yl, nl)}</div><div class="was">was {prec(*c3rows[0][1:])} · v3 {prec(*c3rows[1][1:]) if len(c3rows) > 1 else '–'}</div></div>
 <div class="tile"><div class="k">LLM calls for verb-centred rows</div><div class="v">~{(costs[-1][1] or 0):,}</div><div class="was">was ~{(costs[0][1] or 0):,} · peak ~{max(c or 0 for _, c in costs):,}</div></div>
</div>
<div class="card" style="margin-bottom:12px">
 <h2>Verb-selected share per genre, per run</h2>
 {line_chart(share, labels)}
 <div class="legend"><span><span class="sw" style="background:var(--s1)"></span>recipe &amp; medical</span><span><span class="sw" style="background:var(--s2);opacity:.6"></span>other genres (drama, poetry, prose, non-fiction …)</span></div>
 <ul class="runs">{runs_list}</ul>
 <details><summary>Table</summary><div class="scroll"><table><tr><th>stratum</th>{''.join(f'<th>{esc(l)}</th>' for l in labels)}</tr>{table_rows}</table></div></details>
</div>
<div class="grid2">
 <div class="card"><h2>C3: selected among Rik's 69 labelled passages</h2>{pair_chart(c3rows)}
  <div class="legend"><span><span class="sw" style="background:var(--s1)"></span>food (of 18)</span><span><span class="sw" style="background:var(--s3)"></span>not food (of 51)</span></div></div>
 <div class="card"><h2>Estimated LLM calls, verb-centred rows</h2>{bar_chart(costs, lambda v: f"{v / 1000:.1f}k", label="LLM calls per run")}
  <div class="legend"><span>5.28 calls/row; Step A sieve saving ~43% outside recipe/medical (rough)</span></div></div>
</div>
<div class="card"><h2>Decision log</h2><table class="log">{log}</table>
<p class="sub" style="margin:8px 0 0">Details: <code>docs/evidence/triangulation_b/reharvest_v3.md</code>, <code>plans/steps/VERB_LEXICON.md</code>, <code>plans/steps/TRIANGULATION.md</code> (T8: where frames live, by genre).</p></div>
</main></body></html>"""
    out = OUT / "overview.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} (runs: {', '.join(labels)})")


if __name__ == "__main__":
    main()
