"""Schema tests (no LLM required)."""

from trifecta_annotation.schemas import (
    EntityValidation,
    FrameClassification,
    FormalDimension,
    KwicInput,
    TrifectaAnnotation,
    TrifectaFrame,
    CureQualia,
)


def test_frame_classification_roundtrip() -> None:
    record = FrameClassification(
        selected_frame=TrifectaFrame.CURE,
        lexical_unit="verzachten",
        reasoning="Medicinal use of elderberry sap against cough.",
    )
    data = record.model_dump()
    assert data["selected_frame"] == "CURE"
    assert FrameClassification.model_validate(data).lexical_unit == "verzachten"


def test_frame_legacy_alias() -> None:
    assert TrifectaFrame("USING_CURE") == TrifectaFrame.CURE
    assert TrifectaFrame("USING_INGESTION") == TrifectaFrame.INGESTION


def test_entity_validation_roundtrip() -> None:
    record = EntityValidation(
        is_food_entity=True,
        is_metaphor=False,
        formal_dimension=FormalDimension.FOOD_WHOLE,
        canonical_pref_label="zout",
        ontology_match=True,
        reasoning="Literal food ingredient.",
    )
    assert EntityValidation.model_validate(record.model_dump()).canonical_pref_label == "zout"


def test_kwic_input_and_annotation() -> None:
    inp = KwicInput(
        record_id="1",
        corpus="voc_recipes",
        target_word="zout",
        context_text="een hand vol zout",
    )
    ann = TrifectaAnnotation(
        provenance={
            "corpus": inp.corpus,
            "target_word": inp.target_word,
            "context_text": inp.context_text,
            "record_id": inp.record_id,
        },
        step_c=CureQualia(
            CURE_Affliction="hoest",
            CURE_Food_Treatment="verzachten",
            lexical_unit="sap",
        ),
    )
    assert ann.step_c is not None
    assert ann.step_c.frame == TrifectaFrame.CURE


def test_cure_qualia_legacy_field_names() -> None:
    qualia = CureQualia.model_validate(
        {
            "frame": "USING_CURE",
            "cure_affliction": "hoest",
            "cure_food_treatment": "sap",
            "lexical_unit": "drinken",
        },
    )
    assert qualia.CURE_Affliction == "hoest"
    assert qualia.frame == TrifectaFrame.CURE
