"""Stratified sense gallery for polysemous target words."""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from trifecta_annotation.adapters.food_snippets import (
    adapt_food_snippet_long_row,
    load_food_snippets_long_frame,
)
from trifecta_annotation.clear_frame_examples import target_centered_snippet
from trifecta_annotation.homonym_context import POLYSEMOUS_TARGETS
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.regime_sampling import title_lookup_from_snippets
from trifecta_annotation.review_columns import empty_homonym_review_row
from trifecta_annotation.schemas import KwicInput
from trifecta_annotation.text_regime import TextRegime, infer_text_regime
from trifecta_annotation.thesaurus import filter_long_snippets_frame
from trifecta_annotation.vocabulary import resolve_thesaurus_lookup

REFERENCE_COLUMNS: tuple[str, ...] = (
    "target_word",
    "target_norm",
    "bucket_key",
    "text_regime",
    "gold_frame",
    "gold_drop_reason",
    "in_gold",
    "record_id",
    "doc_id",
    "title",
    "source_path",
    "bucket_pool_size",
    "review_snippet",
    "sense_bucket",
    "homonym_check",
    "homonym_note",
    "gold_step_b_reasoning",
)


@dataclass(frozen=True)
class GoldSummary:
    record_id: str
    target_word: str
    target_norm: str
    text_regime: str
    gold_frame: str
    drop_reason: str
    step_b_reasoning: str
    context_text: str


@dataclass(frozen=True)
class GalleryRow:
    target_word: str
    target_norm: str
    bucket_key: str
    text_regime: str
    gold_frame: str
    gold_drop_reason: str
    in_gold: bool
    record_id: str
    doc_id: str
    title: str
    source_path: str
    bucket_pool_size: int
    review_snippet: str
    sense_bucket: str
    homonym_check: str
    homonym_note: str
    gold_step_b_reasoning: str

    def to_dict(self) -> dict[str, object]:
        return {
            "target_word": self.target_word,
            "target_norm": self.target_norm,
            "bucket_key": self.bucket_key,
            "text_regime": self.text_regime,
            "gold_frame": self.gold_frame,
            "gold_drop_reason": self.gold_drop_reason,
            "in_gold": "true" if self.in_gold else "false",
            "record_id": self.record_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "source_path": self.source_path,
            "bucket_pool_size": self.bucket_pool_size,
            "review_snippet": self.review_snippet,
            "sense_bucket": self.sense_bucket,
            "homonym_check": self.homonym_check,
            "homonym_note": self.homonym_note,
            "gold_step_b_reasoning": self.gold_step_b_reasoning,
        }


def gold_frame_label(record: dict) -> str:
    if record.get("dropped"):
        return "DROPPED"
    step_b = record.get("step_b") or {}
    frame = step_b.get("selected_frame")
    return str(frame) if frame else "NONE"


def _context_key(text: str, *, width: int = 120) -> str:
    cleaned = " ".join(str(text or "").split()).lower()
    return cleaned[:width]


def load_gold_lookup(
    gold_path: str | Path | None = None,
) -> dict[str, GoldSummary]:
    """Index hand gold by record_id (values) plus context-prefix aliases."""
    from trifecta_annotation.gold_io import load_gold_records

    if gold_path is None:
        from data_io import resolve

        gold_path = Path(resolve("trifecta_gold")).parent / "gold.parquet"
    path = Path(gold_path).expanduser()
    if not path.exists():
        return {}

    lookup: dict[str, GoldSummary] = {}
    for record in load_gold_records(gold_path=path):
        prov = record.get("provenance") or {}
        rid = str(prov.get("record_id") or "").strip()
        if not rid:
            continue
        target = str(prov.get("target_word") or "")
        summary = GoldSummary(
            record_id=rid,
            target_word=target,
            target_norm=normalize_hist_dutch(target),
            text_regime=str((prov.get("text_regime") or "UNKNOWN")),
            gold_frame=gold_frame_label(record),
            drop_reason=str(record.get("drop_reason") or ""),
            step_b_reasoning=str((record.get("step_b") or {}).get("reasoning") or ""),
            context_text=str(prov.get("context_text") or ""),
        )
        lookup[rid] = summary
        ctx_key = f"{summary.target_norm}::{_context_key(summary.context_text)}"
        lookup.setdefault(ctx_key, summary)
    return lookup


def unique_gold_summaries(lookup: dict[str, GoldSummary]) -> list[GoldSummary]:
    seen: set[str] = set()
    out: list[GoldSummary] = []
    for summary in lookup.values():
        if summary.record_id in seen:
            continue
        seen.add(summary.record_id)
        out.append(summary)
    return out


