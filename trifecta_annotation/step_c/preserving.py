"""Step C — PRESERVING qualia extraction."""

from __future__ import annotations

from trifecta_annotation.llm import structured_completion
from trifecta_annotation.schemas import FrameClassification, PreservingQualia

SYSTEM_PROMPT = (
    "You are annotating historical Dutch food texts for the TRIFECTA PRESERVING frame. "
    "Extract preservation technique, preserving agent or medium, and target food. "
    "Use empty string when a field is not stated in the context."
)


def fill_preserving(
    target_word: str,
    context_text: str,
    step_b: FrameClassification,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
    technique_hint: str | None = None,
) -> PreservingQualia:
    hint = ""
    if technique_hint:
        hint = f"\nCalibration hint (weak prior): {technique_hint}"
    user_prompt = (
        f"Target Word: {target_word}\n"
        f"Context: {context_text}\n"
        f"Macro-frame trigger: {step_b.lexical_unit}"
        f"{hint}"
    )
    return structured_completion(
        PreservingQualia,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        base_url=base_url,
        client=client,
    )
