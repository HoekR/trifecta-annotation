"""EXPERIMENTAL: 2-stage Step B classifier (prototype, 2026-10-13).

Isolated from the production `step_b.py` — never imported by `pipeline.py` or
`batch.py`. Tests whether splitting the flat 5-way classifier into a coarse
router (TRANSFORM vs OTHER) plus two small group classifiers avoids the
regression found when adding PRESERVING/CURE examples to the flat few-shot
set (see project memory: project_step_b_fewshot_regression). The hypothesis:
PRESERVING/CURE examples only destabilized the model when mixed with
INGESTION/NONE examples in the same prompt — splitting removes that mixing.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from trifecta_annotation.client import make_instructor_client
from trifecta_annotation.config import trifecta_model
from trifecta_annotation.prompts import format_few_shots, load_prompt_asset
from trifecta_annotation.schemas import FrameClassification, TrifectaFrame

ROUTER_SYSTEM_PROMPT = (
    "You are an expert computational linguist annotating historical Dutch corpora "
    "for the TRIFECTA project. Decide only the COARSE group for the food target in "
    "context — not the specific frame yet.\n\n"
    "TRANSFORM: the snippet describes an act that transforms the food — cooking/"
    "preparing it (koken, sieden, mengen), preserving it for later (drogen, roken, "
    "zouten, inleggen, confijten, gisten), or using it as treatment for an "
    "explicit affliction (genezen, verzachten, tegen de hoest).\n\n"
    "OTHER: the snippet describes direct consumption without any transformation "
    "framing (eten, drinken, nuttigen), or the food term is not an active food "
    "practice at all (metaphor, homograph, trade/list mention).\n\n"
    "{few_shots}"
)

TRANSFORM_SYSTEM_PROMPT = (
    "You are an expert computational linguist annotating historical Dutch corpora "
    "for the TRIFECTA project. This snippet has already been judged to involve a "
    "transformation of the food target. Pick exactly which one:\n\n"
    "COOKING_CREATION for thermal or mechanical food preparation; "
    "PRESERVING for smoking, salting, pickling, drying, sugaring (confijten), or "
    "fermenting (gisten) for long-term keeping; "
    "CURE for medicinal treatment of an explicit affliction, not mere recipe-in-"
    "a-medical-book.\n\n"
    "Bind the lexical_unit to the verb that governs the target in this snippet.\n\n"
    "{few_shots}"
)

REST_SYSTEM_PROMPT = (
    "You are an expert computational linguist annotating historical Dutch corpora "
    "for the TRIFECTA project. This snippet has already been judged to NOT involve "
    "a transformation of the food target. Pick exactly which one:\n\n"
    "INGESTION for direct consumption without medical or preparation framing; "
    "NONE when the food term is metaphorical, a homograph, or the passage is not "
    "about food practice at all.\n\n"
    "Bind the lexical_unit to the verb that governs the target in this snippet.\n\n"
    "{few_shots}"
)


class RouterGroup(str, Enum):
    TRANSFORM = "TRANSFORM"
    OTHER = "OTHER"


class RouterClassification(BaseModel):
    group: RouterGroup = Field(description="Coarse group: TRANSFORM or OTHER.")
    lexical_unit: str = Field(description="Trigger word governing the target.")
    reasoning: str = Field(description="Brief justification.")


class TransformClassification(BaseModel):
    selected_frame: Literal[
        TrifectaFrame.COOKING_CREATION,
        TrifectaFrame.PRESERVING,
        TrifectaFrame.CURE,
    ] = Field(description="One of the transformation frames.")
    lexical_unit: str = Field(description="Trigger word governing the target.")
    reasoning: str = Field(description="Brief justification.")


class RestClassification(BaseModel):
    selected_frame: Literal[TrifectaFrame.INGESTION, TrifectaFrame.NONE] = Field(
        description="INGESTION or NONE.",
    )
    lexical_unit: str = Field(description="Trigger word governing the target.")
    reasoning: str = Field(description="Brief justification.")


def classify_context_split(
    target_word: str,
    context_text: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
) -> FrameClassification:
    """2-stage Step B: coarse router, then a group-specific classifier."""
    client = make_instructor_client(base_url=base_url)
    user_prompt = f"Target Word: {target_word}\nContext: {context_text}"
    resolved_model = model or trifecta_model()

    router_few_shots = format_few_shots(
        load_prompt_asset("step_b_router_fewshots.json")["examples"],
    )
    router = client.chat.completions.create(
        model=resolved_model,
        response_model=RouterClassification,
        messages=[
            {
                "role": "system",
                "content": ROUTER_SYSTEM_PROMPT.format(few_shots=router_few_shots),
            },
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
    )

    if router.group == RouterGroup.TRANSFORM:
        few_shots = format_few_shots(
            load_prompt_asset("step_b_transform_fewshots.json")["examples"],
        )
        result = client.chat.completions.create(
            model=resolved_model,
            response_model=TransformClassification,
            messages=[
                {
                    "role": "system",
                    "content": TRANSFORM_SYSTEM_PROMPT.format(few_shots=few_shots),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
    else:
        few_shots = format_few_shots(
            load_prompt_asset("step_b_rest_fewshots.json")["examples"],
        )
        result = client.chat.completions.create(
            model=resolved_model,
            response_model=RestClassification,
            messages=[
                {
                    "role": "system",
                    "content": REST_SYSTEM_PROMPT.format(few_shots=few_shots),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )

    return FrameClassification(
        selected_frame=result.selected_frame,
        lexical_unit=result.lexical_unit,
        reasoning=f"[router={router.group.value}] {result.reasoning}",
    )