def _infer_regime(
    *,
    filename: str,
    title: str,
    source_path: str | None,
) -> TextRegime:
    return infer_text_regime(
        corpus="cort_voc_db",
        title=title or None,
        source_path=source_path or filename or None,
    )


def _match_gold(
    record: KwicInput,
    gold_lookup: dict[str, GoldSummary],
) -> GoldSummary | None:
    if record.record_id in gold_lookup:
        return gold_lookup[record.record_id]
    ctx_key = f"{normalize_hist_dutch(record.target_word)}::{_context_key(record.context_text)}"
    if ctx_key in gold_lookup:
        return gold_lookup[ctx_key]
    target_norm = normalize_hist_dutch(record.target_word)
    for summary in gold_lookup.values():
        if summary.target_norm != target_norm:
            continue
        if summary.record_id == record.record_id:
            return summary
        if summary.context_text and summary.context_text[:80] in record.context_text:
            return summary
        if record.context_text[:80] in summary.context_text:
            return summary
    return None


def bucket_key_for(
    target_norm: str,
    regime: str,
    gold_frame: str,
) -> str:
    frame = gold_frame or "CORPUS"
    return f"{target_norm}|{regime}|{frame}"


def resolve_target_terms(
    *,
    targets: set[str] | None = None,
    polysemous: bool = True,
    gold_path: str | Path | None = None,
    gold_fixes_path: str | Path | None = None,
    include_gold_targets: bool = False,
) -> set[str]:
    """Normalized target lemmas to include in the gallery."""
    terms: set[str] = set()
    if polysemous:
        terms |= set(POLYSEMOUS_TARGETS)
    if targets:
        terms |= {normalize_hist_dutch(term) for term in targets if normalize_hist_dutch(term)}

    if gold_fixes_path:
        path = Path(gold_fixes_path).expanduser()
        if path.exists():
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
            if "target_word" in frame.columns:
                for raw in frame["target_word"]:
                    norm = normalize_hist_dutch(str(raw))
                    if norm:
                        terms.add(norm)

    if include_gold_targets and gold_path:
        for summary in unique_gold_summaries(load_gold_lookup(gold_path)):
            if summary.target_norm:
                terms.add(summary.target_norm)
    return terms


def collect_gallery_pool(
    *,
    targets: set[str],
    logical_name: str = "food_snippets_long",
    path: str | Path | pd.DataFrame | None = None,
    thesaurus_filter: bool = True,
    thesaurus_path: str | None = None,
    snippets_logical: str = "food_snippets",
    gold_lookup: dict[str, GoldSummary] | None = None,
) -> list[GalleryRow]:
    """All snippet rows for *targets*, tagged with regime and optional gold."""
    lookup = gold_lookup if gold_lookup is not None else {}
    titles = title_lookup_from_snippets(logical_name=snippets_logical)
    if isinstance(path, pd.DataFrame):
        frame = path
    else:
        frame = load_food_snippets_long_frame(logical_name=logical_name, path=path)
    if thesaurus_filter:
        food_lookup = resolve_thesaurus_lookup(thesaurus_path=thesaurus_path)
        frame = filter_long_snippets_frame(frame, food_lookup)

    frame = frame.copy()
    frame["_target_norm"] = frame["matched_term"].astype(str).map(normalize_hist_dutch)
    frame = frame[frame["_target_norm"].isin(targets)]

    rows: list[GalleryRow] = []
    seen_ids: set[str] = set()
    homonym_blank = empty_homonym_review_row()

    for _, raw in frame.iterrows():
        doc_id = str(raw.get("doc_id", ""))
        adaptation = adapt_food_snippet_long_row(raw, occurrence=0)
        record = adaptation.input_record
        if record is None or record.record_id in seen_ids:
            continue
        seen_ids.add(record.record_id)

        filename = str(raw.get("filename") or "")
        title = titles.get(filename, str(raw.get("title") or ""))
        regime = _infer_regime(
            filename=filename,
            title=title,
            source_path=record.source_path,
        )
        gold = _match_gold(record, lookup)
        gold_frame = gold.gold_frame if gold else ""
        bucket = bucket_key_for(
            normalize_hist_dutch(record.target_word),
            regime.value,
            gold_frame,
        )
        rows.append(
            GalleryRow(
                target_word=record.target_word,
                target_norm=normalize_hist_dutch(record.target_word),
                bucket_key=bucket,
                text_regime=regime.value,
                gold_frame=gold_frame,
                gold_drop_reason=gold.drop_reason if gold else "",
                in_gold=gold is not None,
                record_id=record.record_id,
                doc_id=doc_id,
                title=title,
                source_path=record.source_path or filename,
                bucket_pool_size=0,
                review_snippet=target_centered_snippet(
                    record.context_text,
                    record.target_word,
                ),
                sense_bucket="",
                homonym_check=homonym_blank["homonym_check"],
                homonym_note=homonym_blank["homonym_note"],
                gold_step_b_reasoning=gold.step_b_reasoning if gold else "",
            ),
        )

    # Pin gold rows that may use non-long record_ids (verb-seeded ids).
    if lookup:
        present_ids = {row.record_id for row in rows}
        for summary in unique_gold_summaries(lookup):
            if summary.target_norm not in targets:
                continue
            if summary.record_id in present_ids:
                continue
            regime_name = summary.text_regime or TextRegime.UNKNOWN.value
            bucket = bucket_key_for(summary.target_norm, regime_name, summary.gold_frame)
            rows.append(
                GalleryRow(
                    target_word=summary.target_word,
                    target_norm=summary.target_norm,
                    bucket_key=bucket,
                    text_regime=regime_name,
                    gold_frame=summary.gold_frame,
                    gold_drop_reason=summary.drop_reason,
                    in_gold=True,
                    record_id=summary.record_id,
                    doc_id=summary.record_id.split("__", 1)[0],
                    title="",
                    source_path=summary.record_id.split("__", 1)[0],
                    bucket_pool_size=0,
                    review_snippet=target_centered_snippet(
                        summary.context_text,
                        summary.target_word,
                    ),
                    sense_bucket="",
                    homonym_check=homonym_blank["homonym_check"],
                    homonym_note=homonym_blank["homonym_note"],
                    gold_step_b_reasoning=summary.step_b_reasoning,
                ),
            )
            present_ids.add(summary.record_id)

    return rows


