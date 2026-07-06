"""CSV import/export for TRIFECTA gold annotation curation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from data_io import load_jsonl, load_parquet, resolve, save_jsonl, save_parquet

from trifecta_annotation.schemas import (
    AnnotationProvenance,
    CookingCreationQualia,
    EntityValidation,
    FormalDimension,
    FrameClassification,
    FrameQualia,
    GoldAnnotation,
    KwicInput,
    PreservingQualia,
    TrifectaAnnotation,
    TrifectaFrame,
    UsingCureQualia,
    UsingIngestionQualia,
)
from trifecta_annotation.thesaurus import canonical_pref_for_term
from trifecta_annotation.text_regime import TextRegime, infer_text_regime

GOLD_CSV_COLUMNS = [
    "record_id",
    "corpus",
    "text_regime",
    "target_word",
    "context_text",
    "date",
    "source_path",
    "dropped",
    "drop_reason",
    "is_food_entity",
    "is_metaphor",
    "formal_dimension",
    "canonical_pref_label",
    "ontology_match",
    "step_a_reasoning",
    "selected_frame",
    "lexical_unit",
    "step_b_reasoning",
    "COOKING_CREATION_Method",
    "COOKING_CREATION_Process",
    "COOKING_CREATION_Food_Product",
    "CURE_Affliction",
    "CURE_Food_Treatment",
    "INGESTION_Context",
    "INGESTION_Ingestor",
    "INGESTION_Manner",
    "PR_Technique",
    "PR_Medium",
    "PR_Food_Patient",
    "labelled",
    "notes",
]

STEP_C_COLUMNS = [
    "COOKING_CREATION_Method",
    "COOKING_CREATION_Process",
    "COOKING_CREATION_Food_Product",
    "CURE_Affliction",
    "CURE_Food_Treatment",
    "INGESTION_Context",
    "INGESTION_Ingestor",
    "INGESTION_Manner",
    "PR_Technique",
    "PR_Medium",
    "PR_Food_Patient",
]

GOLD_FIX_VERDICTS = frozenset({"keep_gold", "adopt_pred", "custom"})

GOLD_FIX_VERDICT_ALIASES = {
    "adopt_gold": "keep_gold",
    "keep": "keep_gold",
    "gold": "keep_gold",
    "k": "keep_gold",
    "adopt": "adopt_pred",
    "pred": "adopt_pred",
    "a": "adopt_pred",
    "adopt_prediction": "adopt_pred",
    "w": "custom",
    "wijzig": "custom",
    "wijzigen": "custom",
}


def normalize_gold_fix_verdict(verdict: object) -> str:
    """Normalize reviewer verdict strings (typos, spacing, aliases, shorthand)."""
    raw = _excel_cell(verdict).lower().replace(" ", "_").replace("-", "_")
    if not raw:
        return ""
    if raw in GOLD_FIX_VERDICT_ALIASES:
        return GOLD_FIX_VERDICT_ALIASES[raw]
    if raw.startswith("keep"):
        return "keep_gold"
    if raw.startswith("adopt") or raw.startswith("pred"):
        return "adopt_pred"
    if raw.startswith("wij") or raw.startswith("custom"):
        return "custom"
    return raw

GOLD_FIX_OVERRIDE_COLUMNS = [
    "selected_frame",
    "dropped",
    "drop_reason",
    "is_food_entity",
    "is_metaphor",
    "formal_dimension",
    "canonical_pref_label",
    "ontology_match",
    "step_a_reasoning",
    "lexical_unit",
    "step_b_reasoning",
    "notes",
    *STEP_C_COLUMNS,
]

GOLD_FIXES_SHEET_COLUMNS = [
    "record_id",
    "target_word",
    "issue",
    "context_snippet",
    "gold_frame",
    "pred_frame",
    "gold_dropped",
    "pred_dropped",
    "verdict",
    "review_notes",
    "reviewed_at",
    "export_updated_at",
    *GOLD_FIX_OVERRIDE_COLUMNS,
]

# Legacy CSV column names still accepted on import.
_CSV_LEGACY_ALIASES = {
    "preparation_method": "COOKING_CREATION_Method",
    "heat_or_mechanical_process": "COOKING_CREATION_Process",
    "result_state": "COOKING_CREATION_Food_Product",
    "cure_affliction": "CURE_Affliction",
    "cure_food_treatment": "CURE_Food_Treatment",
    "consumption_context": "INGESTION_Context",
    "consumer": "INGESTION_Ingestor",
    "manner": "INGESTION_Manner",
    "preservation_technique": "PR_Technique",
    "preserving_agent": "PR_Medium",
    "target_food": "PR_Food_Patient",
}

BOOL_COLUMNS = {"dropped", "is_food_entity", "is_metaphor", "ontology_match", "labelled"}


def _parse_bool(value: object) -> bool | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"", "nan", "none"}:
        return None
    if text in {"true", "1", "yes", "y", "ja"}:
        return True
    if text in {"false", "0", "no", "n", "nee"}:
        return False
    raise ValueError(f"Cannot parse boolean value: {value!r}")


def _parse_text_regime(value: object) -> TextRegime | None:
    if _empty(value):
        return None
    try:
        return TextRegime(str(value).strip())
    except ValueError:
        return None


def _empty(value: object) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == ""


def _parse_formal_dimension(value: object) -> FormalDimension | None:
    if _empty(value):
        return None
    text = str(value).strip()
    for item in FormalDimension:
        if text == item.value or text == item.name:
            return item
    return FormalDimension(text)


def _parse_frame(value: object) -> TrifectaFrame | None:
    if _empty(value):
        return None
    text = str(value).strip()
    legacy = {"USING_CURE": "CURE", "USING_INGESTION": "INGESTION"}
    text = legacy.get(text, text)
    for item in TrifectaFrame:
        if text == item.value or text == item.name:
            return item
    return TrifectaFrame(text)


def _normalize_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for legacy, canonical in _CSV_LEGACY_ALIASES.items():
        if legacy in out and _empty(out.get(canonical)) and not _empty(out.get(legacy)):
            out[canonical] = out[legacy]
    if not _empty(out.get("selected_frame")):
        out["selected_frame"] = _parse_frame(out["selected_frame"])
        if out["selected_frame"] is not None:
            out["selected_frame"] = out["selected_frame"].value
    return out


def _step_c_from_row(row: dict[str, Any], frame: TrifectaFrame) -> FrameQualia | None:
    lu = str(row.get("lexical_unit") or "")
    if frame == TrifectaFrame.COOKING_CREATION:
        if all(_empty(row.get(c)) for c in STEP_C_COLUMNS[:3]):
            return None
        return CookingCreationQualia(
            COOKING_CREATION_Method=str(row.get("COOKING_CREATION_Method") or ""),
            COOKING_CREATION_Process=str(row.get("COOKING_CREATION_Process") or ""),
            COOKING_CREATION_Food_Product=str(row.get("COOKING_CREATION_Food_Product") or ""),
            lexical_unit=lu,
        )
    if frame == TrifectaFrame.CURE:
        if all(_empty(row.get(c)) for c in STEP_C_COLUMNS[3:5]):
            return None
        return UsingCureQualia(
            CURE_Affliction=str(row.get("CURE_Affliction") or ""),
            CURE_Food_Treatment=str(row.get("CURE_Food_Treatment") or ""),
            lexical_unit=lu,
        )
    if frame == TrifectaFrame.INGESTION:
        if all(_empty(row.get(c)) for c in STEP_C_COLUMNS[5:8]):
            return None
        return UsingIngestionQualia(
            INGESTION_Context=str(row.get("INGESTION_Context") or ""),
            INGESTION_Ingestor=str(row.get("INGESTION_Ingestor") or ""),
            INGESTION_Manner=str(row.get("INGESTION_Manner") or ""),
            lexical_unit=lu,
        )
    if frame == TrifectaFrame.PRESERVING:
        if all(_empty(row.get(c)) for c in STEP_C_COLUMNS[8:]):
            return None
        return PreservingQualia(
            PR_Technique=str(row.get("PR_Technique") or ""),
            PR_Medium=str(row.get("PR_Medium") or ""),
            PR_Food_Patient=str(row.get("PR_Food_Patient") or ""),
            lexical_unit=lu,
        )
    return None


def _step_c_to_row(step_c: dict[str, Any] | None) -> dict[str, str]:
    empty = {col: "" for col in STEP_C_COLUMNS}
    if not step_c:
        return empty
    frame = step_c.get("frame")
    if frame == TrifectaFrame.COOKING_CREATION.value:
        empty["COOKING_CREATION_Method"] = str(step_c.get("COOKING_CREATION_Method", ""))
        empty["COOKING_CREATION_Process"] = str(step_c.get("COOKING_CREATION_Process", ""))
        empty["COOKING_CREATION_Food_Product"] = str(step_c.get("COOKING_CREATION_Food_Product", ""))
    elif frame in {TrifectaFrame.CURE.value, "USING_CURE"}:
        empty["CURE_Affliction"] = str(step_c.get("CURE_Affliction", step_c.get("cure_affliction", "")))
        empty["CURE_Food_Treatment"] = str(
            step_c.get("CURE_Food_Treatment", step_c.get("cure_food_treatment", "")),
        )
    elif frame in {TrifectaFrame.INGESTION.value, "USING_INGESTION"}:
        empty["INGESTION_Context"] = str(step_c.get("INGESTION_Context", step_c.get("consumption_context", "")))
        empty["INGESTION_Ingestor"] = str(step_c.get("INGESTION_Ingestor", step_c.get("consumer", "")))
        empty["INGESTION_Manner"] = str(step_c.get("INGESTION_Manner", step_c.get("manner", "")))
    elif frame == TrifectaFrame.PRESERVING.value:
        empty["PR_Technique"] = str(step_c.get("PR_Technique", step_c.get("preservation_technique", "")))
        empty["PR_Medium"] = str(step_c.get("PR_Medium", step_c.get("preserving_agent", "")))
        empty["PR_Food_Patient"] = str(step_c.get("PR_Food_Patient", step_c.get("target_food", "")))
    return empty


def annotation_to_row(annotation: GoldAnnotation | dict[str, Any]) -> dict[str, Any]:
    """Flatten a gold annotation to a CSV row."""
    if isinstance(annotation, GoldAnnotation):
        data = annotation.model_dump(mode="json")
    else:
        data = annotation

    provenance = data.get("provenance") or {}
    step_a = data.get("step_a") or {}
    step_b = data.get("step_b") or {}
    step_c = data.get("step_c") or {}

    row = {
        "record_id": provenance.get("record_id", ""),
        "corpus": provenance.get("corpus", ""),
        "text_regime": provenance.get("text_regime", "") or "",
        "target_word": provenance.get("target_word", ""),
        "context_text": provenance.get("context_text", ""),
        "date": provenance.get("date", ""),
        "source_path": provenance.get("source_path", ""),
        "dropped": data.get("dropped", False),
        "drop_reason": data.get("drop_reason", ""),
        "is_food_entity": step_a.get("is_food_entity", ""),
        "is_metaphor": step_a.get("is_metaphor", ""),
        "formal_dimension": step_a.get("formal_dimension", ""),
        "canonical_pref_label": step_a.get("canonical_pref_label", ""),
        "ontology_match": step_a.get("ontology_match", ""),
        "step_a_reasoning": step_a.get("reasoning", ""),
        "selected_frame": (step_b.get("selected_frame") if step_b else ""),
        "lexical_unit": step_b.get("lexical_unit", "") if step_b else "",
        "step_b_reasoning": step_b.get("reasoning", "") if step_b else "",
        "labelled": bool(step_a) or bool(data.get("dropped")),
        "notes": data.get("notes", ""),
    }
    row.update(_step_c_to_row(step_c))
    return row


def _resolve_step_a_bools(row: dict[str, Any]) -> tuple[bool, bool]:
    """Parse Step A booleans; infer ``is_food_entity`` from ontology fields when blank."""
    entity = _parse_bool(row.get("is_food_entity"))
    metaphor = _parse_bool(row.get("is_metaphor"))
    if metaphor is None:
        metaphor = False
    if entity is None:
        if not _empty(row.get("formal_dimension")) or not _empty(row.get("canonical_pref_label")):
            entity = True
        elif _parse_bool(row.get("ontology_match")) is True:
            entity = True
        else:
            entity = False
    return entity, metaphor


def _has_step_a_context(row: dict[str, Any]) -> bool:
    return any(
        not _empty(row.get(key))
        for key in (
            "is_food_entity",
            "is_metaphor",
            "formal_dimension",
            "canonical_pref_label",
            "step_a_reasoning",
            "ontology_match",
        )
    )


def row_to_annotation(row: dict[str, Any]) -> GoldAnnotation | None:
    row = _normalize_csv_row(row)
    """Convert a labelled CSV row to GoldAnnotation; skip unlabelled rows."""
    labelled = _parse_bool(row.get("labelled"))
    if labelled is False:
        return None

    entity = _parse_bool(row.get("is_food_entity"))
    metaphor = _parse_bool(row.get("is_metaphor"))
    has_any_step_a = entity is not None or metaphor is not None
    has_step_a_context = _has_step_a_context(row)
    dropped = _parse_bool(row.get("dropped")) or False
    if labelled is None and not has_step_a_context and not dropped:
        return None

    provenance = AnnotationProvenance(
        record_id=str(row["record_id"]),
        corpus=str(row.get("corpus") or ""),
        target_word=str(row.get("target_word") or ""),
        context_text=str(row.get("context_text") or ""),
        date=None if _empty(row.get("date")) else str(row.get("date")),
        source_path=None if _empty(row.get("source_path")) else str(row.get("source_path")),
        text_regime=_parse_text_regime(row.get("text_regime")),
        title=None,
    )

    step_a: EntityValidation | None = None
    drop_reason: str | None = None
    if has_any_step_a and entity is not None and metaphor is not None:
        step_a = EntityValidation(
            is_food_entity=entity,
            is_metaphor=metaphor,
            formal_dimension=_parse_formal_dimension(row.get("formal_dimension")),
            canonical_pref_label=None
            if _empty(row.get("canonical_pref_label"))
            else str(row.get("canonical_pref_label")),
            ontology_match=bool(_parse_bool(row.get("ontology_match")) or False),
            reasoning=str(row.get("step_a_reasoning") or ""),
        )
        if dropped is False:
            dropped, drop_reason = _drop_from_step_a(step_a)
        else:
            drop_reason = None if _empty(row.get("drop_reason")) else str(row.get("drop_reason"))
    elif has_any_step_a and dropped:
        drop_reason = None if _empty(row.get("drop_reason")) else str(row.get("drop_reason"))
    elif has_step_a_context:
        entity, metaphor = _resolve_step_a_bools(row)
        step_a = EntityValidation(
            is_food_entity=entity,
            is_metaphor=metaphor,
            formal_dimension=_parse_formal_dimension(row.get("formal_dimension")),
            canonical_pref_label=None
            if _empty(row.get("canonical_pref_label"))
            else str(row.get("canonical_pref_label")),
            ontology_match=bool(_parse_bool(row.get("ontology_match")) or False),
            reasoning=str(row.get("step_a_reasoning") or ""),
        )
        if dropped is False:
            dropped, drop_reason = _drop_from_step_a(step_a)
        else:
            drop_reason = None if _empty(row.get("drop_reason")) else str(row.get("drop_reason"))
    else:
        drop_reason = None if _empty(row.get("drop_reason")) else str(row.get("drop_reason"))

    step_b: FrameClassification | None = None
    step_c: FrameQualia | None = None
    frame = _parse_frame(row.get("selected_frame"))
    if frame is not None and not dropped:
        step_b = FrameClassification(
            selected_frame=frame,
            lexical_unit=str(row.get("lexical_unit") or ""),
            reasoning=str(row.get("step_b_reasoning") or ""),
        )
        step_c = _step_c_from_row(row, frame)

    return GoldAnnotation(
        provenance=provenance,
        step_a=step_a,
        step_b=step_b,
        step_c=step_c,
        dropped=dropped,
        drop_reason=drop_reason,
        gold=True,
    )


def _drop_from_step_a(step_a: EntityValidation) -> tuple[bool, str | None]:
    if step_a.is_metaphor:
        return True, "metaphor"
    if not step_a.is_food_entity:
        return True, "not_food_entity"
    return False, None


def annotation_to_labelling_row(
    annotation: TrifectaAnnotation | GoldAnnotation,
    *,
    notes: str = "",
    labelled: bool = True,
) -> dict[str, Any]:
    """Flatten a pipeline or gold annotation into a gold_labelling CSV row."""
    if isinstance(annotation, TrifectaAnnotation):
        gold = GoldAnnotation.model_validate(
            {**annotation.model_dump(mode="json"), "gold": True},
        )
    else:
        gold = annotation
    row = annotation_to_row(gold)
    row["labelled"] = labelled
    if notes:
        existing = str(row.get("notes") or "").strip()
        row["notes"] = f"{existing}; {notes}".strip("; ").strip()
    return row


def bootstrap_gold_rows_from_annotations(
    annotations: list[TrifectaAnnotation],
    *,
    notes: str = "llm_bootstrap",
) -> list[dict[str, Any]]:
    """Convert pipeline outputs into importable gold CSV rows."""
    return [
        annotation_to_labelling_row(ann, notes=notes, labelled=True)
        for ann in annotations
    ]


def merge_labelling_rows(
    existing: pd.DataFrame,
    updates: list[dict[str, Any]],
    *,
    overwrite_labelled: bool = False,
) -> pd.DataFrame:
    """Merge bootstrap or hand labels into a candidate CSV by record_id."""
    update_index = {str(row["record_id"]): row for row in updates}
    rows: list[dict[str, Any]] = []
    for record in existing.to_dict(orient="records"):
        record_id = str(record.get("record_id", ""))
        if record_id in update_index:
            incoming = update_index[record_id]
            labelled = _parse_bool(record.get("labelled"))
            if labelled and not overwrite_labelled:
                rows.append(record)
            else:
                merged = {**record, **incoming}
                rows.append(merged)
        else:
            rows.append(record)
    seen = {str(row.get("record_id", "")) for row in rows}
    for record_id, incoming in update_index.items():
        if record_id not in seen:
            rows.append({col: incoming.get(col, "") for col in GOLD_CSV_COLUMNS})
    return pd.DataFrame(rows, columns=GOLD_CSV_COLUMNS)


def _excel_cell(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _append_review_note(existing: object, review_notes: object) -> str:
    note = _excel_cell(review_notes)
    if not note:
        return _excel_cell(existing)
    base = _excel_cell(existing)
    tagged = f"review: {note}"
    return f"{base}; {tagged}".strip("; ").strip() if base else tagged


def prediction_to_labelling_row(
    prediction: dict[str, Any],
    *,
    review_notes: str = "",
) -> dict[str, Any]:
    """Convert a pipeline prediction dict into an importable gold CSV row."""
    row = annotation_to_labelling_row(
        TrifectaAnnotation.model_validate(prediction),
        labelled=True,
    )
    if review_notes:
        row["notes"] = _append_review_note(row.get("notes"), review_notes)
    return row


def build_gold_fixes_rows(disagreement_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Deduplicate disagreement rows into a ``gold_fixes`` review sheet."""
    by_id: dict[str, dict[str, object]] = {}
    for row in disagreement_rows:
        record_id = _excel_cell(row.get("record_id"))
        if not record_id:
            continue
        issue = _excel_cell(row.get("issue"))
        if record_id in by_id:
            prior = _excel_cell(by_id[record_id].get("issue"))
            if issue and issue not in prior:
                by_id[record_id]["issue"] = f"{prior}; {issue}".strip("; ")
            continue
        by_id[record_id] = {
            "record_id": record_id,
            "target_word": row.get("target_word", ""),
            "issue": issue,
            "context_snippet": row.get("context_snippet", ""),
            "gold_frame": row.get("gold_frame", ""),
            "pred_frame": row.get("pred_frame", ""),
            "gold_dropped": row.get("gold_dropped", ""),
            "pred_dropped": row.get("pred_dropped", ""),
            "verdict": "",
            "review_notes": "",
            "reviewed_at": "",
            "export_updated_at": "",
            **{col: "" for col in GOLD_FIX_OVERRIDE_COLUMNS},
        }
    return [by_id[record_id] for record_id in sorted(by_id)]


