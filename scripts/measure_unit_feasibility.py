#!/usr/bin/env python3
"""Measure whether remedy/recipe-unit annotation is viable on this corpus.

Feasibility study behind the §9d reframe (PLAN.md): `CURE_Affliction` and
`COOKING_CREATION_Food_Product` resist every extraction method tried because
they are the text's *organizing concept* (a remedy is identified by what it
treats, a recipe by what it makes) while the pipeline enters through a food
mention and tries to recover them from one participant's local window.

Four measurements, no model inference and no LLM calls:

  A. segmenter-vs-known-boundaries — `voc_recipes` has 3.3k hand-separated
     Title/Content pairs, so concatenating consecutive recipes gives real
     boundaries to score unit detection against (precision/recall), rather
     than eyeballing.
  B. goal-reachability (the decisive number) — how often the product named in
     a recipe's title is absent from its body, i.e. structurally unreachable
     for any body-anchored extractor at any window size.
  C. segmentability by source/regime — long-KWIC recipe/medical passages vs a
     literary control vs 20th-c printed cookbooks.
  D. affliction side — for gold rows with a non-empty CURE_Affliction, does
     unit-goal detection recover the hand-labelled value, versus the current
     food-anchored ±180 window baseline?

Report n per bucket; anything under ~30 is indicative only (the explicit
lesson from docs/DECISIONS.md 2026-10-16).
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trifecta_annotation.eval import soft_qualia_match
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.stepc_span_export import DEFAULT_CONTEXT_RADIUS, find_span
from trifecta_annotation.unit_segmentation import (
    extract_unit_goal,
    find_unit_boundaries,
    goal_with_inheritance,
)

MEASUREMENTS = ("A", "B", "C", "D", "E")

DEFAULT_ENGLISH_EXPORT = (
    "/Volumes/Extreme SSD/scratch/trifecta/inception_en/export_20261014/annotation"
)
# Genre is encoded in the English filenames: 1741_hr_enghousewifry → household
# recipes, 1791_ms_Domesticmedicine → medical, 1799_te_Travels → travel.
_ENGLISH_GENRE = {"hr": "RECIPE_PRACTICE", "ms": "MEDICAL", "te": "TRAVEL"}
SMALL_BUCKET = 30

# A recipe body often *restates* the goal at its head ("Om te maken
# blancmengyer. Neemt ...") — that is evidence for the structure claim, not an
# ingredient mention, so B scores it separately instead of counting it as
# "goal reachable from the body".
_BODY_HEAD_CHARS = 60


def _recipe_goal_from_title(title: str) -> str:
    """Parse the product named by a voc_recipes Title."""
    text = re.sub(r"^\s*\d+\s*", "", str(title)).strip()
    text = text.replace("*", " ")
    marker = re.search(
        r"\b(?:om\s+te\s+maken|wildi\s+maken|te\s+maken|om)\b", text, flags=re.IGNORECASE
    )
    tail = text[marker.end():] if marker else text
    tail = re.split(r"[.;:]| tot | totten | buyten ", tail, maxsplit=1)[0]
    tokens = re.findall(r"[A-Za-zÀ-ÿſ][A-Za-zÀ-ÿſ'\-]*", tail)
    skip = {"een", "eenen", "eene", "de", "den", "het", "der", "dye", "die", "ofte", "oft", "of"}
    kept = [tok for tok in tokens if normalize_hist_dutch(tok) not in skip]
    return " ".join(kept[:3]).strip()


def measure_a_segmenter_vs_known(limit: int | None) -> dict[str, Any]:
    """Score unit detection against voc_recipes' hand-separated boundaries."""
    import pandas as pd
    from data_io import resolve

    frame = pd.read_csv(resolve("voc_recipes")).dropna(subset=["Title", "Content"])
    if limit:
        frame = frame.head(limit)

    # Build synthetic passages of 4 consecutive recipes; record true boundaries.
    group_size = 4
    tp = fp = fn = 0
    tolerance = 25  # chars; a boundary found within this of the true one counts
    passages = 0
    for start in range(0, len(frame) - group_size, group_size):
        rows = frame.iloc[start : start + group_size]
        parts: list[str] = []
        true_boundaries: list[int] = []
        cursor = 0
        for _, row in rows.iterrows():
            piece = f"{str(row['Title']).strip()} {str(row['Content']).strip()} "
            true_boundaries.append(cursor)
            parts.append(piece)
            cursor += len(piece)
        passage = "".join(parts)
        passages += 1

        found = [unit.start for unit in find_unit_boundaries(passage)]
        matched_true: set[int] = set()
        for position in found:
            near = [b for b in true_boundaries if abs(b - position) <= tolerance]
            if near:
                tp += 1
                matched_true.add(near[0])
            else:
                fp += 1
        fn += len([b for b in true_boundaries if b not in matched_true])

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision == precision and recall == recall and (precision + recall) > 0
        else float("nan")
    )
    return {
        "passages": passages,
        "recipes_per_passage": group_size,
        "boundary_tolerance_chars": tolerance,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def measure_b_goal_reachability(limit: int | None) -> dict[str, Any]:
    """How often is the title's product absent from the recipe body?"""
    import pandas as pd
    from data_io import resolve

    frame = pd.read_csv(resolve("voc_recipes")).dropna(subset=["Title", "Content"])
    if limit:
        frame = frame.head(limit)

    parsed = 0
    unparsed = 0
    in_body_head = 0
    in_body_elsewhere = 0
    absent = 0
    # Coverage bias check: titles the parser can't handle are scored with a
    # cruder fallback (whole title minus leading number) so the headline can be
    # shown not to depend on which half parsed.
    fallback_absent = 0
    fallback_present = 0
    examples: list[dict[str, str]] = []

    for _, row in frame.iterrows():
        goal = _recipe_goal_from_title(row["Title"])
        if not goal:
            unparsed += 1
            fallback = re.sub(r"^\s*\d+\s*", "", str(row["Title"])).replace("*", " ").strip()
            tokens = re.findall(r"[A-Za-zÀ-ÿſ][A-Za-zÀ-ÿſ'\-]*", fallback)
            if tokens:
                head = normalize_hist_dutch(tokens[0])
                if head and head in normalize_hist_dutch(str(row["Content"])):
                    fallback_present += 1
                else:
                    fallback_absent += 1
            continue
        parsed += 1
        body = str(row["Content"])
        head = body[:_BODY_HEAD_CHARS]
        norm_goal_head = normalize_hist_dutch(goal).split()[0] if goal.split() else ""
        if not norm_goal_head:
            unparsed += 1
            parsed -= 1
            continue
        if norm_goal_head in normalize_hist_dutch(head):
            in_body_head += 1
        elif norm_goal_head in normalize_hist_dutch(body):
            in_body_elsewhere += 1
        else:
            absent += 1
            if len(examples) < 8:
                examples.append(
                    {
                        "goal": goal,
                        "title": str(row["Title"])[:90],
                        "body_head": body[:90],
                    }
                )

    return {
        "recipes": int(len(frame)),
        "goal_parsed": parsed,
        "goal_unparsed": unparsed,
        "goal_restated_at_body_head": in_body_head,
        "goal_present_elsewhere_in_body": in_body_elsewhere,
        "goal_absent_from_body": absent,
        "unreachable_rate_strict": absent / parsed if parsed else float("nan"),
        "unreachable_rate_incl_head_restatement": (
            (absent + in_body_head) / parsed if parsed else float("nan")
        ),
        "fallback_unparsed_absent": fallback_absent,
        "fallback_unparsed_present": fallback_present,
        "fallback_unparsed_absent_rate": (
            fallback_absent / (fallback_absent + fallback_present)
            if (fallback_absent + fallback_present)
            else float("nan")
        ),
        "combined_absent": absent + fallback_absent,
        "combined_scored": parsed + fallback_absent + fallback_present,
        "combined_absent_rate": (
            (absent + fallback_absent) / (parsed + fallback_absent + fallback_present)
            if (parsed + fallback_absent + fallback_present)
            else float("nan")
        ),
        "examples_absent": examples,
    }


def measure_c_segmentability(literary_sample: int) -> dict[str, Any]:
    """Unit-signal rate per source/regime: recipe/medical vs literary control."""
    import pandas as pd
    from data_io import resolve

    from trifecta_annotation.text_regime import infer_text_regime

    frame = pd.read_csv(
        resolve("food_snippets_long_kwic"), usecols=["doc_id", "title", "filename", "snippet"]
    ).drop_duplicates(subset=["doc_id"])

    by_regime: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"passages": 0, "with_units": 0, "unit_counts": [], "signals": Counter()}
    )
    literary_seen = 0

    for _, row in frame.iterrows():
        regime = infer_text_regime(
            corpus="cort_voc_db", title=row["title"], source_path=row["filename"]
        ).value
        if regime == "LITERARY":
            if literary_seen >= literary_sample:
                continue
            literary_seen += 1
        bucket = by_regime[regime]
        units = find_unit_boundaries(str(row["snippet"]))
        bucket["passages"] += 1
        if units:
            bucket["with_units"] += 1
            bucket["unit_counts"].append(len(units))
            bucket["signals"].update(unit.signal for unit in units)

    out: dict[str, Any] = {}
    for regime, bucket in by_regime.items():
        counts = bucket["unit_counts"]
        out[regime] = {
            "passages": bucket["passages"],
            "with_units": bucket["with_units"],
            "with_units_rate": bucket["with_units"] / bucket["passages"] if bucket["passages"] else 0.0,
            "median_units_when_present": statistics.median(counts) if counts else 0,
            "signals": dict(bucket["signals"].most_common()),
            "small_bucket": bucket["passages"] < SMALL_BUCKET,
        }

    out["_ldk2025_cookbooks"] = _measure_ldk_cookbooks()
    return out


