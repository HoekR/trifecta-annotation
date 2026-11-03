"""Review helpers for Step A dropout / NONE silver candidates."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from trifecta_annotation.homonym_context import assess_homonym_context
from trifecta_annotation.review_columns import HOMONYM_REVIEW_COLUMNS, empty_homonym_review_row
from trifecta_annotation.silver_merge import is_step_a_dropout, silver_record_id

_RECIPE_CUE = re.compile(
    r"\b(?:kook\w*|syroop|siroop|recept|elx een pond|neem\w*|meng\w*)\b",
    re.IGNORECASE,
)

ACCEPT_VERDICTS = frozenset({"accept", "a", "yes", "y", "k", "keep"})
REJECT_VERDICTS = frozenset({"reject", "r", "no", "n", "drop", "skip"})

DROPOUT_REVIEW_COLUMNS: tuple[str, ...] = (
    "record_id",
    "target_word",
    "kwic_batch",
    "drop_reason",
    "step_a_metaphor",
    "step_a_food_entity",
    "step_a_reasoning",
    "homonym_risk",
    "homonym_hint",
    "recipe_context",
    "context_snippet",
    "verdict",
    "review_notes",
) + HOMONYM_REVIEW_COLUMNS


def _short_context(text: str, target: str, *, width: int = 280) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return ""
    needle = str(target or "").strip()
    if needle:
        match = re.search(rf"\b{re.escape(needle)}\b", text, flags=re.IGNORECASE)
        if match:
            start = max(0, match.start() - width // 3)
            end = min(len(text), match.end() + (2 * width) // 3)
            snippet = text[start:end]
            return ("…" if start else "") + snippet + ("…" if end < len(text) else "")
    return text[:width] + ("…" if len(text) > width else "")


def build_dropout_review_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    """One review row per Step A dropout in *records*."""
    rows: list[dict[str, str]] = []
    for record in records:
        if not is_step_a_dropout(record):
            continue
        provenance = record.get("provenance") or {}
        step_a = record.get("step_a") or {}
        target = str(provenance.get("target_word") or "")
        context = str(provenance.get("context_text") or "")
        assessment = assess_homonym_context(target, context)
        rows.append(
            {
                "record_id": silver_record_id(record),
                "target_word": target,
                "kwic_batch": str(provenance.get("kwic_batch") or ""),
                "drop_reason": str(record.get("drop_reason") or ""),
                "step_a_metaphor": str(step_a.get("is_metaphor", "")),
                "step_a_food_entity": str(step_a.get("is_food_entity", "")),
                "step_a_reasoning": str(step_a.get("reasoning") or "")[:400],
                "homonym_risk": assessment.risk,
                "homonym_hint": "; ".join(assessment.reasons[:3]),
                "recipe_context": "true" if _RECIPE_CUE.search(context) else "false",
                "context_snippet": _short_context(context, target),
                "verdict": "",
                "review_notes": "",
                **empty_homonym_review_row(),
            },
        )
    return rows


def parse_verdict(raw: object) -> str:
    return str(raw or "").strip().lower()


def accepted_record_ids(review: pd.DataFrame) -> set[str]:
    """``record_id`` values marked accept/keep in review CSV."""
    if review.empty or "record_id" not in review.columns:
        return set()
    verdicts = review["record_id"].astype(str)
    if "verdict" not in review.columns:
        return set(verdicts)
    mask = review["verdict"].map(parse_verdict).isin(ACCEPT_VERDICTS)
    return set(review.loc[mask, "record_id"].astype(str))


def filter_dropout_records(
    records: list[dict[str, Any]],
    review: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Keep Step A dropouts; when *review* is set, only accepted ``record_id``s."""
    dropouts = [record for record in records if is_step_a_dropout(record)]
    if review is None:
        return dropouts
    allowed = accepted_record_ids(review)
    if not allowed:
        return []
    return [record for record in dropouts if silver_record_id(record) in allowed]
