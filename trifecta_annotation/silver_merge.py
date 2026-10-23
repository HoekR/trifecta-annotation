"""Merge TRIFECTA silver JSONL sources for training export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from data_io import load_jsonl


def silver_record_id(record: dict[str, Any]) -> str:
    provenance = record.get("provenance") or {}
    return str(provenance.get("record_id") or record.get("record_id") or "")


def is_step_a_dropout(record: dict[str, Any]) -> bool:
    """True when Step A marks metaphor or non-food entity (NONE silver candidate)."""
    if record.get("dropped"):
        reason = record.get("drop_reason")
        return reason in {None, "metaphor", "not_food_entity"}
    step_a = record.get("step_a") or {}
    if not step_a:
        return False
    return bool(step_a.get("is_metaphor")) or not bool(step_a.get("is_food_entity", True))


def merge_silver_records(
    base_records: list[dict[str, Any]],
    append_records: list[dict[str, Any]],
    *,
    dropout_only: bool = False,
    append_limit: int | None = None,
) -> list[dict[str, Any]]:
    """Merge *append_records* into *base_records*, deduping by ``record_id``."""
    merged = list(base_records)
    seen = {silver_record_id(record) for record in merged if silver_record_id(record)}

    candidates = append_records
    if dropout_only:
        candidates = [record for record in candidates if is_step_a_dropout(record)]
    if append_limit is not None:
        candidates = candidates[:append_limit]

    added = 0
    for record in candidates:
        record_id = silver_record_id(record)
        if not record_id or record_id in seen:
            continue
        merged.append(record)
        seen.add(record_id)
        added += 1
    return merged


def load_and_merge_silver(
    base_path: str | Path,
    append_path: str | Path,
    *,
    dropout_only: bool = False,
    append_limit: int | None = None,
) -> list[dict[str, Any]]:
    return merge_silver_records(
        load_jsonl(base_path),
        load_jsonl(append_path),
        dropout_only=dropout_only,
        append_limit=append_limit,
    )
