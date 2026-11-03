#!/usr/bin/env python3
"""Batch Step A (entity validation / dropout) on KwicInput JSONL."""

from __future__ import annotations

import argparse
from pathlib import Path

from data_io import load_jsonl

from trifecta_annotation.batch import load_inputs, run_step_a_batch
from trifecta_annotation.silver_merge import is_step_a_dropout


def _default_output_path() -> str:
    from data_io import resolve

    return str(Path(resolve("trifecta_gold")).parent / "reizen_step_a.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch Step A on KwicInput JSONL.")
    parser.add_argument("--input-logical", default="kwic_inputs")
    parser.add_argument("--input-path", default=None)
    parser.add_argument(
        "--output-path",
        default=None,
        help="Output JSONL (default: scratch/trifecta/reizen_step_a.jsonl)",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--english-hint", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true", help="Skip record_ids already in output")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Parallel LLM calls (2–4 speeds up Ollama if it keeps up; default 1)",
    )
    args = parser.parse_args()

    output_path = args.output_path or _default_output_path()

    inputs = load_inputs(
        input_logical=None if args.input_path else args.input_logical,
        input_path=args.input_path,
    )
    if args.limit is not None:
        inputs = inputs[: args.limit]

    path = run_step_a_batch(
        inputs,
        output_path=output_path,
        model=args.model,
        base_url=args.base_url,
        resume=args.resume,
        concurrency=args.concurrency,
        english_hint=args.english_hint,
    )

    records = load_jsonl(path)
    dropouts = sum(1 for record in records if is_step_a_dropout(record))
    print(f"Done: {path} ({len(records)} rows, {dropouts} Step A dropouts)")


if __name__ == "__main__":
    main()
