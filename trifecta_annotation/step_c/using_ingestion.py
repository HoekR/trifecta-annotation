"""Step C — INGESTION qualia extraction."""

from __future__ import annotations

from trifecta_annotation.llm import structured_completion
from trifecta_annotation.prompts import format_few_shots, load_prompt_asset
from trifecta_annotation.schemas import FrameClassification, IngestionQualia

SYSTEM_PROMPT = (
    "You are annotating historical Dutch food texts for the TRIFECTA INGESTION frame. "
    "Extract the following qualia roles:\n"
    "- INGESTION_Context: Situation, setting, or social environment of consumption (e.g. aan tafel, taveerne, feest).\n"
    "- INGESTION_Ingestor: Person, group, or consumer eating/drinking/smoking (e.g. gasten, reizigers, zieke, scheepsvolk).\n"
    "- INGESTION_Manner: Mode of ingestion (eating, drinking, smoking, warm, nuchter, gulzig).\n"
    "- INGESTION_Food_Patient: Specific food, beverage, tobacco, or dish consumed (e.g. glas wijn, pijp tabak, soep, brood).\n"
    "- INGESTION_Purpose: Occasion, social intent, or health toast (e.g. toasting health, feest, vermaeck, ontbijt).\n\n"
    "Use empty string when a field is not stated in the context.\n\n"
    "{few_shots}"
)


def fill_using_ingestion(
    target_word: str,
    context_text: str,
    step_b: FrameClassification,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
) -> IngestionQualia:
    few_shots = format_few_shots(load_prompt_asset("step_c_ingestion_fewshots.json")["examples"])
    system = SYSTEM_PROMPT.format(few_shots=few_shots)
    user_prompt = (
        f"Target Word: {target_word}\n"
        f"Context: {context_text}\n"
        f"Macro-frame trigger: {step_b.lexical_unit}"
    )
    return structured_completion(
        IngestionQualia,
        system_prompt=system,
        user_prompt=user_prompt,
        model=model,
        base_url=base_url,
        client=client,
    )
