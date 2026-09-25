"""Tests for Step C few-shot assets across all macro-frames."""

from __future__ import annotations

import json
from trifecta_annotation.prompts import format_few_shots, load_prompt_asset
from trifecta_annotation.schemas import (
    CookingCreationQualia,
    CureQualia,
    IngestionQualia,
    PreservingQualia,
)


def test_cooking_fewshots_asset() -> None:
    doc = load_prompt_asset("step_c_cooking_fewshots.json")
    examples = doc["examples"]
    assert len(examples) == 11
    assert len(doc["record_ids"]) == 11
    block = format_few_shots(examples)
    assert "Example 1:" in block
    for example in examples:
        payload = json.loads(example["output"])
        parsed = CookingCreationQualia.model_validate(payload)
        assert parsed.frame.value == "COOKING_CREATION"
        assert example["target_word"]
        assert example["context_text"]


def test_preserving_fewshots_asset() -> None:
    doc = load_prompt_asset("step_c_preserving_fewshots.json")
    examples = doc["examples"]
    assert len(examples) >= 5
    assert len(doc["record_ids"]) >= 5
    block = format_few_shots(examples)
    assert "Example 1:" in block
    assert "PRESERVING" in block
    for example in examples:
        payload = json.loads(example["output"])
        parsed = PreservingQualia.model_validate(payload)
        assert parsed.frame.value == "PRESERVING"
        assert example["target_word"]
        assert example["context_text"]


def test_cure_fewshots_asset() -> None:
    doc = load_prompt_asset("step_c_cure_fewshots.json")
    examples = doc["examples"]
    assert len(examples) >= 5
    assert len(doc["record_ids"]) >= 5
    block = format_few_shots(examples)
    assert "Example 1:" in block
    assert "CURE" in block
    for example in examples:
        payload = json.loads(example["output"])
        parsed = CureQualia.model_validate(payload)
        assert parsed.frame.value == "CURE"
        assert example["target_word"]
        assert example["context_text"]


def test_ingestion_fewshots_asset() -> None:
    doc = load_prompt_asset("step_c_ingestion_fewshots.json")
    examples = doc["examples"]
    assert len(examples) >= 5
    assert len(doc["record_ids"]) >= 5
    block = format_few_shots(examples)
    assert "Example 1:" in block
    assert "INGESTION" in block
    for example in examples:
        payload = json.loads(example["output"])
        parsed = IngestionQualia.model_validate(payload)
        assert parsed.frame.value == "INGESTION"
        assert example["target_word"]
        assert example["context_text"]
        assert hasattr(parsed, "INGESTION_Food_Patient")
        assert hasattr(parsed, "INGESTION_Purpose")
