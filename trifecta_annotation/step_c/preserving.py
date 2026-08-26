"""Step C — PRESERVING qualia extraction."""

from __future__ import annotations

from trifecta_annotation.llm import structured_completion
from trifecta_annotation.prompts import format_few_shots, load_prompt_asset
from trifecta_annotation.schemas import FrameClassification, PreservingQualia

SYSTEM_PROMPT = (
    "You are annotating historical Dutch food texts for the TRIFECTA PRESERVING frame. "
    "Extract PR_Technique, PR_Medium, and PR_Food_Patient. "
    "Prefer concise spans or standardized technique descriptions (droogen, pekelen, rooken, inleggen). "
    "Use empty string when a field is not stated in the context.\n\n"
    "{few_shots}"
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
    few_shots = format_few_shots(load_prompt_asset("step_c_preserving_fewshots.json")["examples"])
    system = SYSTEM_PROMPT.format(few_shots=few_shots)
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
        system_prompt=system,
        user_prompt=user_prompt,
        model=model,
        base_url=base_url,
        client=client,
    )
