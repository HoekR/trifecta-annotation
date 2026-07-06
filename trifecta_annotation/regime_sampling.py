"""Stratified KWIC sampling by text_regime (Layer 0)."""

from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path

import pandas as pd
from data_io import load_jsonl, resolve

from trifecta_annotation.adapters.food_snippets import (
    adapt_food_snippet_long_row,
    load_food_snippets_long_frame,
)
from trifecta_annotation.schemas import KwicInput
from trifecta_annotation.text_regime import TextRegime, infer_text_regime
from trifecta_annotation.thesaurus import filter_long_snippets_frame
from trifecta_annotation.vocabulary import resolve_thesaurus_lookup


def title_lookup_from_snippets(
  *,
    logical_name: str = "food_snippets",
    path: str | Path | None = None,
) -> dict[str, str]:
    """Map filename / source_path → document title."""
    try:
        if path is not None:
            frame = pd.read_csv(path, usecols=["filename", "title"], dtype=str)
        else:
            frame = pd.read_csv(resolve(logical_name), usecols=["filename", "title"], dtype=str)
    except (FileNotFoundError, ValueError, KeyError):
        return {}
    return {
        str(row["filename"]): str(row["title"])
        for row in frame.drop_duplicates("filename").to_dict(orient="records")
        if str(row.get("filename", "")).strip()
    }


def enrich_kwic_regime(
    record: KwicInput,
    *,
    titles: dict[str, str] | None = None,
) -> KwicInput:
    """Attach title + inferred text_regime when missing."""
    titles = titles or {}
    source = str(record.source_path or "").strip()
    title = (record.title or titles.get(source, "") or "").strip() or None
    regime = record.text_regime
    if regime is None:
        regime = infer_text_regime(
            corpus=record.corpus,
            title=title,
            source_path=source,
        )
    updates: dict[str, object] = {}
    if title and not record.title:
        updates["title"] = title
    if record.text_regime is None:
        updates["text_regime"] = regime
    if updates:
        return record.model_copy(update=updates)
    return record


def _load_candidate_pool(
    *,
    include_inception: bool = True,
    include_kwic_inputs: bool = True,
    long_sample_size: int = 8000,
    seed: int = 0,
    thesaurus_filter: bool = True,
    thesaurus_path: str | None = None,
) -> list[KwicInput]:
    """Build a candidate pool with regime metadata."""
    pool: list[KwicInput] = []
    seen: set[str] = set()
    titles = title_lookup_from_snippets()

    def add(records: list[KwicInput]) -> None:
        for record in records:
            if record.record_id in seen:
                continue
            seen.add(record.record_id)
            pool.append(enrich_kwic_regime(record, titles=titles))

    if include_kwic_inputs:
        kwic_path = Path(resolve("kwic_inputs"))
        if kwic_path.exists():
            add([KwicInput.model_validate(row) for row in load_jsonl(kwic_path)])

    inception_path = Path(resolve("trifecta_gold")).parent / "inception_kwic_inputs.jsonl"
    if include_inception and inception_path.exists():
        add([KwicInput.model_validate(row) for row in load_jsonl(inception_path)])

    frame = load_food_snippets_long_frame()
    lookup: dict[str, str] = {}
    if thesaurus_filter:
        lookup = resolve_thesaurus_lookup(thesaurus_path=thesaurus_path)
        frame = filter_long_snippets_frame(frame, lookup)

    if len(frame) > long_sample_size:
        frame = frame.sample(n=long_sample_size, random_state=seed)

    for _, row in frame.iterrows():
        result = adapt_food_snippet_long_row(row)
        if result.input_record is None:
            continue
        record = enrich_kwic_regime(result.input_record, titles=titles)
        if record.record_id in seen:
            continue
        seen.add(record.record_id)
        pool.append(record)

    return pool


