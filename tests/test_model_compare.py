"""Tests for multi-model comparison helpers."""

from __future__ import annotations

from pathlib import Path

from trifecta_annotation.model_compare import (
    compare_runs,
    predictions_path_for_model,
    render_comparison_markdown,
    safe_model_slug,
)


def test_safe_model_slug() -> None:
    assert safe_model_slug("qwen2.5-coder:latest") == "qwen2.5-coder_latest"
    assert safe_model_slug("llama3.1:8b") == "llama3.1_8b"


def test_predictions_path_for_model(tmp_path: Path) -> None:
    path = predictions_path_for_model(tmp_path, "qwen2.5-coder:latest", english_hint=True)
    assert path.name == "gold_predictions_qwen2.5-coder_latest_en_hint.jsonl"


def test_compare_runs_ranks_by_step_b() -> None:
    gold = [
        {
            "provenance": {"record_id": "1", "corpus": "t", "target_word": "zout", "context_text": "x"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "PRESERVING", "lexical_unit": "zout", "reasoning": ""},
        },
    ]
    good = [
        {
            "provenance": {"record_id": "1", "corpus": "t", "target_word": "zout", "context_text": "x"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "PRESERVING", "lexical_unit": "zout", "reasoning": ""},
        },
    ]
    bad = [
        {
            "provenance": {"record_id": "1", "corpus": "t", "target_word": "zout", "context_text": "x"},
            "dropped": False,
            "step_a": {"is_food_entity": True, "is_metaphor": False, "ontology_match": True, "reasoning": ""},
            "step_b": {"selected_frame": "INGESTION", "lexical_unit": "eten", "reasoning": ""},
        },
    ]
    report = compare_runs(gold, [("bad", bad), ("good", good)])
    assert report["ranked_by_step_b"] == ["good", "bad"]
    md = render_comparison_markdown({"slice": "full", "record_count": 1, "english_hint": False, **report})
    assert "good" in md
    assert "Step B acc" in md
