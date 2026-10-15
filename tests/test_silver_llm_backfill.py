"""Silver LLM backfill merge tests."""

from trifecta_annotation.silver_llm_backfill import (
    merge_llm_into_silver,
    needs_llm_step_b,
    select_records_needing_llm,
)


def _out_of_scope_silver() -> dict:
    return {
        "provenance": {
            "record_id": "r1",
            "corpus": "cort_voc_db",
            "target_word": "brood",
            "context_text": "Hij at brood bij het venster.",
        },
        "step_a": {
            "is_food_entity": True,
            "is_metaphor": False,
            "reasoning": "coarse",
        },
        "coarse_frame": "OUT_OF_SCOPE",
        "annotation_type": "coarse_inception",
        "model": "inception:annotator1",
    }


def test_needs_llm_step_b_only_out_of_scope_without_step_b() -> None:
    assert needs_llm_step_b(_out_of_scope_silver()) is True
    with_frame = {
        **_out_of_scope_silver(),
        "step_b": {
            "selected_frame": "INGESTION",
            "lexical_unit": "at",
            "reasoning": "fine",
        },
    }
    assert needs_llm_step_b(with_frame) is False


def test_merge_llm_into_silver_overlays_step_b() -> None:
    silver = [_out_of_scope_silver()]
    llm = [
        {
            "provenance": silver[0]["provenance"],
            "step_b": {
                "selected_frame": "INGESTION",
                "lexical_unit": "at",
                "reasoning": "llm",
            },
            "dropped": False,
            "model": "qwen2.5-coder:latest",
        }
    ]
    merged = merge_llm_into_silver(silver, llm, llm_model="qwen2.5-coder:latest")
    assert len(merged) == 1
    assert merged[0]["step_b"]["selected_frame"] == "INGESTION"
    assert merged[0]["coarse_frame"] == "OUT_OF_SCOPE"
    assert merged[0]["llm_backfill"] is True
    assert "inception:annotator1+qwen2.5-coder:latest" == merged[0]["model"]


def test_select_records_needing_llm() -> None:
    second = _out_of_scope_silver()
    second["provenance"] = {**second["provenance"], "record_id": "r2"}
    rows = [_out_of_scope_silver(), second]
    assert len(select_records_needing_llm(rows)) == 2