def _measure_ldk_cookbooks() -> dict[str, Any]:
    """20th-c printed cookbooks: structural contrast with the historical corpus."""
    from data_io import resolve

    root = Path(resolve("ldk2025_cookbooks"))
    if not root.exists():
        return {"available": False}
    per_file: dict[str, Any] = {}
    for path in sorted(root.glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="replace")
        units = find_unit_boundaries(text)
        per_file[path.name] = {
            "chars": len(text),
            "units": len(units),
            "units_per_10k_chars": round(len(units) / (len(text) / 10000), 1) if text else 0,
            "signals": dict(Counter(unit.signal for unit in units).most_common()),
        }
    return {"available": True, "files": per_file}


def measure_d_affliction_side() -> dict[str, Any]:
    """Does unit-goal detection recover gold CURE_Affliction values?

    Broken down by `text_regime`, because the reframe is genre-bounded by
    construction: in literary/descriptive text a food mention is incidental
    (a meal in a novel) and there is no unit-with-a-goal to recover, so the
    current mention-based model is arguably right there. A low literary number
    marks the reframe's scope, not its failure — the number that matters is
    the recipe/medical one.
    """
    from trifecta_annotation.gold_io import load_gold_records
    from trifecta_annotation.homonym_context import _target_span, local_context_window
    from trifecta_annotation.schemas import TrifectaAnnotation

    gold = load_gold_records()
    total = 0
    unit_exact = 0
    unit_soft = 0
    window_contains = 0
    no_units = 0
    per_regime: dict[str, dict[str, int]] = defaultdict(
        lambda: {"n": 0, "window": 0, "exact": 0, "soft": 0, "no_units": 0}
    )

    for record in gold:
        try:
            annotation = TrifectaAnnotation.model_validate(record)
        except Exception:
            continue
        if annotation.step_c is None:
            continue
        values = annotation.step_c.model_dump(mode="json")
        gold_value = str(values.get("CURE_Affliction") or "").strip()
        if not gold_value:
            continue
        context = annotation.provenance.context_text or ""
        target = annotation.provenance.target_word or ""
        if not context:
            continue
        total += 1
        regime = (
            annotation.provenance.text_regime.value
            if annotation.provenance.text_regime
            else "UNSET"
        )
        bucket = per_regime[regime]
        bucket["n"] += 1

        # Current food-anchored baseline: does the ±180 window even contain it?
        window = local_context_window(context, target, radius=DEFAULT_CONTEXT_RADIUS) if target else context
        if find_span(window, gold_value) is not None:
            window_contains += 1
            bucket["window"] += 1

        units = find_unit_boundaries(context)
        if not units:
            no_units += 1
            bucket["no_units"] += 1
            continue
        target_span = _target_span(context, target) if target else None
        position = target_span[0] if target_span else 0
        index = next(
            (i for i, unit in enumerate(units) if unit.start <= position < unit.end),
            None,
        )
        if index is None:
            continue
        goal = goal_with_inheritance(context, units, index) or extract_unit_goal(context, units[index])
        if goal is None:
            continue
        norm_gold = normalize_hist_dutch(gold_value)
        if goal.norm == norm_gold:
            unit_exact += 1
            unit_soft += 1
            bucket["exact"] += 1
            bucket["soft"] += 1
        elif soft_qualia_match(norm_gold, goal.norm):
            unit_soft += 1
            bucket["soft"] += 1

    return {
        "gold_rows_with_affliction": total,
        "by_regime": {
            regime: {
                **counts,
                "window_rate": counts["window"] / counts["n"] if counts["n"] else float("nan"),
                "exact_rate": counts["exact"] / counts["n"] if counts["n"] else float("nan"),
                "soft_rate": counts["soft"] / counts["n"] if counts["n"] else float("nan"),
                "small_bucket": counts["n"] < SMALL_BUCKET,
            }
            for regime, counts in sorted(per_regime.items())
        },
        "food_anchored_window_contains_value": window_contains,
        "food_anchored_rate": window_contains / total if total else float("nan"),
        "unit_goal_exact": unit_exact,
        "unit_goal_exact_rate": unit_exact / total if total else float("nan"),
        "unit_goal_soft": unit_soft,
        "unit_goal_soft_rate": unit_soft / total if total else float("nan"),
        "passages_with_no_units": no_units,
        "no_units_rate": no_units / total if total else float("nan"),
        "small_bucket": total < SMALL_BUCKET,
        "caveat": (
            "Not a fair test of the hypothesis. Gold context_text is a KWIC snippet "
            "already cut around the food word (median 367 chars for these rows), so any "
            "governing header was truncated away before segmentation ever sees it — which "
            "is why most of these passages contain no detectable unit structure. Testing "
            "the affliction side needs gold re-derived from source documents with wider "
            "windows; stored gold cannot answer it."
        ),
    }


