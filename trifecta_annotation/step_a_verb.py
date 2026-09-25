"""Step A — simplified entity validation for verbs (verb-first POC).

For verb-KWIC, skip full entity validation. Instead:
1. Check if target_word is a known frame verb in lexicon → continue
2. If not in lexicon → drop (NONE verb, not a TRIFECTA trigger)
"""

from __future__ import annotations

from trifecta_annotation.frame_verbs import FrameVerbLexicon
from trifecta_annotation.schemas import EntityValidation


def validate_verb_entity(
    target_word: str,
    context_text: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    client=None,
    english_hint: str | None = None,
) -> EntityValidation:
    """Check if target_word is a known frame verb (simplified Step A for verbs).
    
    Returns a synthetic EntityValidation:
    - is_food_entity=True if verb is in frame-verb lexicon
    - is_metaphor=False (verbs are less metaphorical than nouns)
    - formal_dimension=None (not applicable for verbs)
    """
    lex = FrameVerbLexicon()
    entry = lex.entry_for(target_word)
    
    if entry is not None:
        # Verb is in lexicon → pass through Step A
        return EntityValidation(
            is_food_entity=True,
            is_metaphor=False,
            formal_dimension=None,
            canonical_pref_label=target_word,
            ontology_match=True,
            reasoning=f"Frame verb '{target_word}' found in lexicon (frames: {[s for s in entry.sources]})",
        )
    else:
        # Verb not in lexicon → drop at Step A (NONE signal)
        return EntityValidation(
            is_food_entity=False,
            is_metaphor=False,
            formal_dimension=None,
            canonical_pref_label=None,
            ontology_match=False,
            reasoning=f"Verb '{target_word}' not in frame-verb lexicon; likely NONE or non-trigger verb.",
        )


def should_drop_verb(step_a: EntityValidation) -> tuple[bool, str | None]:
    """Return dropout flag and reason from Step A output (verb mode).
    
    Drop only if verb is not in lexicon (is_food_entity=False).
    """
    if not step_a.is_food_entity:
        return True, "verb_not_in_lexicon"
    return False, None
