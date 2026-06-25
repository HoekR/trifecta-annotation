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
            "step_b": {"selected_frame": "USING_INGESTION", "lexical_unit": "drinken", "reasoning": ""},
        },
    ]
    metrics = evaluate(gold, pred)
    assert metrics.total == 2
    assert metrics.step_b_accuracy == 1.0
    assert metrics.dropout_agreement == 0.5
