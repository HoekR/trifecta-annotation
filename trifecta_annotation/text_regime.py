"""Text-regime (genre) inference for stratified TRIFECTA annotation."""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field


class TextRegime(str, Enum):
    """Discourse type of the source document (Layer 0)."""

    RECIPE_PRACTICE = "RECIPE_PRACTICE"
    MEDICAL = "MEDICAL"
    TRAVEL = "TRAVEL"
    LITERARY = "LITERARY"
    ADMIN_TRADE = "ADMIN_TRADE"
    SCIENTIFIC = "SCIENTIFIC"
    UNKNOWN = "UNKNOWN"


_CORPUS_REGIME: dict[str, TextRegime] = {
    "voc_recipes": TextRegime.RECIPE_PRACTICE,
    "recipe_web": TextRegime.RECIPE_PRACTICE,
}

# First match wins; recipe before literary (overlap in titles).
_TITLE_PATTERNS: list[tuple[TextRegime, re.Pattern[str]]] = [
    (
        TextRegime.RECIPE_PRACTICE,
        re.compile(
            r"recept|koek|kook|keuken|huishoud|displegt|culin|bakker|"
            r"spys|toespys|heerl(?:ijk|yke)\s+konst|smaak|keuken",
            re.IGNORECASE,
        ),
    ),
    (
        TextRegime.MEDICAL,
        re.compile(
            r"pharm|medic|chirurg|apotheek|heelk|genees|ziekte|chir\b",
            re.IGNORECASE,
        ),
    ),
    (
        TextRegime.TRAVEL,
        re.compile(
            r"reis|reisiger|geograph|tartarye|amerika|oost[\s-]?ind|west[\s-]?ind|"
            r"zeevaart|scheep|voyage|landen\s+van",
            re.IGNORECASE,
        ),
    ),
    (
        TextRegime.ADMIN_TRADE,
        re.compile(
            r"marchand|handel|koopman|comptoir|compagnie|staten|ordonnant|"
            r"dialog.*marchand",
            re.IGNORECASE,
        ),
    ),
    (
        TextRegime.SCIENTIFIC,
        re.compile(
            r"natuurk|natuurlyke\s+historie|encyclop|botan|historie\s+van\s+d",
            re.IGNORECASE,
        ),
    ),
    (
        TextRegime.LITERARY,
        re.compile(
            r"letteroefen|vermaak|verhaal|roman|dicht|blijspel|tijdspiegel|"
            r"huisvriend|juffertje|tooneel|boeck\s+van",
            re.IGNORECASE,
        ),
    ),
]


def infer_text_regime(
    *,
    corpus: str | None = None,
    title: str | None = None,
    source_path: str | None = None,
    text_regime: str | TextRegime | None = None,
) -> TextRegime:
    """Infer document regime from corpus id and/or source metadata."""
    if text_regime is not None and str(text_regime).strip():
        try:
            return TextRegime(str(text_regime).strip())
        except ValueError:
            pass

    corpus_key = (corpus or "").strip().lower()
    if corpus_key in _CORPUS_REGIME:
        return _CORPUS_REGIME[corpus_key]

    haystack = " ".join(
        part for part in (title or "", source_path or "") if part
    ).strip()
    if not haystack:
        return TextRegime.UNKNOWN

    for regime, pattern in _TITLE_PATTERNS:
        if pattern.search(haystack):
            return regime
    return TextRegime.UNKNOWN


class TextRegimeContext(BaseModel):
    """Layer-0 metadata carried on KWIC / gold rows."""

    text_regime: TextRegime = Field(default=TextRegime.UNKNOWN)
    title: str | None = None
