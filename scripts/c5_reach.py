"""C5 (plans/steps/VERB_LEXICON.md §4): reachability of food-first frames by the verb route, by *which* verbs
reach them. A large list can make "a verb within ±150 chars" trivial, so the decision rule is read at three
levels:

- any:      any verb candidate in the window;
- unflagged: not ambiguous / aux-ambiguous / check / multi-frame;
- specific: unflagged and not a light verb (`verb_probe.LIGHT_VERBS`).

    uv run python scripts/c5_reach.py docs/evidence/triangulation_v3   # reads rows.csv, writes c5_report.md
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

from scripts.eval_gold_by_position import wilson
from scripts.verb_probe import LIGHT_VERBS
from trifecta_annotation.frame_verbs import get_frame_verb_lexicon

REAL = {"COOKING_CREATION", "INGESTION", "CURE", "PRESERVING"}
WEAK = {"ambiguous", "aux-ambiguous", "check", "multi-frame"}


def main(folder: str) -> None:
    out = Path(folder)
    df = pd.read_csv(out / "rows.csv").fillna("")
    lex = get_frame_verb_lexicon()
    light = set(LIGHT_VERBS)

    def level(verb: str) -> tuple[str, str]:
        e = lex.entry_for(verb)
        if e is None:
            # indication constructions (goed_voor …) are curated: specific. Anything else was in the pool when
            # the run started but has since been dropped from the list (komen, zien): it does not count.
            return ("specific", verb) if "_" in verb else ("dropped", verb)
        lemma = e.canonical_lemma or verb
        if e.flags & WEAK:
            return "flagged", lemma
        return ("light" if lemma in light or "light" in e.flags else "specific"), lemma

    frames = df[df.food_label.isin(REAL)].copy()
    best, via = [], Counter()
    for cell in frames.pool_verbs:
        levels = [level(v) for v in str(cell).split(";") if v]
        kinds = {k for k, _ in levels}
        b = ("specific" if "specific" in kinds else "light" if "light" in kinds else
             "flagged" if "flagged" in kinds else "dropped" if kinds else "none")
        best.append(b)
        if b in ("light", "flagged"):
            via.update(lem for k, lem in levels if k == b)
    frames["reached_by"] = best
    n = len(frames)
    # What dropping / flagging would cost (Rik, 16 Nov): real frames reached only through light, flagged or
    # dropped verbs, to read: was that verb the evoker, or just nearby?
    only = frames[frames.reached_by.isin(["light", "flagged", "dropped"])]
    only.sample(min(40, len(only)), random_state=20261116)[
        ["work", "target", "food_label", "reached_by", "pool_verbs", "context"]
    ].assign(verb_is_evoker="").to_csv(out / "c5_only_weak_verbs_sample.csv", index=False)
    lines = [f"# C5: which verbs reach the food-first frames ({out})", "",
             f"Food-first rows with a real frame: {n}.", "",
             "| level | reachable | unreachable | unreachable share (95% CI) |", "|---|---:|---:|---|"]
    for name, ok in [("any verb", {"specific", "light", "flagged"}), ("unflagged", {"specific", "light"}),
                     ("specific (unflagged, no light verbs)", {"specific"})]:
        k = int((~frames.reached_by.isin(ok)).sum())
        lo, hi = wilson(k, n)
        lines.append(f"| {name} | {n - k} | {k} | {k / n:.0%} ({lo:.0%}–{hi:.0%}) |")
    lines += ["", "By frame (best level reached):", "",
              pd.crosstab(frames.food_label, frames.reached_by, margins=True).to_markdown(), "",
              "Lemmas that are the *only* reach (light or flagged), most frequent:", "",
              ", ".join(f"{lem} {c}" for lem, c in via.most_common(30)), "",
              "Decision rule (VERB_LEXICON.md §4): ≥ 75% unreachable → stop extending the list; < 50% → it was the "
              "list; in between → C3. Read it between *unflagged* and *specific*: light verbs are 26% of gold verb "
              "LUs (geven 28, nemen 17, maken 13 …), so excluding them understates reach, while *any* also counts "
              "flagged forms that would be near any noun. Rows reached only by weak verbs: "
              f"`c5_only_weak_verbs_sample.csv` ({len(only)} rows, sample of 40) for reading.", ""]
    (out / "c5_report.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1])
