"""Historic Dutch text normalization for thesaurus alias matching."""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

_long_s_map = str.maketrans({"ſ": "s"})
_lig_map = {"æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe"}


def normalize_hist_dutch(text: str) -> str:
    """Lowercase historic Dutch with long-s and ligature normalization."""
    t = unicodedata.normalize("NFKC", str(text))
    t = t.translate(_long_s_map)
    for key, value in _lig_map.items():
        t = t.replace(key, value)
    t = re.sub(r"[^a-zA-ZÀ-ÿ\s\-']", " ", t)
    t = re.sub(r"\-+", "-", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip().lower()


def normalize_series(values: pd.Series) -> pd.Series:
    """Vectorized wrapper — one normalize call per element, no Python row loops."""
    return values.fillna("").astype(str).map(normalize_hist_dutch)