def stratify_gallery(
    pool: list[GalleryRow],
    *,
    max_per_bucket: int = 3,
    seed: int = 0,
    pin_gold: bool = True,
) -> list[GalleryRow]:
    """Sample up to *max_per_bucket* corpus rows per bucket; always keep gold rows."""
    buckets: dict[str, list[GalleryRow]] = defaultdict(list)
    for row in pool:
        buckets[row.bucket_key].append(row)

    rng = random.Random(seed)
    selected: list[GalleryRow] = []
    for bucket_key, items in sorted(buckets.items()):
        gold_rows = [item for item in items if item.in_gold]
        corpus_rows = [item for item in items if not item.in_gold]
        rng.shuffle(corpus_rows)
        picked = list(gold_rows) if pin_gold else []
        remaining = max(0, max_per_bucket - len(picked))
        picked.extend(corpus_rows[:remaining])
        pool_size = len(items)
        for item in picked:
            selected.append(
                GalleryRow(
                    target_word=item.target_word,
                    target_norm=item.target_norm,
                    bucket_key=item.bucket_key,
                    text_regime=item.text_regime,
                    gold_frame=item.gold_frame,
                    gold_drop_reason=item.gold_drop_reason,
                    in_gold=item.in_gold,
                    record_id=item.record_id,
                    doc_id=item.doc_id,
                    title=item.title,
                    source_path=item.source_path,
                    bucket_pool_size=pool_size,
                    review_snippet=item.review_snippet,
                    sense_bucket=item.sense_bucket,
                    homonym_check=item.homonym_check,
                    homonym_note=item.homonym_note,
                    gold_step_b_reasoning=item.gold_step_b_reasoning,
                ),
            )

    selected.sort(
        key=lambda row: (
            row.target_norm,
            row.text_regime,
            row.gold_frame or "ZZZ",
            row.in_gold is False,
            row.record_id,
        ),
    )
    return selected


def gallery_summary(rows: list[GalleryRow]) -> dict[str, object]:
    by_target: dict[str, int] = defaultdict(int)
    by_bucket: dict[str, int] = defaultdict(int)
    gold_rows = 0
    for row in rows:
        by_target[row.target_norm] += 1
        by_bucket[row.bucket_key] += 1
        if row.in_gold:
            gold_rows += 1
    return {
        "rows": len(rows),
        "gold_rows": gold_rows,
        "targets": len(by_target),
        "buckets": len(by_bucket),
        "by_target": dict(sorted(by_target.items())),
    }
