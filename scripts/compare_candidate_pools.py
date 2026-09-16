#!/usr/bin/env python3
"""Compare embedding hybrid candidates vs a KWIC sample (E4).

First-pass metrics only (no full A→B→C). Optional Step A comparison is documented
for the operator to run separately.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from data_io import load_jsonl, resolve

from trifecta_annotation.embedding_candidates import find_lu_anchor
from trifecta_annotation.gold_io import load_gold_records
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.thesaurus import DEFAULT_DENYLIST, alt_label_index, build_thesaurus
from trifecta_annotation.vocabulary import load_food_terms


def _load_pool(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    if limit is not None:
        rows = rows[: int(limit)]
    return rows


def _batch_hist(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        raw = str(row.get("kwic_batch") or "").strip()
        if not raw:
            counts["(missing)"] += 1
            continue
        for part in raw.split("|"):
            tag = part.strip().lower()
            if tag:
                counts[tag] += 1
    return dict(counts.most_common())


def _frame_hint_hist(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(r.get("frame_hint") or "(none)") for r in rows).most_common())


def _denylist_hit_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    hits = 0
    for row in rows:
        target = normalize_hist_dutch(str(row.get("target_word") or ""))
        if target in DEFAULT_DENYLIST:
            hits += 1
    return hits / len(rows)


def _gold_lookups(gold_records: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """Return (food_context_norms, none_context_norms) keyed by normalized context+target."""
    food: set[str] = set()
    none: set[str] = set()
    for rec in gold_records:
        prov = rec.get("provenance") or {}
        ctx = normalize_hist_dutch(str(prov.get("context_text") or ""))
        tgt = normalize_hist_dutch(str(prov.get("target_word") or ""))
        if not ctx:
            continue
        key = f"{tgt}||{ctx[:240]}"
        dropped = bool(rec.get("dropped"))
        step_b = rec.get("step_b") or {}
        frame = step_b.get("selected_frame")
        frame_s = frame if isinstance(frame, str) else getattr(frame, "value", None)
        if dropped or frame_s in {None, "NONE"}:
            none.add(key)
        else:
            food.add(key)
    return food, none


def _overlap_with_gold(
    rows: list[dict[str, Any]],
    food_keys: set[str],
    none_keys: set[str],
) -> dict[str, int]:
    food_hits = 0
    none_hits = 0
    for row in rows:
        ctx = normalize_hist_dutch(str(row.get("context_text") or ""))
        tgt = normalize_hist_dutch(str(row.get("target_word") or ""))
        key = f"{tgt}||{ctx[:240]}"
        if key in food_keys:
            food_hits += 1
        if key in none_keys:
            none_hits += 1
    return {"gold_food_overlap": food_hits, "gold_none_overlap": none_hits}


def _pool_metrics(
    name: str,
    rows: list[dict[str, Any]],
    *,
    food_keys: set[str],
    none_keys: set[str],
    alias_index: dict[str, str],
) -> dict[str, Any]:
    lu_ok = 0
    for row in rows:
        ctx = str(row.get("context_text") or "")
        tgt = str(row.get("target_word") or "").strip()
        if not tgt:
            continue
        hit = find_lu_anchor(ctx, alias_index, denylist=DEFAULT_DENYLIST)
        if hit and normalize_hist_dutch(hit["target_word"]) == normalize_hist_dutch(tgt):
            lu_ok += 1
        elif hit:
            lu_ok += 1  # any LU still present in window
    return {
        "name": name,
        "n": len(rows),
        "denylist_target_rate": round(_denylist_hit_rate(rows), 4),
        "kwic_batch": _batch_hist(rows),
        "frame_hint": _frame_hint_hist(rows),
        "lu_present_rate": round(lu_ok / max(len(rows), 1), 4),
        **_overlap_with_gold(rows, food_keys, none_keys),
        "mean_embedding_score": _mean_float(rows, "embedding_score"),
        "mean_none_score": _mean_float(rows, "none_score"),
    }


def _mean_float(rows: list[dict[str, Any]], key: str) -> float | None:
    vals = [float(r[key]) for r in rows if r.get(key) is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 4)


def _sample_kwic_baseline(*, limit: int, seed: int) -> list[dict[str, Any]]:
    """Sample KWIC inputs from existing kwic_inputs or rebuild from long_kwic via adapter."""
    path = Path(resolve("kwic_inputs"))
    if path.is_file():
        rows = load_jsonl(path)
        if len(rows) >= limit:
            rng = random.Random(seed)
            return rng.sample(rows, limit)
        return rows[:limit]

    from trifecta_annotation.adapters.food_snippets import load_kwic_inputs_from_food_snippets_long

    records, _skipped = load_kwic_inputs_from_food_snippets_long(limit=limit)
    return [r.model_dump(mode="json") for r in records]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare embedding vs KWIC candidate pools (E4).")
    parser.add_argument("--embedding-path", type=Path, default=None)
    parser.add_argument("--kwic-path", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Default: scratch trifecta/embedding/e4_compare_report.json",
    )
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    emb_path = args.embedding_path or Path(resolve("embedding_candidates"))
    if not emb_path.is_file():
        raise SystemExit(f"Missing embedding candidates: {emb_path} (run export_embedding_candidates.py)")

    emb_rows = _load_pool(emb_path, limit=args.limit)
    if args.kwic_path is not None:
        kwic_rows = _load_pool(args.kwic_path, limit=args.limit)
    else:
        kwic_rows = _sample_kwic_baseline(limit=args.limit, seed=args.seed)

    gold = load_gold_records()
    food_keys, none_keys = _gold_lookups(gold)
    alias_index = alt_label_index(build_thesaurus(food_terms=load_food_terms()), kept_only=True)

    report = {
        "limit": args.limit,
        "seed": args.seed,
        "embedding": _pool_metrics(
            "embedding_hybrid",
            emb_rows,
            food_keys=food_keys,
            none_keys=none_keys,
            alias_index=alias_index,
        ),
        "kwic": _pool_metrics(
            "kwic_baseline",
            kwic_rows,
            food_keys=food_keys,
            none_keys=none_keys,
            alias_index=alias_index,
        ),
        "semantic_only_n": None,
        "next_optional_step_a": (
            "uv run python scripts/batch_step_a.py "
            "--input-logical embedding_candidates --output-path "
            "\"$SCRATCH/trifecta/embedding/step_a_emb.jsonl\" --concurrency 2 --resume"
        ),
    }

    sem_path = Path(resolve("embedding_candidates_semantic_only"))
    if sem_path.is_file():
        report["semantic_only_n"] = len(load_jsonl(sem_path))

    out = args.output_path or (Path(resolve("embedding_candidates")).parent / "e4_compare_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.summary:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(out)


if __name__ == "__main__":
    main()
