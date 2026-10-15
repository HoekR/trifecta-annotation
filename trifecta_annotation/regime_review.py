"""Regime review helpers for existing gold rows."""

from __future__ import annotations

import pandas as pd

from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS
from trifecta_annotation.text_regime import TextRegime, infer_text_regime

REVIEW_COLUMNS = [
    "record_id",
    "target_word",
    "corpus",
    "source_path",
    "title_hint",
    "current_text_regime",
    "suggested_text_regime",
    "review_text_regime",
    "context_snippet",
    "notes",
]


def title_hint(row: dict[str, str], titles: dict[str, str]) -> str:
    source = str(row.get("source_path") or "").strip()
    if source and source in titles:
        return titles[source]
    notes = str(row.get("notes") or "").strip()
    if notes:
        return notes.split(";")[0].strip()[:120]
    return ""


def is_unknown_regime(regime: str) -> bool:
    text = (regime or "").strip().upper()
    return not text or text == TextRegime.UNKNOWN.value


def build_review_rows(frame: pd.DataFrame, *, titles: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in frame.to_dict(orient="records"):
        current = str(record.get("text_regime") or "").strip() or TextRegime.UNKNOWN.value
        if not is_unknown_regime(current):
            continue
        hint = title_hint(record, titles)
        suggested = infer_text_regime(
            corpus=str(record.get("corpus") or ""),
            title=hint,
            source_path=str(record.get("source_path") or ""),
        ).value
        context = str(record.get("context_text") or "")
        snippet = context if len(context) <= 160 else context[:157] + "…"
        rows.append(
            {
                "record_id": str(record.get("record_id") or ""),
                "target_word": str(record.get("target_word") or ""),
                "corpus": str(record.get("corpus") or ""),
                "source_path": str(record.get("source_path") or ""),
                "title_hint": hint,
                "current_text_regime": current,
                "suggested_text_regime": suggested,
                "review_text_regime": "",
                "context_snippet": snippet,
                "notes": str(record.get("notes") or ""),
            },
        )
    return rows


def apply_regime_review(
    gold_all: pd.DataFrame,
    review: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """Merge ``review_text_regime`` (or ``text_regime``) into gold labelling CSV."""
    fixes: dict[str, str] = {}
    for row in review.to_dict(orient="records"):
        rid = str(row.get("record_id") or "").strip()
        val = str(row.get("review_text_regime") or row.get("text_regime") or "").strip()
        if rid and val:
            fixes[rid] = val
    if not fixes:
        return gold_all, 0

    rows: list[dict[str, str]] = []
    applied = 0
    for record in gold_all.to_dict(orient="records"):
        row = dict(record)
        rid = str(row.get("record_id") or "").strip()
        if rid in fixes:
            try:
                regime = TextRegime(fixes[rid]).value
            except ValueError:
                regime = fixes[rid]
            row["text_regime"] = regime
            applied += 1
        rows.append(row)
    return pd.DataFrame(rows).reindex(columns=GOLD_CSV_COLUMNS, fill_value=""), applied
