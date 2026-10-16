"""Segment historical passages into remedy/recipe units and read their stated goal.

Measurement tool for the feasibility question in `plans/steps/` and PLAN.md §9d:
`CURE_Affliction` and `COOKING_CREATION_Food_Product` resist every extraction
method tried (§9b–§9d) because they are the *organizing concept* of the text —
a remedy is identified by what it treats, a recipe by what it makes — while the
pipeline enters through a food mention and tries to recover that concept from
one participant's local window.

So: can these passages be cut into units that each state a goal? This module
only measures; it changes nothing in the pipeline. Everything here is a
heuristic, and every unit records *which* cue opened it so the report can break
results down per signal rather than trusting any single pattern.

Observed structure in the corpus (checked against `food_snippets_long_kwic`,
not assumed): passages are flowing text, not line-broken, so unit cues are
sentence-initial patterns — ``Om <goal> te <verb>`` purpose headers, numbered
or roman section markers, ``Tegens de <affliction>``, and the CURE indication
constructions already in `frame_verbs.py`. Two cues (``Een ander``, ``Item``)
open a unit that *inherits* the previous unit's goal instead of stating its
own — the inheritance pattern this study exists to quantify.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from trifecta_annotation.frame_verbs import find_cure_indication_hits
from trifecta_annotation.normalize import normalize_hist_dutch

# Sentence-initial unit cues. Order matters only for reporting ties; overlapping
# hits are resolved by position then by this list's order.
_UNIT_CUE_PATTERNS: tuple[tuple[str, str], ...] = (
    # "67. Manieren van Stoven." / "XXX. Neemt een handvol Huisloock"
    (r"(?:(?<=^)|(?<=[.!?;:]\s)|(?<=[.!?;:]\s\s))\s*\d{1,3}\.\s+", "numbered"),
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*[IVXLC]{1,6}\.\s+", "roman"),
    # "Om den Wijn te beletten sijn kracht te verliesen." — purpose header
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*Om\s+(?=[^.!?]{3,120}?\bte\b)", "purpose_om"),
    # "Tegens de Dronckenschap." / "Voor de hoest"
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*(?:Tegen(?:s|)|Voor)\s+(?:de|den|het|'t|der|een)\b", "tegens"),
    # "Hulpmiddelen voor den Hik." — explicit remedy-section header
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*(?:Hulpmiddel(?:en)?|Remedie|Remedien|Middel(?:en)?)\s+(?:voor|tegen)\b", "remedy_header"),
    # "Een ander." / "Item," — opens a unit that inherits the previous goal
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*Een\s+ander\b", "inheritance"),
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*Item\b", "inheritance"),
)

_INHERITANCE_SIGNALS = frozenset({"inheritance"})

_COMPILED_CUES = tuple(
    (re.compile(pattern), kind) for pattern, kind in _UNIT_CUE_PATTERNS
)

# Goal NP boundaries: stop at punctuation, coordination, or a clause break.
_GOAL_STOP = re.compile(
    r"[.!?;:,]|\b(?:en|ende|of|maer|maar|dan|soo|zo|als|die|dat|want|om|te)\b",
    re.IGNORECASE,
)
_DETERMINERS = frozenset({"de", "den", "het", "t", "der", "des", "een", "eene", "eenen", "d"})
_MAX_GOAL_TOKENS = 5


@dataclass(frozen=True)
class UnitSpan:
    """One remedy/recipe unit: the cue that opened it, its header, its body."""

    start: int
    end: int
    signal: str
    header_start: int
    header_end: int
    inherits_goal: bool

    @property
    def header(self) -> str:
        return ""  # filled by helpers that hold the source text


@dataclass(frozen=True)
class GoalCandidate:
    """The goal NP named by a unit's header, if it states one."""

    text: str
    norm: str
    signal: str
    start: int
    end: int


def find_unit_signals(text: str) -> list[tuple[int, int, str]]:
    """Return (start, end, kind) for every sentence-initial unit cue, in order."""
    if not text or not text.strip():
        return []
    hits: list[tuple[int, int, str]] = []
    for pattern, kind in _COMPILED_CUES:
        for match in pattern.finditer(text):
            hits.append((match.start(), match.end(), kind))

    # CURE indication constructions ("goed voor", "krachtig tegen", ...) already
    # have gated detection in frame_verbs — reuse rather than re-pattern them.
    for hit in find_cure_indication_hits(text):
        hits.append((hit.start, hit.end, "indication"))

    hits.sort(key=lambda item: (item[0], item[1]))
    # Drop cues that start inside an earlier cue's match.
    deduped: list[tuple[int, int, str]] = []
    for start, end, kind in hits:
        if deduped and start < deduped[-1][1]:
            continue
        deduped.append((start, end, kind))
    return deduped


def find_unit_boundaries(text: str) -> list[UnitSpan]:
    """Cut *text* into units, one per detected cue (cue start → next cue start)."""
    signals = find_unit_signals(text)
    if not signals:
        return []
    units: list[UnitSpan] = []
    for index, (start, cue_end, kind) in enumerate(signals):
        end = signals[index + 1][0] if index + 1 < len(signals) else len(text)
        header_end = _header_end(text, cue_end, end)
        units.append(
            UnitSpan(
                start=start,
                end=end,
                signal=kind,
                header_start=start,
                header_end=header_end,
                inherits_goal=kind in _INHERITANCE_SIGNALS,
            )
        )
    return units