def measure_e_cross_language(english_export: str, limit: int | None) -> dict[str, Any]:
    """Same goal-reachability metric on Dutch and English, detected boundaries.

    The headline in B uses `voc_recipes`' *given* Title/Content split, which has
    no English equivalent. To compare traditions rather than measurement bases,
    this runs `goal_body_reachability` — segmenter-detected boundaries — over
    both sides. Convergent validity check: Dutch here should land near B's
    given-boundary figure.
    """
    import pandas as pd
    from data_io import resolve

    from trifecta_annotation.adapters.inception_tsv import parse_webanno_tsv
    from trifecta_annotation.text_regime import infer_text_regime
    from trifecta_annotation.unit_segmentation import goal_body_reachability

    def rates(counts: dict[str, int]) -> dict[str, Any]:
        with_goal = counts.get("with_goal", 0) or 1
        return {
            **counts,
            "first_token_absent_rate": counts.get("first_token_absent", 0) / with_goal,
            "head_token_absent_rate": counts.get("head_token_absent", 0) / with_goal,
            "small_bucket": counts.get("with_goal", 0) < SMALL_BUCKET,
        }

    out: dict[str, Any] = {}

    # Dutch — voc_recipes concatenated so boundaries must be detected, not given.
    frame = pd.read_csv(resolve("voc_recipes")).dropna(subset=["Title", "Content"])
    if limit:
        frame = frame.head(limit)
    dutch: dict[str, int] = defaultdict(int)
    group = 6
    for start in range(0, len(frame) - group, group):
        rows = frame.iloc[start : start + group]
        text = " ".join(
            f"{str(row['Title']).strip()} {str(row['Content']).strip()}" for _, row in rows.iterrows()
        )
        for key, value in goal_body_reachability(text, language="nl").items():
            dutch[key] += value
    out["dutch_voc_recipes"] = rates(dict(dutch))

    # Dutch — long-KWIC recipe/medical/unknown passages (real, uncurated text).
    long_kwic = pd.read_csv(
        resolve("food_snippets_long_kwic"), usecols=["doc_id", "title", "filename", "snippet"]
    ).drop_duplicates(subset=["doc_id"])
    dutch_lk: dict[str, int] = defaultdict(int)
    passages = 0
    for _, row in long_kwic.iterrows():
        regime = infer_text_regime(
            corpus="cort_voc_db", title=row["title"], source_path=row["filename"]
        ).value
        if regime not in {"RECIPE_PRACTICE", "MEDICAL", "UNKNOWN"}:
            continue
        passages += 1
        for key, value in goal_body_reachability(str(row["snippet"]), language="nl").items():
            dutch_lk[key] += value
    out["dutch_long_kwic_recipe_medical"] = {**rates(dict(dutch_lk)), "passages": passages}

    # English — INCEpTION export documents, bucketed by filename genre code.
    root = Path(english_export)
    if not root.exists():
        out["english"] = {"available": False, "path": str(root)}
        return out

    english: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for doc in sorted(root.iterdir()):
        if not doc.is_dir():
            continue
        tsv = doc / "INITIAL_CAS.tsv"
        if not tsv.exists():
            tsv = next(iter(sorted(doc.glob("*.tsv"))), None)
        if tsv is None:
            continue
        parts = doc.name.split("_")
        genre = _ENGLISH_GENRE.get(parts[1] if len(parts) > 1 else "", "OTHER")
        try:
            text = " ".join(sentence.text for sentence in parse_webanno_tsv(tsv))
        except Exception:
            continue
        english[genre]["docs"] += 1
        for key, value in goal_body_reachability(text, language="en").items():
            english[genre][key] += value
    out["english"] = {
        "available": True,
        "by_genre": {genre: rates(dict(counts)) for genre, counts in sorted(english.items())},
    }
    return out


