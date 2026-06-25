"""Gold CSV roundtrip tests."""

from trifecta_annotation.gold_io import annotation_to_row, row_to_annotation
from trifecta_annotation.schemas import (
    AnnotationProvenance,
    EntityValidation,
    FormalDimension,
    FrameClassification,
    GoldAnnotation,
    TrifectaFrame,
)


def test_gold_csv_roundtrip() -> None:
    ann = GoldAnnotation(
        provenance=AnnotationProvenance(
            record_id="g1",
            corpus="voc_recipes",
            target_word="zout",
            context_text="een hand vol zout",
            date="1750",
        ),
        step_a=EntityValidation(
            is_food_entity=True,
            is_metaphor=False,
            formal_dimension=FormalDimension.FOOD_WHOLE,
            canonical_pref_label="zout",
            ontology_match=True,
            reasoning="Literal salt.",
        ),
        step_b=FrameClassification(
            selected_frame=TrifectaFrame.PRESERVING,
            lexical_unit="zout",
            reasoning="Salting context.",
        ),
        dropped=False,
    )
    row = annotation_to_row(ann)
    row["labelled"] = True
    parsed = row_to_annotation(row)
    assert parsed is not None
    assert parsed.provenance.record_id == "g1"
    assert parsed.step_b is not None
    assert parsed.step_b.selected_frame == TrifectaFrame.PRESERVING


def test_gold_csv_dropout_row() -> None:
    row = {
        "record_id": "g2",
        "corpus": "voc_recipes",
        "target_word": "brood",
        "context_text": "het brood des levens",
        "date": "",
        "source_path": "",
        "dropped": "true",
        "drop_reason": "metaphor",
        "is_food_entity": "false",
        "is_metaphor": "true",
        "formal_dimension": "",
        "canonical_pref_label": "",
        "ontology_match": "false",
        "step_a_reasoning": "Religious idiom.",
        "selected_frame": "",
        "lexical_unit": "",
        "step_b_reasoning": "",
        "labelled": "true",
        "notes": "",
    }
    parsed = row_to_annotation(row)
    assert parsed is not None
    assert parsed.dropped is True
    assert parsed.drop_reason == "metaphor"
    assert parsed.step_b is None
