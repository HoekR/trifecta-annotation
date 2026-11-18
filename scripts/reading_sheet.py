"""Reading workbook for the latest annotated set (Rik, 17 Nov 2026: "how do i check?").

Turns the two reading lists from `triangulation_sample.py report --tag <tag>` into one Excel workbook with
the food word (and verb) in bold, a wider context, plain frame names and dropdowns:

    uv run python scripts/reading_sheet.py build     # -> docs/evidence/triangulation_b/reading_<tag>.xlsx
    uv run python scripts/reading_sheet.py verb      # -> reading_verb_<vtag>.xlsx: verb-route frames, non-recipe
    uv run python scripts/reading_sheet.py progress  # how many rows are marked

`build` refuses to overwrite an existing workbook (it may hold your marks).
`scripts/procedure_html.py` reads progress from the workbook when it exists.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from data_io import resolve

ROOT = Path(__file__).resolve().parents[1]
TRI = ROOT / "docs" / "evidence" / "triangulation_b"
TAG = "v3d"
WORKBOOK = TRI / f"reading_{TAG}.xlsx"
VTAG = "v3f"  # verb-route reading (Rik, 18 Nov): the counterpart of sheet 1, so both routes are read alike
VERB_WORKBOOK = TRI / f"reading_verb_{VTAG}.xlsx"
VERB_SHEET = "3 Verb-route frames"
PER_GENRE = 12  # equal per non-recipe genre (8 genres -> 96 rows)
SEED = 20261118
FRAME = {"COOKING_CREATION": "cooking", "INGESTION": "eating/drinking", "CURE": "cure",
         "PRESERVING": "preserving", "NONE": "no frame", "DROPPED": "not food (dropped)"}
GENRE = {"RECIPE": "recipe books", "MEDICAL": "medical books", "proza": "prose", "drama": "drama",
         "poëzie": "poetry", "non-fictie": "non-fiction", "jeugdliteratuur": "youth literature",
         "sec - letterkunde": "studies of literature", "sec - taalkunde": "studies of language"}
SHEETS = {  # sheet name -> (answer column, choices)
    "1 Food-only frames": ("your_verdict", ["right", "wrong frame", "not food", "unsure"]),
    "2 Disagreements": ("which_is_right", ["noun-centred", "verb-centred", "both", "neither", "unsure"]),
    VERB_SHEET: ("your_verdict", ["right", "wrong frame", "not food", "unsure"]),
}
HALF = 220  # characters either side of the food word


def inputs(tag: str = TAG) -> dict[str, dict]:
    out = {}
    with open(resolve(f"triangulation_b_{tag}_run_kwic_inputs"), encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                out[r["record_id"]] = r
    return out


def window(r: dict) -> tuple[str, int]:
    """Context around the food word; returns (text, position of the word in text)."""
    c = str(r["context_text"]).replace("\n", " ")
    w = str(r["target_word"])
    hits = [m.start() for m in re.finditer(rf"(?<!\w){re.escape(w)}(?!\w)", c, flags=re.I)]
    i = min(hits, key=lambda h: abs(h - len(c) // 2)) if hits else len(c) // 2
    a, b = max(0, i - HALF), min(len(c), i + len(w) + HALF)
    return ("…" if a else "") + c[a:b] + ("…" if b < len(c) else ""), i - a + (1 if a else 0)


def rich(text: str, words: list[str], at: int):
    """Bold the food word at `at` and whole-word occurrences of the other words (the verb)."""
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont

    spans = []
    if words and words[0]:
        spans.append((at, at + len(words[0])))
    for w in words[1:]:
        if w:
            spans += [(m.start(), m.end()) for m in re.finditer(rf"(?<!\w){re.escape(w)}(?!\w)", text, flags=re.I)]
    spans = sorted(s for s in set(spans) if 0 <= s[0] < len(text))
    bold = InlineFont(b=True, color="C2410C")
    parts, pos = [], 0
    for s, e in spans:
        if s < pos:
            continue
        if s > pos:
            parts.append(text[pos:s])
        parts.append(TextBlock(bold, text[s:e]))
        pos = e
    if pos < len(text):
        parts.append(text[pos:])
    return CellRichText(*parts) if any(isinstance(p, TextBlock) for p in parts) else text


def add_sheet(wb, name, header, records, widths) -> None:
    """One reading sheet: header, records, a yellow dropdown answer column and a note column."""
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    yellow = PatternFill("solid", fgColor="FFF2CC")
    top = Alignment(wrap_text=True, vertical="top")
    ans, choices = SHEETS[name]
    ws = wb.create_sheet(name)
    ws.append(header + [ans, "note"])
    for c in ws[1]:
        c.font = Font(bold=True)
    dv = DataValidation(type="list", formula1='"' + ",".join(choices) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    for rec in records:
        ws.append([None] * (len(header) + 2))
        r = ws.max_row
        for j, v in enumerate(rec, 1):
            ws.cell(row=r, column=j, value=v).alignment = top
        a = ws.cell(row=r, column=len(header) + 1)
        a.fill = yellow
        a.alignment = top
        dv.add(a)
        ws.cell(row=r, column=len(header) + 2).alignment = top
    for j, w in enumerate(widths + [16, 30], 1):
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = w
    ws.freeze_panes = "A2"


def build() -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    if WORKBOOK.exists():
        raise SystemExit(f"{WORKBOOK} exists (it may hold your marks). Move it aside to rebuild.")
    inp = inputs()
    rows = pd.read_csv(TRI / f"rows_{TAG}.csv")
    rid = {(r.work, r.target, str(r.context)[:300]): r.record_id for r in rows.itertuples()}

    fo = pd.read_csv(TRI / f"read_food_only_frames_{TAG}.csv")
    fo["record_id"] = [rid.get((r.work, r.target, str(r.context)[:300])) for r in fo.itertuples()]
    fo["recipe"] = fo.stratum.isin(["RECIPE", "MEDICAL"])
    fo = fo.sort_values(["recipe", "stratum"]).reset_index(drop=True)
    dis = pd.read_csv(TRI / f"read_centring_disagreements_{TAG}.csv")

    wb = Workbook()
    rm = wb.active
    rm.title = "Read me"
    n_lit = int((~fo.recipe).sum())
    for i, (t, b) in enumerate([
        (f"Reading the annotated set ({TAG}, 17 Nov 2026)", True),
        ("Pick from the dropdown in the yellow column; add a note if useful. Empty = not read. Save and tell "
         "Claude; the overview page counts your progress.", False),
        ("", False),
        ("1 Food-only frames: 100 random passages where the model found a frame without any verb nearby. "
         "Is the frame right?", True),
        ("   right = the food word really is in this frame · wrong frame = food, but a different frame · "
         "not food = no food sense here · unsure.", False),
        (f"   Rows 2–{n_lit + 1} are the non-recipe genres, where the question is. The recipe and medical "
         "rows come last: you may stop before them if you think recipe precision is not in doubt.", False),
        ("", False),
        ("2 Disagreements: the same occurrence annotated twice, once with the context centred on the food "
         "word, once centred on the verb. The two got different labels. Which is right?", True),
        ("   Food word and verb are bold. noun-centred / verb-centred = that label is right · both = both "
         "fit (e.g. cooking procedure under a cure heading) · neither · unsure.", False),
    ], 1):
        c = rm.cell(row=i, column=1, value=t)
        c.font = Font(bold=b)
        c.alignment = Alignment(wrap_text=True)
    rm.column_dimensions["A"].width = 130

    def sheet(name, header, records, widths):
        add_sheet(wb, name, header, records, widths)

    recs = []
    for r in fo.itertuples():
        src = inp.get(r.record_id)
        text, at = window(src) if src else (str(r.context), 0)
        recs.append([GENRE.get(r.stratum, r.stratum), str(r.work).replace("_01.xml", ""), r.target,
                     FRAME.get(r.label, r.label), rich(text, [r.target], at)])
    sheet("1 Food-only frames", ["genre", "work", "food word", "model says", "passage"], recs, [18, 16, 14, 16, 100])

    recs = []
    for r in dis.itertuples():
        src = inp.get(r.record_id)
        text, at = window(src) if src else (str(r.context), 0)
        recs.append([GENRE.get(src["stratum"], src["stratum"]) if src else "", str(r.work).replace("_01.xml", ""),
                     r.target, r.verb, FRAME.get(r.label, r.label), FRAME.get(r.label_verbctx, r.label_verbctx),
                     rich(text, [r.target, str(r.verb) if pd.notna(r.verb) else ""], at), r.record_id])
    sheet("2 Disagreements", ["genre", "work", "food word", "verb", "noun-centred says", "verb-centred says",
                              "passage", "id"], recs, [16, 14, 12, 12, 15, 15, 95, 10])
    wb.save(WORKBOOK)
    print(f"wrote {WORKBOOK}: {len(fo)} food-only ({n_lit} non-recipe first), {len(dis)} disagreements")


def build_verb() -> None:
    """Verb-route frames outside recipe books: noun-centred rows of verb-selected occurrences that got a frame,
    PER_GENRE at random per genre. Same verdicts as sheet 1, so the two routes' precision compare directly."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    if VERB_WORKBOOK.exists():
        raise SystemExit(f"{VERB_WORKBOOK} exists (it may hold your marks). Move it aside to rebuild.")
    inp = inputs(VTAG)
    rows = pd.read_csv(TRI / f"rows_{VTAG}.csv")
    pool = rows[(rows.set == "verb_noun") & rows.frame.astype(bool) & (rows.stratum != "RECIPE")]
    pick = (pd.concat(g.sample(min(PER_GENRE, len(g)), random_state=SEED) for _, g in pool.groupby("stratum"))
              .sort_values(["stratum", "work"]).reset_index(drop=True))

    wb = Workbook()
    rm = wb.active
    rm.title = "Read me"
    for i, (t, b) in enumerate([
        (f"Reading verb-route frames ({VTAG}, 18 Nov 2026)", True),
        ("The counterpart of the food-only sheet you read: here the food word has a reviewed verb nearby, and the "
         "model found a frame. Is the frame right? Same choices as before, so the two routes compare directly.", False),
        (f"{PER_GENRE} random passages per genre, recipe books left out ({len(pick)} rows). Food word and verb "
         "are bold.", False),
        ("   right = the food word really is in this frame · wrong frame = food, but a different frame · "
         "not food = no food sense here · unsure.", False),
    ], 1):
        c = rm.cell(row=i, column=1, value=t)
        c.font = Font(bold=b)
        c.alignment = Alignment(wrap_text=True)
    rm.column_dimensions["A"].width = 130

    recs = []
    for r in pick.itertuples():
        src = inp.get(r.record_id)
        text, at = window(src) if src else (str(r.context), 0)
        verb = str(r.verb) if pd.notna(r.verb) else ""
        recs.append([GENRE.get(r.stratum, r.stratum), str(r.work).replace("_01.xml", ""), r.target, verb,
                     FRAME.get(r.label, r.label), rich(text, [r.target, verb], at), r.record_id])
    add_sheet(wb, VERB_SHEET, ["genre", "work", "food word", "verb", "model says", "passage", "id"], recs,
              [18, 14, 14, 12, 16, 100, 10])
    wb.save(VERB_WORKBOOK)
    print(f"wrote {VERB_WORKBOOK}: {len(pick)} verb-route frames, " + ", ".join(
        f"{GENRE.get(k, k)} {v}" for k, v in pick.stratum.value_counts().sort_index().items()))


def progress() -> dict[str, tuple[int, int]]:
    """sheet name -> (marked, total), over both workbooks."""
    out = {}
    for wbk in (WORKBOOK, VERB_WORKBOOK):
        if not wbk.exists():
            continue
        x = pd.read_excel(wbk, sheet_name=None, dtype=str)
        for name, (ans, _) in SHEETS.items():
            d = x.get(name)
            if d is not None:
                out[name] = (int(d[ans].fillna("").str.strip().ne("").sum()), len(d))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "verb", "progress"])
    a = ap.parse_args()
    if a.cmd == "build":
        build()
    elif a.cmd == "verb":
        build_verb()
    else:
        for k, (n, t) in progress().items():
            print(f"{k}: {n} of {t}")


if __name__ == "__main__":
    main()
