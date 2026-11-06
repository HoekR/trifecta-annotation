"""Full A→B→C pipeline orchestrator."""

from __future__ import annotations

from typing import Any

from trifecta_annotation.config import trifecta_model
from trifecta_annotation.gijsbert_export import mark_kwic_context
from trifecta_annotation.regime_routing import needs_encoder_sieve, routing_regime
from trifecta_annotation.schemas import (
    AnnotationProvenance,
    KwicInput,
    TrifectaAnnotation,
    TrifectaFrame,
)
from trifecta_annotation.step_a import should_drop, validate_entity
from trifecta_annotation.step_b import classify_context
from trifecta_annotation.step_c import fill_qualia


def _provenance_from_input(inp: KwicInput) -> AnnotationProvenance:
    return AnnotationProvenance(
        corpus=inp.corpus,
        target_word=inp.target_word,
        context_text=inp.context_text,
        source_path=inp.source_path,
        record_id=inp.record_id,
        date=inp.date,
        discovery_verb=inp.discovery_verb,
        frame_hint=inp.frame_hint,
        kwic_mode=inp.kwic_mode,
        kwic_batch=inp.kwic_batch,
        text_regime=inp.text_regime,
        title=inp.title,
        unit_id=inp.unit_id,
        unit_start=inp.unit_start,
        unit_end=inp.unit_end,
        target_char_offset=inp.target_char_offset,
        structural_header=inp.structural_header,
        structural_goal=inp.structural_goal,
        structural_goal_inherited=inp.structural_goal_inherited,
        structural_signal=inp.structural_signal,
        tei_scope_head=inp.tei_scope_head,
    )


def _sieve_drop_if_needed(
    inp: KwicInput,
    *,
    provenance: AnnotationProvenance,
    resolved_model: str,
    step_a_sieve: Any | None,
) -> TrifectaAnnotation | None:
    """Return a dropped annotation when the weak-regime encoder says DROP."""
    if step_a_sieve is None:
        return None
    if not needs_encoder_sieve(
        text_regime=inp.text_regime,
        tei_scope_head=inp.tei_scope_head or inp.structural_header,
    ):
        return None
    marked = mark_kwic_context(inp.context_text, target_word=inp.target_word, mark_mode="food")
    if step_a_sieve.predict_keep(marked):
        return None
    sieve_name = getattr(step_a_sieve, "path", None)
    return TrifectaAnnotation(
        provenance=provenance,
        dropped=True,
        drop_reason="step_a_sieve",
        model=resolved_model,
        sieve_model=str(sieve_name) if sieve_name else "step_a_keepdrop",
    )


def annotate_record(
    inp: KwicInput,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
    technique_hint: str | None = None,
    english_hint: str | None = None,
    step_a_sieve: Any | None = None,
) -> TrifectaAnnotation:
    """Run the gated TRIFECTA pipeline for one KWIC record.

    When ``step_a_sieve`` is provided, weak regimes (LITERARY / TRAVEL /
    UNKNOWN / …, after TEI scope upgrade) are encoder-sieved before LLM Step A.
    RECIPE_PRACTICE / MEDICAL always go straight to the LLM.
    """
    resolved_model = model or trifecta_model()
    provenance = _provenance_from_input(inp)
    # Stash effective routing regime for debugging (does not change stored text_regime).
    _ = routing_regime(
        text_regime=inp.text_regime,
        tei_scope_head=inp.tei_scope_head or inp.structural_header,
    )

    early = _sieve_drop_if_needed(
        inp,
        provenance=provenance,
        resolved_model=resolved_model,
        step_a_sieve=step_a_sieve,
    )
    if early is not None:
        return early

    step_a = validate_entity(
        inp.target_word,
        inp.context_text,
        model=resolved_model,
        base_url=base_url,
        client=client,
        english_hint=english_hint,
    )
    dropped, drop_reason = should_drop(step_a)
    if dropped:
        return TrifectaAnnotation(
            provenance=provenance,
            step_a=step_a,
            dropped=True,
            drop_reason=drop_reason,
            model=resolved_model,
        )

    step_b = classify_context(
        inp.target_word,
        inp.context_text,
        model=resolved_model,
        base_url=base_url,
        english_hint=english_hint,
    )
    if step_b.selected_frame == TrifectaFrame.NONE:
        return TrifectaAnnotation(
            provenance=provenance,
            step_a=step_a,
            step_b=step_b,
            dropped=False,
            model=resolved_model,
        )

    step_c = fill_qualia(
        step_b.selected_frame,
        inp.target_word,
        inp.context_text,
        step_b,
        model=resolved_model,
        base_url=base_url,
        client=client,
        technique_hint=technique_hint,
    )
    return TrifectaAnnotation(
        provenance=provenance,
        step_a=step_a,
        step_b=step_b,
        step_c=step_c,
        dropped=False,
        model=resolved_model,
    )


def annotate_step_a(
    inp: KwicInput,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
    english_hint: str | None = None,
    step_a_sieve: Any | None = None,
) -> TrifectaAnnotation:
    """Run Step A only (entity validation / early dropout)."""
    resolved_model = model or trifecta_model()
    provenance = _provenance_from_input(inp)
    early = _sieve_drop_if_needed(
        inp,
        provenance=provenance,
        resolved_model=resolved_model,
        step_a_sieve=step_a_sieve,
    )
    if early is not None:
        return early
    step_a = validate_entity(
        inp.target_word,
        inp.context_text,
        model=resolved_model,
        base_url=base_url,
        client=client,
        english_hint=english_hint,
    )
    dropped, drop_reason = should_drop(step_a)
    return TrifectaAnnotation(
        provenance=provenance,
        step_a=step_a,
        dropped=dropped,
        drop_reason=drop_reason,
        model=resolved_model,
    )
