"""Tests for COOKING_CREATION Step C few-shot asset."""

from __future__ import annotations

import json

from trifecta_annotation.prompts import format_few_shots, load_prompt_asset


def test_cooking_fewshots_asset_loads() -> None:
    doc = load_prompt_asset("step_c_cooking_fewshots.json")
    examples = doc["examples"]
    assert len(examples) == 11
    assert len(doc["record_ids"]) == 11
    block = format_few_shots(examples)
    assert "Example 1:" in block
    assert "COOKING_CREATION" in block
    for example in examples:
        payload = json.loads(example["output"])
        assert payload["frame"] == "COOKING_CREATION"
        assert "COOKING_CREATION_Method" in payload
        assert example["target_word"]
        assert example["context_text"]
