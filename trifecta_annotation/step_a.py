"""Step A — entity validation and formal layer."""

from __future__ import annotations

from trifecta_annotation.llm import structured_completion
from trifecta_annotation.prompts import format_few_shots, load_prompt_asset
from trifecta_annotation.schemas import EntityValidation
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

SYSTEM_PROMPT = (
    "You are an expert computational linguist annotating historical Dutch corpora "
    "for the TRIFECTA project. Validate whether the target word functions as a food "
    "entity in context. Identify formal dimensions: FOOD_Unit (measure phrase), "
    "FOOD_Constituent_Part (peel, seed, etc.), FOOD_Whole (whole food item), or OTHER. "
    "Mark is_metaphor true when the word is not used literally as food. "
    "Mark is_food_entity false for ship names, place names, or irrelevant entities.\n\n"
    "{few_shots}"
)


def ontology_hint(target_word: str) -> tuple[bool, str | None]:
    """Return ontology match flag and canonical label for *target_word*."""
    index = alt_label_index(load_food_terms())
    canonical = index.get(target_word.strip().lower())
    return canonical is not None, canonical


def should_drop(step_a: EntityValidation) -> tuple[bool, str | None]:
    """Return dropout flag and reason from Step A output."""
    if step_a.is_metaphor:
        return True, "metaphor"
    if not step_a.is_food_entity:
        return True, "not_food_entity"
    return False, None


def validate_entity(
    target_word: str,
    context_text: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
) -> EntityValidation:
    """Validate food entity status and formal layer for *target_word*."""
    matched, canonical = ontology_hint(target_word)
    few_shots = format_few_shots(load_prompt_asset("step_a_fewshots.json")["examples"])
    system = SYSTEM_PROMPT.format(few_shots=few_shots)
    hint = ""
    if matched:
        hint = f"\nOntology hint: maps to canonical label '{canonical}'."

    user_prompt = (
        f"Target Word: {target_word}\n"
        f"Context: {context_text}"
        f"{hint}"
    )
    result = structured_completion(
        EntityValidation,
        system_prompt=system,
        user_prompt=user_prompt,
        model=model,
        base_url=base_url,
        client=client,
    )
    if matched and not result.canonical_pref_label:
        result.canonical_pref_label = canonical
    if matched:
        result.ontology_match = True
    return result
