"""Step C — COOKING_CREATION qualia extraction."""

from __future__ import annotations

from trifecta_annotation.llm import structured_completion
from trifecta_annotation.schemas import CookingCreationQualia, FrameClassification

SYSTEM_PROMPT = (
    "You are annotating historical Dutch food texts for the TRIFECTA COOKING_CREATION frame. "
    "Extract COOKING_CREATION_Method, COOKING_CREATION_Process, and COOKING_CREATION_Food_Product. "
    "Use empty string when a field is not stated in the context."
)


def fill_cooking_creation(
    target_word: str,
    context_text: str,
    step_b: FrameClassification,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
) -> CookingCreationQualia:
    user_prompt = (
        f"Target Word: {target_word}\n"
        f"Context: {context_text}\n"
        f"Macro-frame trigger: {step_b.lexical_unit}"
    )
    return structured_completion(
        CookingCreationQualia,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model,
        base_url=base_url,
        client=client,
    )
