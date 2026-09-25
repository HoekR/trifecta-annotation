"""Match annotation context text back to cort_voc food_snippets metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.text_regime import TextRegime, infer_text_regime

_WS_RE = re.compile(r"\s+")


def normalize_snippet_text(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip())


@dataclass(frozen=True)
class SnippetMatch:
    doc_id: str
    filename: str
    title: str
    text_regime: TextRegime
    matched_term: str | None = None


@lru_cache(maxsize=1)
def _snippet_lookup_frame() -> pd.DataFrame:
    """Wide food_snippets, one row per distinct snippet text."""
    path = Path(resolve("food_snippets"))
    frame = pd.read_csv(
        path,
        dtype=str,
        usecols=["doc_id", "filename", "title", "snippet"],
    )
    frame["snippet_norm"] = frame["snippet"].map(normalize_snippet_text)
    frame = frame[frame["snippet_norm"].ne("")]
    return frame.drop_duplicates("snippet_norm", keep="first").reset_index(drop=True)


def lookup_snippet_metadata(
    context_text: str,
    *,
    frame: pd.DataFrame | None = None,
) -> SnippetMatch | None:
    """
    Resolve a KWIC / INCEpTION line to cort_voc snippet metadata.

    Tries exact snippet match first, then shortest containing snippet.
    """
    text = normalize_snippet_text(context_text)
    if len(text) < 12:
        return None

    pool = frame if frame is not None else _snippet_lookup_frame()

    exact = pool.loc[pool["snippet_norm"] == text]
    if not exact.empty:
        return _row_to_match(exact.iloc[0])

    pattern = re.escape(text)
    hits = pool.loc[pool["snippet_norm"].str.contains(pattern, na=False, regex=True)]
    if hits.empty:
        return None

    best = hits.assign(_len=hits["snippet_norm"].str.len()).sort_values("_len").iloc[0]
    return _row_to_match(best)


def _row_to_match(row: pd.Series) -> SnippetMatch:
    filename = str(row.get("filename") or "").strip()
    title = str(row.get("title") or "").strip()
    return SnippetMatch(
        doc_id=str(row.get("doc_id") or "").strip(),
        filename=filename,
        title=title,
        text_regime=infer_text_regime(
            corpus="cort_voc_db",
            title=title,
            source_path=filename,
        ),
        matched_term=None,
    )
