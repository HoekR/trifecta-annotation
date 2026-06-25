"""Few-shot prompt assets (JSON)."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_prompt_asset(name: str) -> dict[str, Any]:
    """Load a JSON prompt asset from trifecta_annotation.prompts."""
    with resources.files("trifecta_annotation.prompts").joinpath(name).open(
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


def format_few_shots(examples: list[dict[str, str]]) -> str:
    """Format few-shot examples for inclusion in a system prompt."""
    blocks: list[str] = []
    for index, example in enumerate(examples, start=1):
        blocks.append(
            f"Example {index}:\n"
            f"Target: {example['target_word']}\n"
            f"Context: {example['context_text']}\n"
            f"Output: {example['output']}"
        )
    return "\n\n".join(blocks)