def _render_report(results: dict[str, Any]) -> str:
    lines = [
        "# Remedy/recipe-unit annotation — feasibility study",
        "",
        "Measures whether these texts support making the remedy/recipe *unit* the",
        "annotation record (goal fields as identity, ingredients/preparation trailing),",
        "instead of entering through a food mention. Heuristics only — no model",
        "inference, no LLM calls, nothing in the pipeline changed.",
        "",
        f"Generated: {results['finished_at']}",
        "",
    ]

    if "A" in results:
        a = results["A"]
        lines += [
            "## A. Segmenter vs. known boundaries (voc_recipes)",
            "",
            f"- Synthetic passages ({a['recipes_per_passage']} consecutive recipes each): {a['passages']}",
            f"- Boundary precision **{a['precision']:.3f}** / recall **{a['recall']:.3f}** / F1 **{a['f1']:.3f}** "
            f"(tolerance {a['boundary_tolerance_chars']} chars; tp={a['tp']} fp={a['fp']} fn={a['fn']})",
            "",
        ]

    if "B" in results:
        b = results["B"]
        lines += [
            "## B. Goal reachability — the decisive number (voc_recipes)",
            "",
            f"- Recipes: {b['recipes']} · title goal parsed: {b['goal_parsed']} · unparsed: {b['goal_unparsed']}",
            f"- Goal **absent from the body entirely**: {b['goal_absent_from_body']} "
            f"(**{b['unreachable_rate_strict']:.1%}** of parsed goals)",
            f"- Goal only restated at the body head (itself a goal statement, not an ingredient mention): "
            f"{b['goal_restated_at_body_head']}",
            f"- Goal genuinely present later in the body: {b['goal_present_elsewhere_in_body']}",
            f"- Counting head restatements as unreachable-from-ingredients too: "
            f"**{b['unreachable_rate_incl_head_restatement']:.1%}**",
            "",
            f"Coverage bias check: the {b['goal_unparsed']} titles the parser could not "
            f"handle were scored with a cruder fallback (title minus leading number) and "
            f"came out **more** extreme, not less — {b['fallback_unparsed_absent_rate']:.1%} "
            f"absent. So the headline does not depend on which half parsed. Combined over "
            f"all scored recipes: **{b['combined_absent']}/{b['combined_scored']} = "
            f"{b['combined_absent_rate']:.1%}** name a goal in the title whose head word "
            f"never appears in the body.",
            "",
            "A goal absent from the body cannot be recovered by *any* body-anchored",
            "extractor at any window size — which is the structural claim behind the",
            "reframe, measured here on thousands of recipes rather than the 44 gold",
            "`COOKING_CREATION_Food_Product` values §9b–§9d argued over.",
            "",
        ]
        if b["examples_absent"]:
            lines += ["Examples where the goal never appears in the body:", ""]
            for example in b["examples_absent"][:5]:
                lines.append(f"- goal `{example['goal']}` — title: {example['title']!r}")
            lines.append("")

    if "C" in results:
        lines += [
            "## C. Segmentability by regime (long-KWIC) + cookbook contrast",
            "",
            "| Regime | passages | with units | rate | median units | top signals |",
            "|---|---:|---:|---:|---:|---|",
        ]
        for regime, stats in sorted(results["C"].items()):
            if regime.startswith("_"):
                continue
            top = ", ".join(f"{k}:{v}" for k, v in list(stats["signals"].items())[:3]) or "—"
            flag = " ⚠" if stats["small_bucket"] else ""
            lines.append(
                f"| {regime}{flag} | {stats['passages']} | {stats['with_units']} | "
                f"{stats['with_units_rate']:.1%} | {stats['median_units_when_present']} | {top} |"
            )
        lines += ["", "⚠ = under 30 passages, indicative only.", ""]
        ldk = results["C"].get("_ldk2025_cookbooks", {})
        if ldk.get("available"):
            lines += ["20th-c printed cookbooks (structural contrast):", ""]
            for name, stats in ldk["files"].items():
                lines.append(
                    f"- `{name}`: {stats['units']} units over {stats['chars']} chars "
                    f"({stats['units_per_10k_chars']}/10k chars)"
                )
            lines.append("")

    if "D" in results:
        d = results["D"]
        lines += [
            "## D. Affliction side (gold CURE_Affliction) — inconclusive by construction",
            "",
            f"> {d['caveat']}",
            "",
            f"- Gold rows with a non-empty value: {d['gold_rows_with_affliction']}"
            + (" ⚠ small" if d["small_bucket"] else ""),
            f"- Passages with no detectable unit structure: {d['passages_with_no_units']} "
            f"({d['no_units_rate']:.0%}) — the truncation artifact above, not a finding",
            f"- Current food-anchored ±{DEFAULT_CONTEXT_RADIUS} window contains the value: "
            f"{d['food_anchored_rate']:.1%}",
            f"- Unit-goal detection recovers it — exact {d['unit_goal_exact_rate']:.1%}, "
            f"soft {d['unit_goal_soft_rate']:.1%}",
            f"- Passages where no unit structure was detected at all: {d['passages_with_no_units']}",
            "",
            "Soft match is bidirectional containment (`soft_qualia_match`), so it is",
            "generous — check agreements by hand before trusting the soft figure",
            "(same caveat as docs/DECISIONS.md 2026-10-14).",
            "",
            "### By regime — the reframe is genre-bounded by construction",
            "",
            "In literary/descriptive text a food mention is incidental (a meal in a",
            "novel): there is no unit-with-a-goal to recover, and the current",
            "mention-based model is arguably correct there. A low literary number marks",
            "the reframe's **scope**, not its failure — the recipe/medical rows are the",
            "ones that decide it.",
            "",
            "| Regime | n | window contains | unit exact | unit soft | no units |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for regime, stats in d.get("by_regime", {}).items():
            flag = " ⚠" if stats["small_bucket"] else ""
            lines.append(
                f"| {regime}{flag} | {stats['n']} | {stats['window_rate']:.1%} | "
                f"{stats['exact_rate']:.1%} | {stats['soft_rate']:.1%} | {stats['no_units']} |"
            )
        lines += [
            "",
            "⚠ = under 30 rows, indicative only. `UNKNOWN`/`UNSET` is large because gold",
            "rows carry no document title, so regime inference has little to work with",
            "there — those rows are mostly recipe/remedy works in practice.",
            "",
        ]

    if "E" in results:
        e = results["E"]
        lines += [
            "## E. Cross-language: is this Dutch, or is it the genre?",
            "",
            "Same metric (`goal_body_reachability`) and the same *detected*-boundary",
            "basis on both sides, so the comparison is between traditions rather than",
            "between measurement methods. B's headline uses `voc_recipes`' given",
            "Title/Content split, which has no English equivalent.",
            "",
            "| Source | units | goals | head-token absent | first-token absent |",
            "|---|---:|---:|---:|---:|",
        ]
        for key in ("dutch_voc_recipes", "dutch_long_kwic_recipe_medical"):
            stats = e.get(key)
            if not stats:
                continue
            flag = " ⚠" if stats.get("small_bucket") else ""
            lines.append(
                f"| {key}{flag} | {stats.get('units', 0)} | {stats.get('with_goal', 0)} | "
                f"**{stats['head_token_absent_rate']:.1%}** | {stats['first_token_absent_rate']:.1%} |"
            )
        english = e.get("english", {})
        if english.get("available"):
            for genre, stats in english["by_genre"].items():
                flag = " ⚠" if stats.get("small_bucket") else ""
                lines.append(
                    f"| english {genre}{flag} | {stats.get('units', 0)} | {stats.get('with_goal', 0)} | "
                    f"**{stats['head_token_absent_rate']:.1%}** | {stats['first_token_absent_rate']:.1%} |"
                )
        else:
            lines.append(f"| english | — | — | export not found at {english.get('path')} | — |")
        lines += [
            "",
            "Two token choices are reported because they diverge by language and",
            "picking one silently decides the answer: English receipt titles are",
            "compositional (`CUCUMBER SOOP` = ingredient + dish type), so the first",
            "token is an ingredient that recurs in the body while the head noun may",
            "not; Middle Dutch titles are opaque dish names (`blancmengier`, `bruwet`)",
            "where neither appears.",
            "",
            "**Read:** the structural gap is present in both traditions but roughly",
            "half as severe in English — so it is a property of the recipe/remedy",
            "*genre*, amplified in Dutch by opaque culinary vocabulary, not an artifact",
            "of the Dutch corpus that produced the finding.",
            "",
        ]

    lines += [
        "## Decision gates",
        "",
        "- Unit-goal detection recovering materially more gold affliction/product",
        "  values than the food-anchored window → reframe supported; next step is a",
        "  design decision (two-stage Step C vs unit-based re-annotation), not a rewrite.",
        "- Low segmentability, or detected goals that disagree with gold → reframe",
        "  unsupported on this corpus; document as a negative like §9a/§9b/§9d.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        default=",".join(MEASUREMENTS),
        help=f"Comma-separated subset of {MEASUREMENTS} (default: all)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Cap voc_recipes rows (A/B)")
    parser.add_argument(
        "--literary-sample",
        type=int,
        default=300,
        help="Literary passages to use as negative control (default 300; the full pool is ~4.3k)",
    )
    parser.add_argument(
        "--english-export",
        default=DEFAULT_ENGLISH_EXPORT,
        help="INCEpTION English export annotation/ dir (measurement E)",
    )
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--summary", action="store_true", help="Print the report to stdout")
    args = parser.parse_args()

    wanted = {part.strip().upper() for part in args.only.split(",") if part.strip()}
    results: dict[str, Any] = {"finished_at": datetime.now(UTC).isoformat()}

    if "A" in wanted:
        results["A"] = measure_a_segmenter_vs_known(args.limit)
    if "B" in wanted:
        results["B"] = measure_b_goal_reachability(args.limit)
    if "C" in wanted:
        results["C"] = measure_c_segmentability(args.literary_sample)
    if "D" in wanted:
        results["D"] = measure_d_affliction_side()
    if "E" in wanted:
        results["E"] = measure_e_cross_language(args.english_export, args.limit)

    out_dir = Path(args.output_dir) if args.output_dir else Path(_resolve_output_dir())
    out_dir.mkdir(parents=True, exist_ok=True)
    report = _render_report(results)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    (out_dir / "metrics.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if args.summary:
        print(report)
    print(json.dumps({"report": str(out_dir / "report.md"), "metrics": str(out_dir / "metrics.json")}, indent=2))


def _resolve_output_dir() -> str:
    """Resolve the report dir, tolerating a manifest without the logical.

    `data_manifest.toml` is gitignored (machine-local paths) and the tracked
    `.example` is only a starter template, so a checkout elsewhere may not have
    `unit_feasibility` defined — same fallback shape as
    `scripts/export_stepc_span.py`.
    """
    from data_io import resolve

    try:
        return resolve("unit_feasibility")
    except Exception:
        return "trifecta/unit_feasibility"


if __name__ == "__main__":
    main()
