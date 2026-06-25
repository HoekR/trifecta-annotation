"""Shared instructor structured-completion helper."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from trifecta_annotation.client import make_instructor_client
from trifecta_annotation.config import trifecta_model

if TYPE_CHECKING:
    from instructor import Instructor

T = TypeVar("T", bound=BaseModel)


def structured_completion(
    response_model: type[T],
    *,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    base_url: str | None = None,
    client: Instructor | None = None,
    temperature: float = 0.0,
) -> T:
    """Run one structured LLM call and return a validated Pydantic model."""
    instructor_client = client or make_instructor_client(base_url=base_url)
    return instructor_client.chat.completions.create(
        model=model or trifecta_model(),
        response_model=response_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
