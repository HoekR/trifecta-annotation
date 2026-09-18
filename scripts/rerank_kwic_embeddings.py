#!/usr/bin/env python3
"""Re-rank existing KWIC inputs with embedding centroids + NONE margin (E5a)."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

import numpy as np
from data_io import load_jsonl, resolve, save_semi_structured

from trifecta_annotation.embedding_candidates import (
    FOOD_QUERY_FRAMES,
    GysbertEmbedder,
    frame_centroids_from_embeddings,
    load_exemplars_jsonl,
    l2_normalize,
)
from trifecta_annotation.schemas import KwicInput


def _sample_rows(rows: list[dict], *, limit: int | None, seed: int) -> list[dict]:
    if limit is None or len(rows) <= limit:
        return list(rows)
    rng = random.Random(seed)
    return rng.sample(rows, limit)


def _score_rows_per_frame(
    rows: list[dict],
    vectors: np.ndarray,
    centroids: dict[str, np.ndarray],
    *,
    none_margin: float,
    frames: tuple[str, ...] = FOOD_QUERY_FRAMES,
) -> dict[str, list[dict]]:
    """Score every row against each food frame; keep those beating NONE+margin (or margin fallback)."""
    mat = l2_normalize(vectors)
    none_vec = centroids.get("NONE")
    none_scores = (
        (mat @ l2_normalize(none_vec.reshape(1, -1)).T).ravel()
        if none_vec is not None
        else np.full(len(rows), np.nan)
    )
    per_frame: dict[str, list[dict]] = {f: [] for f in frames}
    for frame in frames:
        if frame not in centroids:
            continue
        scores = (mat @ l2_normalize(centroids[frame].reshape(1, -1)).T).ravel()
        for i, row in enumerate(rows):
            score = float(scores[i])
            none_score = float(none_scores[i]) if none_vec is not None else None
            if none_score is not None and score < none_score + none_margin:
                continue
            out = dict(row)
            out["frame_hint"] = frame
            out["embedding_score"] = score
            out["none_score"] = none_score
            out["kwic_mode"] = "embedding_rerank"
            per_frame[frame].append(out)
        per_frame[frame].sort(key=lambda r: float(r["embedding_score"]), reverse=True)

    # Fallback for empty frames: rank by (score - none) without hard margin.
    if none_vec is not None:
        for frame in frames:
            if per_frame.get(frame) or frame not in centroids:
                continue
            scores = (mat @ l2_normalize(centroids[frame].reshape(1, -1)).T).ravel()
            margin = scores - none_scores
            order = np.argsort(-margin)
            filled: list[dict] = []
            for i in order[: max(len(rows), 1)]:
                idx = int(i)
                out = dict(rows[idx])
                out["frame_hint"] = frame
                out["embedding_score"] = float(scores[idx])
                out["none_score"] = float(none_scores[idx])
                out["kwic_mode"] = "embedding_rerank"
                filled.append(out)
            per_frame[frame] = filled
    return per_frame


def _apply_frame_quota_from_buckets(
    per_frame: dict[str, list[dict]],
    *,
    keep: int,
    frames: tuple[str, ...] = FOOD_QUERY_FRAMES,
) -> list[dict]:
    cursors = {f: 0 for f in frames}
    selected: list[dict] = []
    seen: set[str] = set()
    while len(selected) < keep:
        progressed = False
        for frame in frames:
            if len(selected) >= keep:
                break
            bucket = per_frame.get(frame) or []
            while cursors[frame] < len(bucket):
                row = bucket[cursors[frame]]
                cursors[frame] += 1
                rid = str(row.get("record_id") or id(row))
                if rid in seen:
                    continue
                seen.add(rid)
                selected.append(row)
                progressed = True
                break
        if not progressed:
            break
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="KWIC embedding re-ranker (E5a).")
    parser.add_argument("--input-logical", default="kwic_inputs")
    parser.add_argument("--input-path", type=Path, default=None)
    parser.add_argument("--exemplars-logical", default="embedding_exemplars")
    parser.add_argument("--sample-limit", type=int, default=2000, help="KWIC rows to score")
    parser.add_argument("--keep", type=int, default=500, help="Rows to keep after re-rank")
    parser.add_argument("--none-margin", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--no-frame-quota", action="store_true")
    parser.add_argument("--output-logical", default="embedding_kwic_reranked")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    in_path = args.input_path or Path(resolve(args.input_logical))
    rows = _sample_rows(load_jsonl(in_path), limit=args.sample_limit, seed=args.seed)
    if not rows:
        raise SystemExit(f"No KWIC rows in {in_path}")

    exemplars = load_exemplars_jsonl(resolve(args.exemplars_logical))
    embedder = GysbertEmbedder()

    def _encode(texts: list[str]) -> np.ndarray:
        return embedder.encode(texts, batch_size=args.batch_size)

    centroids = frame_centroids_from_embeddings(exemplars, _encode)
    vectors = _encode([str(r.get("context_text") or "") for r in rows])
    per_frame = _score_rows_per_frame(
        rows, vectors, centroids, none_margin=args.none_margin
    )
    passed = sum(len(v) for v in per_frame.values())
    if args.no_frame_quota:
        flat = [r for bucket in per_frame.values() for r in bucket]
        flat.sort(key=lambda r: float(r.get("embedding_score") or 0.0), reverse=True)
        seen: set[str] = set()
        kept = []
        for row in flat:
            rid = str(row.get("record_id") or id(row))
            if rid in seen:
                continue
            seen.add(rid)
            kept.append(row)
            if len(kept) >= args.keep:
                break
    else:
        kept = _apply_frame_quota_from_buckets(per_frame, keep=args.keep)

    # Validate as KwicInput + keep scores
    out_rows: list[dict] = []
    for row in kept:
        payload = {
            k: row.get(k)
            for k in (
                "record_id",
                "corpus",
                "target_word",
                "context_text",
                "date",
                "source_path",
                "title",
                "candidate_terms",
                "text_regime",
                "kwic_mode",
                "kwic_batch",
                "discovery_verb",
                "frame_hint",
            )
        }
        dumped = KwicInput.model_validate(payload).model_dump(mode="json")
        dumped["embedding_score"] = row.get("embedding_score")
        dumped["none_score"] = row.get("none_score")
        out_rows.append(dumped)

    path = save_semi_structured(
        out_rows,
        logical_name=args.output_logical,
        script=__file__,
    )
    report = {
        "input": str(in_path),
        "scored": len(rows),
        "passed_none_margin_assignments": passed,
        "kept": len(out_rows),
        "pass_rate": round(passed / max(len(rows) * max(len(FOOD_QUERY_FRAMES), 1), 1), 4),
        "frame_hint": dict(Counter(str(r.get("frame_hint")) for r in out_rows)),
        "none_margin": args.none_margin,
        "frame_quota": not args.no_frame_quota,
        "output": str(path),
    }
    report_path = Path(path).parent / "e5a_rerank_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.summary:
        print(json.dumps(report, indent=2))
    else:
        print(path)


if __name__ == "__main__":
    main()
