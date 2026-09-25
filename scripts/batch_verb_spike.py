#!/usr/bin/env python3
"""Batch runner for verb-first POC spike.

Runs verb-KWIC inputs through the simplified A→B→C verb pipeline.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from data_io import load_jsonl
from tqdm import tqdm

from trifecta_annotation.client import make_instructor_client
from trifecta_annotation.pipeline_verb import annotate_record_verb_first
from trifecta_annotation.schemas import KwicInput, TrifectaAnnotation


def _load_existing_ids(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()
    ids: set[str] = set()
    for record in load_jsonl(output_path):
        if record.get("error"):
            continue
        provenance = record.get("provenance") or {}
        record_id = provenance.get("record_id")
        if record_id:
            ids.add(str(record_id))
    return ids


def _annotate_one_verb(
    record: dict[str, Any],
    *,
    model: str | None,
    base_url: str | None,
    client=None,
) -> dict[str, Any]:
    """Annotate one record using verb-first pipeline."""
    inp = KwicInput.model_validate(record)
    try:
        result = annotate_record_verb_first(
            inp,
            model=model,
            base_url=base_url,
            client=client,
        )
        return result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001
        return TrifectaAnnotation(
            provenance={
                "corpus": inp.corpus,
                "target_word": inp.target_word,
                "context_text": inp.context_text,
                "record_id": inp.record_id,
                "date": inp.date,
                "source_path": inp.source_path,
            },
            dropped=True,
            drop_reason="error",
            error=str(exc),
            model=model,
        ).model_dump(mode="json")


def run_verb_batch(
    inputs: list[dict[str, Any]],
    *,
    output_path: str | Path,
    model: str | None = None,
    base_url: str | None = None,
    resume: bool = False,
    concurrency: int = 1,
) -> Path:
    """Run verb-first pipeline on KWIC inputs; append results incrementally."""
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    instructor_client = make_instructor_client(base_url=base_url)

    existing_ids = _load_existing_ids(path) if resume else set()
    if not resume and path.exists():
        path.unlink()

    pending = [
        record
        for record in inputs
        if str(record.get("record_id", "")) not in existing_ids
    ]
    skipped = len(inputs) - len(pending)
    if skipped:
        print(f"Skipping {skipped} rows already in {path.name}")

    def _write(record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    if concurrency <= 1:
        for record in tqdm(pending, desc="Verb-KWIC batch", unit="row"):
            result = _annotate_one_verb(record, model=model, base_url=base_url)
            _write(result)
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(
                    _annotate_one_verb,
                    record,
                    model=model,
                    base_url=base_url,
                    client=instructor_client,
                ): record
                for record in pending
            }
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Verb-KWIC batch",
                unit="row",
            ):
                result = future.result()
                _write(result)

    return path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print(
            "Usage: python -m trifecta_annotation.batch_verb_spike "
            "<input_jsonl_path> <output_jsonl_path> [model] [base_url] [concurrency]"
        )
        sys.exit(2)

    input_path = Path(sys.argv[1]).expanduser()
    output_path = Path(sys.argv[2]).expanduser()
    model = sys.argv[3] if len(sys.argv) > 3 else None
    base_url = sys.argv[4] if len(sys.argv) > 4 else None
    concurrency = int(sys.argv[5]) if len(sys.argv) > 5 else 1

    if not input_path.exists():
        print(f"✗ Input file not found: {input_path}")
        sys.exit(1)

    inputs = list(load_jsonl(input_path))
    print(f"✓ Loaded {len(inputs)} inputs from {input_path}")

    result_path = run_verb_batch(
        inputs,
        output_path=output_path,
        model=model,
        base_url=base_url,
        concurrency=concurrency,
    )

    records = list(load_jsonl(result_path))
    ok = sum(1 for record in records if not record.get("error"))
    step_c = sum(1 for record in records if record.get("step_c"))
    frames = {}
    for rec in records:
        if rec.get("step_b") and rec["step_b"].get("selected_frame"):
            frame = rec["step_b"]["selected_frame"]
            frames[frame] = frames.get(frame, 0) + 1

    print(f"\n✓ Done: {result_path}")
    print(f"  Total rows: {len(records)}")
    print(f"  Passed (no error): {ok}")
    print(f"  With Step C: {step_c}")
    print(f"  Frame breakdown: {frames}")
