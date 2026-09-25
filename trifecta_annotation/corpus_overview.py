"""Build a catalogue of cort_voc source texts (filename, title, regime, counts)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.text_regime import TextRegime, infer_text_regime

OVERVIEW_COLUMNS = [
    "filename",
    "title",
    "text_regime",
    "snippet_rows",
    "distinct_doc_ids",
    "gold_rows",
    "in_gold",
]


def _gold_counts_from_csv(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    counts: dict[str, int] = {}
    for row in frame.to_dict(orient="records"):
        if str(row.get("labelled", "")).lower() != "true":
            continue
        source = str(row.get("source_path") or "").strip()
        if source:
            counts[source] = counts.get(source, 0) + 1
    return counts


def _gold_counts_from_parquet(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    frame = pd.read_parquet(path)
    counts: dict[str, int] = {}
    for raw in frame.get("annotation_json", []):
        data = json.loads(raw) if isinstance(raw, str) else raw
        source = str((data.get("provenance") or {}).get("source_path") or "").strip()
        if source:
            counts[source] = counts.get(source, 0) + 1
    return counts


def build_corpus_overview(
    *,
    snippets_path: str | Path | None = None,
    gold_csv_path: str | Path | None = None,
    gold_parquet_path: str | Path | None = None,
) -> pd.DataFrame:
    """Aggregate one row per source file from ``food_snippets`` (+ optional gold counts)."""
    snippets_path = Path(snippets_path or resolve("food_snippets"))
    frame = pd.read_csv(
        snippets_path,
        dtype=str,
        usecols=["filename", "title", "snippet", "doc_id"],
    )
    frame["filename"] = frame["filename"].astype(str).str.strip()
    frame = frame[frame["filename"].ne("")]

    grouped = (
        frame.groupby("filename", as_index=False)
        .agg(
            title=("title", "first"),
            snippet_rows=("snippet", "count"),
            distinct_doc_ids=("doc_id", "nunique"),
        )
    )

    grouped["text_regime"] = grouped.apply(
        lambda row: infer_text_regime(
            corpus="cort_voc_db",
            title=str(row["title"] or ""),
            source_path=str(row["filename"] or ""),
        ).value,
        axis=1,
    )

    gold_counts: dict[str, int] = {}
    if gold_csv_path is not None:
        gold_counts = _gold_counts_from_csv(Path(gold_csv_path))
    elif gold_parquet_path is not None:
        gold_counts = _gold_counts_from_parquet(Path(gold_parquet_path))
    else:
        scratch = Path(resolve("trifecta_gold")).parent
        merged = scratch / "gold_labelling_all.csv"
        parquet = Path(resolve("trifecta_gold"))
        if merged.exists():
            gold_counts = _gold_counts_from_csv(merged)
        elif parquet.exists():
            gold_counts = _gold_counts_from_parquet(parquet)

    grouped["gold_rows"] = grouped["filename"].map(gold_counts).fillna(0).astype(int)
    grouped["in_gold"] = grouped["gold_rows"].gt(0)
    return grouped.reindex(columns=OVERVIEW_COLUMNS).sort_values(
        ["text_regime", "title", "filename"],
        kind="stable",
    )


def overview_summary(frame: pd.DataFrame) -> dict[str, object]:
    """Counts for logging / ``--summary``."""
    by_regime = (
        frame["text_regime"]
        .value_counts()
        .sort_index()
        .to_dict()
    )
    return {
        "works": len(frame),
        "snippet_rows": int(frame["snippet_rows"].sum()),
        "gold_rows": int(frame["gold_rows"].sum()),
        "works_in_gold": int(frame["in_gold"].sum()),
        "by_regime": by_regime,
        "unknown_works": int((frame["text_regime"] == TextRegime.UNKNOWN.value).sum()),
    }
