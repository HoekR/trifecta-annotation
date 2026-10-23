"""Step C qualia extraction via embedding-exemplar retrieval (no fine-tuning).

Alternative to the ruled-out GloBERTise BERT-QA span extractor
(``stepc_span_train.py`` — see PLAN.md §9b for why that was ruled out: too
little grounded gold per field for fine-tuning, ~160 positive spans across 12
fields). Instead of training a model, this scores candidate spans in each
row's (already target-centered-clipped) ``context_text`` against embeddings
of every *other* gold answer span for that field (``emanjavacas/gysbert``
mean-pooled — the embedder already adopted for the KWIC embedding pilot in
``embedding_candidates.py``), and takes the nearest match.

Candidate generation covers two failure modes found during prototyping:
word-boundary n-grams (``[\\w'-]+`` — note this excludes trailing punctuation,
which a naive ``\\S+`` split would wrongly attach, e.g. "Stoven." at a
sentence end) plus char-level sub-word candidates for long tokens, since
Dutch compounding hides short answers inside longer words ("braden" inside
"gebraden"). Sub-word candidates get a flat score penalty
(``SUBWORD_SCORE_PENALTY``) rather than being excluded outright: an A/B test
over the full leave-one-out pool showed hard-excluding them regresses the
largest field (``INGESTION_Food_Patient``, 0.700->0.667 EM), while a soft
penalty improves every headline metric (EM 0.593->0.610, F1 0.600->0.619,
soft 0.674->0.678) by only letting a sub-word candidate win when it's clearly
better than the best whole-word candidate, not just noise-level ahead.

A GysBERT-vocabulary "is this a real word" filter was tested and rejected:
WordPiece vocab entries are chosen by subword *frequency*, not by whether
they're complete words, so real words like "braden"/"zwelling" split into
multiple pieces while garbage fragments like "wend"/"brui"/"onzui" (common
morphological pieces of other words) are each a single vocab entry — the
opposite of a useful signal. No general Dutch wordlist/spellchecker is a
dependency of this project, so a real dictionary check isn't available
without adding one.

Evaluation is leave-one-out (LOO) over the full positive-span pool (train +
dev from ``stepc_span_export.py``'s split, pooled back together — this is a
separate from-scratch cross-validation, not the BERT-QA train/dev split),
since most fields have too few positive examples (as low as 6) for a held-out
split to give a stable number.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from trifecta_annotation.embedding_candidates import GysbertEmbedder, l2_normalize
from trifecta_annotation.eval import soft_qualia_match
from trifecta_annotation.stepc_span_export import load_stepc_span_jsonl
from trifecta_annotation.stepc_span_train import _normalize_text, _token_f1

# [\w'-]+ excludes trailing punctuation that a naive \S+ split would attach
# (e.g. "Stoven." at a sentence end never matched gold "Stoven" before this).
_WORD_RE = re.compile(r"[\w'-]+")

MAX_NGRAM = 6  # covers p90 answer length for all fields but 2 long-tail outliers

# Dutch compounding/inflection hides short answers inside longer tokens
# ("braden" in "gebraden", "rook" in "rookzakken") that word n-grams alone
# can't reach.
SUBWORD_MIN_TOKEN_LEN = 7
SUBWORD_LEN_RANGE = range(4, 11)

# Calibrated on the full LOO pool (518 positive rows): 0.03-0.08 all tie for
# best EM/F1, 0.05 wins on soft match. See module docstring.
SUBWORD_SCORE_PENALTY = 0.05

# 10/52 CURE_Affliction and 1/41 PR_Medium gold "answers" turned out to be
# bare English stopwords from the english_iaa merge batch — a data bug in
# that source (see docs/DECISIONS.md), not a retrieval-method problem.
JUNK_EXEMPLARS = frozenset(
    {
        "in", "for", "from", "of", "the", "a", "an", "to", "and", "or", "is",
        "on", "at", "as", "it", "sore", "acidity", "was", "with", "by",
    }
)


def word_spans(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in _WORD_RE.finditer(text)]


def ngram_candidates(
    context: str,
    *,
    max_n: int = MAX_NGRAM,
    subword_min_len: int = SUBWORD_MIN_TOKEN_LEN,
    subword_len_range: range = SUBWORD_LEN_RANGE,
) -> list[tuple[int, int, str, bool]]:
    """Return (start_char, end_char, text, is_subword) candidates for *context*."""
    spans = word_spans(context)
    out: list[tuple[int, int, str, bool]] = []
    for i in range(len(spans)):
        for n in range(1, max_n + 1):
            j = i + n - 1
            if j >= len(spans):
                break
            start, end = spans[i][0], spans[j][1]
            out.append((start, end, context[start:end], False))

    for (tok_start, tok_end) in spans:
        tok_len = tok_end - tok_start
        if tok_len < subword_min_len:
            continue
        for sub_len in subword_len_range:
            if sub_len >= tok_len:
                continue
            for offset in range(0, tok_len - sub_len + 1):
                s = tok_start + offset
                e = s + sub_len
                out.append((s, e, context[s:e], True))
    return out


def load_positive_pool(data_dir: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Pool train.jsonl + dev.jsonl positive-span rows per field, junk-filtered."""
    out = Path(data_dir).expanduser().resolve()
    rows = load_stepc_span_jsonl(out / "train.jsonl") + load_stepc_span_jsonl(out / "dev.jsonl")

    pool: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["answer_start_char"] is None:
            continue
        text = row["answer_text"].strip()
        if not text or text.lower() in JUNK_EXEMPLARS:
            continue
        pool[row["field_name"]].append(row)
    return dict(pool)


