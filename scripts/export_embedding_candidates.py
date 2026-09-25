#!/usr/bin/env python3
"""Export hybrid embedding candidates with thesaurus LU anchors (E3).

Heavy: loads GysBERT and embeds a bounded passage pool. Prefer running in a
dedicated terminal (not via the agent) for large --passage-limit values.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from data_io import resolve, save_semi_structured
from data_io.provenance import ProvenanceRecord, git_commit_hash, write_sidecar

from trifecta_annotation.embedding_candidates import (
    FOOD_QUERY_FRAMES,
    GysbertEmbedder,
    chunk_passages,
    frame_centroids_from_embeddings,
    hybrid_candidates_from_ranked,
    load_exemplars_jsonl,
    retrieve_chunks_by_frame,
    unique_passages_from_long_kwic,
)
from trifecta_annotation.schemas import KwicInput
from trifecta_annotation.thesaurus import DEFAULT_DENYLIST, alt_label_index, build_thesaurus
from trifecta_annotation.vocabulary import load_food_terms


def _rows_to_kwic_dicts(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
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
        # Preserve ranking metadata outside the strict schema via model_dump extras? 
        # KwicInput rejects unknown fields by default — keep schema-clean JSONL and
        # write scores into a parallel sidecar summary.
        kwic = KwicInput.model_validate(payload)
        dumped = kwic.model_dump(mode="json")
        dumped["embedding_score"] = row.get("embedding_score")
        dumped["none_score"] = row.get("none_score")
        dumped["pref_label"] = row.get("pref_label")
        dumped["chunk_id"] = row.get("chunk_id")
        out.append(dumped)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid embedding candidate export (E3).")
    parser.add_argument("--passage-limit", type=int, default=200,
                        help="Unique passages to index (default 200 pilot; raise toward 5000 after smoke)")
    parser.add_argument("--candidate-limit", type=int, default=500)
    parser.add_argument(
        "--top-k-per-frame",
        type=int,
        default=500,
        help="Max chunks kept per food frame after NONE margin filter",
    )
    parser.add_argument("--none-margin", type=float, default=0.0)
    parser.add_argument("--max-chars", type=int, default=300)
    parser.add_argument("--overlap", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=0, help="Passage sample seed")
    parser.add_argument(
        "--exemplars-logical",
        default="embedding_exemplars",
        help="Manifest key for exemplar JSONL",
    )
    parser.add_argument("--snippets-logical", default="food_snippets_long_kwic")
    parser.add_argument("--model", default=None, help="Override embedder model id")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chunk + LU stats only (no model encode / no write)",
    )
    parser.add_argument("--summary", action="store_true")
    parser.add_argument(
        "--no-frame-quota",
        action="store_true",
        help="Disable round-robin frame quotas (legacy best-frame merge)",
    )
    args = parser.parse_args()

    long = pd.read_csv(resolve(args.snippets_logical))
    passages = unique_passages_from_long_kwic(
        long, passage_limit=args.passage_limit, seed=args.seed
    )
    chunks = chunk_passages(passages, max_chars=args.max_chars, overlap=args.overlap)
    passages_by_id = {p["source_record_id"]: p for p in passages}

    thesaurus = build_thesaurus(food_terms=load_food_terms())
    alias_index = alt_label_index(thesaurus, kept_only=True)

    if args.dry_run:
        from trifecta_annotation.embedding_candidates import find_lu_anchor

        anchored_n = sum(
            1
            for c in chunks
            if find_lu_anchor(c.text, alias_index, denylist=DEFAULT_DENYLIST) is not None
        )
        print(
            json.dumps(
                {
                    "passages": len(passages),
                    "chunks": len(chunks),
                    "chunks_with_lu": anchored_n,
                    "alias_index_size": len(alias_index),
                },
                indent=2,
            )
        )
        return

    exemplars = load_exemplars_jsonl(resolve(args.exemplars_logical))
    embedder = GysbertEmbedder(model_name=args.model) if args.model else GysbertEmbedder()

    def _encode(texts: list[str]) -> np.ndarray:
        return embedder.encode(texts, batch_size=args.batch_size)

    centroids = frame_centroids_from_embeddings(exemplars, _encode)
    chunk_vecs = _encode([c.text for c in chunks])
    ranked = retrieve_chunks_by_frame(
        chunk_vecs,
        centroids,
        frames=FOOD_QUERY_FRAMES,
        top_k_per_frame=args.top_k_per_frame,
        none_margin=args.none_margin,
        quota_mode=not args.no_frame_quota,
        candidate_limit=args.candidate_limit * 2,  # headroom before LU filter
    )
    anchored, semantic_only, stats = hybrid_candidates_from_ranked(
        ranked,
        chunks,
        passages_by_id,
        alias_index,
        candidate_limit=args.candidate_limit,
        denylist=DEFAULT_DENYLIST,
        frame_quota=not args.no_frame_quota,
    )

    kwic_rows = _rows_to_kwic_dicts(anchored)
    cand_path = save_semi_structured(
        kwic_rows,
        logical_name="embedding_candidates",
        script=__file__,
    )
    sem_path = save_semi_structured(
        semantic_only,
        logical_name="embedding_candidates_semantic_only",
        script=__file__,
    )

    # Lightweight chunk index metadata (no vectors — keep pilot scratch small).
    index_path = resolve("embedding_chunk_index")
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_rows = [c.to_dict() for c in chunks]
    with index_path.open("w", encoding="utf-8") as handle:
        for row in index_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_sidecar(
        index_path,
        ProvenanceRecord(
            logical_name="embedding_chunk_index",
            phase="semi",
            parent_sources=["food_snippets_long_kwic"],
            description="Chunk metadata for embedding pilot (no vectors)",
            created_by_script=__file__,
            record_count=len(index_rows),
            git_commit=git_commit_hash(index_path.parent),
        ),
    )

    report = {
        "passages": len(passages),
        "chunks": len(chunks),
        "centroids": {k: True for k in centroids},
        "stats": stats,
        "candidates_path": str(cand_path),
        "semantic_only_path": str(sem_path),
        "chunk_index_path": str(index_path),
        "model": embedder.model_name,
        "passage_limit": args.passage_limit,
        "candidate_limit": args.candidate_limit,
    }
    report_path = Path(resolve("embedding_candidates")).parent / "e3_export_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.summary:
        print(json.dumps(report, indent=2))
    else:
        print(cand_path)


if __name__ == "__main__":
    main()
