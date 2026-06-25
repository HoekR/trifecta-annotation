"""TRIFECTA Pydantic schemas (Steps A–C, I/O records)."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class TrifectaFrame(str, Enum):
    COOKING_CREATION = "COOKING_CREATION"
    USING_CURE = "USING_CURE"
    USING_INGESTION = "USING_INGESTION"
    PRESERVING = "PRESERVING"
    NONE = "NONE"


class FormalDimension(str, Enum):
    FOOD_UNIT = "FOOD_Unit"
    FOOD_CONSTITUENT_PART = "FOOD_Constituent_Part"
    FOOD_WHOLE = "FOOD_Whole"
    OTHER = "OTHER"


class FrameClassification(BaseModel):
    """Step B: macro-frame surrounding the food target in context."""

    selected_frame: TrifectaFrame = Field(
        description="Active TRIFECTA macro-frame surrounding the food target.",
    )
    lexical_unit: str = Field(
        description="Trigger word (verb or noun) activating the frame.",
    )
    reasoning: str = Field(
        description="Brief linguistic justification per TRIFECTA guidelines.",
    )


class EntityValidation(BaseModel):
    """Step A: entity validation and formal layer."""

    is_food_entity: bool = Field(
        description="True when the target functions as a food entity in context.",
    )
    is_metaphor: bool = Field(
        description="True when the target is used metaphorically, not literally as food.",
    )
    formal_dimension: FormalDimension | None = Field(
        default=None,
        description="Structural dimension of the food mention when applicable.",
    )
    canonical_pref_label: str | None = Field(
        default=None,
        description="Canonical ontology label when matched to Food_terms.",
    )
    ontology_match: bool = Field(
        default=False,
        description="Whether target_word maps to the food ontology lexicon.",
    )
    reasoning: str = Field(
        description="Brief justification for entity validation.",
    )


class UsingCureQualia(BaseModel):
    frame: Literal[TrifectaFrame.USING_CURE] = TrifectaFrame.USING_CURE
    cure_affliction: str = Field(description="Ailment or symptom being treated.")
    cure_food_treatment: str = Field(description="How the food acts as treatment.")
    lexical_unit: str = Field(description="Trigger word activating the cure frame.")


class CookingCreationQualia(BaseModel):
    frame: Literal[TrifectaFrame.COOKING_CREATION] = TrifectaFrame.COOKING_CREATION
    preparation_method: str = Field(description="Named preparation or recipe step.")
    heat_or_mechanical_process: str = Field(
        description="Thermal or mechanical process applied.",
    )
    result_state: str = Field(description="Resulting food state after preparation.")
    lexical_unit: str = Field(description="Trigger word activating the cooking frame.")


class UsingIngestionQualia(BaseModel):
    frame: Literal[TrifectaFrame.USING_INGESTION] = TrifectaFrame.USING_INGESTION
    consumption_context: str = Field(description="Situation or setting of consumption.")
    consumer: str = Field(description="Who consumes the food, if stated.")
    manner: str = Field(description="Manner of ingestion (eating, drinking, etc.).")
    lexical_unit: str = Field(description="Trigger word activating the ingestion frame.")


class PreservingQualia(BaseModel):
    frame: Literal[TrifectaFrame.PRESERVING] = TrifectaFrame.PRESERVING
    preservation_technique: str = Field(
        description="Technique: salting, smoking, pickling, drying, etc.",
    )
    preserving_agent: str = Field(
        description="Agent or medium used (salt, smoke, vinegar, etc.).",
    )
    target_food: str = Field(description="Food item being preserved.")
    lexical_unit: str = Field(description="Trigger word activating the preserving frame.")


FrameQualia = Annotated[
    UsingCureQualia
    | CookingCreationQualia
    | UsingIngestionQualia
    | PreservingQualia,
    Field(discriminator="frame"),
]


class KwicInput(BaseModel):
    """Normalized pipeline input from any corpus source."""

    record_id: str
    corpus: str
    target_word: str
    context_text: str
    date: str | None = None
    source_path: str | None = None
    title: str | None = None
    candidate_terms: list[str] | None = None


class AnnotationProvenance(BaseModel):
    """Metadata attached to every pipeline output."""

    corpus: str = Field(description="Source corpus identifier, e.g. voc_recipes, recipe_web.")
    target_word: str
    context_text: str
    source_path: str | None = None
    record_id: str | None = None
    date: str | None = None


class TrifectaAnnotation(BaseModel):
    """Full pipeline output for one KWIC record."""

    provenance: AnnotationProvenance
    step_a: EntityValidation | None = None
    step_b: FrameClassification | None = None
    step_c: FrameQualia | None = None
    dropped: bool = False
    drop_reason: str | None = None
    error: str | None = None
    model: str | None = None


class GoldAnnotation(TrifectaAnnotation):
    """Hand-labelled reference record for evaluation."""

    gold: bool = True
