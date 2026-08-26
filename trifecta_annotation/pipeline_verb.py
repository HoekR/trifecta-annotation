"""Full A→B→C pipeline orchestrator for verb-first POC.

Uses simplified Step A (lexicon check) and augmented Step B (verb hint).
"""

from __future__ import annotations

from trifecta_annotation.config import trifecta_model
from trifecta_annotation.schemas import (
    AnnotationProvenance,
    KwicInput,
    TrifectaAnnotation,
    TrifectaFrame,
)
from trifecta_annotation.step_a_verb import should_drop_verb, validate_verb_entity
from trifecta_annotation.step_b_verb import classify_context_with_verb_hint
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
    )


def annotate_record_verb_first(
    inp: KwicInput,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
    technique_hint: str | None = None,
    english_hint: str | None = None,
) -> TrifectaAnnotation:
    """Run the gated TRIFECTA pipeline for one verb-KWIC record.
    
    Uses simplified Step A (lexicon check) and augmented Step B (verb hint).
    """
    resolved_model = model or trifecta_model()
    provenance = _provenance_from_input(inp)

    # Step A (simplified): check if verb is in lexicon
    step_a = validate_verb_entity(
        inp.target_word,
        inp.context_text,
        model=resolved_model,
        base_url=base_url,
        client=client,
        english_hint=english_hint,
    )
    dropped, drop_reason = should_drop_verb(step_a)
    if dropped:
        return TrifectaAnnotation(
            provenance=provenance,
            step_a=step_a,
            dropped=True,
            drop_reason=drop_reason,
            model=resolved_model,
        )

    # Step B (augmented with verb hint)
    step_b = classify_context_with_verb_hint(
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

    # Step C (unchanged)
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
