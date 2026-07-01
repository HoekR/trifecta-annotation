"""Stratified sampling for diverse gold annotation candidates."""

from __future__ import annotations

import random
from collections import defaultdict

import pandas as pd

from trifecta_annotation.adapters.food_snippets import (
    adapt_food_snippet_long_row,
    adapt_food_snippet_row,
    load_food_snippets_frame,
    load_food_snippets_long_frame,
    load_kwic_inputs_from_food_snippets,
    parse_found_terms,
    terms_in_snippet,
)
from trifecta_annotation.schemas import KwicInput
from trifecta_annotation.thesaurus import filter_long_snippets_frame
from trifecta_annotation.verb_kwic import sample_verb_kwic_for_gold
from trifecta_annotation.vocabulary import resolve_thesaurus_lookup


def _work_key(row: pd.Series) -> str:
    title = str(row.get("title") or "").strip()
    if title:
        return title
    filename = str(row.get("filename") or "").strip()
    return filename or str(row.get("doc_id") or "unknown")


def _row_has_target(row: pd.Series) -> bool:
    snippet = str(row.get("snippet") or "").strip()
    if not snippet:
        return False
    if "matched_term" in row.index and str(row.get("matched_term") or "").strip():
        term = str(row["matched_term"]).strip()
        return bool(terms_in_snippet(snippet, [term]))
    terms = parse_found_terms(row.get("original_found_terms"))
    return bool(terms_in_snippet(snippet, terms))


def stratified_row_indices(
    frame: pd.DataFrame,
    *,
    limit: int,
    seed: int = 0,
    max_per_work: int = 3,
) -> list[int]:
    """Pick diverse row indices grouped by work (title), round-robin across works."""
    eligible = frame[frame.apply(_row_has_target, axis=1)].copy()
    if eligible.empty:
        return []

    eligible["_work"] = eligible.apply(_work_key, axis=1)
    by_work: dict[str, list[int]] = defaultdict(list)
    for index in eligible.index:
        work = eligible.loc[index, "_work"]
        if len(by_work[work]) < max_per_work:
            by_work[work].append(index)

    works = sorted(by_work)
    rng = random.Random(seed)
    rng.shuffle(works)

    picked: list[int] = []
    while len(picked) < limit and works:
        progressed = False
        for work in list(works):
            bucket = by_work[work]
            if not bucket:
                works.remove(work)
                continue
            picked.append(bucket.pop(rng.randrange(len(bucket))))
            progressed = True
            if len(picked) >= limit:
                break
        if not progressed:
            break
    return picked


def _adapt_indices(frame: pd.DataFrame, indices: list[int]) -> list[KwicInput]:
    records: list[KwicInput] = []
    long_format = "matched_term" in frame.columns
    for index in indices:
        if long_format:
            result = adapt_food_snippet_long_row(frame.loc[index])
        else:
            result = adapt_food_snippet_row(frame.loc[index])
        if result.input_record is not None:
            records.append(result.input_record)
    return records


def _dedupe_by_target(records: list[KwicInput], limit: int) -> list[KwicInput]:
    """Prefer unique target_word values when trimming to *limit*."""
    seen_targets: set[str] = set()
    unique: list[KwicInput] = []
    rest: list[KwicInput] = []
    for record in records:
        key = record.target_word.lower()
        if key not in seen_targets:
            seen_targets.add(key)
            unique.append(record)
        else:
            rest.append(record)
    combined = unique + rest
    return combined[:limit]


