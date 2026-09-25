"""Adapter for TRIFECTA cort_voc_db food snippets (manual annotation source)."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.schemas import KwicInput
from trifecta_annotation.text_regime import infer_text_regime

# Cort_voc "snippets" are often passage-length; clip around target for pipeline/GijsBERT.
DEFAULT_KWIC_CONTEXT_RADIUS = 180


@dataclass(frozen=True)
class FoodSnippetAdaptation:
    input_record: KwicInput | None
    candidate_terms: list[str]
    reason: str | None = None


def parse_found_terms(raw: object) -> list[str]:
    """Parse a list-literal column (``original_found_terms``, ``matched_terms``, …)."""
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


def merge_kwic_batches(values: pd.Series) -> str:
    """Union pipe-separated KWIC batch tags (``recept``, ``reizen``, …)."""
    parts: set[str] = set()
    for raw in values.dropna():
        text = str(raw).strip()
        if not text:
            continue
        for piece in text.split("|"):
            piece = piece.strip()
            if piece:
                parts.add(piece)
    return "|".join(sorted(parts))


def kwic_batch_from_manual_labels(raw: object) -> str:
    """Normalize ``manual_labels`` to a sorted ``|``-joined batch string."""
    return kwic_batch_from_labels_list(parse_found_terms(raw))


def kwic_batch_from_labels_list(labels: list[str]) -> str:
    return "|".join(sorted({label.strip() for label in labels if label.strip()}))


def filter_kwic_batch_frame(frame: pd.DataFrame, *batches: str) -> pd.DataFrame:
    """Keep rows whose ``kwic_batch`` intersects *batches* (vectorized)."""
    if not batches or "kwic_batch" not in frame.columns:
        return frame
    targets = {batch.strip().lower() for batch in batches if batch.strip()}
    if not targets:
        return frame
    row_batches = (
        frame["kwic_batch"]
        .fillna("")
        .str.split("|")
        .map(lambda parts: {part.strip().lower() for part in parts if part.strip()})
    )
    mask = row_batches.map(lambda parts: bool(parts & targets))
    return frame.loc[mask].copy()


def _term_lists_from_wide_frame(
    frame: pd.DataFrame,
    *,
    terms_column: str = "matched_terms",
    fallback_column: str = "original_found_terms",
    dedupe_within_row: bool = True,
) -> pd.Series:
    """Parse per-row term lists from wide snippet columns."""
    if terms_column in frame.columns:
        source = frame[terms_column]
    elif fallback_column in frame.columns:
        source = frame[fallback_column]
    else:
        msg = f"wide frame needs {terms_column!r} or {fallback_column!r}"
        raise ValueError(msg)

    lists = source.map(parse_found_terms)
    if not dedupe_within_row:
        return lists

    def _dedupe_terms(terms: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for term in terms:
            norm = term.strip().lower()
            if not norm or norm in seen:
                continue
            seen.add(norm)
            unique.append(term.strip())
        return unique

    return lists.map(_dedupe_terms)


def explode_food_snippets_wide_frame(
    wide: pd.DataFrame,
    *,
    terms_column: str = "matched_terms",
    fallback_column: str = "original_found_terms",
    dedupe_within_row: bool = True,
) -> pd.DataFrame:
    """Explode wide snippets to one row per matched keyword."""
    frame = wide.copy()
    frame["_term_list"] = _term_lists_from_wide_frame(
        frame,
        terms_column=terms_column,
        fallback_column=fallback_column,
        dedupe_within_row=dedupe_within_row,
    )
    if "manual_labels" in frame.columns:
        frame["kwic_batch"] = frame["manual_labels"].map(kwic_batch_from_manual_labels)
    exploded = frame.explode("_term_list", ignore_index=True)
    exploded = exploded.rename(columns={"_term_list": "matched_term"})
    mask = exploded["matched_term"].notna() & exploded["matched_term"].astype(str).str.strip().ne("")
    exploded = exploded.loc[mask].copy()
    exploded["matched_term"] = exploded["matched_term"].astype(str).str.strip()
    exploded["matched_term_norm"] = exploded["matched_term"].str.lower()
    return exploded


def dedupe_food_snippets_long_frame(
    long: pd.DataFrame,
    *,
    subset: tuple[str, ...] = ("doc_id", "matched_term_norm"),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Collapse redundant keyword rows; merge ``kwic_batch`` / ``manual_labels``.

    Default key ``(doc_id, matched_term_norm)`` matches legacy ``kwic_inputs`` loading.
    Prefer ``(snippet, matched_term_norm)`` for KWIC ingest — removes duplicate search
    hits while keeping multiple targets (and multiple windows) per chapter ``doc_id``.

    Returns ``(deduped, dropped_summary)`` where *dropped_summary* has one row per
    duplicate key with ``duplicate_rows`` and merged batch tags.
    """
    frame = long.copy()
    if "matched_term_norm" not in frame.columns:
        frame["matched_term_norm"] = frame["matched_term"].astype(str).str.lower().str.strip()

    dup_mask = frame.duplicated(subset=list(subset), keep=False)
    if not dup_mask.any():
        return frame.drop(columns=["matched_term_norm"], errors="ignore"), pd.DataFrame()

    static_cols = [
        col
        for col in (
            "doc_id",
            "filename",
            "title",
            "snippet",
            "original_found_terms",
            "term_count",
            "matched_term",
        )
        if col in frame.columns and col not in subset
    ]
    agg: dict[str, str | callable] = {col: "first" for col in static_cols}
    if "kwic_batch" in frame.columns:
        agg["kwic_batch"] = merge_kwic_batches
    if "manual_labels" in frame.columns:
        agg["manual_labels"] = merge_kwic_batches

    keyed = frame.groupby(list(subset), dropna=False)
    deduped = keyed.agg(agg).reset_index()
    counts = keyed.size().reset_index(name="duplicate_rows")
    dropped = counts[counts["duplicate_rows"] > 1].copy()
    if "kwic_batch" in frame.columns:
        merged_batches = keyed["kwic_batch"].apply(merge_kwic_batches).reset_index(name="kwic_batch")
        dropped = dropped.merge(merged_batches, on=list(subset), how="left")

    deduped = deduped.drop(columns=["matched_term_norm"], errors="ignore")
    return deduped, dropped


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
        text_regime=infer_text_regime(
            corpus=_corpus_from_filename(str(row.get("filename", ""))),
            title=str(row.get("title") or "") or None,
            source_path=str(row.get("filename") or "") or None,
        ),
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


