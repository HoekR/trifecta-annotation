"""CSV-backed store for gold labelling UI."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import pandas as pd
from data_io import resolve

from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS, _parse_bool
from trifecta_annotation.schemas import FormalDimension, TrifectaFrame
from trifecta_annotation.text_regime import TextRegime


def csv_path(logical: str = "trifecta_gold_csv", path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()
    return resolve(logical)  # type: ignore[return-value]


def load_frame(path: Path | None = None, *, logical: str = "trifecta_gold_csv") -> pd.DataFrame:
    p = path or csv_path(logical)
    if not p.exists():
        raise FileNotFoundError(f"Gold CSV not found: {p}")
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def save_frame(frame: pd.DataFrame, path: Path | None = None, *, logical: str = "trifecta_gold_csv") -> Path:
    p = path or csv_path(logical)
    p.parent.mkdir(parents=True, exist_ok=True)
    out = frame.reindex(columns=GOLD_CSV_COLUMNS, fill_value="")
    out.to_csv(p, index=False)
    return p


def rows_as_dicts(frame: pd.DataFrame) -> list[dict[str, str]]:
    return [{k: str(v) for k, v in row.items()} for row in frame.to_dict(orient="records")]


def is_labelled(row: dict[str, Any]) -> bool:
    parsed = _parse_bool(row.get("labelled"))
    if parsed is not None:
        return parsed
    has_a = str(row.get("is_food_entity", "")).strip() != ""
    dropped = str(row.get("dropped", "")).strip().lower() in {"true", "1", "yes"}
    return has_a or dropped


def stats(frame: pd.DataFrame) -> dict[str, int]:
    rows = rows_as_dicts(frame)
    labelled = sum(1 for row in rows if is_labelled(row))
    return {
        "total": len(rows),
        "labelled": labelled,
        "pending": len(rows) - labelled,
    }


def record_index(frame: pd.DataFrame, record_id: str) -> int:
    ids = frame["record_id"].astype(str).tolist()
    try:
        return ids.index(record_id)
    except ValueError as exc:
        raise KeyError(record_id) from exc


def get_row(frame: pd.DataFrame, record_id: str) -> dict[str, str]:
    match = frame[frame["record_id"].astype(str) == str(record_id)]
    if match.empty:
        raise KeyError(record_id)
    return rows_as_dicts(match)[0]


def update_row(
    frame: pd.DataFrame,
    record_id: str,
    payload: dict[str, Any],
) -> pd.DataFrame:
    idx = record_index(frame, record_id)
    row = rows_as_dicts(frame)[idx]
    row.update({k: "" if v is None else str(v) for k, v in payload.items()})
    row["record_id"] = record_id
    if "labelled" not in payload:
        row["labelled"] = "true"
    for col in GOLD_CSV_COLUMNS:
        if col not in row:
            row[col] = ""
    updated = frame.copy()
    for col, value in row.items():
        if col in updated.columns:
            updated.at[idx, col] = value
    return updated


def next_unlabelled_id(frame: pd.DataFrame, *, start: int = 0) -> str | None:
    rows = rows_as_dicts(frame)
    for offset in range(len(rows)):
        idx = (start + offset) % len(rows)
        if not is_labelled(rows[idx]):
            return rows[idx]["record_id"]
    return None


def highlight_target(context_text: str, target_word: str) -> str:
    """Return HTML-safe context with the target word marked."""
    if not target_word.strip():
        return html.escape(context_text)
    pattern = re.compile(rf"(\b{re.escape(target_word)}\b)", re.IGNORECASE)

    parts: list[str] = []
    last = 0
    replaced = False
    for match in pattern.finditer(context_text):
        if replaced:
            break
        parts.append(html.escape(context_text[last : match.start()]))
        parts.append(f'<mark class="target">{html.escape(match.group(1))}</mark>')
        last = match.end()
        replaced = True
    parts.append(html.escape(context_text[last:]))
    return "".join(parts)


def choice_options() -> dict[str, list[str]]:
    return {
        "frames": [frame.value for frame in TrifectaFrame],
        "formal_dimensions": [dim.value for dim in FormalDimension],
        "drop_reasons": ["metaphor", "not_food_entity", "irrelevant", "ambiguous"],
        "text_regimes": [regime.value for regime in TextRegime],
    }