def sample_kwic_by_regime(
    quotas: dict[TextRegime, int],
    *,
    seed: int = 0,
    exclude_record_ids: set[str] | None = None,
    max_per_target: int = 2,
    include_inception: bool = True,
    thesaurus_filter: bool = True,
    thesaurus_path: str | None = None,
) -> tuple[list[KwicInput], dict[str, int]]:
    """
    Sample KWIC rows stratified by ``text_regime``.

    Returns selected records and per-regime fill counts (may be below quota).
    """
    exclude = exclude_record_ids or set()
    pool = _load_candidate_pool(
        include_inception=include_inception,
        seed=seed,
        thesaurus_filter=thesaurus_filter,
        thesaurus_path=thesaurus_path,
    )

    by_regime: dict[TextRegime, list[KwicInput]] = defaultdict(list)
    for record in pool:
        if record.record_id in exclude:
            continue
        regime = record.text_regime or TextRegime.UNKNOWN
        by_regime[regime].append(record)

    rng = random.Random(seed)
    selected: list[KwicInput] = []
    target_counts: dict[str, int] = defaultdict(int)
    filled: dict[str, int] = {}

    for regime, quota in quotas.items():
        if quota <= 0:
            filled[regime.value] = 0
            continue
        bucket = list(by_regime.get(regime, []))
        rng.shuffle(bucket)
        picked = 0
        for record in bucket:
            key = record.target_word.lower()
            if target_counts[key] >= max_per_target:
                continue
            selected.append(record)
            target_counts[key] += 1
            picked += 1
            if picked >= quota:
                break
        filled[regime.value] = picked

    rng.shuffle(selected)
    return selected, dict(filled)


def parse_regime_quotas(spec: str) -> dict[TextRegime, int]:
    """Parse ``RECIPE_PRACTICE:25,MEDICAL:25`` into a quota map."""
    quotas: dict[TextRegime, int] = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"Expected REGIME:count, got: {part}")
        name, count_s = part.split(":", 1)
        quotas[TextRegime(name.strip())] = int(count_s.strip())
    return quotas


def default_inception_silver_path() -> Path:
    return Path(resolve("trifecta_gold")).parent / "inception_silver_labelling.csv"


def refresh_labelling_regimes(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Re-infer ``text_regime`` from corpus/title/source_path on labelling rows."""
    refreshed: list[dict[str, object]] = []
    for row in rows:
        context = str(row.get("context_text") or "")
        existing = str(row.get("text_regime") or "").strip()
        if existing and existing != TextRegime.UNKNOWN.value:
            try:
                regime = TextRegime(existing)
            except ValueError:
                regime = TextRegime.UNKNOWN
        else:
            regime = infer_text_regime(
                corpus=str(row.get("corpus") or ""),
                title=str(row.get("title") or ""),
                source_path=str(row.get("source_path") or ""),
            )
        if regime == TextRegime.UNKNOWN and context:
            from trifecta_annotation.snippet_lookup import lookup_snippet_metadata

            match = lookup_snippet_metadata(context)
            if match is not None:
                regime = match.text_regime
        refreshed.append({**row, "text_regime": regime.value})
    return refreshed


def sample_inception_silver(
    quotas: dict[TextRegime, int],
    *,
    seed: int = 0,
    exclude_record_ids: set[str] | None = None,
    silver_path: Path | None = None,
    refresh_regimes: bool = True,
    max_per_target: int = 3,
    labelled_only: bool = True,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """
    Sample pre-labelled INCEpTION silver rows by ``text_regime`` quota.

    Returns labelling CSV rows (``labelled=true``) and per-regime fill counts.
    """
    path = silver_path or default_inception_silver_path()
    if not path.exists():
        return [], {regime.value: 0 for regime in quotas}

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    rows = frame.to_dict(orient="records")
    if refresh_regimes:
        rows = refresh_labelling_regimes(rows)

    exclude = exclude_record_ids or set()
    eligible: list[dict[str, object]] = []
    for row in rows:
        record_id = str(row.get("record_id") or "").strip()
        if not record_id or record_id in exclude:
            continue
        if labelled_only and str(row.get("labelled", "")).lower() != "true":
            continue
        eligible.append(row)

    by_regime: dict[TextRegime, list[dict[str, object]]] = defaultdict(list)
    for row in eligible:
        regime_raw = str(row.get("text_regime") or TextRegime.UNKNOWN.value).strip()
        try:
            regime = TextRegime(regime_raw)
        except ValueError:
            regime = TextRegime.UNKNOWN
        by_regime[regime].append(row)

    rng = random.Random(seed)
    selected: list[dict[str, object]] = []
    target_counts: dict[str, int] = defaultdict(int)
    filled: dict[str, int] = {}

    for regime, quota in quotas.items():
        if quota <= 0:
            filled[regime.value] = 0
            continue
        bucket = list(by_regime.get(regime, []))
        rng.shuffle(bucket)
        picked = 0
        for row in bucket:
            key = str(row.get("target_word") or "").lower()
            if key and target_counts[key] >= max_per_target:
                continue
            selected.append(row)
            if key:
                target_counts[key] += 1
            picked += 1
            if picked >= quota:
                break
        filled[regime.value] = picked

    rng.shuffle(selected)
    return selected, dict(filled)
