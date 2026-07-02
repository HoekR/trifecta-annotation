"""Instructor client factory (Ollama local or OpenAI-compatible vLLM)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import instructor
from openai import OpenAI

from trifecta_annotation.config import ollama_base_url, trifecta_api_key

if TYPE_CHECKING:
    from instructor import Instructor


def make_instructor_client(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> Instructor:
    """Return an instructor client pointed at Ollama or a vLLM OpenAI endpoint."""
    client = OpenAI(
        base_url=base_url or ollama_base_url(),
        api_key=api_key or trifecta_api_key(),
    )
    return instructor.from_openai(client, mode=instructor.Mode.JSON)