def load_food_snippets_long_frame(
    *,
    logical_name: str = "food_snippets_long",
    path: str | Path | None = None,
) -> pd.DataFrame:
    """Load exploded snippet CSV (one row per matched keyword)."""
    resolved = Path(path).expanduser().resolve() if path else resolve(logical_name)
    return pd.read_csv(resolved)


def _term_in_snippet(snippet: str, term: str) -> bool:
    if len(term) < 3:
        return False
    return bool(re.search(rf"\b{re.escape(term.lower())}\b", snippet.lower()))


def make_long_record_id(doc_id: str, term: str, occurrence: int = 0) -> str:
    """Stable id for one (snippet, keyword) pair; suffix when term repeats in snippet."""
    base = f"{doc_id}__{term.lower()}"
    return base if occurrence == 0 else f"{base}__{occurrence}"


def adapt_food_snippet_long_row(
    row: pd.Series,
    *,
    occurrence: int = 0,
    context_radius: int | None = None,
) -> FoodSnippetAdaptation:
    """Adapt one row from food_snippets_long.csv (explicit ``matched_term``)."""
    snippet = str(row.get("snippet", "")).strip()
    if not snippet:
        return FoodSnippetAdaptation(None, [], "empty_snippet")

    term = str(row.get("matched_term", "")).strip()
    if not term:
        return FoodSnippetAdaptation(None, [], "empty_matched_term")
    if not _term_in_snippet(snippet, term):
        return FoodSnippetAdaptation(None, [term], "term_not_in_snippet")

    if context_radius is not None and context_radius > 0:
        from trifecta_annotation.homonym_context import local_context_window

        snippet = local_context_window(snippet, term, radius=context_radius)

    doc_id = str(row["doc_id"])
    kwic_batch = str(row.get("kwic_batch") or "").strip() or None
    record = KwicInput(
        record_id=make_long_record_id(doc_id, term, occurrence),
        corpus=_corpus_from_filename(str(row.get("filename", ""))),
        target_word=term,
        context_text=snippet,
        date=None,
        source_path=str(row.get("filename") or "") or None,
        title=str(row.get("title") or "") or None,
        candidate_terms=[term],
        kwic_batch=kwic_batch,
        text_regime=infer_text_regime(
            corpus=_corpus_from_filename(str(row.get("filename", ""))),
            title=str(row.get("title") or "") or None,
            source_path=str(row.get("filename") or "") or None,
        ),
    )
    return FoodSnippetAdaptation(record, [term])


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


