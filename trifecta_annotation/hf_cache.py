"""HuggingFace hub cache on scratch tier (not ~/.cache)."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_SCRATCH_HF_HUB = Path("/Volumes/Extreme SSD/scratch/trifecta/models/hub")

# Pretrained bases used for TRIFECTA frame classification.
DEFAULT_FRAME_MODELS: tuple[str, ...] = (
    "emanjavacas/gysbert",
    "emanjavacas/GysBERT-v2",
    "dbmdz/bert-base-historic-dutch-cased",
)


def resolve_hf_hub_cache() -> Path:
    """Return HF hub cache directory, preferring scratch over ~/.cache."""
    for key in ("TRIFECTA_HF_HUB_CACHE", "HF_HOME", "HUGGINGFACE_HUB_CACHE"):
        raw = os.environ.get(key)
        if raw:
            path = Path(raw).expanduser().resolve()
            path.mkdir(parents=True, exist_ok=True)
            return path

    try:
        from data_io import resolve

        path = resolve("trifecta_hf_hub")
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        pass

    path = DEFAULT_SCRATCH_HF_HUB
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_hf_hub_cache() -> Path:
    """Set HF env vars so transformers/huggingface_hub use scratch.

    Also force a PyTorch-only transformers import path. A Keras 3 install
    otherwise pulls TF stubs and raises ``tf_keras`` / Keras 3 errors even
    when training is torch-only.
    """
    cache = resolve_hf_hub_cache()
    os.environ.setdefault("HF_HOME", str(cache))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache))
    # Must be set before ``import transformers``.
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
    os.environ.setdefault("USE_FLAX", "0")
    return cache