def _header_end(text: str, cue_end: int, unit_end: int) -> int:
    """Header runs from the cue to the end of its sentence (bounded)."""
    window = text[cue_end:unit_end]
    match = re.search(r"[.!?]", window)
    if match is None:
        return min(unit_end, cue_end + 160)
    return min(unit_end, cue_end + match.end())


def extract_unit_goal(text: str, unit: UnitSpan) -> GoalCandidate | None:
    """Read the goal NP out of *unit*'s header, or None if it states none.

    Inheritance units ("Een ander") state no goal by definition — the caller
    decides whether to carry the previous unit's goal forward.
    """
    if unit.inherits_goal:
        return None
    header = text[unit.header_start : unit.header_end]
    if not header.strip():
        return None

    if unit.signal == "purpose_om":
        span = _goal_after_om(header)
    elif unit.signal in {"tegens", "remedy_header", "indication"}:
        span = _goal_after_preposition(header)
    else:
        span = _goal_after_numbering(header)

    if span is None:
        return None
    rel_start, rel_end = span
    value = header[rel_start:rel_end].strip(" ,.;:'\"")
    if not value:
        return None
    return GoalCandidate(
        text=value,
        norm=normalize_hist_dutch(value),
        signal=unit.signal,
        start=unit.header_start + rel_start,
        end=unit.header_start + rel_start + len(value),
    )


def _goal_after_om(header: str) -> tuple[int, int] | None:
    """``Om <goal> te <verb>`` → the span between "Om" and "te"."""
    match = re.search(r"\bOm\b", header, flags=re.IGNORECASE)
    if match is None:
        return None
    rest_start = match.end()
    te = re.search(r"\bte\b", header[rest_start:], flags=re.IGNORECASE)
    if te is None:
        return None
    return rest_start, rest_start + te.start()


def _goal_after_preposition(header: str) -> tuple[int, int] | None:
    """``… voor/tegen <goal>`` → the NP following the preposition."""
    match = None
    for candidate in re.finditer(r"\b(?:voor|tegen|tegens|vo(?:o|e)r)\b", header, flags=re.IGNORECASE):
        match = candidate
    if match is None:
        return None
    return _np_after(header, match.end())


def _goal_after_numbering(header: str) -> tuple[int, int] | None:
    """``39. Ontlediging van een Schaapen-achterbout`` → the whole header NP."""
    stripped = re.match(r"\s*(?:\d{1,3}|[IVXLC]{1,6})\.\s*", header)
    offset = stripped.end() if stripped else 0
    return _np_after(header, offset, allow_determiner_only=True)


def _np_after(text: str, offset: int, *, allow_determiner_only: bool = False) -> tuple[int, int] | None:
    """Take up to _MAX_GOAL_TOKENS tokens from *offset*, stopping at a boundary."""
    rest = text[offset:]
    stop = _GOAL_STOP.search(rest)
    chunk = rest[: stop.start()] if stop else rest

    tokens = list(re.finditer(r"[A-Za-zÀ-ÿſ][A-Za-zÀ-ÿſ'\-]*", chunk))
    if not tokens:
        return None
    kept: list[re.Match[str]] = []
    for token in tokens:
        if len(kept) >= _MAX_GOAL_TOKENS:
            break
        norm = normalize_hist_dutch(token.group(0))
        if not kept and norm in _DETERMINERS:
            if not allow_determiner_only:
                continue  # skip a leading determiner, keep looking for the head
        kept.append(token)
    if not kept:
        return None
    return offset + kept[0].start(), offset + kept[-1].end()


def unit_for_position(units: list[UnitSpan], position: int) -> UnitSpan | None:
    """The unit containing *position*, if any."""
    for unit in units:
        if unit.start <= position < unit.end:
            return unit
    return None


def goal_with_inheritance(text: str, units: list[UnitSpan], index: int) -> GoalCandidate | None:
    """Goal for ``units[index]``, carrying forward across inheritance units.

    "Een ander." means "another remedy for the same thing", so its goal is the
    nearest preceding unit that states one — the discourse-level inheritance
    this study is measuring.

    **Two warnings for anyone scoring or analysing with this.** Propagating one
    header's goal across every unit under it (a chapter headed "Remedies voor
    de hik" covering 40 remedies):

    1. *Inflates evaluation trivially.* The label becomes constant within the
       chapter, so per-row accuracy on that field rises without anything being
       extracted. Score propagation per *unit-group*, not per row — this is the
       same family of trap as the trivial-no-answer inflation in PLAN.md §9b and
       the presence-threshold inflation in §9d.
    2. *Changes what the annotation means.* Per-mention "this remedy treats X"
       becomes per-chapter "this chapter is about X". For counts and trends that
       is a 40-fold over-count of a single stated affliction, so a propagated
       value must be marked as inherited rather than stated before it reaches
       any analysis export.
    """
    for back in range(index, -1, -1):
        goal = extract_unit_goal(text, units[back])
        if goal is not None:
            return goal
    return None
