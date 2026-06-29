"""Step B — TRIFECTA macro-frame classification."""

from __future__ import annotations

from trifecta_annotation.client import make_instructor_client
from trifecta_annotation.config import trifecta_model
from trifecta_annotation.schemas import FrameClassification

SYSTEM_PROMPT = (
    "You are an expert computational linguist annotating historical Dutch corpora "
    "for the TRIFECTA project. Classify the macro-frame strictly according to the "
    "guidelines. Use COOKING_CREATION for thermal or mechanical food preparation, "
    "CURE for medicinal treatment, INGESTION for direct consumption, "
    "PRESERVING for smoking, salting, pickling, or drying, and NONE when the food "
    "term is metaphorical or the passage is not about food practice."
)


def classify_context(
    target_word: str,
    context_text: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
) -> FrameClassification:
    """Classify the TRIFECTA macro-frame for *target_word* in *context_text*."""
    client = make_instructor_client(base_url=base_url)
    prompt = f"Target Word: {target_word}\nContext: {context_text}"

    return client.chat.completions.create(
        model=model or trifecta_model(),
        response_model=FrameClassification,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
