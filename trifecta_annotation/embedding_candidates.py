"""Chunk passages and embed texts for hybrid candidate retrieval.

Pilot track: plans/steps/EMBEDDING_CANDIDATES.md (E1–E3).
Mean-pooled GysBERT vectors; thesaurus LU anchoring for KwicInput export.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

DEFAULT_EMBED_MODEL = "emanjavacas/gysbert"
DEFAULT_MAX_CHARS = 300
DEFAULT_OVERLAP = 50
DEFAULT_MAX_LENGTH = 256

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…;:])\s+|\n+")


@dataclass(frozen=True)
class TextChunk:
    """One window cut from a longer passage."""

    chunk_id: str
    text: str
    start_char: int
    end_char: int
    source_record_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "source_record_id": self.source_record_id,
        }


def chunk_passage(
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
    source_record_id: str | None = None,
    chunk_id_prefix: str = "c",
) -> list[TextChunk]:
    """Split *text* into overlapping character windows, preferring sentence boundaries.

    Short texts (≤ max_chars) yield a single chunk. Overlap is applied between
    successive windows; windows never exceed max_chars.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    if max_chars < 1:
        raise ValueError("max_chars must be >= 1")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be >= 0 and < max_chars")

    if len(cleaned) <= max_chars:
        return [
            TextChunk(
                chunk_id=f"{chunk_id_prefix}0",
                text=cleaned,
                start_char=0,
                end_char=len(cleaned),
                source_record_id=source_record_id,
            )
        ]

    spans = _sentence_spans(cleaned)
    windows: list[tuple[int, int]] = []
    start = 0
    n = len(cleaned)
    while start < n:
        hard_end = min(start + max_chars, n)
        end = _prefer_sentence_end(spans, start, hard_end, cleaned)
        if end <= start:
            end = hard_end
        windows.append((start, end))
        if end >= n:
            break
        next_start = max(end - overlap, start + 1)
        # Skip leading whitespace on the next window.
        while next_start < n and cleaned[next_start].isspace():
            next_start += 1
        start = next_start

    chunks: list[TextChunk] = []
    for i, (s, e) in enumerate(windows):
        piece = cleaned[s:e].strip()
        if not piece:
            continue
        # Re-align start/end to stripped piece inside the original window.
        rel = cleaned[s:e].find(piece)
        abs_s = s + (rel if rel >= 0 else 0)
        abs_e = abs_s + len(piece)
        chunks.append(
            TextChunk(
                chunk_id=f"{chunk_id_prefix}{i}",
                text=piece,
                start_char=abs_s,
                end_char=abs_e,
                source_record_id=source_record_id,
            )
        )
    return chunks


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    pos = 0
    for part in _SENTENCE_SPLIT.split(text):
        if not part:
            continue
        idx = text.find(part, pos)
        if idx < 0:
            idx = pos
        end = idx + len(part)
        spans.append((idx, end))
        pos = end
    if not spans:
        return [(0, len(text))]
    return spans


def _prefer_sentence_end(
    spans: Sequence[tuple[int, int]],
    start: int,
    hard_end: int,
    text: str,
) -> int:
    """Pick the latest sentence end in (start, hard_end]; else hard_end."""
    best = hard_end
    found = False
    for _s, e in spans:
        if e <= start:
            continue
        if e > hard_end:
            break
        best = e
        found = True
    if found:
        return best
    # Soft fallback: break on last whitespace before hard_end.
    window = text[start:hard_end]
    ws = window.rfind(" ")
    if ws > max_chars_soft_min(hard_end - start):
        return start + ws
    return hard_end


