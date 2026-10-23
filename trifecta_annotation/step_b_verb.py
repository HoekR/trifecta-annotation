"""Step B — macro-frame classification with verb hint injection (verb-first POC).

Augments the standard Step B prompt with an explicit verb → frame prior.
"""

from __future__ import annotations

from trifecta_annotation.client import make_instructor_client
from trifecta_annotation.config import trifecta_model
from trifecta_annotation.english_hint import append_english_hint_block
from trifecta_annotation.frame_verbs import FrameVerbLexicon
from trifecta_annotation.prompts import format_few_shots, load_prompt_asset
from trifecta_annotation.schemas import FrameClassification, TrifectaFrame

SYSTEM_PROMPT_TEMPLATE = (
    "You are an expert computational linguist annotating historical Dutch corpora "
    "for the TRIFECTA project. Classify the macro-frame strictly according to the "
    "guidelines.\n\n"
    "Important: text_regime (recipe book, medical text) is NOT the frame. "
    "A recipe prepared for a cure is still COOKING_CREATION when the snippet "
    "describes preparation steps (koken, sieden, mengen). Use CURE only when the "
    "snippet frames the food as treatment for an affliction (verzachten, genezen, "
    "tegen de hoest), with CURE_Affliction/CURE_Food_Treatment roles in play.\n\n"
    "Use COOKING_CREATION for thermal or mechanical food preparation, "
    "CURE for medicinal treatment (not mere recipe-in-a-medical-book), "
    "INGESTION for direct consumption without medical framing, "
    "PRESERVING for smoking, salting, pickling, or drying, and NONE when the food "
    "term is metaphorical or the passage is not about food practice.\n\n"
    "Disambiguate homographs from context: the same spelling may be a food noun, "
    "a different word (e.g. biet=offer/plead vs beet), or a non-practice referent "
    "(trade lists, flood water, dictionary glosses). Bind the lexical_unit to the "
    "verb that governs the target in this snippet — not a nearby homograph "
    "(nuttigen arbeid ≠ eating boter).\n\n"
    "{verb_hint}"
    "{few_shots}"
)


def _build_verb_hint(target_verb: str) -> str:
    """Construct a verb → frame prior hint based on lexicon."""
    lex = FrameVerbLexicon()
    entry = lex.entry_for(target_verb)
    
    if entry is None:
        return ""
    
    frame = entry.frame
    hint = f"⚠ VERB HINT (lexicon prior): The verb '{target_verb}' typically marks the {frame.value} frame. "
    hint += f"Use this as a strong signal, but rely on context to confirm or override if needed.\n\n"
    return hint


def classify_context_with_verb_hint(
    target_word: str,
    context_text: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    english_hint: str | None = None,
) -> FrameClassification:
    """Classify macro-frame with explicit verb hint injection.
    
    target_word is expected to be a frame verb.
    """
    client = make_instructor_client(base_url=base_url)
    
    verb_hint = _build_verb_hint(target_word)
    few_shots = format_few_shots(load_prompt_asset("step_b_fewshots.json")["examples"])
    system = SYSTEM_PROMPT_TEMPLATE.format(
        verb_hint=verb_hint,
        few_shots=few_shots,
    )
    prompt = append_english_hint_block(
        f"Target Word (verb): {target_word}\nContext: {context_text}",
        english_hint,
    )

    return client.chat.completions.create(
        model=model or trifecta_model(),
        response_model=FrameClassification,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