def load_kwic_inputs_from_food_snippets_long(
    *,
    logical_name: str = "food_snippets_long",
    path: str | Path | None = None,
    limit: int | None = None,
    dedupe_doc_term: bool = True,
    thesaurus_filter: bool = True,
    thesaurus_path: str | Path | None = None,
    kwic_batches: list[str] | None = None,
    context_radius: int | None = None,
) -> tuple[list[KwicInput], list[dict[str, object]]]:
    """Build KwicInput records from food_snippets_long.csv (one keyword per row)."""
    from trifecta_annotation.thesaurus import filter_long_snippets_frame
    from trifecta_annotation.vocabulary import resolve_thesaurus_lookup

    frame = load_food_snippets_long_frame(logical_name=logical_name, path=path)
    if kwic_batches:
        frame = filter_kwic_batch_frame(frame, *kwic_batches)
    if thesaurus_filter:
        lookup = resolve_thesaurus_lookup(thesaurus_path=thesaurus_path)
        frame = filter_long_snippets_frame(frame, lookup)
    records: list[KwicInput] = []
    skipped: list[dict[str, object]] = []
    seen_doc_term: set[str] = set()
    occurrence: dict[str, int] = {}

    for _, row in frame.iterrows():
        doc_id = str(row.get("doc_id", ""))
        term = str(row.get("matched_term", "")).strip().lower()
        doc_term_key = f"{doc_id}__{term}"

        if dedupe_doc_term:
            if doc_term_key in seen_doc_term:
                skipped.append(
                    {
                        "doc_id": doc_id,
                        "matched_term": term,
                        "reason": "duplicate_doc_term",
                    },
                )
                continue
            seen_doc_term.add(doc_term_key)
            occ = 0
        else:
            occ = occurrence.get(doc_term_key, 0)
            occurrence[doc_term_key] = occ + 1

        result = adapt_food_snippet_long_row(
            row,
            occurrence=occ,
            context_radius=context_radius,
        )
        if result.input_record is None:
            skipped.append(
                {
                    "doc_id": doc_id,
                    "matched_term": term,
                    "reason": result.reason,
                },
            )
            continue
        records.append(result.input_record)
        if limit is not None and len(records) >= limit:
            break

    return records, skipped


def load_kwic_inputs_from_food_snippets_kwic(
    *,
    logical_name: str = "food_snippets_long_kwic",
    path: str | Path | None = None,
    limit: int | None = None,
    kwic_batches: list[str] | None = None,
    thesaurus_filter: bool = True,
    thesaurus_path: str | Path | None = None,
    context_radius: int | None = DEFAULT_KWIC_CONTEXT_RADIUS,
) -> tuple[list[KwicInput], list[dict[str, object]]]:
    """Build KwicInput records from ingested KWIC xlsx long CSV (pre-deduped, ``kwic_batch``)."""
    return load_kwic_inputs_from_food_snippets_long(
        logical_name=logical_name,
        path=path,
        limit=limit,
        dedupe_doc_term=False,
        thesaurus_filter=thesaurus_filter,
        thesaurus_path=thesaurus_path,
        kwic_batches=kwic_batches,
        context_radius=context_radius,
    )
