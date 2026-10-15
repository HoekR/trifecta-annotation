"""Build verb-seeded KwicInput records (frame verb discovers snippet, food is target)."""

from __future__ import annotations

import random
from collections import defaultdict

import pandas as pd

from trifecta_annotation.adapters.food_snippets import (
    load_food_snippets_frame,
    parse_found_terms,
)
from trifecta_annotation.frame_verbs import (
    find_frame_verbs_in_text,
    pick_food_near_verb,
    snippet_has_frame_verb,
    term_positions,
)
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import KwicInput, TrifectaFrame
from trifecta_annotation.text_regime import infer_text_regime
from trifecta_annotation.vocabulary import resolve_thesaurus_lookup


def _corpus_from_filename(filename: str) -> str:
    return "cort_voc_db"


def _food_terms_for_row(row: pd.Series, lookup: dict[str, str]) -> list[str]:
    terms = parse_found_terms(row.get("original_found_terms"))
    kept: list[str] = []
    seen: set[str] = set()
    for term in terms:
        norm = normalize_hist_dutch(term)
        if norm in lookup and norm not in seen:
            kept.append(term)
            seen.add(norm)
    if kept:
        return kept
    if "matched_term" in row.index:
        term = str(row.get("matched_term") or "").strip()
        if term and normalize_hist_dutch(term) in lookup:
            return [term]
    return []


def verb_kwic_from_snippet_row(
    row: pd.Series,
    *,
    lookup: dict[str, str],
    verb_hit_index: int = 0,
    require_food: bool = True,
) -> KwicInput | None:
    """One KwicInput from a snippet row + frame verb hit."""
    snippet = str(row.get("snippet", "")).strip()
    if not snippet:
        return None

    food_terms = _food_terms_for_row(row, lookup)
    if require_food and not food_terms:
        return None

    hits = find_frame_verbs_in_text(snippet)
    if not hits:
        return None
    if verb_hit_index >= len(hits):
        return None
    hit = hits[verb_hit_index]

    food_positions = term_positions(snippet, food_terms)
    food_target = pick_food_near_verb(hit.start, food_positions)
    if require_food and not food_target:
        return None

    target = food_target or hit.verb
    mode = "verb_food" if food_target else "verb"
    doc_id = str(row["doc_id"])
    record_id = f"{doc_id}__v_{normalize_hist_dutch(hit.verb)}__{normalize_hist_dutch(target)}"

    return KwicInput(
        record_id=record_id,
        corpus=_corpus_from_filename(str(row.get("filename", ""))),
        target_word=target,
        context_text=snippet,
        date=None,
        source_path=str(row.get("filename") or "") or None,
        title=str(row.get("title") or "") or None,
        candidate_terms=food_terms or None,
        discovery_verb=hit.verb,
        frame_hint=hit.frame.value,
        kwic_mode=mode,
        text_regime=infer_text_regime(
            corpus=_corpus_from_filename(str(row.get("filename", ""))),
            title=str(row.get("title") or "") or None,
            source_path=str(row.get("filename") or "") or None,
        ),
    )


def iter_verb_kwic_candidates(
    frame: pd.DataFrame,
    *,
    lookup: dict[str, str],
    require_food: bool = True,
) -> list[KwicInput]:
    """Scan snippet rows; return one candidate per (snippet, first verb hit)."""
    snippets = frame["snippet"].astype(str).str.strip()
    eligible = frame[snippets.ne("") & snippets.map(snippet_has_frame_verb)]
    records: list[KwicInput] = []
    seen_ids: set[str] = set()
    for _, row in eligible.iterrows():
        record = verb_kwic_from_snippet_row(
            row,
            lookup=lookup,
            verb_hit_index=0,
            require_food=require_food,
        )
        if record is None or record.record_id in seen_ids:
            continue
        seen_ids.add(record.record_id)
        records.append(record)
    return records


def _work_key(record: KwicInput) -> str:
    return (record.title or record.source_path or record.corpus or "unknown")[:80]


def sample_verb_kwic_for_gold(
    *,
    limit: int = 25,
    seed: int = 0,
    logical_name: str = "food_snippets",
    path: str | None = None,
    thesaurus_path: str | None = None,
    require_food: bool = True,
    max_per_work: int = 2,
    frames: tuple[TrifectaFrame, ...] | None = None,
) -> list[KwicInput]:
    """
    Stratified verb-seeded sample: round-robin across frame_hint buckets.

    Uses wide ``food_snippets`` (one row per snippet with ``original_found_terms``).
    """
    lookup = resolve_thesaurus_lookup(thesaurus_path=thesaurus_path)
    if not lookup:
        return []

    snippets = load_food_snippets_frame(logical_name=logical_name, path=path)
    pool = iter_verb_kwic_candidates(snippets, lookup=lookup, require_food=require_food)

    target_frames = frames or (
        TrifectaFrame.PRESERVING,
        TrifectaFrame.CURE,
        TrifectaFrame.COOKING_CREATION,
        TrifectaFrame.INGESTION,
    )
    by_frame: dict[str, list[KwicInput]] = defaultdict(list)
    work_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for record in pool:
        hint = record.frame_hint or TrifectaFrame.NONE.value
        if hint not in {f.value for f in target_frames}:
            continue
        work = _work_key(record)
        if work_counts[hint][work] >= max_per_work:
            continue
        by_frame[hint].append(record)
        work_counts[hint][work] += 1

    rng = random.Random(seed)
    for bucket in by_frame.values():
        rng.shuffle(bucket)

    frame_order = [f.value for f in target_frames if by_frame.get(f.value)]
    rng.shuffle(frame_order)
    selected: list[KwicInput] = []
    seen: set[str] = set()

    while len(selected) < limit and frame_order:
        progressed = False
        for hint in list(frame_order):
            bucket = by_frame.get(hint, [])
            while bucket:
                record = bucket.pop(rng.randrange(len(bucket)))
                if record.record_id in seen:
                    continue
                selected.append(record)
                seen.add(record.record_id)
                progressed = True
                break
            if len(selected) >= limit:
                break
        if not progressed:
            break

    return selected[:limit]


def verb_sample_summary(records: list[KwicInput]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        counts[record.frame_hint or "unknown"] += 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
