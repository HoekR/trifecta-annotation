"""Adapter for TRIFECTA cort_voc_db food snippets (manual annotation source)."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.schemas import KwicInput


@dataclass(frozen=True)
class FoodSnippetAdaptation:
    input_record: KwicInput | None
    candidate_terms: list[str]
    reason: str | None = None


def parse_found_terms(raw: object) -> list[str]:
    """Parse ``original_found_terms`` column (Python list literal string)."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, list):
        return [str(term) for term in raw]
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(term) for term in parsed]


def terms_in_snippet(snippet: str, terms: list[str]) -> list[str]:
    """Return ontology terms that appear as whole words in *snippet*."""
    lowered = snippet.lower()
    found: list[tuple[int, str]] = []
    for term in terms:
        if len(term) < 3:
            continue
        match = re.search(rf"\b{re.escape(term.lower())}\b", lowered)
        if match:
            found.append((match.start(), term))
    found.sort(key=lambda item: item[0])
    return [term for _, term in found]


def pick_target_word(snippet: str, terms: list[str]) -> tuple[str | None, list[str]]:
    """Pick leftmost matching term; return all matches for reviewer context."""
    in_snippet = terms_in_snippet(snippet, terms)
    if not in_snippet:
        return None, []
    return in_snippet[0], in_snippet


def _corpus_from_filename(filename: str) -> str:
    return "cort_voc_db"


def adapt_food_snippet_row(row: pd.Series) -> FoodSnippetAdaptation:
    snippet = str(row.get("snippet", "")).strip()
    if not snippet:
        return FoodSnippetAdaptation(None, [], "empty_snippet")

    terms = parse_found_terms(row.get("original_found_terms"))
    target, candidates = pick_target_word(snippet, terms)
    if target is None:
        return FoodSnippetAdaptation(None, candidates, "no_target_in_snippet")

    record = KwicInput(
        record_id=str(row["doc_id"]),
        corpus=_corpus_from_filename(str(row.get("filename", ""))),
        target_word=target,
        context_text=snippet,
        date=None,
        source_path=str(row.get("filename") or "") or None,
        title=str(row.get("title") or "") or None,
        candidate_terms=candidates or None,
    )
    return FoodSnippetAdaptation(record, candidates)


def load_manual_snippet_texts(
    *,
    logical_name: str = "food_snippets_manual",
    path: str | Path | None = None,
) -> list[str]:
    """Load stripped non-empty lines from the manual annotation txt file."""
    resolved = Path(path).expanduser().resolve() if path else resolve(logical_name)
    lines = resolved.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def load_food_snippets_frame(
    *,
    logical_name: str = "food_snippets",
    path: str | Path | None = None,
) -> pd.DataFrame:
    resolved = Path(path).expanduser().resolve() if path else resolve(logical_name)
    return pd.read_csv(resolved)


def load_kwic_inputs_from_food_snippets(
    *,
    logical_name: str = "food_snippets",
    path: str | Path | None = None,
    manual_only: bool = False,
    manual_logical: str = "food_snippets_manual",
    manual_path: str | Path | None = None,
    limit: int | None = None,
) -> tuple[list[KwicInput], list[dict[str, object]]]:
    """Build KwicInput records from food_snippets_for_annotation.csv."""
    frame = load_food_snippets_frame(logical_name=logical_name, path=path)
    frame["snippet_norm"] = frame["snippet"].astype(str).str.strip()

    if manual_only:
        manual_texts = load_manual_snippet_texts(
            logical_name=manual_logical,
            path=manual_path,
        )
        manual_set = set(manual_texts)
        frame = frame[frame["snippet_norm"].isin(manual_set)]

    records: list[KwicInput] = []
    skipped: list[dict[str, object]] = []

    for _, row in frame.iterrows():
        result = adapt_food_snippet_row(row)
        if result.input_record is None:
            skipped.append(
                {
                    "doc_id": row.get("doc_id"),
                    "reason": result.reason,
                    "candidate_terms": result.candidate_terms,
                },
            )
            continue
        records.append(result.input_record)
        if limit is not None and len(records) >= limit:
            break

    return records, skipped