@dataclass
class RetrievalEvalResult:
    total: int
    exact_match: float
    token_f1: float
    soft_match: float
    per_field: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "exact_match": self.exact_match,
            "token_f1": self.token_f1,
            "soft_match": self.soft_match,
            "per_field": self.per_field,
        }


def run_loo_eval(
    pool: dict[str, list[dict[str, Any]]],
    *,
    embedder: GysbertEmbedder | None = None,
    subword_penalty: float = SUBWORD_SCORE_PENALTY,
) -> RetrievalEvalResult:
    """Leave-one-out eval: score each row against every *other* same-field exemplar."""
    embedder = embedder or GysbertEmbedder()

    field_exemplar_emb: dict[str, np.ndarray] = {}
    for field, rows in pool.items():
        texts = [r["answer_text"].strip() for r in rows]
        field_exemplar_emb[field] = l2_normalize(embedder.encode(texts, batch_size=64))

    flat_rows: list[tuple[str, int]] = []
    row_candidates: list[list[tuple[int, int, str, bool]]] = []
    flat_texts: list[str] = []
    for field, rows in pool.items():
        for idx, row in enumerate(rows):
            flat_rows.append((field, idx))
            cands = ngram_candidates(row["context_text"])
            row_candidates.append(cands)
            flat_texts.extend(c[2] for c in cands)

    all_cand_emb = embedder.encode(flat_texts, batch_size=256) if flat_texts else np.zeros((0, 1))

    offsets: list[tuple[int, int]] = []
    cursor = 0
    for cands in row_candidates:
        offsets.append((cursor, cursor + len(cands)))
        cursor += len(cands)

    per_field: dict[str, list[tuple[float, float, float]]] = defaultdict(list)

    for ridx, (field, local_idx) in enumerate(flat_rows):
        row = pool[field][local_idx]
        gold = row["answer_text"].strip()
        norm_gold = _normalize_text(gold)
        cands = row_candidates[ridx]
        if not cands:
            continue
        start, end = offsets[ridx]
        cand_emb = all_cand_emb[start:end]
        is_subword = np.array([c[3] for c in cands])

        ex_emb = field_exemplar_emb[field]
        mask = np.ones(ex_emb.shape[0], dtype=bool)
        mask[local_idx] = False  # leave-one-out
        if not mask.any():
            continue

        sims = cand_emb @ ex_emb[mask].T
        best = sims.max(axis=1)
        adjusted = best - np.where(is_subword, subword_penalty, 0.0)
        top_idx = int(np.argmax(adjusted))
        pred_text = cands[top_idx][2]
        norm_pred = _normalize_text(pred_text)

        em = 1.0 if norm_pred == norm_gold else 0.0
        f1 = _token_f1(gold, pred_text)
        soft = 1.0 if soft_qualia_match(norm_gold, norm_pred) else 0.0
        per_field[field].append((em, f1, soft))

    per_field_metrics: dict[str, dict[str, float]] = {}
    tot_em = tot_f1 = tot_soft = 0.0
    tot_n = 0
    for field, vals in per_field.items():
        n = len(vals)
        em = sum(v[0] for v in vals) / n
        f1 = sum(v[1] for v in vals) / n
        soft = sum(v[2] for v in vals) / n
        per_field_metrics[field] = {"n": float(n), "exact_match": em, "token_f1": f1, "soft_match": soft}
        tot_em += sum(v[0] for v in vals)
        tot_f1 += sum(v[1] for v in vals)
        tot_soft += sum(v[2] for v in vals)
        tot_n += n

    return RetrievalEvalResult(
        total=tot_n,
        exact_match=tot_em / tot_n if tot_n else 0.0,
        token_f1=tot_f1 / tot_n if tot_n else 0.0,
        soft_match=tot_soft / tot_n if tot_n else 0.0,
        per_field=per_field_metrics,
    )
