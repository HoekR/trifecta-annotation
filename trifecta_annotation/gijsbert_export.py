"""Export TRIFECTA annotations to GijsBERT sequence-classification training format."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from trifecta_annotation.schemas import TrifectaAnnotation, TrifectaFrame

FRAME_LABELS: list[str] = [frame.value for frame in TrifectaFrame]
LABEL2ID: dict[str, int] = {label: idx for idx, label in enumerate(FRAME_LABELS)}
ID2LABEL: dict[int, str] = {idx: label for label, idx in LABEL2ID.items()}

DEFAULT_TARGET_OPEN = "[TGT]"
DEFAULT_TARGET_CLOSE = "[/TGT]"


def mark_target_in_context(
    context_text: str,
    target_word: str,
    *,
    open_marker: str = DEFAULT_TARGET_OPEN,
    close_marker: str = DEFAULT_TARGET_CLOSE,
) -> str:
    """Wrap the first whole-word occurrence of *target_word* in *context_text*."""
    if not target_word.strip():
        return context_text
    pattern = re.compile(rf"\b({re.escape(target_word)})\b", re.IGNORECASE)

    def _repl(match: re.Match[str]) -> str:
        return f"{open_marker}{match.group(1)}{close_marker}"

    marked, count = pattern.subn(_repl, context_text, count=1)
    if count == 0:
        return f"{open_marker}{target_word}{close_marker} {context_text}"
    return marked


def frame_label_from_record(record: dict[str, Any]) -> str | None:
    """Return macro-frame label for training, or None if row should be skipped."""
    ann = TrifectaAnnotation.model_validate(record)
    if ann.dropped or ann.error:
        return TrifectaFrame.NONE.value
    if ann.step_b is None:
        return None
    return ann.step_b.selected_frame.value


def annotation_to_gijsbert_row(
    record: dict[str, Any],
    *,
    open_marker: str = DEFAULT_TARGET_OPEN,
    close_marker: str = DEFAULT_TARGET_CLOSE,
) -> dict[str, Any] | None:
    """Convert one annotation dict to a GijsBERT training/eval row."""
    ann = TrifectaAnnotation.model_validate(record)
    label = frame_label_from_record(record)
    if label is None:
        return None
    provenance = ann.provenance
    text = mark_target_in_context(
        provenance.context_text,
        provenance.target_word,
        open_marker=open_marker,
        close_marker=close_marker,
    )
    return {
        "record_id": provenance.record_id,
        "text": text,
        "label": label,
        "label_id": LABEL2ID[label],
        "corpus": provenance.corpus,
        "date": provenance.date,
        "target_word": provenance.target_word,
    }


def export_gijsbert_jsonl(
    records: list[dict[str, Any]],
    output_path: str | Path,
    *,
    open_marker: str = DEFAULT_TARGET_OPEN,
    close_marker: str = DEFAULT_TARGET_CLOSE,
) -> Path:
    """Write filtered GijsBERT rows to JSONL."""
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for record in records:
        row = annotation_to_gijsbert_row(
            record,
            open_marker=open_marker,
            close_marker=close_marker,
        )
        if row is not None:
            rows.append(row)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def export_gijsbert_splits(
    *,
    silver_records: list[dict[str, Any]],
    gold_records: list[dict[str, Any]],
    output_dir: str | Path,
    open_marker: str = DEFAULT_TARGET_OPEN,
    close_marker: str = DEFAULT_TARGET_CLOSE,
) -> dict[str, Path]:
    """
    Write train (silver), dev/test (gold) JSONL plus label manifest.

    Gold rows are excluded from train when record_id overlaps silver.
    """
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    gold_ids = {
        str((r.get("provenance") or {}).get("record_id"))
        for r in gold_records
        if (r.get("provenance") or {}).get("record_id")
    }
    train_records = [
        r
        for r in silver_records
        if str((r.get("provenance") or {}).get("record_id")) not in gold_ids
    ]

    paths = {
        "train": export_gijsbert_jsonl(
            train_records,
            out / "train.jsonl",
            open_marker=open_marker,
            close_marker=close_marker,
        ),
        "dev": export_gijsbert_jsonl(
            gold_records,
            out / "dev.jsonl",
            open_marker=open_marker,
            close_marker=close_marker,
        ),
        "test": export_gijsbert_jsonl(
            gold_records,
            out / "test.jsonl",
            open_marker=open_marker,
            close_marker=close_marker,
        ),
    }
    manifest = {
        "labels": FRAME_LABELS,
        "label2id": LABEL2ID,
        "id2label": ID2LABEL,
        "counts": {
            "train": sum(
                1 for r in train_records if annotation_to_gijsbert_row(r) is not None
            ),
            "dev": sum(
                1 for r in gold_records if annotation_to_gijsbert_row(r) is not None
            ),
        },
        "target_markers": [open_marker, close_marker],
        "model_base": "emanjavacas/gysbert",
    }
    manifest_path = out / "label_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    paths["manifest"] = manifest_path
    return paths


def load_gijsbert_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
