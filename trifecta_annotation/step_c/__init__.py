"""Step C — frame-specific qualia router."""

from __future__ import annotations

from trifecta_annotation.schemas import FrameClassification, FrameQualia, TrifectaFrame
from trifecta_annotation.step_c.cooking_creation import fill_cooking_creation
from trifecta_annotation.step_c.preserving import fill_preserving
from trifecta_annotation.step_c.using_cure import fill_using_cure
from trifecta_annotation.step_c.using_ingestion import fill_using_ingestion


def fill_qualia(
    frame: TrifectaFrame,
    target_word: str,
    context_text: str,
    step_b: FrameClassification,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
    technique_hint: str | None = None,
) -> FrameQualia:
    """Fill frame-specific qualia roles for the macro-frame selected in Step B."""
    if frame == TrifectaFrame.CURE:
        return fill_using_cure(
            target_word,
            context_text,
            step_b,
            model=model,
            base_url=base_url,
            client=client,
        )
    if frame == TrifectaFrame.COOKING_CREATION:
        return fill_cooking_creation(
            target_word,
            context_text,
            step_b,
            model=model,
            base_url=base_url,
            client=client,
        )
    if frame == TrifectaFrame.INGESTION:
        return fill_using_ingestion(
            target_word,
            context_text,
            step_b,
            model=model,
            base_url=base_url,
            client=client,
        )
    if frame == TrifectaFrame.PRESERVING:
        return fill_preserving(
            target_word,
            context_text,
            step_b,
            model=model,
            base_url=base_url,
            client=client,
            technique_hint=technique_hint,
        )
    raise ValueError(f"Step C does not apply to frame {frame}")
