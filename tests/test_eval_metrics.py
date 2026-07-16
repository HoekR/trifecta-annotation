"""Evaluation metric tests."""

from trifecta_annotation.eval import (
    _per_class_scores,
    _score_step_c_pair,
    evaluate,
    normalize_qualia_value,
    soft_qualia_match,
)
from trifecta_annotation.schemas import CookingCreationQualia


def test_normalize_qualia_value() -> None:
    assert normalize_qualia_value("  Braden ") == "braden"
    assert normalize_qualia_value("in  de\toven") == "in de oven"
    assert normalize_qualia_value("") == ""
    assert normalize_qualia_value(None) == ""


def test_soft_qualia_match() -> None:
    assert soft_qualia_match("braden", "braden") is True
    assert soft_qualia_match("braden", "braden en koken") is True
    assert soft_qualia_match("braden en koken", "braden") is True
    assert soft_qualia_match("", "") is True
    assert soft_qualia_match("braden", "") is False
    assert soft_qualia_match("", "braden") is False
    assert soft_qualia_match("braden", "bakken") is False


def test_score_step_c_pair_cooking() -> None:
    gold = CookingCreationQualia(
        COOKING_CREATION_Method="braden",
        COOKING_CREATION_Process="koken",
        COOKING_CREATION_Food_Product="",
        lexical_unit="braden",
    )
    pred_ok = CookingCreationQualia(
        COOKING_CREATION_Method="Braden",
        COOKING_CREATION_Process="koken",
        COOKING_CREATION_Food_Product="",
        lexical_unit="braden",
    )
    hits, joint = _score_step_c_pair(gold, pred_ok)
    assert joint is True
    assert hits["COOKING_CREATION_Method"] is True

    pred_miss = CookingCreationQualia(
        COOKING_CREATION_Method="bakken",
        COOKING_CREATION_Process="koken",
        COOKING_CREATION_Food_Product="",
        lexical_unit="bakken",
    )
    hits2, joint2 = _score_step_c_pair(gold, pred_miss)
    assert joint2 is False
    assert hits2["COOKING_CREATION_Method"] is False
    assert hits2["COOKING_CREATION_Process"] is True

    hits3, joint3 = _score_step_c_pair(gold, None)
    assert joint3 is False
    assert all(v is False for v in hits3.values())

    pred_long = CookingCreationQualia(
        COOKING_CREATION_Method="braden en koken hun vlees",
        COOKING_CREATION_Process="koken",
        COOKING_CREATION_Food_Product="",
        lexical_unit="braden",
    )
    exact_hits, exact_joint = _score_step_c_pair(gold, pred_long)
    soft_hits, soft_joint = _score_step_c_pair(gold, pred_long, soft=True)
    assert exact_joint is False
    assert exact_hits["COOKING_CREATION_Method"] is False
    assert soft_joint is True
    assert soft_hits["COOKING_CREATION_Method"] is True


def test_per_class_scores_precision_recall() -> None:
    scores = _per_class_scores(
        ["A", "A", "B"],
        ["A", "B", "B"],
    )
    assert scores.precision["A"] == 1.0
    assert scores.recall["A"] == 0.5
    assert scores.f1["A"] == 2 / 3
    assert scores.precision["B"] == 0.5
    assert scores.recall["B"] == 1.0


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
    assert metrics.step_b_per_frame_precision["PRESERVING"] == 1.0
    assert metrics.step_b_per_frame_recall["PRESERVING"] == 1.0


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
    assert "per_frame_precision" in metrics.by_text_regime["LITERARY"]
    assert metrics.by_text_regime["LITERARY"]["per_frame_precision"]["NONE"] == 1.0


def test_evaluate_step_c_field_match() -> None:
    gold = [
        {
            "provenance": {"record_id": "1", "corpus": "t", "target_word": "vlees", "context_text": "x"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "COOKING_CREATION", "lexical_unit": "braden", "reasoning": ""},
            "step_c": {
                "frame": "COOKING_CREATION",
                "COOKING_CREATION_Method": "braden",
                "COOKING_CREATION_Process": "koken",
                "COOKING_CREATION_Food_Product": "gebraad",
                "lexical_unit": "braden",
            },
        },
        {
            "provenance": {"record_id": "2", "corpus": "t", "target_word": "vis", "context_text": "y"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "COOKING_CREATION", "lexical_unit": "koken", "reasoning": ""},
            "step_c": {
                "frame": "COOKING_CREATION",
                "COOKING_CREATION_Method": "koken",
                "COOKING_CREATION_Process": "",
                "COOKING_CREATION_Food_Product": "",
                "lexical_unit": "koken",
            },
        },
    ]
    pred = [
        {
            "provenance": {"record_id": "1", "corpus": "t", "target_word": "vlees", "context_text": "x"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "COOKING_CREATION", "lexical_unit": "braden", "reasoning": ""},
            "step_c": {
                "frame": "COOKING_CREATION",
                "COOKING_CREATION_Method": "Braden",
                "COOKING_CREATION_Process": "koken",
                "COOKING_CREATION_Food_Product": "gebraad",
                "lexical_unit": "braden",
            },
        },
        {
            "provenance": {"record_id": "2", "corpus": "t", "target_word": "vis", "context_text": "y"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "COOKING_CREATION", "lexical_unit": "koken", "reasoning": ""},
            "step_c": {
                "frame": "COOKING_CREATION",
                "COOKING_CREATION_Method": "stoven",
                "COOKING_CREATION_Process": "stoven",
                "COOKING_CREATION_Food_Product": "",
                "lexical_unit": "stoven",
            },
        },
    ]
    metrics = evaluate(gold, pred)
    assert metrics.step_c_gold_rows == 2
    assert metrics.step_c_comparable_rows == 2
    assert metrics.step_c_joint_accuracy == 0.5
    assert metrics.step_c_field_accuracy["COOKING_CREATION_Method"] == 0.5
    assert metrics.step_c_field_accuracy["COOKING_CREATION_Process"] == 0.5
    assert metrics.step_c_field_accuracy["COOKING_CREATION_Food_Product"] == 1.0
    assert metrics.step_c_by_frame["COOKING_CREATION"]["comparable"] == 2
    # Soft equals exact here (no containment-only hits).
    assert metrics.step_c_soft_joint_accuracy == 0.5
    assert metrics.step_c_soft_field_accuracy["COOKING_CREATION_Method"] == 0.5
