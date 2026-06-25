"""Batch runner for TRIFECTA annotation pipeline."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from data_io import load_jsonl, resolve, save_semi_structured

from trifecta_annotation.pipeline import annotate_record
from trifecta_annotation.schemas import KwicInput, TrifectaAnnotation


def _load_existing_ids(output_path: Path) -> set[str]:
    if not output_path.exists():
        return set()
    ids: set[str] = set()
    for record in load_jsonl(output_path):
        provenance = record.get("provenance") or {}
        record_id = provenance.get("record_id")
        if record_id:
            ids.add(str(record_id))
    return ids


def _annotate_one(
    record: dict[str, Any],
    *,
    model: str | None,
    base_url: str | None,
) -> dict[str, Any]:
    inp = KwicInput.model_validate(record)
    try:
        result = annotate_record(inp, model=model, base_url=base_url)
        return result.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 — per-record batch resilience
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


def run_batch(
    inputs: list[dict[str, Any]],
    *,
    output_logical: str = "trifecta_annotations",
    output_path: str | Path | None = None,
    model: str | None = None,
    base_url: str | None = None,
    resume: bool = False,
    concurrency: int = 1,
    parent_sources: list[str] | None = None,
    description: str = "TRIFECTA batch annotation run",
    script: str | None = None,
) -> Path:
    """Annotate a list of KwicInput dicts and write JSONL output."""
    if output_path is not None:
        path = Path(output_path).expanduser().resolve()
    else:
        path = resolve(output_logical)

    existing_ids = _load_existing_ids(path) if resume else set()
    pending = [
        record
        for record in inputs
        if str(record.get("record_id", "")) not in existing_ids
    ]

    results: list[dict[str, Any]] = []
    if concurrency <= 1:
        for record in pending:
            results.append(_annotate_one(record, model=model, base_url=base_url))
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(_annotate_one, record, model=model, base_url=base_url): record
                for record in pending
            }
            for future in as_completed(futures):
                results.append(future.result())

    if resume and path.exists():
        with path.open("a", encoding="utf-8") as handle:
            for record in results:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    save_semi_structured(
        results,
        logical_name=output_logical if output_path is None else None,
        out_path=path if output_path is not None else None,
        parent_sources=parent_sources,
        description=description,
        script=script,
    )
    return path


def load_inputs(
    *,
    input_logical: str | None = None,
    input_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    if input_logical:
        return load_jsonl(resolve(input_logical))
    if input_path is None:
        raise ValueError("Provide input_logical or input_path")
    return load_jsonl(Path(input_path))
