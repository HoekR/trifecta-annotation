"""Runtime configuration (Ollama / vLLM endpoints)."""

from __future__ import annotations

import os

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5-coder:latest"
DEFAULT_API_KEY = "ollama"


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")


def trifecta_model() -> str:
    return os.environ.get("TRIFECTA_MODEL", DEFAULT_MODEL)


def trifecta_api_key() -> str:
    """API key for OpenAI-compatible endpoints (OpenRouter, vLLM, remote Ollama)."""
    return (
        os.environ.get("TRIFECTA_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or DEFAULT_API_KEY
    )