def carry_forward_gold_fixes(
    fresh: list[dict[str, object]],
    existing: pd.DataFrame,
) -> list[dict[str, object]]:
    """Keep reviewer edits when re-exporting disagreements."""
    if existing.empty or "record_id" not in existing.columns:
        return fresh
    saved = {
        _excel_cell(row["record_id"]): row
        for row in existing.to_dict(orient="records")
        if _excel_cell(row.get("record_id"))
    }
    merged: list[dict[str, object]] = []
    for row in fresh:
        out = dict(row)
        prior = saved.get(_excel_cell(row.get("record_id")))
        if prior is None:
            merged.append(out)
            continue
        for col in (
            "verdict",
            "review_notes",
            "reviewed_at",
            "export_updated_at",
            *GOLD_FIX_OVERRIDE_COLUMNS,
        ):
            val = _excel_cell(prior.get(col))
            if val:
                out[col] = prior[col] if col in ("gold_dropped", "pred_dropped") else val
        merged.append(out)
    return merged


def apply_gold_fix_row(
    gold_row: dict[str, Any],
    fix_row: dict[str, Any],
    *,
    prediction: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Apply one ``gold_fixes`` row onto a gold labelling row.

    Returns ``None`` when the fix row has no verdict (skip).
    """
    verdict = normalize_gold_fix_verdict(fix_row.get("verdict"))
    if not verdict:
        return None
    if verdict not in GOLD_FIX_VERDICTS:
        raise ValueError(
            f"Row {fix_row.get('record_id')}: verdict must be one of {sorted(GOLD_FIX_VERDICTS)} "
            f"(got {fix_row.get('verdict')!r})",
        )

    if verdict == "keep_gold":
        out = dict(gold_row)
        out["notes"] = _append_review_note(out.get("notes"), fix_row.get("review_notes"))
        return out

    if verdict == "adopt_pred":
        if prediction is None:
            raise ValueError(f"Row {fix_row.get('record_id')}: adopt_pred requires predictions")
        out = prediction_to_labelling_row(
            prediction,
            review_notes=_excel_cell(fix_row.get("review_notes")),
        )
        for col in ("record_id", "corpus", "target_word", "context_text", "date", "source_path"):
            if _excel_cell(gold_row.get(col)):
                out[col] = gold_row[col]
        return out

    out = dict(gold_row)
    for col in GOLD_FIX_OVERRIDE_COLUMNS:
        val = fix_row.get(col)
        if not _empty(val):
            out[col] = val
    out["labelled"] = True
    out["notes"] = _append_review_note(out.get("notes"), fix_row.get("review_notes"))
    return out


def apply_gold_fixes_dataframe(
    gold_frame: pd.DataFrame,
    fixes_frame: pd.DataFrame,
    *,
    predictions: list[dict[str, Any]] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Merge ``gold_fixes`` sheet rows into a gold labelling CSV frame."""
    pred_index = {
        str((row.get("provenance") or {}).get("record_id")): row
        for row in (predictions or [])
        if (row.get("provenance") or {}).get("record_id")
    }
    gold_index = {
        str(row.get("record_id", "")): row
        for row in gold_frame.to_dict(orient="records")
    }
    updates: list[dict[str, Any]] = []
    applied: list[str] = []
    for fix_row in fixes_frame.to_dict(orient="records"):
        record_id = _excel_cell(fix_row.get("record_id"))
        if not record_id:
            continue
        if record_id not in gold_index:
            raise ValueError(f"gold_fixes row not in gold CSV: {record_id}")
        updated = apply_gold_fix_row(
            gold_index[record_id],
            fix_row,
            prediction=pred_index.get(record_id),
        )
        if updated is None:
            continue
        updates.append(updated)
        applied.append(record_id)
    if not updates:
        return gold_frame, applied
    merged = merge_labelling_rows(gold_frame, updates, overwrite_labelled=True)
    return merged, applied


def load_gold_fixes_frame(path: str | Path, *, sheet_name: str = "gold_fixes") -> pd.DataFrame:
    """Load a ``gold_fixes`` table from CSV (preferred) or Excel."""
    resolved = Path(path).expanduser().resolve()
    if resolved.suffix.lower() == ".csv":
        return pd.read_csv(resolved, dtype=str, keep_default_na=False)
    return load_gold_fixes_sheet(resolved, sheet_name=sheet_name)


def load_gold_fixes_sheet(path: str | Path, *, sheet_name: str = "gold_fixes") -> pd.DataFrame:
    frame = pd.read_excel(path, sheet_name=sheet_name, dtype=str)
    frame = frame.fillna("")
    return frame


def merge_gold_csv_with_fixes(
    *,
    gold_csv_path: str | Path,
    fixes_path: str | Path,
    predictions_path: str | Path | None = None,
    output_csv_path: str | Path | None = None,
    sheet_name: str = "gold_fixes",
) -> tuple[pd.DataFrame, list[str], Path]:
    """Apply reviewed ``gold_fixes`` CSV or Excel sheet and write an updated gold CSV."""
    gold_path = Path(gold_csv_path).expanduser().resolve()
    fixes_file = Path(fixes_path).expanduser().resolve()
    out_path = Path(output_csv_path).expanduser().resolve() if output_csv_path else gold_path

    gold_frame = pd.read_csv(gold_path, dtype=str, keep_default_na=False)
    fixes_frame = load_gold_fixes_frame(fixes_file, sheet_name=sheet_name)
    predictions = None
    if predictions_path is not None:
        predictions = load_jsonl(Path(predictions_path).expanduser().resolve())

    merged, applied = apply_gold_fixes_dataframe(
        gold_frame,
        fixes_frame,
        predictions=predictions,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.reindex(columns=GOLD_CSV_COLUMNS, fill_value="").to_csv(out_path, index=False)
    return merged, applied, out_path


def merge_gold_csv_with_fixes_xlsx(
    *,
    gold_csv_path: str | Path,
    fixes_xlsx_path: str | Path,
    predictions_path: str | Path | None = None,
    output_csv_path: str | Path | None = None,
    sheet_name: str = "gold_fixes",
) -> tuple[pd.DataFrame, list[str], Path]:
    """Backward-compatible alias for Excel fixes workbooks."""
    return merge_gold_csv_with_fixes(
        gold_csv_path=gold_csv_path,
        fixes_path=fixes_xlsx_path,
        predictions_path=predictions_path,
        output_csv_path=output_csv_path,
        sheet_name=sheet_name,
    )


def kwic_input_to_candidate_row(
    inp: KwicInput,
    *,
    thesaurus_lookup: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build an empty labelling row from a KwicInput."""
    notes = ""
    if inp.discovery_verb:
        notes = f"discovery_verb={inp.discovery_verb}"
        if inp.frame_hint:
            notes += f"; frame_hint={inp.frame_hint}"
        notes += f"; kwic_mode={inp.kwic_mode}"
    if inp.candidate_terms and len(inp.candidate_terms) > 1:
        extra = f"candidate_terms: {', '.join(inp.candidate_terms)}"
        notes = f"{notes}. {extra}".strip(". ")
    if inp.title:
        notes = f"{inp.title}. {notes}".strip()

    canonical = canonical_pref_for_term(inp.target_word, thesaurus_lookup or {})
    return {
        "record_id": inp.record_id,
        "corpus": inp.corpus,
        "text_regime": (inp.text_regime.value if inp.text_regime else infer_text_regime(
            corpus=inp.corpus,
            title=inp.title,
            source_path=inp.source_path,
        ).value),
        "target_word": inp.target_word,
        "context_text": inp.context_text,
        "date": inp.date or "",
        "source_path": inp.source_path or "",
        "dropped": "",
        "drop_reason": "",
        "is_food_entity": "",
        "is_metaphor": "",
        "formal_dimension": "",
        "canonical_pref_label": canonical or "",
        "ontology_match": "true" if canonical else "",
        "step_a_reasoning": "",
        "selected_frame": "",
        "lexical_unit": "",
        "step_b_reasoning": "",
        **{col: "" for col in STEP_C_COLUMNS},
        "labelled": False,
        "notes": notes,
    }


def load_kwic_input_candidates(
    *,
    limit: int | None = None,
    input_logical: str = "kwic_inputs",
    input_path: str | Path | None = None,
) -> list[KwicInput]:
    if input_path is not None:
        records = load_jsonl(Path(input_path))
    else:
        records = load_jsonl(resolve(input_logical))
    inputs = [KwicInput.model_validate(record) for record in records]
    if limit is not None:
        return inputs[:limit]
    return inputs


def export_candidates_csv(
    *,
    limit: int | None = 50,
    output_logical: str = "trifecta_gold_csv",
    output_path: str | Path | None = None,
    input_logical: str = "kwic_inputs",
    input_path: str | Path | None = None,
    source: str = "diverse",
    seed: int = 0,
    include_manual: bool = True,
    verb_share: float = 0.0,
    thesaurus_filter: bool = True,
    thesaurus_path: str | Path | None = None,
) -> Path:
    """Export blank labelling rows for gold annotation."""
    from trifecta_annotation.vocabulary import resolve_thesaurus_lookup

    lookup = (
        resolve_thesaurus_lookup(thesaurus_path=thesaurus_path)
        if thesaurus_filter
        else {}
    )
    to_row = lambda inp: kwic_input_to_candidate_row(inp, thesaurus_lookup=lookup or None)

    if source in {"diverse", "mixed"}:
        from trifecta_annotation.sampling import sample_kwic_inputs_for_gold

        share = 0.5 if source == "mixed" else verb_share
        records = sample_kwic_inputs_for_gold(
            limit=limit or 50,
            seed=seed,
            include_manual=include_manual,
            verb_share=share,
            snippet_format="long",
            logical_name="food_snippets_long",
            thesaurus_filter=thesaurus_filter,
            thesaurus_path=str(thesaurus_path) if thesaurus_path else None,
        )
        rows = [to_row(inp) for inp in records]
    elif source == "verb":
        from trifecta_annotation.verb_kwic import sample_verb_kwic_for_gold

        records = sample_verb_kwic_for_gold(
            limit=limit or 25,
            seed=seed,
            thesaurus_path=str(thesaurus_path) if thesaurus_path else None,
        )
        rows = [to_row(inp) for inp in records]
    elif input_path is not None or source == "kwic_inputs":
        rows = [
            to_row(inp)
            for inp in load_kwic_input_candidates(
                limit=limit,
                input_logical=input_logical,
                input_path=input_path,
            )
        ]
    elif source == "long":
        from trifecta_annotation.adapters.food_snippets import (
            load_kwic_inputs_from_food_snippets_long,
        )

        records, _ = load_kwic_inputs_from_food_snippets_long(
            limit=limit,
            thesaurus_filter=thesaurus_filter,
            thesaurus_path=str(thesaurus_path) if thesaurus_path else None,
        )
        rows = [to_row(inp) for inp in records]
    else:
        from trifecta_annotation.adapters.food_snippets import (
            load_kwic_inputs_from_food_snippets,
        )

        records, _ = load_kwic_inputs_from_food_snippets(
            manual_only=(source == "manual"),
            limit=limit,
        )
        rows = [to_row(inp) for inp in records]
    return export_gold_csv(rows, output_logical=output_logical, output_path=output_path)


def export_gold_csv(
    rows: list[dict[str, Any]],
    *,
    output_logical: str | None = "trifecta_gold_csv",
    output_path: str | Path | None = None,
) -> Path:
    """Write gold rows to CSV."""
    frame = pd.DataFrame(rows, columns=GOLD_CSV_COLUMNS)
    if output_path is not None:
        path = Path(output_path).expanduser().resolve()
    else:
        path = resolve(output_logical)  # type: ignore[arg-type]
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def import_gold_csv(
    *,
    input_logical: str | None = "trifecta_gold_csv",
    input_path: str | Path | None = None,
    output_logical: str = "trifecta_gold",
    output_jsonl_logical: str = "trifecta_gold_jsonl",
    script: str | None = None,
) -> tuple[list[GoldAnnotation], Path, Path]:
    """Import labelled CSV rows into gold parquet + JSONL."""
    if input_path is not None:
        path = Path(input_path).expanduser().resolve()
    else:
        path = resolve(input_logical)  # type: ignore[arg-type]

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    annotations: list[GoldAnnotation] = []
    for row in frame.to_dict(orient="records"):
        parsed = row_to_annotation(row)
        if parsed is not None:
            annotations.append(parsed)

    if not annotations:
        raise ValueError(
            "No labelled rows found in CSV. Set labelled=true and fill Step A/B "
            "columns for rows you want to import (see docs/GOLD_LABELLING.md).",
        )

    records = [ann.model_dump(mode="json") for ann in annotations]
    jsonl_path = save_jsonl(
        records,
        logical_name=output_jsonl_logical,
        parent_sources=["trifecta_gold_csv"],
        description="Hand-labelled TRIFECTA gold set (JSONL mirror)",
        script=script,
    )
    parquet_df = pd.DataFrame({"annotation_json": [json.dumps(record) for record in records]})
    parquet_path = save_parquet(
        parquet_df,
        logical_name=output_logical,
        parent_sources=["trifecta_gold_csv", output_jsonl_logical],
        description="Hand-labelled TRIFECTA gold eval set",
        script=script,
    )
    return annotations, parquet_path, jsonl_path


def _records_from_gold_dataframe(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    if "annotation_json" in df.columns:
        return [json.loads(text) for text in df["annotation_json"]]
    return df.to_dict(orient="records")


def load_gold_records(
    *,
    gold_logical: str = "trifecta_gold",
    gold_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Load gold annotations from parquet (annotation_json) or JSONL."""
    if gold_path is not None:
        path = Path(gold_path)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
            return [
                ann.model_dump(mode="json")
                for row in frame.to_dict(orient="records")
                if (ann := row_to_annotation(row)) is not None
            ]
        if suffix == ".parquet":
            from data_io.parquet_io import load_parquet

            return _records_from_gold_dataframe(load_parquet(path=path))
        return load_jsonl(path)

    df = load_parquet(gold_logical)
    return _records_from_gold_dataframe(df)


def export_existing_gold_csv(
    *,
    gold_logical: str = "trifecta_gold",
    gold_path: str | Path | None = None,
    output_logical: str = "trifecta_gold_csv",
    output_path: str | Path | None = None,
) -> Path:
    """Export an existing gold set back to CSV for editing."""
    records = load_gold_records(gold_logical=gold_logical, gold_path=gold_path)
    rows = [annotation_to_row(record) for record in records]
    return export_gold_csv(rows, output_logical=output_logical, output_path=output_path)
