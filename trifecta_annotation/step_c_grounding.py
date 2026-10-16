"""Ground production Step C qualia values in literal context spans.

Hybrid design (plans/steps/STEPC_GROUNDING.md): keep the LLM's presence/
absence judgment and its draft answer, but require the final value to match
a real literal span from ``context_text`` when one exists. Targets the
failure mode diagnosed in `project_step_c_grounding_prototype` memory — most
LLM Step C misses are hallucinated substitutions, not wording variants —
without needing the calibrated empty-vs-answer threshold a full retrieval
replacement would require (an empty LLM value is never second-guessed).

Three tiers per field, cheapest first:

1. Empty value -> unchanged.
2. Value already a literal (case-insensitive) substring of context -> unchanged,
   no embedding call.
3. Otherwise: embed the LLM's draft value, generate candidate spans from a
   target-word-centered window of context_text (same radius and candidate
   generator as stepc_embedding_retrieval.py / stepc_span_export.py — the
   ±180-char window that already captures 79.5%+ of real gold answers and
   avoids the book-length-context contamination problem documented in
   DECISIONS.md), take the nearest candidate. Above threshold -> replace the
   value with that grounded span. Below -> keep the LLM's original value,
   report ``grounded=False`` rather than silently dropping it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trifecta_annotation.embedding_candidates import GysbertEmbedder, l2_normalize
from trifecta_annotation.homonym_context import local_context_window
from trifecta_annotation.stepc_embedding_retrieval import SUBWORD_SCORE_PENALTY, ngram_candidates
from trifecta_annotation.stepc_span_export import DEFAULT_CONTEXT_RADIUS, find_span

# Not yet calibrated — see plans/steps/STEPC_GROUNDING.md G0. Placeholder
# until the sweep in scripts/eval_stepc_grounding.py picks a value.
DEFAULT_GROUNDING_THRESHOLD = 0.85


@dataclass
class GroundingResult:
    value: str
    grounded: bool
    original_value: str
    replaced: bool


def ground_value(
    value: str,
    context_text: str,
    target_word: str,
    *,
    embedder: GysbertEmbedder,
    threshold: float = DEFAULT_GROUNDING_THRESHOLD,
    context_radius: int = DEFAULT_CONTEXT_RADIUS,
    subword_penalty: float = SUBWORD_SCORE_PENALTY,
) -> GroundingResult:
    """Ground one qualia field value against a literal span in context."""
    stripped = value.strip()
    if not stripped:
        return GroundingResult(value=value, grounded=True, original_value=value, replaced=False)

    window = local_context_window(context_text, target_word, radius=context_radius) if target_word else context_text

    if find_span(window, stripped) is not None:
        return GroundingResult(value=value, grounded=True, original_value=value, replaced=False)

    candidates = ngram_candidates(window)
    if not candidates:
        return GroundingResult(value=value, grounded=False, original_value=value, replaced=False)

    cand_texts = [c[2] for c in candidates]
    is_subword = [c[3] for c in candidates]
    cand_emb = l2_normalize(embedder.encode(cand_texts, batch_size=256))
    draft_emb = l2_normalize(embedder.encode([stripped]))[0]

    sims = cand_emb @ draft_emb
    adjusted = [s - (subword_penalty if sub else 0.0) for s, sub in zip(sims, is_subword, strict=True)]
    best_idx = max(range(len(adjusted)), key=lambda i: adjusted[i])
    best_score = adjusted[best_idx]

    if best_score >= threshold:
        grounded_text = cand_texts[best_idx]
        return GroundingResult(value=grounded_text, grounded=True, original_value=value, replaced=True)
    return GroundingResult(value=value, grounded=False, original_value=value, replaced=False)


def ground_step_c_dict(
    step_c: dict[str, Any],
    field_names: tuple[str, ...],
    context_text: str,
    target_word: str,
    *,
    embedder: GysbertEmbedder,
    threshold: float = DEFAULT_GROUNDING_THRESHOLD,
) -> tuple[dict[str, Any], dict[str, bool]]:
    """Ground every field in *field_names* of a raw step_c dict in place.

    Returns the (mutated) dict and a {field_name: grounded} audit map.
    """
    audit: dict[str, bool] = {}
    for field_name in field_names:
        value = str(step_c.get(field_name) or "")
        result = ground_value(value, context_text, target_word, embedder=embedder, threshold=threshold)
        step_c[field_name] = result.value
        audit[field_name] = result.grounded
    return step_c, audit
