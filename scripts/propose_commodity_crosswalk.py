"""Propose a food-vocabulary -> kg_mockup commodity crosswalk for hand editing.

Writes `crosswalks/kg_mockup_commodities.proposal.csv`: one row per
(vocabulary entry, commodity) candidate, with how it matched, how many frame
rows it would bring into the kg_mockup export, and an example context.
Hand decisions live in `crosswalks/kg_mockup_commodities.xlsx` (sheet
`decisions`, column `decision` y / n, plus a `why` column); that workbook is
the only file to edit and the one the export reads. This script never writes
it, so rerunning it cannot clobber hand edits; new candidates it proposes have
to be copied into the workbook by hand.

Match bases, strongest first:
  alias     a pref/alt label equals a kg_mockup `historical_aliases` entry
  english   our Eng_translation equals the commodity's English name
  compound  a label contains an alias (suikerbrood, kaneelwater): a product
            made from the commodity, not the commodity itself; your call

    uv run python scripts/propose_commodity_crosswalk.py
"""

from __future__ import annotations

import ast
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from data_io import resolve

from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

KG_COMMODITIES = Path.home() / "develop/kg_mockup/src/dal/domain/commodities.py"
OUT = Path(__file__).resolve().parents[1] / "crosswalks" / "kg_mockup_commodities.proposal.csv"
ANNOTATION_SOURCES = (
    "trifecta_annotations", "colonial_annotations", "handdownload_annotations",
    "dbnl_sweep_annotations", "entry_scope_annotations",
)


def kg_registry() -> dict[str, dict]:
    """commodity_id -> {english, aliases}, read from kg_mockup's source text.

    Not imported: kg_mockup's `dal/__init__` pulls in MySQL connectors, and
    this project should not depend on them.
    """
    tree = ast.parse(KG_COMMODITIES.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "CommodityDefinition":
            kw = {k.arg: k.value for k in node.keywords}
            cid = ast.literal_eval(kw["commodity_id"])
            display = ast.literal_eval(kw["display_name"])
            english = re.sub(r"\s*\(.*\)", "", display).strip().lower()
            aliases = {a.strip().lower() for a in ast.literal_eval(kw.get("historical_aliases", ast.List([])))}
            out[cid] = {"english": english, "aliases": aliases | {cid.lower()}}
    return out


def _split(cell) -> list[str]:
    if cell is None or (isinstance(cell, float)):
        return []
    return [p.strip().lower() for p in re.split(r"[,;/]", str(cell)) if p.strip()]


def frame_rows_by_pref() -> tuple[Counter, dict[str, str]]:
    """Frame rows per pref label across all annotation sources, plus one example.

    entry_scope_annotations is filtered to the current inputs: the resumed run
    appends, so rows from the first (mis-capped) selection are still in it.
    """
    canonical = alt_label_index(load_food_terms())
    current = None
    inputs_path = Path(resolve("entry_scope_kwic_inputs"))
    if inputs_path.exists():
        current = {json.loads(l)["record_id"] for l in inputs_path.open(encoding="utf-8") if l.strip()}
    counts: Counter = Counter()
    example: dict[str, str] = {}
    for logical in ANNOTATION_SOURCES:
        path = Path(resolve(logical))
        if not path.exists():
            continue
        for line in path.open(encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            frame = (r.get("step_b") or {}).get("selected_frame")
            if r.get("error") or r.get("dropped") or frame in (None, "NONE"):
                continue
            pv = r["provenance"]
            if logical == "entry_scope_annotations" and current is not None and pv["record_id"] not in current:
                continue
            word = (pv.get("target_word") or "").lower()
            pref = canonical.get(word, word)
            counts[pref] += 1
            if pref not in example:
                ctx = pv.get("context_text") or ""
                i = ctx.lower().find(word)
                example[pref] = re.sub(r"\s+", " ", ctx[max(0, i - 60): i + 60] if i >= 0 else ctx[:120])
    return counts, example


def main() -> None:
    registry = kg_registry()
    terms = load_food_terms()
    counts, example = frame_rows_by_pref()

    rows: list[dict] = []
    matched_aliases: dict[str, set[str]] = defaultdict(set)
    for _, t in terms.iterrows():
        pref = str(t["Pref_label"]).strip().lower()
        labels = [pref, *_split(t["Alt_label"])]
        english = _split(t["Eng_translation"])
        for cid, reg in registry.items():
            basis = None
            hit = [l for l in labels if l in reg["aliases"]]
            if hit:
                basis = "alias"
                matched_aliases[cid].update(hit)
            elif reg["english"] in english:
                basis = "english"
            elif any(len(a) >= 4 and a in l for l in labels for a in reg["aliases"]):
                basis = "compound"
            if basis is None:
                continue
            rows.append({
                "decision": "y" if basis == "alias" else "?",
                "commodity_id": cid,
                "vocab_id": t["ID"],
                "pref_label": pref,
                "alt_labels": ", ".join(labels[1:]),
                "eng_translation": ", ".join(english),
                "type": t["Type"] if isinstance(t["Type"], str) else "",
                "basis": basis,
                "frame_rows": counts.get(pref, 0),
                "example": example.get(pref, ""),
            })

    order = {"alias": 0, "english": 1, "compound": 2}
    rows.sort(key=lambda r: (r["commodity_id"], order[r["basis"]], -r["frame_rows"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    by_basis = Counter(r["basis"] for r in rows)
    print(f"wrote {len(rows)} candidate rows -> {OUT}  ({dict(by_basis)})")
    unmatched = [cid for cid in registry if not any(r["commodity_id"] == cid for r in rows)]
    print("commodities with no vocabulary entry:", ", ".join(unmatched) or "none")


if __name__ == "__main__":
    main()
