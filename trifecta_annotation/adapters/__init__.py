"""Adapters for normalizing external KWIC sources into KwicInput records."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd
from data_io import resolve

from trifecta_annotation.schemas import KwicInput
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms


@dataclass(frozen=True)
class KwicAdaptation:
    """Result of adapting one source row."""

    input_record: KwicInput | None
    ambiguous: bool
    matched_terms: list[str]


def _find_food_terms(snippet: str, index: dict[str, str]) -> list[str]:
    """Return ontology terms found in *snippet* (longest match per position)."""
    lowered = snippet.lower()
    found: list[tuple[int, int, str]] = []
    for term in sorted(index, key=len, reverse=True):
        if len(term) < 3:
            continue
        pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        for match in pattern.finditer(lowered):
            start, end = match.span()
            if any(not (end <= other_start or start >= other_end) for other_start, other_end, _ in found):
                continue
            found.append((start, end, term))
    found.sort(key=lambda item: item[0])
    return [term for _, _, term in found]


def adapt_kwic_review_row(
    row: pd.Series,
    *,
    index: dict[str, str] | None = None,
) -> KwicAdaptation:
    """Adapt one row from ollama_kwic_review.csv."""
    snippet = str(row.get("snippet", "")).strip()
    if not snippet:
        return KwicAdaptation(input_record=None, ambiguous=False, matched_terms=[])

    lookup = index or alt_label_index(load_food_terms())
    matched = _find_food_terms(snippet, lookup)
    if not matched:
        return KwicAdaptation(input_record=None, ambiguous=True, matched_terms=[])

    target_word = matched[0]
    ambiguous = len(matched) > 1
    record = KwicInput(
        record_id=str(row["recipe_id"]),
        corpus="voc_recipes",
        target_word=target_word,
        context_text=snippet,
        date=None,
        source_path=None,
    )
    return KwicAdaptation(input_record=record, ambiguous=ambiguous, matched_terms=matched)


def load_kwic_inputs_from_review(
    *,
    include_ambiguous: bool = False,
) -> tuple[list[KwicInput], list[dict[str, object]]]:
    """Build KwicInput list from kwic_gold_review manifest dataset."""
    path = resolve("kwic_gold_review")
    frame = pd.read_csv(path)
    index = alt_label_index(load_food_terms())
    records: list[KwicInput] = []
    skipped: list[dict[str, object]] = []

    for _, row in frame.iterrows():
        result = adapt_kwic_review_row(row, index=index)
        if result.input_record is None:
            skipped.append(
                {
                    "recipe_id": row.get("recipe_id"),
                    "reason": "no_food_term" if not result.matched_terms else "empty_snippet",
                },
            )
            continue
        if result.ambiguous and not include_ambiguous:
            skipped.append(
                {
                    "recipe_id": row.get("recipe_id"),
                    "reason": "ambiguous_target",
                    "matched_terms": result.matched_terms,
                },
            )
            continue
        records.append(result.input_record)
    return records, skipped