def max_chars_soft_min(window_len: int) -> int:
    """Minimum cut position when falling back to whitespace (avoid tiny tails)."""
    return max(window_len // 3, 1)


def l2_normalize(matrix: np.ndarray, *, eps: float = 1e-12) -> np.ndarray:
    """Row-wise L2 normalize a 2D array."""
    arr = np.asarray(matrix, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / np.maximum(norms, eps)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between rows of *a* (n,d) and *b* (m,d) → (n,m).

    Inputs are L2-normalized first so the product is cosine.
    """
    a_n = l2_normalize(a)
    b_n = l2_normalize(b)
    return a_n @ b_n.T


def mean_pool(
    last_hidden: np.ndarray,
    attention_mask: np.ndarray,
) -> np.ndarray:
    """Mean-pool token embeddings with attention mask (batch, seq, hidden)."""
    mask = attention_mask.astype(np.float32)[..., None]
    summed = (last_hidden * mask).sum(axis=1)
    counts = np.maximum(mask.sum(axis=1), 1e-9)
    return summed / counts


FRAME_QUERY_LABELS: tuple[str, ...] = (
    "COOKING_CREATION",
    "CURE",
    "INGESTION",
    "PRESERVING",
    "NONE",
)


def _gold_selected_frame(record: dict[str, Any]) -> str | None:
    """Return gold macro-frame label, mapping early dropout to NONE."""
    if record.get("dropped"):
        return "NONE"
    step_b = record.get("step_b") or {}
    frame = step_b.get("selected_frame")
    if frame is None:
        return None
    if isinstance(frame, str):
        raw = frame
    else:
        raw = getattr(frame, "value", str(frame))
    if raw in {"USING_CURE", "CURE"}:
        return "CURE"
    if raw in {"USING_INGESTION", "INGESTION"}:
        return "INGESTION"
    if raw in FRAME_QUERY_LABELS:
        return raw
    return None


def _gold_provenance(record: dict[str, Any]) -> dict[str, Any]:
    prov = record.get("provenance") or {}
    return prov if isinstance(prov, dict) else {}


def exemplar_from_gold_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Map one gold annotation dict to an embedding query exemplar, or None."""
    frame = _gold_selected_frame(record)
    if frame is None:
        return None
    prov = _gold_provenance(record)
    context = str(prov.get("context_text") or "").strip()
    target = str(prov.get("target_word") or "").strip()
    if not context:
        return None
    record_id = str(prov.get("record_id") or record.get("record_id") or "").strip()
    return {
        "record_id": record_id,
        "context_text": context,
        "target_word": target,
        "selected_frame": frame,
        "corpus": prov.get("corpus"),
        "text_regime": prov.get("text_regime"),
        "kwic_batch": prov.get("kwic_batch"),
        "dropped": bool(record.get("dropped")),
    }


def build_frame_exemplars(
    gold_records: Sequence[dict[str, Any]],
    *,
    per_frame_cap: int = 30,
    frames: Sequence[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Group gold rows into per-frame exemplar lists (capped, insertion order).

    Dropped / NONE gold rows feed the NONE contrast set. Frames with no rows
    still appear as empty lists when listed in *frames* (default: all five).
    """
    wanted = list(frames) if frames is not None else list(FRAME_QUERY_LABELS)
    buckets: dict[str, list[dict[str, Any]]] = {f: [] for f in wanted}
    for record in gold_records:
        ex = exemplar_from_gold_record(record)
        if ex is None:
            continue
        frame = ex["selected_frame"]
        if frame not in buckets:
            continue
        if len(buckets[frame]) >= per_frame_cap:
            continue
        buckets[frame].append(ex)
    return buckets


def exemplar_summary(exemplars: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    """Counts per frame for CLI / reports."""
    return {frame: len(rows) for frame, rows in exemplars.items()}


FOOD_QUERY_FRAMES: tuple[str, ...] = (
    "COOKING_CREATION",
    "CURE",
    "INGESTION",
    "PRESERVING",
)


def load_exemplars_jsonl(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Load flat exemplar JSONL (from ``build_embedding_exemplars``) into frame buckets."""
    from data_io import load_jsonl

    buckets: dict[str, list[dict[str, Any]]] = {f: [] for f in FRAME_QUERY_LABELS}
    for row in load_jsonl(path):
        frame = str(row.get("selected_frame") or "")
        if frame not in buckets:
            continue
        buckets[frame].append(row)
    return buckets


def frame_centroids_from_embeddings(
    exemplars: dict[str, list[dict[str, Any]]],
    encode_fn,
) -> dict[str, np.ndarray]:
    """Mean-pool exemplar embeddings per frame → L2-normalized centroids.

    *encode_fn* maps ``Sequence[str]`` → ``(n, d)`` array (already L2-normalized preferred).
    """
    centroids: dict[str, np.ndarray] = {}
    for frame, rows in exemplars.items():
        texts = [str(r.get("context_text") or "").strip() for r in rows]
        texts = [t for t in texts if t]
        if not texts:
            continue
        mat = np.asarray(encode_fn(texts), dtype=np.float32)
        if mat.size == 0:
            continue
        centroid = mat.mean(axis=0, keepdims=True)
        centroids[frame] = l2_normalize(centroid)[0]
    return centroids


def find_lu_anchor(
    text: str,
    alias_to_pref: dict[str, str],
    *,
    denylist: frozenset[str] | None = None,
    min_alias_len: int = 3,
) -> dict[str, str] | None:
    """Longest thesaurus alias (whole-token) in *text*; skip denylist norms.

    Returns ``{target_word, pref_label, alias_norm}`` or None.
    """
    from trifecta_annotation.normalize import normalize_hist_dutch
    from trifecta_annotation.thesaurus import DEFAULT_DENYLIST

    blocked = denylist if denylist is not None else DEFAULT_DENYLIST
    if not text or not alias_to_pref:
        return None

    # Tokenize surface forms; match on normalized tokens (and multi-token aliases via window).
    tokens = list(re.finditer(r"[A-Za-zÀ-ÿſ][A-Za-zÀ-ÿſ\-']*", text))
    if not tokens:
        return None

    norms = [normalize_hist_dutch(m.group(0)) for m in tokens]
    best: tuple[int, int, str, str] | None = None  # (alen, start, surface, pref)

    # Single-token aliases
    for i, (norm, match) in enumerate(zip(norms, tokens, strict=True)):
        if len(norm) < min_alias_len or norm in blocked:
            continue
        pref = alias_to_pref.get(norm)
        if not pref:
            continue
        surface = match.group(0)
        candidate = (len(norm), -match.start(), surface, pref)
        if best is None or candidate[0] > best[0] or (
            candidate[0] == best[0] and candidate[1] > best[1]
        ):
            best = candidate

    # Multi-token aliases (join consecutive norms with space)
    max_n = 4
    for n in range(2, max_n + 1):
        for i in range(0, len(norms) - n + 1):
            joined = " ".join(norms[i : i + n])
            if len(joined) < min_alias_len or any(
                part in blocked for part in norms[i : i + n]
            ):
                continue
            pref = alias_to_pref.get(joined)
            if not pref:
                continue
            start_m = tokens[i]
            end_m = tokens[i + n - 1]
            surface = text[start_m.start() : end_m.end()]
            candidate = (len(joined), -start_m.start(), surface, pref)
            if best is None or candidate[0] > best[0] or (
                candidate[0] == best[0] and candidate[1] > best[1]
            ):
                best = candidate

    if best is None:
        return None
    _alen, _neg_start, surface, pref = best
    return {
        "target_word": surface,
        "pref_label": pref,
        "alias_norm": normalize_hist_dutch(surface),
    }


def unique_passages_from_long_kwic(
    frame,
    *,
    passage_limit: int | None = None,
    text_column: str = "snippet",
    id_column: str = "doc_id",
    seed: int | None = 0,
    stratify_batch: bool = True,
) -> list[dict[str, Any]]:
    """Dedupe long-KWIC rows to one passage per doc_id.

    When *passage_limit* is set, sample (optionally stratified by ``kwic_batch``)
    instead of taking the first N rows — CSV head order is pharmacopoeia-heavy.
    """
    import random

    import pandas as pd

    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    if text_column not in frame.columns:
        raise ValueError(f"missing column {text_column!r}")

    work = frame.copy()
    if id_column in work.columns:
        work = work.drop_duplicates(subset=[id_column], keep="first")
    else:
        work = work.drop_duplicates(subset=[text_column], keep="first")

    if passage_limit is not None and len(work) > int(passage_limit):
        limit = int(passage_limit)
        rng = random.Random(seed)
        if stratify_batch and "kwic_batch" in work.columns:
            # Round-robin across primary batch tags for coverage.
            buckets: dict[str, list[int]] = {}
            for idx, raw in work["kwic_batch"].fillna("").items():
                tags = [p.strip().lower() for p in str(raw).split("|") if p.strip()]
                key = tags[0] if tags else "(missing)"
                buckets.setdefault(key, []).append(idx)
            for key in buckets:
                rng.shuffle(buckets[key])
            keys = sorted(buckets)
            rng.shuffle(keys)
            picked: list[int] = []
            while len(picked) < limit and keys:
                progressed = False
                for key in list(keys):
                    bucket = buckets[key]
                    if not bucket:
                        keys.remove(key)
                        continue
                    picked.append(bucket.pop())
                    progressed = True
                    if len(picked) >= limit:
                        break
                if not progressed:
                    break
            work = work.loc[picked]
        else:
            idxs = list(work.index)
            rng.shuffle(idxs)
            work = work.loc[idxs[:limit]]

    rows: list[dict[str, Any]] = []
    for idx, row in work.iterrows():
        text = str(row.get(text_column) or "").strip()
        if not text:
            continue
        doc_id = str(row.get(id_column) or idx).strip()
        rows.append(
            {
                "source_record_id": doc_id,
                "text": text,
                "corpus": "food_snippets_long_kwic",
                "title": (str(row["title"]).strip() if "title" in row and pd.notna(row["title"]) else None),
                "source_path": (
                    str(row["filename"]).strip()
                    if "filename" in row and pd.notna(row["filename"])
                    else None
                ),
                "kwic_batch": (
                    str(row["kwic_batch"]).strip()
                    if "kwic_batch" in row and pd.notna(row["kwic_batch"])
                    else None
                ),
            }
        )
    return rows


def chunk_passages(
    passages: Sequence[dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap: int = DEFAULT_OVERLAP,
) -> list[TextChunk]:
    """Chunk each passage; chunk_id = ``{source_record_id}::{local}``."""
    out: list[TextChunk] = []
    for passage in passages:
        source_id = str(passage.get("source_record_id") or "pass")
        local = chunk_passage(
            str(passage.get("text") or ""),
            max_chars=max_chars,
            overlap=overlap,
            source_record_id=source_id,
            chunk_id_prefix="c",
        )
        for ch in local:
            out.append(
                TextChunk(
                    chunk_id=f"{source_id}::{ch.chunk_id}",
                    text=ch.text,
                    start_char=ch.start_char,
                    end_char=ch.end_char,
                    source_record_id=source_id,
                )
            )
    return out


def retrieve_chunks_by_frame(
    chunk_embeddings: np.ndarray,
    centroids: dict[str, np.ndarray],
    *,
    frames: Sequence[str] = FOOD_QUERY_FRAMES,
    top_k_per_frame: int = 200,
    none_margin: float = 0.0,
    quota_mode: bool = False,
    candidate_limit: int | None = None,
) -> list[dict[str, Any]]:
    """Rank chunks per food-frame centroid; drop those closer to NONE (+ margin).

    Default (*quota_mode=False*): each chunk kept once under its best food frame.

    *quota_mode=True*: round-robin across frames (fixes PRESERVING/INGESTION skew).
    Uses up to *top_k_per_frame* candidates per frame, then fills to
    *candidate_limit* (default: ``top_k_per_frame * len(frames)``).
    """
    if chunk_embeddings.size == 0:
        return []
    mat = l2_normalize(chunk_embeddings)
    none_vec = centroids.get("NONE")
    none_scores = None
    if none_vec is not None:
        none_scores = (mat @ l2_normalize(none_vec.reshape(1, -1)).T).ravel()

    per_frame: dict[str, list[dict[str, Any]]] = {f: [] for f in frames}
    for frame in frames:
        vec = centroids.get(frame)
        if vec is None:
            continue
        scores = (mat @ l2_normalize(vec.reshape(1, -1)).T).ravel()
        order = np.argsort(-scores)
        taken = 0
        for idx in order:
            if taken >= top_k_per_frame:
                break
            i = int(idx)
            score = float(scores[i])
            none_score = float(none_scores[i]) if none_scores is not None else None
            if none_score is not None and score < none_score + none_margin:
                continue
            taken += 1
            per_frame[frame].append(
                {
                    "chunk_index": i,
                    "frame_hint": frame,
                    "score": score,
                    "none_score": none_score,
                }
            )

    # Fallback: frames starved by NONE margin still need quota representation.
    # Top up by (score - none_score) without hard margin so INGESTION etc. can appear.
    if quota_mode and none_scores is not None:
        for frame in frames:
            if len(per_frame.get(frame) or []) >= max(top_k_per_frame // 4, 1):
                continue
            vec = centroids.get(frame)
            if vec is None:
                continue
            scores = (mat @ l2_normalize(vec.reshape(1, -1)).T).ravel()
            margin = scores - none_scores
            order = np.argsort(-margin)
            existing = {int(h["chunk_index"]) for h in per_frame[frame]}
            for idx in order:
                if len(per_frame[frame]) >= top_k_per_frame:
                    break
                i = int(idx)
                if i in existing:
                    continue
                per_frame[frame].append(
                    {
                        "chunk_index": i,
                        "frame_hint": frame,
                        "score": float(scores[i]),
                        "none_score": float(none_scores[i]),
                    }
                )
                existing.add(i)

    if not quota_mode:
        best_for_chunk: dict[int, dict[str, Any]] = {}
        for frame in frames:
            for hit in per_frame[frame]:
                i = int(hit["chunk_index"])
                prev = best_for_chunk.get(i)
                if prev is None or float(hit["score"]) > float(prev["score"]):
                    best_for_chunk[i] = hit
        return sorted(best_for_chunk.values(), key=lambda r: float(r["score"]), reverse=True)

    limit = candidate_limit if candidate_limit is not None else top_k_per_frame * max(len(frames), 1)
    return _round_robin_frame_hits(per_frame, frames=frames, limit=limit)


def _round_robin_frame_hits(
    per_frame: dict[str, list[dict[str, Any]]],
    *,
    frames: Sequence[str],
    limit: int,
) -> list[dict[str, Any]]:
    """Take hits round-robin so each frame gets a fair share (dedupe by chunk_index)."""
    cursors = {f: 0 for f in frames}
    seen: set[int] = set()
    selected: list[dict[str, Any]] = []
    while len(selected) < limit:
        progressed = False
        for frame in frames:
            if len(selected) >= limit:
                break
            bucket = per_frame.get(frame) or []
            while cursors[frame] < len(bucket):
                hit = bucket[cursors[frame]]
                cursors[frame] += 1
                idx = int(hit["chunk_index"])
                if idx in seen:
                    continue
                seen.add(idx)
                selected.append(hit)
                progressed = True
                break
        if not progressed:
            break
    return selected


def hybrid_candidates_from_ranked(
    ranked: Sequence[dict[str, Any]],
    chunks: Sequence[TextChunk],
    passages_by_id: dict[str, dict[str, Any]],
    alias_to_pref: dict[str, str],
    *,
    candidate_limit: int = 500,
    denylist: frozenset[str] | None = None,
    frame_quota: bool = True,
    frames: Sequence[str] = FOOD_QUERY_FRAMES,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Apply LU anchor; split into anchored KwicInput-like rows vs semantic_only.

    Returns ``(anchored, semantic_only, stats)``.
    """
    from trifecta_annotation.text_regime import infer_text_regime

    anchored: list[dict[str, Any]] = []
    semantic_only: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    frame_counts: dict[str, int] = {f: 0 for f in frames}
    quota = max(candidate_limit // max(len(frames), 1), 1) if frame_quota else candidate_limit

    deferred: list[dict[str, Any]] = []

    def _try_add(hit: dict[str, Any], *, enforce_quota: bool) -> None:
        nonlocal anchored, semantic_only
        if len(anchored) >= candidate_limit and len(semantic_only) >= candidate_limit:
            return
        idx = int(hit["chunk_index"])
        if idx < 0 or idx >= len(chunks):
            return
        chunk = chunks[idx]
        passage = passages_by_id.get(chunk.source_record_id or "", {})
        lu = find_lu_anchor(chunk.text, alias_to_pref, denylist=denylist)
        base = {
            "chunk_id": chunk.chunk_id,
            "context_text": chunk.text,
            "frame_hint": hit.get("frame_hint"),
            "embedding_score": hit.get("score"),
            "none_score": hit.get("none_score"),
            "corpus": passage.get("corpus") or "food_snippets_long_kwic",
            "title": passage.get("title"),
            "source_path": passage.get("source_path"),
            "kwic_batch": passage.get("kwic_batch"),
            "source_record_id": chunk.source_record_id,
        }
        if lu is None:
            if len(semantic_only) < candidate_limit:
                semantic_only.append({**base, "record_id": f"sem::{chunk.chunk_id}"})
            return

        key = (chunk.source_record_id or "", lu["alias_norm"])
        if key in seen_keys:
            return
        if len(anchored) >= candidate_limit:
            return
        hint = str(hit.get("frame_hint") or "")
        if enforce_quota and hint in frame_counts and frame_counts[hint] >= quota:
            deferred.append(hit)
            return
        seen_keys.add(key)
        if hint in frame_counts:
            frame_counts[hint] += 1
        regime = infer_text_regime(
            corpus=base.get("corpus"),
            title=base.get("title"),
            source_path=base.get("source_path"),
        )
        record_id = f"emb::{chunk.chunk_id}::{lu['alias_norm']}"
        anchored.append(
            {
                "record_id": record_id,
                "corpus": base["corpus"],
                "target_word": lu["target_word"],
                "context_text": chunk.text,
                "date": None,
                "source_path": base["source_path"],
                "title": base["title"],
                "candidate_terms": [lu["pref_label"]],
                "text_regime": regime.value,
                "kwic_mode": "embedding_hybrid",
                "kwic_batch": base["kwic_batch"],
                "discovery_verb": None,
                "frame_hint": base["frame_hint"],
                "embedding_score": base["embedding_score"],
                "none_score": base["none_score"],
                "pref_label": lu["pref_label"],
                "chunk_id": chunk.chunk_id,
            }
        )

    for hit in ranked:
        if len(anchored) >= candidate_limit and len(semantic_only) >= candidate_limit:
            break
        _try_add(hit, enforce_quota=frame_quota)

    if frame_quota and len(anchored) < candidate_limit:
        for hit in deferred:
            if len(anchored) >= candidate_limit:
                break
            _try_add(hit, enforce_quota=False)

    stats = {
        "ranked": len(ranked),
        "anchored": len(anchored),
        "semantic_only": len(semantic_only),
        "lu_anchor_rate": (
            len(anchored) / max(len(anchored) + len(semantic_only), 1)
        ),
        "frame_counts": dict(frame_counts),
        "frame_quota": quota if frame_quota else None,
    }
    return anchored, semantic_only, stats


class GysbertEmbedder:
    """Mean-pooled GysBERT encoder (requires ``gijsbert`` / transformers extra)."""

    def __init__(
        self,
        model_name: str = DEFAULT_EMBED_MODEL,
        *,
        max_length: int = DEFAULT_MAX_LENGTH,
        device: str | None = None,
    ) -> None:
        from trifecta_annotation.hf_cache import configure_hf_hub_cache

        configure_hf_hub_cache()
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - env dependent
            raise ImportError(
                "GysbertEmbedder requires transformers+torch "
                "(uv sync --extra gijsbert)"
            ) from exc

        self.model_name = model_name
        self.max_length = max_length
        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()
        if device is None:
            device = "mps" if torch.backends.mps.is_available() else (
                "cuda" if torch.cuda.is_available() else "cpu"
            )
        self.device = device
        self.model.to(device)

    def encode(
        self,
        texts: Sequence[str],
        *,
        batch_size: int = 16,
        normalize: bool = True,
    ) -> np.ndarray:
        """Encode texts → (n, hidden) float32 matrix."""
        if not texts:
            return np.zeros((0, self.model.config.hidden_size), dtype=np.float32)

        torch = self._torch
        parts: list[np.ndarray] = []
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch = list(texts[i : i + batch_size])
                encoded = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                )
                encoded = {k: v.to(self.device) for k, v in encoded.items()}
                out = self.model(**encoded)
                hidden = out.last_hidden_state.detach().cpu().numpy()
                mask = encoded["attention_mask"].detach().cpu().numpy()
                pooled = mean_pool(hidden, mask)
                parts.append(pooled)
        matrix = np.vstack(parts).astype(np.float32)
        return l2_normalize(matrix) if normalize else matrix
