"""Flatten batch annotations to an analysis parquet table."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from data_io import load_jsonl, resolve, save_parquet

from trifecta_annotation.eval import STEP_C_FIELDS
from trifecta_annotation.schemas import TrifectaAnnotation

UNCERTAINTY_NOTE = (
    "LLM hypothesis — Step C qualia are unvalidated unless this row is hand gold. "
    "Do not treat aggregates as analytic claims without spot-checks."
)

PROVENANCE_COLUMNS = (
    "record_id",
    "corpus",
    "date",
    "text_regime",
    "target_word",
    "context_text",
    "source_path",
    "title",
    "kwic_batch",
    "discovery_verb",
)

STEP_C_ROLE_COLUMNS: tuple[str, ...] = tuple(
    name for fields in STEP_C_FIELDS.values() for name in fields
)


def _frame_value(frame: object) -> str:
    if frame is None:
        return ""
    return getattr(frame, "value", str(frame))


def annotation_to_analysis_row(record: dict[str, Any]) -> dict[str, Any]:
    """One flat analysis row from a TrifectaAnnotation JSON object."""
    ann = TrifectaAnnotation.model_validate(record)
    prov = ann.provenance
    row: dict[str, Any] = {
        "record_id": prov.record_id or "",
        "corpus": prov.corpus or "",
        "date": prov.date or "",
        "text_regime": _frame_value(prov.text_regime),
        "target_word": prov.target_word or "",
        "context_text": prov.context_text or "",
        "source_path": prov.source_path or "",
        "title": prov.title or "",
        "kwic_batch": prov.kwic_batch or "",
        "discovery_verb": prov.discovery_verb or "",
        "dropped": bool(ann.dropped),
        "drop_reason": ann.drop_reason or "",
        "error": ann.error or "",
        "model": ann.model or "",
        "annotation_type": ann.annotation_type or "",
        "is_food_entity": None,
        "is_metaphor": None,
        "selected_frame": "",
        "lexical_unit": "",
        "step_b_reasoning": "",
        "step_c_frame": "",
        "step_c_lexical_unit": "",
        "uncertainty_note": UNCERTAINTY_NOTE,
    }
    for name in STEP_C_ROLE_COLUMNS:
        row[name] = ""

    if ann.step_a is not None:
        row["is_food_entity"] = ann.step_a.is_food_entity
        row["is_metaphor"] = ann.step_a.is_metaphor
    if ann.step_b is not None:
        row["selected_frame"] = _frame_value(ann.step_b.selected_frame)
        row["lexical_unit"] = ann.step_b.lexical_unit or ""
        row["step_b_reasoning"] = ann.step_b.reasoning or ""
    if ann.step_c is not None:
        data = ann.step_c.model_dump(mode="json")
        row["step_c_frame"] = _frame_value(ann.step_c.frame)
        row["step_c_lexical_unit"] = str(data.get("lexical_unit") or "")
        for name in STEP_C_FIELDS.get(ann.step_c.frame, ()):
            row[name] = str(data.get(name) or "")
    return row


def annotations_to_analysis_frame(
    records: list[dict[str, Any]],
    *,
    require_step_c: bool = False,
    exclude_dropped: bool = False,
) -> pd.DataFrame:
    """Build an analysis DataFrame from annotation dicts."""
    rows: list[dict[str, Any]] = []
    for record in records:
        if exclude_dropped and bool(record.get("dropped")):
            continue
        if require_step_c and not record.get("step_c"):
            continue
        rows.append(annotation_to_analysis_row(record))
    columns = [
        *PROVENANCE_COLUMNS,
        "dropped",
        "drop_reason",
        "error",
        "model",
        "annotation_type",
        "is_food_entity",
        "is_metaphor",
        "selected_frame",
        "lexical_unit",
        "step_b_reasoning",
        "step_c_frame",
        "step_c_lexical_unit",
        *STEP_C_ROLE_COLUMNS,
        "uncertainty_note",
    ]
    return pd.DataFrame(rows, columns=columns)


def export_analysis_parquet(
    *,
    input_path: Path | None = None,
    input_logical: str | None = None,
    output_logical: str = "trifecta_analysis",
    output_path: Path | None = None,
    require_step_c: bool = False,
    exclude_dropped: bool = False,
    script: str | None = None,
) -> Path:
    """
    Load batch JSONL and write flat analysis parquet via ``data_io``.

    Defaults: ``trifecta_analysis`` logical dataset.
    """
    if input_path is not None:
        records = load_jsonl(Path(input_path))
    elif input_logical:
        records = load_jsonl(resolve(input_logical))
    else:
        raise ValueError("Provide input_path or input_logical")

    frame = annotations_to_analysis_frame(
        records,
        require_step_c=require_step_c,
        exclude_dropped=exclude_dropped,
    )
    return save_parquet(
        frame,
        logical_name=None if output_path else output_logical,
        out_path=output_path,
        phase="frozen",
        description=(
            "Flat A→B→C analysis table (LLM hypotheses; see uncertainty_note)"
        ),
        script=script,
        parent_sources=[str(input_path or input_logical or "")],
    )
