"""Genre-routed Step A/B sieve policy (PLAN.md §9i / DECISIONS 2026-11-06).

Collocation stays at harvest. Encoders sieve high-drop regimes. LLM remains
authoritative on survivors — especially RECIPE_PRACTICE / MEDICAL.
"""

from __future__ import annotations

import re
from typing import Any

from trifecta_annotation.text_regime import TextRegime

# Direct to LLM Step A — measured high Step A survival (§9i).
DIRECT_LLM_REGIMES: frozenset[TextRegime] = frozenset(
    {
        TextRegime.RECIPE_PRACTICE,
        TextRegime.MEDICAL,
    }
)

# Encoder keep/drop first (when a sieve model is loaded).
WEAK_REGIMES: frozenset[TextRegime] = frozenset(
    {
        TextRegime.LITERARY,
        TextRegime.TRAVEL,
        TextRegime.ADMIN_TRADE,
        TextRegime.SCIENTIFIC,
        TextRegime.UNKNOWN,
    }
)

KEEP_LABEL = "KEEP"
DROP_LABEL = "DROP"
KEEP_DROP_LABELS: list[str] = [KEEP_LABEL, DROP_LABEL]
KEEP_DROP_LABEL2ID: dict[str, int] = {label: idx for idx, label in enumerate(KEEP_DROP_LABELS)}
KEEP_DROP_ID2LABEL: dict[int, str] = {idx: label for label, idx in KEEP_DROP_LABEL2ID.items()}

# Entry-head cues that upgrade UNKNOWN → a direct-LLM regime (TEI scope).
_MEDICAL_HEAD = re.compile(
    r"\b("
    r"middel|middelen|tegens?|tegen|remedie|remedi[eë]n|ziekte|ziekten|"
    r"aamborstig|koorts|pijn|kwalen?|genees|heelt|heelen|apteek|apotheek|"
    r"pharmac|medic"
    r")\b",
    re.IGNORECASE,
)
_RECIPE_HEAD = re.compile(
    r"\b("
    r"kook|koek|keuken|recept|bereid|om\s+te\s+maken|om\s+te\s+bereiden|"
    r"manier\s+om|confituur|inmaken|pekel|zouten|rooken|droogen"
    r")\b",
    re.IGNORECASE,
)


def parse_regime(value: TextRegime | str | None) -> TextRegime | None:
    if value is None or value == "":
        return None
    if isinstance(value, TextRegime):
        return value
    try:
        return TextRegime(str(value))
    except ValueError:
        return None


def regime_from_tei_scope_head(scope_head: str | None) -> TextRegime | None:
    """Map a TEI entry scope/head to RECIPE or MEDICAL when cues are clear."""
    if not scope_head or not scope_head.strip():
        return None
    if _MEDICAL_HEAD.search(scope_head):
        return TextRegime.MEDICAL
    if _RECIPE_HEAD.search(scope_head):
        return TextRegime.RECIPE_PRACTICE
    return None


def routing_regime(
    *,
    text_regime: TextRegime | str | None,
    tei_scope_head: str | None = None,
) -> TextRegime:
    """Effective regime for sieve routing.

    UNKNOWN (or missing) may be upgraded from TEI entry scope; otherwise
    missing → UNKNOWN (weak path).
    """
    regime = parse_regime(text_regime) or TextRegime.UNKNOWN
    if regime is TextRegime.UNKNOWN:
        upgraded = regime_from_tei_scope_head(tei_scope_head)
        if upgraded is not None:
            return upgraded
    return regime


def needs_encoder_sieve(
    *,
    text_regime: TextRegime | str | None,
    tei_scope_head: str | None = None,
) -> bool:
    """True when this row should run the Step A keep/drop encoder before LLM A."""
    return routing_regime(text_regime=text_regime, tei_scope_head=tei_scope_head) in WEAK_REGIMES


def tei_scope_from_record(record: dict[str, Any]) -> str | None:
    """Prefer explicit tei_scope_head; fall back to structural_header."""
    for key in ("tei_scope_head", "structural_header"):
        value = record.get(key)
        if value:
            return str(value)
    provenance = record.get("provenance") or {}
    if isinstance(provenance, dict):
        for key in ("tei_scope_head", "structural_header"):
            value = provenance.get(key)
            if value:
                return str(value)
    return None
