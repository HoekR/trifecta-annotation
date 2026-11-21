"""Instructor client factory (Ollama local or OpenAI-compatible vLLM)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import instructor
from openai import OpenAI

from trifecta_annotation.config import ollama_base_url, trifecta_api_key

REQUEST_TIMEOUT_S = 120.0

if TYPE_CHECKING:
    from instructor import Instructor


def make_instructor_client(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = REQUEST_TIMEOUT_S,
    max_retries: int = 0,
) -> Instructor:
    """Return an instructor client pointed at Ollama or a vLLM OpenAI endpoint.

    The openai defaults (600 s per request, 2 transport retries) let one passage the model never finishes
    cost ~30 min; 18 such rows cost the routed run 6+ h (19-20 Nov 2026). A normal row takes ~5 s.
    """
    client = OpenAI(
        base_url=base_url or ollama_base_url(),
        api_key=api_key or trifecta_api_key(),
        timeout=timeout,
        max_retries=max_retries,
    )
    return instructor.from_openai(client, mode=instructor.Mode.JSON)
