"""Tests for E3 hybrid retrieve + LU anchor (no HF download)."""

from __future__ import annotations

import numpy as np

from trifecta_annotation.embedding_candidates import (
    TextChunk,
    find_lu_anchor,
    frame_centroids_from_embeddings,
    hybrid_candidates_from_ranked,
    retrieve_chunks_by_frame,
)


def test_find_lu_anchor_longest_wins() -> None:
    alias = {"boter": "boter", "roomboter": "roomboter", "suiker": "suiker"}
    hit = find_lu_anchor("Neem roomboter en suiker.", alias)
    assert hit is not None
    assert hit["pref_label"] == "roomboter"


def test_find_lu_anchor_skips_denylist() -> None:
    alias = {"mede": "mede", "boter": "boter"}
    hit = find_lu_anchor("Met mede en boter.", alias)
    assert hit is not None
    assert hit["pref_label"] == "boter"


def test_find_lu_anchor_none() -> None:
    assert find_lu_anchor("Geen voedsel hier.", {"boter": "boter"}) is None


def test_retrieve_prefers_food_over_none() -> None:
    # 2-d embeddings: chunk0 near cooking, chunk1 near none
    chunks = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    centroids = {
        "COOKING_CREATION": np.array([1.0, 0.0], dtype=np.float32),
        "NONE": np.array([0.0, 1.0], dtype=np.float32),
    }
    ranked = retrieve_chunks_by_frame(
        chunks, centroids, frames=("COOKING_CREATION",), top_k_per_frame=2
    )
    assert len(ranked) == 1
    assert ranked[0]["chunk_index"] == 0
    assert ranked[0]["frame_hint"] == "COOKING_CREATION"


def test_retrieve_quota_round_robin() -> None:
    # Three chunks, each aligned to a different food frame.
    chunks = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.9, 0.1, 0.0],  # also cooking-ish
        ],
        dtype=np.float32,
    )
    centroids = {
        "COOKING_CREATION": np.array([1.0, 0.0, 0.0], dtype=np.float32),
        "CURE": np.array([0.0, 1.0, 0.0], dtype=np.float32),
        "INGESTION": np.array([0.0, 0.0, 1.0], dtype=np.float32),
        "NONE": np.array([-1.0, -1.0, -1.0], dtype=np.float32),
    }
    ranked = retrieve_chunks_by_frame(
        chunks,
        centroids,
        frames=("COOKING_CREATION", "CURE", "INGESTION"),
        top_k_per_frame=2,
        quota_mode=True,
        candidate_limit=3,
    )
    hints = [r["frame_hint"] for r in ranked]
    assert set(hints) == {"COOKING_CREATION", "CURE", "INGESTION"}
    assert len(ranked) == 3


def test_frame_centroids_mean() -> None:
    exemplars = {
        "COOKING_CREATION": [
            {"context_text": "a"},
            {"context_text": "b"},
        ]
    }

    def encode(texts):
        # map a -> [1,0], b -> [0,1]
        rows = []
        for t in texts:
            rows.append([1.0, 0.0] if t == "a" else [0.0, 1.0])
        return np.array(rows, dtype=np.float32)

    cents = frame_centroids_from_embeddings(exemplars, encode)
    vec = cents["COOKING_CREATION"]
    np.testing.assert_allclose(np.linalg.norm(vec), 1.0, atol=1e-5)


def test_hybrid_splits_semantic_only() -> None:
    chunks = [
        TextChunk("d1::c0", "Neem boter in de pan.", 0, 20, "d1"),
        TextChunk("d1::c1", "Reizen naar Indië.", 0, 18, "d1"),
    ]
    ranked = [
        {"chunk_index": 0, "frame_hint": "COOKING_CREATION", "score": 0.9, "none_score": 0.1},
        {"chunk_index": 1, "frame_hint": "COOKING_CREATION", "score": 0.8, "none_score": 0.2},
    ]
    passages = {"d1": {"corpus": "test", "title": "t", "source_path": "f.xml", "kwic_batch": "recept"}}
    alias = {"boter": "boter"}
    anchored, semantic, stats = hybrid_candidates_from_ranked(
        ranked, chunks, passages, alias, candidate_limit=10
    )
    assert len(anchored) == 1
    assert anchored[0]["target_word"].lower() == "boter"
    assert anchored[0]["kwic_mode"] == "embedding_hybrid"
    assert len(semantic) == 1
    assert stats["anchored"] == 1
