"""Pipeline dropout tests with mocked LLM steps."""

from unittest.mock import patch

from trifecta_annotation.pipeline import annotate_record
from trifecta_annotation.schemas import (
    EntityValidation,
    FormalDimension,
    FrameClassification,
    KwicInput,
    TrifectaFrame,
)


def test_pipeline_drops_metaphor_at_step_a() -> None:
    inp = KwicInput(
        record_id="m1",
        corpus="test",
        target_word="brood",
        context_text="het brood des levens",
    )
    step_a = EntityValidation(
        is_food_entity=False,
        is_metaphor=True,
        formal_dimension=None,
        reasoning="Metaphorical use.",
    )
    with patch("trifecta_annotation.pipeline.validate_entity", return_value=step_a):
        result = annotate_record(inp, model="test-model")
    assert result.dropped is True
    assert result.drop_reason == "metaphor"
    assert result.step_b is None


def test_pipeline_stops_at_none_frame() -> None:
    inp = KwicInput(
        record_id="m2",
        corpus="test",
        target_word="zout",
        context_text="met zout bestrooid",
    )
    step_a = EntityValidation(
        is_food_entity=True,
        is_metaphor=False,
        formal_dimension=FormalDimension.FOOD_WHOLE,
        reasoning="Literal food.",
    )
    step_b = FrameClassification(
        selected_frame=TrifectaFrame.NONE,
        lexical_unit="",
        reasoning="No active frame.",
    )
    with (
        patch("trifecta_annotation.pipeline.validate_entity", return_value=step_a),
        patch("trifecta_annotation.pipeline.classify_context", return_value=step_b),
    ):
        result = annotate_record(inp, model="test-model")
    assert result.dropped is False
    assert result.step_b is not None
    assert result.step_c is None