def sample_kwic_inputs_for_gold(
    *,
    limit: int = 50,
    seed: int = 0,
    include_manual: bool = True,
    manual_share: float = 0.5,
    verb_share: float = 0.0,
    max_per_work: int = 3,
    logical_name: str = "food_snippets_long",
    path: str | None = None,
    snippet_format: str = "long",
    thesaurus_filter: bool = True,
    thesaurus_path: str | None = None,
) -> list[KwicInput]:
    """
    Build a diverse annotation set across works and target words.

    1. Optionally seed from manual txt subset (curated snippets).
    2. Optionally seed from verb-discovered snippets (``verb_share``).
    3. Fill remaining slots via stratified sample from long/wide CSV.
    """
    if verb_share > 0:
        verb_limit = int(limit * verb_share)
        food_limit = limit - verb_limit
        verb_records = sample_verb_kwic_for_gold(
            limit=verb_limit,
            seed=seed,
            thesaurus_path=thesaurus_path,
        ) if verb_limit > 0 else []
        food_records = _sample_food_kwic_for_gold(
            limit=food_limit,
            seed=seed,
            include_manual=include_manual,
            manual_share=manual_share,
            max_per_work=max_per_work,
            logical_name=logical_name,
            path=path,
            snippet_format=snippet_format,
            thesaurus_filter=thesaurus_filter,
            thesaurus_path=thesaurus_path,
            exclude_ids={r.record_id for r in verb_records},
        )
        return _merge_kwic_samples(verb_records + food_records, limit=limit)

    return _sample_food_kwic_for_gold(
        limit=limit,
        seed=seed,
        include_manual=include_manual,
        manual_share=manual_share,
        max_per_work=max_per_work,
        logical_name=logical_name,
        path=path,
        snippet_format=snippet_format,
        thesaurus_filter=thesaurus_filter,
        thesaurus_path=thesaurus_path,
        exclude_ids=set(),
    )


def _merge_kwic_samples(records: list[KwicInput], *, limit: int) -> list[KwicInput]:
    seen: set[str] = set()
    out: list[KwicInput] = []
    for record in records:
        if record.record_id in seen:
            continue
        seen.add(record.record_id)
        out.append(record)
        if len(out) >= limit:
            break
    return out


def _sample_food_kwic_for_gold(
    *,
    limit: int,
    seed: int,
    include_manual: bool,
    manual_share: float,
    max_per_work: int,
    logical_name: str,
    path: str | None,
    snippet_format: str,
    thesaurus_filter: bool,
    thesaurus_path: str | None,
    exclude_ids: set[str],
) -> list[KwicInput]:
    selected: list[KwicInput] = []
    seen_ids: set[str] = set()

    manual_limit = int(limit * manual_share) if include_manual else 0
    if manual_limit > 0:
        manual_records, _ = load_kwic_inputs_from_food_snippets(manual_only=True)
        rng = random.Random(seed)
        rng.shuffle(manual_records)
        for record in _dedupe_by_target(manual_records, manual_limit):
            if record.record_id in seen_ids:
                continue
            selected.append(record)
            seen_ids.add(record.record_id)
            if len(selected) >= manual_limit:
                break

    remaining = limit - len(selected)
    if remaining <= 0:
        return selected[:limit]

    frame = (
        load_food_snippets_long_frame(logical_name=logical_name, path=path)
        if snippet_format == "long"
        else load_food_snippets_frame(logical_name=logical_name, path=path)
    )
    if snippet_format == "long" and "doc_id" in frame.columns and "matched_term" in frame.columns:
        frame = frame.assign(
            _term_norm=frame["matched_term"].astype(str).str.lower(),
        ).drop_duplicates(subset=["doc_id", "_term_norm"], keep="first")

    lookup: dict[str, str] = {}
    if thesaurus_filter:
        lookup = resolve_thesaurus_lookup(thesaurus_path=thesaurus_path)
        if snippet_format == "long":
            frame = filter_long_snippets_frame(frame, lookup)

    if seen_ids:
        frame = frame[~frame["doc_id"].astype(str).isin(seen_ids)]

    if exclude_ids and "doc_id" in frame.columns:
        pass  # record_ids differ; filter after adapt

    # Oversample indices then adapt (cheaper than adapting all ~31k rows).
    oversample = min(len(frame), remaining * 8)
    indices = stratified_row_indices(
        frame,
        limit=oversample,
        seed=seed + 1,
        max_per_work=max_per_work,
    )
    pool = _adapt_indices(frame, indices)
    for record in _dedupe_by_target(pool, remaining):
        if record.record_id in seen_ids or record.record_id in exclude_ids:
            continue
        selected.append(record)
        seen_ids.add(record.record_id)
        if len(selected) >= limit:
            break

    return selected[:limit]


def sample_summary(records: list[KwicInput]) -> dict[str, int]:
    """Return counts by work title for logging."""
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        key = (record.title or record.source_path or record.corpus)[:60]
        counts[key] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
