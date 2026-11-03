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
from collections import Counter
from dataclasses import dataclass
from typing import Any

from trifecta_annotation.embedding_candidates import _sentence_spans
from trifecta_annotation.frame_verbs import find_cure_indication_hits
from trifecta_annotation.normalize import normalize_hist_dutch

# Sentence-initial unit cues. Order matters only for reporting ties; overlapping
# hits are resolved by position then by this list's order.
_UNIT_CUE_PATTERNS: tuple[tuple[str, str], ...] = (
    # "67. Manieren van Stoven." / "XXX. Neemt een handvol Huisloock"
    (r"(?:(?<=^)|(?<=[.!?;:]\s)|(?<=[.!?;:]\s\s))\s*\d{1,3}\.\s+", "numbered"),
    # Two or more numerals: a single "I."/"C."/"O." is as often an alphabetical
    # divider in a dictionary as a section number, and matching those inflated
    # `Nederlandtsche woorden-schat` to the highest cue density in the corpus.
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*[IVXLC]{2,6}\.\s+", "roman"),
    # "Om den Wijn te beletten sijn kracht te verliesen." — purpose header
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*Om\s+(?=[^.!?]{3,120}?\bte\b)", "purpose_om"),
    # "Tegens de Dronckenschap." / "Voor de hoest"
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*(?:Tegen(?:s|)|Voor)\s+(?:de|den|het|'t|der|een)\b", "tegens"),
    # "Hulpmiddelen voor den Hik." — explicit remedy-section header
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*(?:Hulpmiddel(?:en)?|Remedie|Remedien|Middel(?:en)?)\s+(?:voor|tegen)\b", "remedy_header"),
    # "Een ander." / "Item," — opens a unit that inherits the previous goal
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*Een\s+ander\b", "inheritance"),
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*Item\b", "inheritance"),
    # "Emplastrum Meliloti." / "Oleum Ovorum." — pharmacopoeia entries are headed
    # by a Latin preparation name, not by an affliction or a dish. Without this,
    # formularies look completely unstructured (Pharmacopoea scored 0.0 cues/10k)
    # even though they are rigidly organised. Note the goal here is the
    # *preparation*, with the affliction stated in the body as an indication —
    # the inverse of the remedy-collection layout. See PLAN.md §9e.
    (
        r"(?:(?<=^)|(?<=[.!?;:]\s))\s*(?:Emplastrum|Syrupus|Unguentum|Pulvis|Pulveres|"
        r"Aqua|Oleum|Olea|Tinctura|Spiritus|Decoctum|Electuarium|Conserva|Species|"
        r"Elixir|Balsamum|Extractum|Trochisci|Pilulae|Linimentum|Essentia)\s+[A-Z][a-z]+",
        "latin_preparation",
    ),
)

_INHERITANCE_SIGNALS = frozenset({"inheritance"})

# English receipt/remedy books use the same organising structure with different
# wording — "CUCUMBER SOOP." (all-caps product title) or "To make ONION SOOP."
# followed by a "Take ..." ingredient body, and "Another"/"The same" as the
# inheritance marker. Kept as a separate cue set so the Dutch path is untouched
# and the two languages can be measured identically for comparison.
_UNIT_CUE_PATTERNS_EN: tuple[tuple[str, str], ...] = (
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*\d{1,3}\.\s+", "numbered"),
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*[IVXLC]{2,6}\.\s+", "roman"),
    # "To make ONION SOOP." / "To preserve cherries" / "To cure a cough"
    (
        r"(?:(?<=^)|(?<=[.!?;:]\s))\s*To\s+(?:make|preserve|cure|dress|boil|roast|bake|stew|"
        r"pickle|keep|candy|dry|fry|prepare|remedy)\b",
        "purpose_to",
    ),
    # "A remedy for the ague." / "Receipt for cramp"
    (
        r"(?:(?<=^)|(?<=[.!?;:]\s))\s*(?:An?\s+)?(?:remedy|receipt|recipe|cure|medicine)\s+"
        r"(?:for|against)\b",
        "remedy_header",
    ),
    # "For the hiccough." / "Against worms."
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*(?:For|Against)\s+(?:the|a|an)\b", "tegens"),
    # "Another." / "The same." / "Ditto."
    (r"(?:(?<=^)|(?<=[.!?;:]\s))\s*(?:Another|The\s+same|Ditto)\b", "inheritance"),
    # "CUCUMBER SOOP." — an all-caps product title (two+ caps words, or one long one)
    (
        r"(?:(?<=^)|(?<=[.!?;:]\s))\s*(?:[A-Z][A-Z'&-]{2,}\s+){1,5}[A-Z][A-Z'&-]{2,}\s*\.",
        "caps_title",
    ),
)

_COMPILED_CUES = tuple(
    (re.compile(pattern), kind) for pattern, kind in _UNIT_CUE_PATTERNS
)
_COMPILED_CUES_EN = tuple(
    (re.compile(pattern), kind) for pattern, kind in _UNIT_CUE_PATTERNS_EN
)


def _cue_set(language: str) -> tuple[tuple[re.Pattern[str], str], ...]:
    return _COMPILED_CUES_EN if language.lower().startswith("en") else _COMPILED_CUES

# Goal NP boundaries: stop at punctuation, coordination, or a clause break.
_GOAL_STOP = re.compile(
    r"[.!?;:,]|\b(?:en|ende|of|maer|maar|dan|soo|zo|als|die|dat|want|om|te)\b",
    re.IGNORECASE,
)
_DETERMINERS = frozenset({"de", "den", "het", "t", "der", "des", "een", "eene", "eenen", "d"})
_MAX_GOAL_TOKENS = 5

# Dutch compounds solidly, so a dish name can be "absent" from its own body on a
# literal token test while its parts are plainly there: "Komkommersla" vs a body
# saying "komkommers" and "sla". A prefix match separates that orthographic case
# from genuine lexical opacity ("blancmengier", "bruwet", which have no
# recoverable relation to the ingredients at all). Length 6 keeps the prefix
# long enough not to collide across unrelated words.
_COMPOUND_PREFIX_LEN = 6


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


def find_unit_signals(text: str, *, language: str = "nl") -> list[tuple[int, int, str]]:
    """Return (start, end, kind) for every sentence-initial unit cue, in order."""
    if not text or not text.strip():
        return []
    hits: list[tuple[int, int, str]] = []
    for pattern, kind in _cue_set(language):
        for match in pattern.finditer(text):
            hits.append((match.start(), match.end(), kind))

    # CURE indication constructions ("goed voor", "krachtig tegen", ...) already
    # have gated detection in frame_verbs — reuse rather than re-pattern them.
    # Dutch-only by construction.
    if not language.lower().startswith("en"):
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


def find_unit_boundaries(text: str, *, language: str = "nl") -> list[UnitSpan]:
    """Cut *text* into units, one per detected cue (cue start → next cue start)."""
    signals = find_unit_signals(text, language=language)
    if not signals:
        return []
    units: list[UnitSpan] = []
    for index, (start, cue_end, kind) in enumerate(signals):
        end = signals[index + 1][0] if index + 1 < len(signals) else len(text)
        # A caps title cue already consumes its own terminating period, so the
        # header is exactly the cue — extending to the next period would swallow
        # the first body sentence and corrupt the body/header split.
        header_end = cue_end if kind == "caps_title" else _header_end(text, cue_end, end)
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
    elif unit.signal == "purpose_to":
        span = _goal_after_to_verb(header)
    elif unit.signal == "caps_title":
        span = _goal_from_caps_title(header)
    elif unit.signal == "latin_preparation":
        span = _np_after(header, 0, allow_determiner_only=True)
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


def _goal_after_to_verb(header: str) -> tuple[int, int] | None:
    """``To make ONION SOOP`` → the NP after the infinitive verb."""
    match = re.search(
        r"\bTo\s+(?:make|preserve|cure|dress|boil|roast|bake|stew|pickle|keep|candy|dry|fry|prepare|remedy)\b",
        header,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    return _np_after(header, match.end(), allow_determiner_only=False)


def _goal_from_caps_title(header: str) -> tuple[int, int] | None:
    """``CUCUMBER SOOP.`` → the title itself is the goal."""
    return _np_after(header, 0, allow_determiner_only=True)


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


def goal_body_reachability(text: str, *, language: str = "nl") -> dict[str, int]:
    """Per unit: is the header's goal reachable from the unit's own body?

    Computed identically for Dutch and English so the structural claim can be
    compared across languages (and therefore across traditions) rather than
    only within the Dutch corpus that produced it. Counts units, not documents.

    Reported for two token choices, because they diverge sharply by language:
    English receipt titles are compositional ("CUCUMBER SOOP" = ingredient +
    dish type), so the *first* token is an ingredient that recurs in the body,
    while the *head* noun ("soop") may not. Middle Dutch titles are often
    opaque dish names ("blancmengier", "bruwet") where neither appears. Picking
    one token silently decides the answer, so both are counted.
    """
    units = find_unit_boundaries(text, language=language)
    counts = {
        "units": len(units),
        "with_goal": 0,
        "inherited": 0,
        "first_token_in_body": 0,
        "first_token_absent": 0,
        "head_token_in_body": 0,
        "head_token_absent": 0,
        # Of the head-token absences, how many are only absent because Dutch
        # compounds solidly (parts present) vs genuinely unrecoverable.
        "head_absent_compound_recoverable": 0,
        "head_absent_truly": 0,
    }
    for unit in units:
        if unit.inherits_goal:
            counts["inherited"] += 1
            continue
        goal = extract_unit_goal(text, unit)
        if goal is None:
            continue
        counts["with_goal"] += 1
        body_norm = normalize_hist_dutch(text[unit.header_end : unit.end])
        tokens = goal.norm.split()
        if not tokens:
            continue
        if tokens[0] in body_norm:
            counts["first_token_in_body"] += 1
        else:
            counts["first_token_absent"] += 1
        head = tokens[-1]
        if head in body_norm:
            counts["head_token_in_body"] += 1
        else:
            counts["head_token_absent"] += 1
            if len(head) >= _COMPOUND_PREFIX_LEN and head[:_COMPOUND_PREFIX_LEN] in body_norm:
                counts["head_absent_compound_recoverable"] += 1
            else:
                counts["head_absent_truly"] += 1
    return counts


def document_unit_profile(text: str, *, language: str = "nl") -> dict[str, Any]:
    """Structural features of a document: cue density and signal mix.

    Intended to be computed at ingestion (while the full document is still
    available) and stored on the record, since unit structure cannot be measured
    from a stored KWIC snippet.

    **This is a diagnostic feature, not a genre classifier.** It was tried as one
    and it does not work — measured on the 61 works in `food_snippets_long_kwic`:

    - *False positive:* `Nederlandtsche woorden-schat`, a word-list, has the
      highest density in the whole corpus (24.2 cues/10k) because dictionary
      entries trip the same cues. A trade-dialogue book scores 6.1.
    - *False negative:* `Pharmacopoea Amstelredamensis`, a genuine remedy
      formulary, scored 0.0 before the `latin_preparation` cue existed.
    - *Not comparable across genres:* a cookbook runs ~16 short recipes per 10k
      chars, a formulary ~1-3 long preparations, so no single density threshold
      separates them.

    Use it to describe structure within a known genre, and take the genre from
    `text_regime` (which carries explicit per-work overrides) instead of trying
    to derive it from these numbers.
    """
    units = find_unit_boundaries(text, language=language)
    chars = len(text)
    signals = Counter(unit.signal for unit in units)
    return {
        "chars": chars,
        "units": len(units),
        "units_per_10k_chars": round(len(units) / (chars / 10000), 2) if chars else 0.0,
        "inherited_units": sum(1 for unit in units if unit.inherits_goal),
        "signals": dict(signals.most_common()),
        "dominant_signal": signals.most_common(1)[0][0] if signals else None,
    }


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


@dataclass(frozen=True)
class TargetSentence:
    """The sentence inside a KWIC window that actually contains the target word.

    `context_text` is a ~180-char window cut around `target_word`, routinely
    starting or ending mid-sentence (see PLAN.md §9e and the docstring at the
    top of this module). A "sentence" deliverable needs the target's own
    sentence carved out of that window, not the raw window — but the window
    edge is not the sentence's real edge, so callers need to know when a
    boundary was cut off rather than silently treat a half-sentence as whole.
    """

    text: str
    start: int
    end: int
    truncated_left: bool
    truncated_right: bool


def target_sentence(context_text: str, target_word: str) -> TargetSentence | None:
    """The sentence in *context_text* containing *target_word*'s first hit.

    Reuses `embedding_candidates._sentence_spans` rather than a third splitter.
    Returns None if *target_word* is not found at all (gold `lexical_unit`
    sometimes paraphrases rather than quoting, in which case there is no
    literal span to anchor a sentence on).
    """
    if not context_text or not target_word:
        return None
    match = re.search(re.escape(target_word), context_text, flags=re.IGNORECASE)
    if match is None:
        return None
    spans = _sentence_spans(context_text)
    for start, end in spans:
        if start <= match.start() < end:
            # The window carries no "start of text" marker to compare against,
            # so truncation is judged by position: a sentence that begins
            # exactly at char 0 or ends exactly at the window's last char is
            # indistinguishable from one that was cut there by the KWIC radius.
            truncated_left = start == 0
            truncated_right = end == len(context_text)
            text = context_text[start:end].strip()
            if not text:
                return None
            return TargetSentence(
                text=text, start=start, end=end,
                truncated_left=truncated_left, truncated_right=truncated_right,
            )
    return None
