"""Step C — CURE qualia extraction."""

from __future__ import annotations

from trifecta_annotation.llm import structured_completion
from trifecta_annotation.prompts import format_few_shots, load_prompt_asset
from trifecta_annotation.schemas import CureQualia, FrameClassification

SYSTEM_PROMPT = (
    "You are annotating historical Dutch food texts for the TRIFECTA CURE frame. "
    "Extract CURE_Affliction (the illness, symptom, or ailment being treated) and "
    "CURE_Food_Treatment (how the food/substance is applied or administered, e.g. drinken, innemen, gorgelen, wasschen, pleister). "
    "Use empty string when a field is not stated in the context.\n\n"
    "{few_shots}"
)


def fill_using_cure(
    target_word: str,
    context_text: str,
    step_b: FrameClassification,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
) -> CureQualia:
    few_shots = format_few_shots(load_prompt_asset("step_c_cure_fewshots.json")["examples"])
    system = SYSTEM_PROMPT.format(few_shots=few_shots)
    user_prompt = (
        f"Target Word: {target_word}\n"
        f"Context: {context_text}\n"
        f"Macro-frame trigger: {step_b.lexical_unit}"
    )
    return structured_completion(
        CureQualia,
        system_prompt=system,
        user_prompt=user_prompt,
        model=model,
        base_url=base_url,
        client=client,
    )
