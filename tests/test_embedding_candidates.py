"""Unit tests for embedding candidate helpers (no HF download)."""

from __future__ import annotations

import numpy as np
import pytest

from trifecta_annotation.embedding_candidates import (
    TextChunk,
    chunk_passage,
    cosine_similarity,
    l2_normalize,
    mean_pool,
)


def test_chunk_passage_empty() -> None:
    assert chunk_passage("") == []
    assert chunk_passage("   ") == []


def test_chunk_passage_short_single() -> None:
    text = "Neem suiker en boter."
    chunks = chunk_passage(text, max_chars=300, overlap=50)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].start_char == 0
    assert chunks[0].end_char == len(text)
    assert chunks[0].chunk_id == "c0"


def test_chunk_passage_overlap_and_coverage() -> None:
    # Build a long multi-sentence string.
    sentences = [f"Zin nummer {i} over voedsel en bereiding." for i in range(20)]
    text = " ".join(sentences)
    chunks = chunk_passage(text, max_chars=80, overlap=20, source_record_id="r1")
    assert len(chunks) >= 3
    assert all(isinstance(c, TextChunk) for c in chunks)
    assert all(len(c.text) <= 80 for c in chunks)
    assert all(c.source_record_id == "r1" for c in chunks)
    # First chunk starts at 0; last ends near end of text.
    assert chunks[0].start_char == 0
    assert chunks[-1].end_char <= len(text)
    # Reconstruct roughly: every char should appear in some chunk window.
    covered = np.zeros(len(text), dtype=bool)
    for c in chunks:
        covered[c.start_char : c.end_char] = True
    # Allow small uncovered gaps only from strip/whitespace edge cases.
    assert covered.mean() > 0.9


def test_chunk_passage_rejects_bad_overlap() -> None:
    with pytest.raises(ValueError):
        chunk_passage("abc", max_chars=10, overlap=10)
    with pytest.raises(ValueError):
        chunk_passage("abc", max_chars=0, overlap=0)


def test_l2_normalize_unit_rows() -> None:
    mat = np.array([[3.0, 4.0], [0.0, 2.0]], dtype=np.float32)
    out = l2_normalize(mat)
    norms = np.linalg.norm(out, axis=1)
    np.testing.assert_allclose(norms, [1.0, 1.0], atol=1e-5)


def test_cosine_similarity_identical() -> None:
    a = np.array([[1.0, 0.0], [0.0, 2.0]], dtype=np.float32)
    sims = cosine_similarity(a, a)
    np.testing.assert_allclose(np.diag(sims), [1.0, 1.0], atol=1e-5)


def test_mean_pool_masks_padding() -> None:
    # batch=1, seq=3, hidden=2 — last token is padding
    hidden = np.array([[[1.0, 1.0], [3.0, 3.0], [99.0, 99.0]]], dtype=np.float32)
    mask = np.array([[1, 1, 0]], dtype=np.int64)
    pooled = mean_pool(hidden, mask)
    np.testing.assert_allclose(pooled, [[2.0, 2.0]], atol=1e-5)


def test_text_chunk_to_dict() -> None:
    c = TextChunk("c0", "boter", 0, 5, source_record_id="x")
    d = c.to_dict()
    assert d["chunk_id"] == "c0"
    assert d["text"] == "boter"
    assert d["source_record_id"] == "x"
