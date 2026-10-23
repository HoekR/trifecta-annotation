"""Tests for Step C review export helpers."""

from trifecta_annotation.step_c_review import (
    StepCReviewConfig,
    build_step_c_review_rows,
    filter_review_rows,
)


def _gold_cooking(*, record_id: str, method: str, process: str = "", product: str = "") -> dict:
    return {
        "provenance": {
            "record_id": record_id,
            "corpus": "t",
            "target_word": "vlees",
            "context_text": "men moet het vlees braden",
            "text_regime": "RECIPE_PRACTICE",
        },
        "dropped": False,
        "step_a": {
            "is_food_entity": True,
            "is_metaphor": False,
            "ontology_match": True,
            "reasoning": "",
        },
        "step_b": {
            "selected_frame": "COOKING_CREATION",
            "lexical_unit": "braden",
            "reasoning": "",
        },
        "step_c": {
            "frame": "COOKING_CREATION",
            "COOKING_CREATION_Method": method,
            "COOKING_CREATION_Process": process,
            "COOKING_CREATION_Food_Product": product,
            "lexical_unit": "braden",
        },
    }


def _pred_cooking(*, record_id: str, method: str, process: str = "", product: str = "") -> dict:
    return {
        "provenance": {
            "record_id": record_id,
            "corpus": "t",
            "target_word": "vlees",
            "context_text": "men moet het vlees braden",
        },
        "dropped": False,
        "step_a": {
            "is_food_entity": True,
            "is_metaphor": False,
            "ontology_match": True,
            "reasoning": "",
        },
        "step_b": {
            "selected_frame": "COOKING_CREATION",
            "lexical_unit": "braden",
            "reasoning": "",
        },
        "step_c": {
            "frame": "COOKING_CREATION",
            "COOKING_CREATION_Method": method,
            "COOKING_CREATION_Process": process,
            "COOKING_CREATION_Food_Product": product,
            "lexical_unit": "braden",
        },
    }


def test_build_step_c_review_joint_and_partial() -> None:
    gold = [
        _gold_cooking(record_id="1", method="braden", process="koken", product=""),
        _gold_cooking(record_id="2", method="braden", process="opkoken", product=""),
    ]
    pred = [
        _pred_cooking(record_id="1", method="Braden", process="koken", product=""),
        _pred_cooking(record_id="2", method="braden", process="stooven", product=""),
    ]
    rows = build_step_c_review_rows(gold, pred)
    assert len(rows) == 2
    assert rows[0]["tier"] == "joint"
    assert rows[0]["fewshot_candidate"] == "yes"
    assert rows[0]["joint"] == "true"
    assert rows[1]["hits"] == 2
    assert rows[1]["tier"] == "partial_strong"
    assert rows[1]["fewshot_candidate"] == "yes"


def test_filter_review_rows_configurable() -> None:
    gold = [
        _gold_cooking(record_id="1", method="braden", process="koken", product=""),
        _gold_cooking(record_id="2", method="braden", process="opkoken", product=""),
    ]
    pred = [
        _pred_cooking(record_id="1", method="Braden", process="koken", product=""),
        _pred_cooking(record_id="2", method="braden", process="stooven", product=""),
    ]
    rows = build_step_c_review_rows(gold, pred)
    few = filter_review_rows(rows, StepCReviewConfig(fewshot_only=True, fewshot_levels=("yes",)))
    assert len(few) == 2
    cooking = filter_review_rows(
        rows,
        StepCReviewConfig(frames=("COOKING_CREATION",), min_hits=3),
    )
    assert len(cooking) == 1
    assert cooking[0]["tier"] == "joint"


def test_print_row_detail_smoke(capsys) -> None:
    from trifecta_annotation.step_c_review import print_row_detail, walk_details
    import pandas as pd

    frame = pd.DataFrame(
        [
            {
                "tier": "joint",
                "target_word": "water",
                "record_id": "r1",
                "gold_frame": "PRESERVING",
                "pred_frame": "PRESERVING",
                "gold_b_frame": "PRESERVING",
                "pred_b_frame": "PRESERVING",
                "hits": 3,
                "n_fields": 3,
                "field_hits": "a=✓",
                "context_snippet": "…",
                "gold_fields": "PR_Technique='boil'",
                "pred_fields": "PR_Technique='boil'",
                "fewshot_candidate": "yes",
            },
        ],
    )
    print_row_detail(frame, 0)
    walk_details(frame, start=0, n=1)
    out = capsys.readouterr().out
    assert "water" in out
    assert "GOLD:" in out
    assert "PRED:" in out


def test_skips_gold_without_step_c() -> None:
    gold = [
        {
            "provenance": {
                "record_id": "x",
                "corpus": "t",
                "target_word": "a",
                "context_text": "b",
            },
            "dropped": True,
        },
    ]
    assert build_step_c_review_rows(gold, []) == []
