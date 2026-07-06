"""Evaluation metric tests."""

from trifecta_annotation.eval import evaluate


def test_evaluate_frame_accuracy() -> None:
    gold = [
        {
            "provenance": {"record_id": "1", "corpus": "t", "target_word": "zout", "context_text": "x"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "PRESERVING", "lexical_unit": "zout", "reasoning": ""},
        },
        {
            "provenance": {"record_id": "2", "corpus": "t", "target_word": "bier", "context_text": "y"},
            "dropped": True,
            "step_a": {"is_food_entity": False, "is_metaphor": True, "ontology_match": False, "reasoning": ""},
        },
    ]
    pred = [
        {
            "provenance": {"record_id": "1", "corpus": "t", "target_word": "zout", "context_text": "x"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "PRESERVING", "lexical_unit": "zout", "reasoning": ""},
        },
        {
            "provenance": {"record_id": "2", "corpus": "t", "target_word": "bier", "context_text": "y"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "INGESTION", "lexical_unit": "drinken", "reasoning": ""},
        },
    ]
    metrics = evaluate(gold, pred)
    assert metrics.total == 2
    assert metrics.step_b_accuracy == 1.0
    assert metrics.dropout_agreement == 0.5


def test_evaluate_by_text_regime() -> None:
    gold = [
        {
            "provenance": {
                "record_id": "1",
                "corpus": "t",
                "target_word": "zout",
                "context_text": "x",
                "text_regime": "RECIPE_PRACTICE",
            },
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "PRESERVING", "lexical_unit": "zout", "reasoning": ""},
        },
        {
            "provenance": {
                "record_id": "2",
                "corpus": "t",
                "target_word": "bier",
                "context_text": "y",
                "text_regime": "LITERARY",
            },
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "NONE", "lexical_unit": "", "reasoning": ""},
        },
    ]
    pred = [
        {
            "provenance": {"record_id": "1", "corpus": "t", "target_word": "zout", "context_text": "x"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "COOKING_CREATION", "lexical_unit": "koken", "reasoning": ""},
        },
        {
            "provenance": {"record_id": "2", "corpus": "t", "target_word": "bier", "context_text": "y"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "NONE", "lexical_unit": "", "reasoning": ""},
        },
    ]
    metrics = evaluate(gold, pred)
    assert "RECIPE_PRACTICE" in metrics.by_text_regime
    assert metrics.by_text_regime["RECIPE_PRACTICE"]["accuracy"] == 0.0
    assert metrics.by_text_regime["LITERARY"]["accuracy"] == 1.0
