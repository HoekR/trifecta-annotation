"""Context heuristics for polysemous food targets and frame-verb homographs.

Keyword search surfaces homonyms (same spelling, different sense). Reviewers
mark disambiguation in review CSV columns ``homonym_check`` / ``homonym_note``
(see ``review_columns``). The rules below are optional hints for mining only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import TrifectaFrame

# Targets that frequently appear as non-food or non-practice senses in cort_voc.
POLYSEMOUS_TARGETS: frozenset[str] = frozenset(
    normalize_hist_dutch(term)
    for term in (
        "water",
        "boter",
        "brood",
        "bloem",
        "biet",
        "noot",
        "nood",
        "thee",
        "olie",
        "appel",
        "appelen",
        "gort",
        "honing",
        "wijn",
    )
)

# Frame verbs that often attach to a different object than the food target.
POLYSEMOUS_VERBS: frozenset[str] = frozenset(
    normalize_hist_dutch(term)
    for term in (
        "nuttigen",
        "houden",
        "maken",
        "breken",
        "genezen",
        "heelen",
        "smaken",
        "trekken",
    )
)

# Snippet-level: target is not a food-practice referent.
_NON_FOOD_TARGET_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # Trade / customs lists (boter, vleesch as export goods)
        r"\b(?:uitvoer|invoer|mondbehoeften|douane|accijns|tol)\b",
        r"\b(?:slijten|verkopen|vervoeren)\b.{0,40}\b(?:melk|boter|kaas|vleesch)\b",
        # Flood / navigation water
        r"\b(?:aanwas|dreigend|stijgend|overstrom)\w*\b.{0,50}\bwater\b",
        r"\b(?:buiten\s+boord|op\s+zee|aan\s+wal)\b.{0,60}\bwater\b",
        r"\blucht\s+en\s+water\b",
        # Dictionary / encyclopedia gloss
        r"\b(?:is\s+een|betekent|te\s+kennen|geneesmiddel|electuarie)\b",
        # Literary verb biet (offer/plead), not beet the vegetable
        r"\bvreucht\s+en\s+biet\b",
        r"\b(?:en\s+biet|niet\s+en\s+biet)\b",
    )
)

# Per-target negative patterns (non-food or wrong-frame sense).
_TARGET_NEGATIVE_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "biet": (
        re.compile(r"\b(?:vreucht|noeyt|noit)\s+en\s+biet\b", re.IGNORECASE),
        re.compile(r"\b(?:en\s+biet|biet\s+daer)\b", re.IGNORECASE),
    ),
    "water": (
        re.compile(r"\b(?:aanwas|dreigend)\b.{0,40}\bwater\b", re.IGNORECASE),
        re.compile(r"\bwater\s+vlier\b", re.IGNORECASE),  # plant name in materia medica list
        re.compile(r"\b(?:lucht|zee|rivier|gracht)\b.{0,30}\bwater\b", re.IGNORECASE),
    ),
    "boter": (
        re.compile(r"\b(?:uitvoer|invoer|mondbehoeften)\b", re.IGNORECASE),
        re.compile(r"\bnuttigen\s+arbeid\b", re.IGNORECASE),
        re.compile(r"\b(?:melk\s+en\s+boter)\b.{0,50}\bslijten\b", re.IGNORECASE),
    ),
    "brood": (
        re.compile(r"\b(?:wapen|sinnebeeld|bieken)\b", re.IGNORECASE),
    ),
    "bloem": (
        re.compile(r"\b(?:op\s+de\s+bloemen|op\s+de\s+roosen)\b", re.IGNORECASE),
    ),
    "noot": (
        re.compile(r"\bwatter\s+dient\b", re.IGNORECASE),
    ),
}

# Local window must show food-practice cues for the suggested frame.
_FRAME_POSITIVE_PATTERNS: dict[TrifectaFrame, tuple[re.Pattern[str], ...]] = {
    TrifectaFrame.COOKING_CREATION: tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\b(?:neem|neemt|doet|doe|leg|legg|week|kook|sied|bak|brad|meng|stam|klop|smor|stov|snij|hak|zeef|bind|pruttel)\w*\b",
            r"\b(?:in\s+de\s+pot|in\s+water|tot\s+het\s+gaar|wel\s+gaar)\b",
            r"\b(?:gersten\s+water|kooktse|weeken)\b",
        )
    ),
    TrifectaFrame.INGESTION: tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\b(?:eet|eten|eeten|drink|drinck|proef|smaak|slik|kauw|ontbijt|diner|maaltijd)\w*\b",
            r"\b(?:aan\s+tafel|te\s+drinken|te\s+eten|bij\s+het\s+ontbijt)\b",
            r"\b(?:als\s+thee\s+te\s+laten\s+trekken)\b",
        )
    ),
}

# Verb binds to a different object than the food target (nuttigen arbeid, etc.).
_VERB_MISATTACHMENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bnuttigen\s+(?:arbeid|werck|arbeidt)\b",
        r"\bhouden\s+(?:feest|bruylop|bruiloft|raad|vergader)\w*\b",
        r"\bmaken\s+(?:dreigend|aanwas|wallen|schan|bolwerk)\w*\b",
        r"\bgenezen\s+(?:met|door)\s+(?:laauw\s+)?water\b",
        r"\bheelen\s+(?:de\s+)?(?:maag|ziel|ziekte)\b",
    )
)


@dataclass(frozen=True)
class HomonymAssessment:
    target_norm: str
    risk: str  # low | medium | high
    food_practice_likely: bool
    reasons: tuple[str, ...] = ()
    local_snippet: str = ""


def _target_span(snippet: str, target_word: str) -> tuple[int, int] | None:
    lowered = snippet.lower()
    target = target_word.lower()
    match = re.search(rf"\b{re.escape(target)}\b", lowered)
    if match:
        return match.start(), match.end()
    match = re.search(re.escape(target), lowered)
    if match:
        return match.start(), match.end()
    return None


def local_context_window(
    snippet: str,
    target_word: str,
    *,
    radius: int = 100,
) -> str:
    span = _target_span(snippet, target_word)
    if span is None:
        return snippet[: radius * 2]
    start = max(0, span[0] - radius)
    end = min(len(snippet), span[1] + radius)
    return snippet[start:end]


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def assess_homonym_context(
    target_word: str,
    snippet: str,
    *,
    suggested_frame: TrifectaFrame | None = None,
    discovery_verb: str | None = None,
    window_radius: int = 100,
) -> HomonymAssessment:
    """Return homograph risk and whether local context supports food practice."""
    target_norm = normalize_hist_dutch(target_word)
    local = local_context_window(snippet, target_word, radius=window_radius)
    reasons: list[str] = []

    hit = _matches_any(snippet, _NON_FOOD_TARGET_PATTERNS)
    if hit:
        reasons.append(f"non_food_snippet:{hit[:40]}")

    for pattern in _TARGET_NEGATIVE_PATTERNS.get(target_norm, ()):
        match = pattern.search(snippet)
        if match:
            reasons.append(f"target_sense:{match.group(0)[:40]}")

    if discovery_verb:
        verb_norm = normalize_hist_dutch(discovery_verb)
        mis = _matches_any(snippet, _VERB_MISATTACHMENT_PATTERNS)
        if mis:
            reasons.append(f"verb_misattach:{mis[:40]}")
        if verb_norm in POLYSEMOUS_VERBS and mis:
            reasons.append("polysemous_verb_wrong_object")

    food_practice_likely = False
    if suggested_frame is not None:
        positive = _FRAME_POSITIVE_PATTERNS.get(suggested_frame, ())
        pos_hit = _matches_any(local, positive)
        if pos_hit:
            food_practice_likely = True
            reasons.append(f"frame_cue:{pos_hit[:30]}")
        elif target_norm not in POLYSEMOUS_TARGETS:
            # Non-polysemous foods: verb proximity elsewhere is enough
            food_practice_likely = True
            reasons.append("non_polysemous_target")

    if reasons and any(
        reason.startswith(prefix)
        for reason in reasons
        for prefix in ("non_food_snippet", "target_sense", "verb_misattach", "polysemous_verb")
    ):
        if not food_practice_likely:
            risk = "high"
        elif target_norm in POLYSEMOUS_TARGETS:
            risk = "medium"
        else:
            risk = "medium"
    elif target_norm in POLYSEMOUS_TARGETS and not food_practice_likely:
        risk = "medium"
    else:
        risk = "low"

    return HomonymAssessment(
        target_norm=target_norm,
        risk=risk,
        food_practice_likely=food_practice_likely,
        reasons=tuple(reasons),
        local_snippet=local,
    )


def homonym_blocks_clear_example(
    assessment: HomonymAssessment,
    *,
    allow_medium: bool = False,
) -> bool:
    """True when homograph risk is too high for auto-suggested silver/gold rows."""
    if assessment.risk == "high":
        return True
    if assessment.risk == "medium" and not allow_medium:
        return not assessment.food_practice_likely
    return False
