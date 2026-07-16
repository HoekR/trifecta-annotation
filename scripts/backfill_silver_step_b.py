#!/usr/bin/env python3
"""Run LLM Step B on coarse OUT_OF_SCOPE silver rows and merge into silver JSONL.

Example::

    uv run python scripts/backfill_silver_step_b.py --run-batch \\
      --silver-path "/Volumes/Extreme SSD/scratch/trifecta/inception_annotations.jsonl" \\
      --output-path "/Volumes/Extreme SSD/scratch/trifecta/inception_annotations_llm.jsonl"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from data_io import load_jsonl

from trifecta_annotation.batch import run_batch
from trifecta_annotation.config import trifecta_model
from trifecta_annotation.silver_llm_backfill import (
    annotation_to_kwic_input,
    merge_llm_into_silver,
    select_records_needing_llm,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LLM backfill for INCEpTION OUT_OF_SCOPE silver (no fine Step B).",
    )
    parser.add_argument("--silver-path", required=True, help="Input silver JSONL")
    parser.add_argument(
        "--output-path",
        required=True,
        help="Merged silver JSONL (inception + LLM step_b where missing)",
    )
    parser.add_argument(
        "--llm-predictions-path",
        default=None,
        help="Optional existing LLM JSONL; skip batch when set without --run-batch",
    )
    parser.add_argument("--run-batch", action="store_true", help="Call Ollama batch")
    parser.add_argument("--model", default=None, help="Ollama model tag (default: TRIFECTA_MODEL)")
    parser.add_argument("--resume", action="store_true", help="Resume partial LLM batch")
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args(argv)

    silver_path = Path(args.silver_path).expanduser().resolve()
    output_path = Path(args.output_path).expanduser().resolve()
    silver = load_jsonl(silver_path)
    pending = select_records_needing_llm(silver)
    print(f"Silver rows: {len(silver)}; OUT_OF_SCOPE needing LLM: {len(pending)}")

    model = args.model or trifecta_model()
    llm_path = (
        Path(args.llm_predictions_path).expanduser().resolve()
        if args.llm_predictions_path
        else output_path.with_suffix(".llm_backfill.jsonl")
    )

    if args.run_batch:
        inputs = [annotation_to_kwic_input(record) for record in pending]
        run_batch(
            inputs,
            output_path=llm_path,
            model=model,
            resume=args.resume,
            concurrency=args.concurrency,
            description=f"LLM Step B backfill for {len(inputs)} OUT_OF_SCOPE silver rows",
            script="scripts/backfill_silver_step_b.py",
        )
    elif not llm_path.exists():
        print(
            f"Missing {llm_path}; pass --run-batch or provide --llm-predictions-path",
            file=sys.stderr,
        )
        return 1

    llm_records = load_jsonl(llm_path)
    merged = merge_llm_into_silver(silver, llm_records, llm_model=model)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in merged:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    filled = sum(1 for record in merged if record.get("llm_backfill"))
    print(json.dumps({"output": str(output_path), "llm_predictions": str(llm_path), "filled": filled}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
