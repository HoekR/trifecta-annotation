"""Step A dropout helper tests."""

from trifecta_annotation.step_a import should_drop
from trifecta_annotation.schemas import EntityValidation


def test_should_drop_metaphor() -> None:
    step_a = EntityValidation(
        is_food_entity=True,
        is_metaphor=True,
        reasoning="Metaphor.",
    )
    dropped, reason = should_drop(step_a)
    assert dropped is True
    assert reason == "metaphor"


def test_should_drop_non_food() -> None:
    step_a = EntityValidation(
        is_food_entity=False,
        is_metaphor=False,
        reasoning="Ship name.",
    )
    dropped, reason = should_drop(step_a)
    assert dropped is True
    assert reason == "not_food_entity"
