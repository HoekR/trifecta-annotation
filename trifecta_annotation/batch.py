"""Batch runner for TRIFECTA annotation pipeline."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from data_io import load_jsonl, resolve

from trifecta_annotation.client import make_instructor_client
from trifecta_annotation.english_hint import (
    default_review_hint_lookup,
    review_hint_for_term,
)
from trifecta_annotation.pipeline import annotate_record, annotate_step_a
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


def _annotate_one(
    record: dict[str, Any],
    *,
    model: str | None,
    base_url: str | None,
    client=None,
    english_hint_lookup: dict[str, str] | None = None,
) -> dict[str, Any]:
    inp = KwicInput.model_validate(record)
    english_hint = None
    if english_hint_lookup is not None:
        english_hint = review_hint_for_term(inp.target_word, english_hint_lookup) or None
    try:
        result = annotate_record(
            inp,
            model=model,
            base_url=base_url,
            client=client,
            english_hint=english_hint,
        )
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


def _annotate_step_a_one(
    record: dict[str, Any],
    *,
    model: str | None,
    base_url: str | None,
    client=None,
    english_hint_lookup: dict[str, str] | None = None,
) -> dict[str, Any]:
    inp = KwicInput.model_validate(record)
    english_hint = None
    if english_hint_lookup is not None:
        english_hint = review_hint_for_term(inp.target_word, english_hint_lookup) or None
    try:
        result = annotate_step_a(
            inp,
            model=model,
            base_url=base_url,
            client=client,
            english_hint=english_hint,
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
                "title": inp.title,
                "kwic_batch": inp.kwic_batch,
            },
            dropped=True,
            drop_reason="error",
            error=str(exc),
            model=model,
        ).model_dump(mode="json")


def run_step_a_batch(
    inputs: list[dict[str, Any]],
    *,
    output_path: str | Path,
    model: str | None = None,
    base_url: str | None = None,
    resume: bool = False,
    concurrency: int = 1,
    english_hint: bool = False,
    api_key: str | None = None,
) -> Path:
    """Run Step A on KwicInput rows; append each result incrementally."""
    from tqdm import tqdm

    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    hint_lookup = default_review_hint_lookup() if english_hint else None
    instructor_client = make_instructor_client(base_url=base_url, api_key=api_key)

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
        for record in tqdm(pending, desc="Step A", unit="row"):
            _write(
                _annotate_step_a_one(
                    record,
                    model=model,
                    base_url=base_url,
                    client=instructor_client,
                    english_hint_lookup=hint_lookup,
                ),
            )
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(
                    _annotate_step_a_one,
                    record,
                    model=model,
                    base_url=base_url,
                    client=instructor_client,
                    english_hint_lookup=hint_lookup,
                )
                for record in pending
            ]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Step A", unit="row"):
                _write(future.result())

    return path


def _strip_retry_errors(path: Path, pending: list[dict[str, Any]]) -> None:
    """Drop prior error rows for record_ids we are about to retry."""
    if not path.exists() or not pending:
        return
    pending_ids = {str(record.get("record_id", "")) for record in pending}
    pending_ids.discard("")
    if not pending_ids:
        return
    kept: list[dict[str, Any]] = []
    for record in load_jsonl(path):
        if record.get("error"):
            provenance = record.get("provenance") or {}
            record_id = str(provenance.get("record_id") or "")
            if record_id in pending_ids:
                continue
        kept.append(record)
    with path.open("w", encoding="utf-8") as handle:
        for record in kept:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_batch_sidecar(
    path: Path,
    *,
    output_logical: str | None,
    parent_sources: list[str] | None,
    description: str,
    script: str | None,
    record_count: int,
) -> None:
    from data_io.manifest import get_manager
    from data_io.provenance import ProvenanceRecord, git_commit_hash, write_sidecar

    phase = "semi"
    logical_name = output_logical or path.stem
    resolved_parents = parent_sources
    resolved_description = description
    if output_logical:
        dataset = get_manager().dataset(output_logical)
        phase = dataset.phase or phase
        if not resolved_description:
            resolved_description = dataset.description
        if resolved_parents is None and dataset.parent:
            resolved_parents = [dataset.parent]
    write_sidecar(
        path,
        ProvenanceRecord(
            logical_name=logical_name,
            phase=phase,
            parent_sources=resolved_parents or [],
            description=resolved_description,
            created_by_script=script or "",
            record_count=record_count,
            git_commit=git_commit_hash(path.parent),
        ),
    )


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
    english_hint: bool = False,
    api_key: str | None = None,
) -> Path:
    """Annotate KwicInput rows; append each result incrementally with tqdm progress."""
    from tqdm import tqdm

    hint_lookup = default_review_hint_lookup() if english_hint else None
    instructor_client = make_instructor_client(base_url=base_url, api_key=api_key)
    if output_path is not None:
        path = Path(output_path).expanduser().resolve()
    else:
        path = resolve(output_logical)

    path.parent.mkdir(parents=True, exist_ok=True)
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
    if resume:
        _strip_retry_errors(path, pending)

    def _write(record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    if concurrency <= 1:
        for record in tqdm(pending, desc="TRIFECTA A→B→C", unit="row"):
            _write(
                _annotate_one(
                    record,
                    model=model,
                    base_url=base_url,
                    client=instructor_client,
                    english_hint_lookup=hint_lookup,
                ),
            )
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(
                    _annotate_one,
                    record,
                    model=model,
                    base_url=base_url,
                    client=instructor_client,
                    english_hint_lookup=hint_lookup,
                )
                for record in pending
            ]
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="TRIFECTA A→B→C",
                unit="row",
            ):
                _write(future.result())

    total_rows = sum(1 for line in path.open(encoding="utf-8") if line.strip())
    _write_batch_sidecar(
        path,
        output_logical=output_logical if output_path is None else None,
        parent_sources=parent_sources,
        description=description,
        script=script,
        record_count=total_rows,
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
