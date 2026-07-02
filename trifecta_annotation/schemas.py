"""TRIFECTA Pydantic schemas (Steps A–C, I/O records)."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from trifecta_annotation.text_regime import TextRegime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class TrifectaFrame(str, Enum):
    COOKING_CREATION = "COOKING_CREATION"
    CURE = "CURE"
    INGESTION = "INGESTION"
    PRESERVING = "PRESERVING"
    NONE = "NONE"

    @classmethod
    def _missing_(cls, value: object) -> TrifectaFrame | None:
        legacy = {
            "USING_CURE": cls.CURE,
            "USING_INGESTION": cls.INGESTION,
        }
        if isinstance(value, str) and value in legacy:
            return legacy[value]
        return None


# Deprecated enum names — kept for imports during migration.
USING_CURE = TrifectaFrame.CURE
USING_INGESTION = TrifectaFrame.INGESTION


def _normalize_qualia_payload(data: object) -> object:
    if isinstance(data, dict):
        frame = data.get("frame")
        if frame == "USING_CURE":
            data = {**data, "frame": TrifectaFrame.CURE}
        elif frame == "USING_INGESTION":
            data = {**data, "frame": TrifectaFrame.INGESTION}
    return data


class FormalDimension(str, Enum):
    FOOD_UNIT = "FOOD_Unit"
    FOOD_CONSTITUENT_PART = "FOOD_Constituent_Part"
    FOOD_WHOLE = "FOOD_Whole"
    FOOD_DESCRIPTOR = "FOOD_Descriptor"
    OTHER = "OTHER"


class FrameClassification(BaseModel):
    """Step B: macro-frame surrounding the food target in context."""

    selected_frame: TrifectaFrame = Field(
        description="Active TRIFECTA macro-frame surrounding the food target.",
    )
    lexical_unit: str = Field(
        description="Trigger word (verb or noun) activating the frame; WebAnno *_LU.",
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


class CureQualia(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _legacy_frame(cls, data: object) -> object:
        return _normalize_qualia_payload(data)

    frame: Literal[TrifectaFrame.CURE] = TrifectaFrame.CURE
    CURE_Affliction: str = Field(
        validation_alias=AliasChoices("CURE_Affliction", "cure_affliction"),
        description="Ailment or symptom being treated (WebAnno CURE_Affliction).",
    )
    CURE_Food_Treatment: str = Field(
        validation_alias=AliasChoices("CURE_Food_Treatment", "cure_food_treatment"),
        description="How the food acts as treatment (WebAnno CURE_Food_Treatment).",
    )
    lexical_unit: str = Field(description="Trigger word activating the frame (CURE_LU).")


class CookingCreationQualia(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    frame: Literal[TrifectaFrame.COOKING_CREATION] = TrifectaFrame.COOKING_CREATION
    COOKING_CREATION_Method: str = Field(
        validation_alias=AliasChoices("COOKING_CREATION_Method", "preparation_method"),
        description="Named preparation or recipe step.",
    )
    COOKING_CREATION_Process: str = Field(
        validation_alias=AliasChoices("COOKING_CREATION_Process", "heat_or_mechanical_process"),
        description="Thermal or mechanical process applied.",
    )
    COOKING_CREATION_Food_Product: str = Field(
        validation_alias=AliasChoices("COOKING_CREATION_Food_Product", "result_state"),
        description="Resulting food state after preparation.",
    )
    lexical_unit: str = Field(description="Trigger word activating the frame (COOKING_CREATION_LU).")


class IngestionQualia(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _legacy_frame(cls, data: object) -> object:
        return _normalize_qualia_payload(data)

    frame: Literal[TrifectaFrame.INGESTION] = TrifectaFrame.INGESTION
    INGESTION_Context: str = Field(
        validation_alias=AliasChoices("INGESTION_Context", "consumption_context"),
        description="Situation or setting of consumption.",
    )
    INGESTION_Ingestor: str = Field(
        validation_alias=AliasChoices("INGESTION_Ingestor", "consumer"),
        description="Who consumes the food, if stated.",
    )
    INGESTION_Manner: str = Field(
        validation_alias=AliasChoices("INGESTION_Manner", "manner"),
        description="Manner of ingestion (eating, drinking, etc.).",
    )
    lexical_unit: str = Field(description="Trigger word activating the frame (INGESTION_LU).")


class PreservingQualia(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    frame: Literal[TrifectaFrame.PRESERVING] = TrifectaFrame.PRESERVING
    PR_Technique: str = Field(
        validation_alias=AliasChoices("PR_Technique", "preservation_technique"),
        description="Technique: salting, smoking, pickling, drying, etc.",
    )
    PR_Medium: str = Field(
        validation_alias=AliasChoices("PR_Medium", "preserving_agent"),
        description="Agent or medium used (salt, smoke, vinegar, etc.).",
    )
    PR_Food_Patient: str = Field(
        validation_alias=AliasChoices("PR_Food_Patient", "target_food"),
        description="Food item being preserved.",
    )
    lexical_unit: str = Field(description="Trigger word activating the frame (PR_LU).")


# Backward-compatible class aliases.
UsingCureQualia = CureQualia
UsingIngestionQualia = IngestionQualia

FrameQualia = Annotated[
    CureQualia | CookingCreationQualia | IngestionQualia | PreservingQualia,
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
    discovery_verb: str | None = Field(
        default=None,
        description="Frame verb that discovered this snippet (verb-seeded KWIC).",
    )
    frame_hint: str | None = Field(
        default=None,
        description="Expected macro-frame from discovery_verb lexicon.",
    )
    kwic_mode: Literal["food", "verb_food", "verb"] = Field(
        default="food",
        description="food = noun target; verb_food = verb found snippet, food highlighted.",
    )
    text_regime: TextRegime | None = Field(
        default=None,
        description="Source document discourse type (genre layer).",
    )


class AnnotationProvenance(BaseModel):
    """Metadata attached to every pipeline output."""

    corpus: str = Field(description="Source corpus identifier, e.g. voc_recipes, recipe_web.")
    target_word: str
    context_text: str
    source_path: str | None = None
    record_id: str | None = None
    date: str | None = None
    discovery_verb: str | None = None
    frame_hint: str | None = None
    kwic_mode: Literal["food", "verb_food", "verb"] = "food"
    text_regime: TextRegime | None = None
    title: str | None = None


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
