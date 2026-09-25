#!/usr/bin/env python3
"""Download HuggingFace pretrained models to scratch hub cache."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from trifecta_annotation.hf_cache import DEFAULT_FRAME_MODELS, configure_hf_hub_cache


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache HF models on scratch disk.")
    parser.add_argument(
        "models",
        nargs="*",
        default=list(DEFAULT_FRAME_MODELS),
        help="Model ids (default: TRIFECTA frame bases)",
    )
    parser.add_argument(
        "--with-classification-head",
        action="store_true",
        help="Also download sequence-classification heads (5 labels)",
    )
    args = parser.parse_args()

    cache = configure_hf_hub_cache()
    from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

    manifest_path = cache.parent / "hub_manifest.json"
    cached: dict[str, str] = {}

    for model_id in args.models:
        print(f"Downloading {model_id} -> {cache}")
        AutoTokenizer.from_pretrained(model_id, cache_dir=str(cache))
        AutoModel.from_pretrained(model_id, cache_dir=str(cache))
        if args.with_classification_head:
            AutoModelForSequenceClassification.from_pretrained(
                model_id,
                num_labels=5,
                cache_dir=str(cache),
            )
        cached[model_id] = str(cache)

    manifest = {
        "hub_cache": str(cache),
        "models": cached,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
