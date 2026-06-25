"""Step C — USING_CURE qualia extraction."""

from __future__ import annotations

from trifecta_annotation.llm import structured_completion
from trifecta_annotation.schemas import FrameClassification, UsingCureQualia

SYSTEM_PROMPT = (
    "You are annotating historical Dutch food texts for the TRIFECTA USING_CURE frame. "
    "Extract the ailment being treated and how the food functions as treatment. "
    "Use empty string when a field is not stated in the context."
)


def fill_using_cure(
    target_word: str,
    context_text: str,
    step_b: FrameClassification,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
) -> UsingCureQualia:
    user_prompt = (
        f"Target Word: {target_word}\n"
        f"Context: {context_text}\n"
        f"Macro-frame trigger: {step_b.lexical_unit}"
    )
    return structured_completion(
        UsingCureQualia,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        base_url=base_url,
        client=client,
    )
