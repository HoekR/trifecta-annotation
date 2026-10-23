"""Merge LLM Step B labels into INCEpTION silver rows missing fine frames."""

from __future__ import annotations

from typing import Any

from trifecta_annotation.coarse_frames import CoarseFrame
from trifecta_annotation.schemas import KwicInput, TrifectaAnnotation


def record_id(record: dict[str, Any]) -> str:
    provenance = record.get("provenance") or {}
    return str(provenance.get("record_id") or record.get("record_id") or "")


def needs_llm_step_b(record: dict[str, Any]) -> bool:
    """True for coarse OUT_OF_SCOPE silver without a fine Step B label."""
    ann = TrifectaAnnotation.model_validate(record)
    if ann.error or ann.dropped or ann.step_b is not None:
        return False
    return ann.coarse_frame == CoarseFrame.OUT_OF_SCOPE.value


def annotation_to_kwic_input(record: dict[str, Any]) -> dict[str, Any]:
    ann = TrifectaAnnotation.model_validate(record)
    provenance = ann.provenance
    inp = KwicInput(
        record_id=str(provenance.record_id or ""),
        corpus=provenance.corpus,
        target_word=provenance.target_word,
        context_text=provenance.context_text,
        date=provenance.date,
        source_path=provenance.source_path,
        title=provenance.title,
        text_regime=provenance.text_regime,
        kwic_mode=provenance.kwic_mode,
        kwic_batch=provenance.kwic_batch,
        discovery_verb=provenance.discovery_verb,
        frame_hint=provenance.frame_hint,
    )
    return inp.model_dump(mode="json")


def select_records_needing_llm(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if needs_llm_step_b(record)]


def merge_llm_into_silver(
    silver_records: list[dict[str, Any]],
    llm_records: list[dict[str, Any]],
    *,
    llm_model: str | None = None,
) -> list[dict[str, Any]]:
    """Overlay LLM pipeline output onto INCEpTION rows (provenance + coarse kept)."""
    llm_by_id = {record_id(record): record for record in llm_records if record_id(record)}

    merged: list[dict[str, Any]] = []
    for silver in silver_records:
        rid = record_id(silver)
        llm = llm_by_id.get(rid)
        if llm is None or not needs_llm_step_b(silver):
            merged.append(silver)
            continue

        out = dict(silver)
        for field in ("step_b", "step_c", "dropped", "drop_reason", "error"):
            if field in llm:
                out[field] = llm[field]
        inception_model = silver.get("model")
        llm_tag = llm_model or llm.get("model") or "llm"
        out["model"] = f"{inception_model}+{llm_tag}" if inception_model else llm_tag
        out["llm_backfill"] = True
        merged.append(out)
    return merged
