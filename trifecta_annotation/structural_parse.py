"""Document-level structural parse, the production counterpart to the
feasibility measurements in `unit_segmentation.py`/`scripts/measure_unit_feasibility.py`.

Implements the "2-way search" design (PLAN.md, "Document-level structural
parse as a pre-Step-A stage"): a KWIC mention is still found by a forward scan
over the whole document (unchanged, done by each ingestion script's own term
scan). This module adds the *backward* half — given a mention's char offset,
look up the structural unit (header + extent) that governs it — plus a
trust/abstention gate so an ingestion script can tell a confidently-headed
unit from a merely-detected one.

Deliberately a thin production wrapper around `unit_segmentation.py`'s
existing, already-measured primitives (`find_unit_boundaries`,
`extract_unit_goal`, `goal_with_inheritance`, `unit_for_position`) rather than
a rewrite — that module stays a pure measurement tool per its own docstring.

Precision over recall: `goal_trusted=False` is the default outcome for any
cue type or inheritance depth not already validated by
`scripts/measure_unit_feasibility.py`'s measurements A/B/F. An ingestion
script seeing `goal_trusted=False` should behave exactly as it does today
(fixed-radius window, no structural fields populated) rather than guess.

**Callers must apply the genre gate themselves before calling this function**
(PLAN.md §2: RECIPE_PRACTICE primarily). The per-cue-type precision figures
this module trusts (`_TRUSTED_GOAL_SIGNALS`) were measured on recipe-
collection text (`voc_recipes`) and do not hold on running/narrative text —
confirmed directly: run against Jacob van Lennep's 1823 travel diary
(447k chars of pure narrative) and 11 of 14 detected units come back
`goal_trusted=True` on the *exact same* cue types ("Om ... te", "Voor/Tegen
...") that are reliable in a recipe collection, because ordinary Dutch prose
uses the same phrasing incidentally. This module has no way to tell "a real
recipe header" from "a sentence that happens to start with Om" on its own —
that's what the genre gate is for, and it must be checked upstream, not here.
"""

from __future__ import annotations

from dataclasses import dataclass

from trifecta_annotation.unit_segmentation import (
    UnitSpan,
    extract_unit_goal,
    find_unit_boundaries,
    goal_with_inheritance,
)

# Cue types measurement A (voc_recipes boundary precision/recall) and
# measurement B/E (goal-reachability) have actually exercised with an
# acceptable precision figure on record. `numbered`/`roman`/`indication` are
# excluded: numbered/roman headers routinely name a chapter, not a recipe
# goal (the "Hoofdstuk" mismatch in PLAN.md §9f), and `indication` is the
# CURE-affliction cue, not a product/goal cue, so trusting it for a
# product-side goal repeats the §9f "wrong cue fired" failure mode.
_TRUSTED_GOAL_SIGNALS = frozenset(
    {"purpose_om", "purpose_to", "remedy_header", "tegens", "caps_title", "latin_preparation"}
)

# Document-level density gate, found necessary by direct inspection on real
# ingestion documents (not synthetic voc_recipes): a RECIPE_PRACTICE-tagged
# document can still be mostly non-recipe prose (front matter, verse) with
# only a handful of incidental cue matches. On `_ams007amst01` ("De
# Amsterdamsze gaare-keuken", genre-gated RECIPE_PRACTICE, 110,751 chars),
# density was 0.36 units/10k chars and both "trusted" hits were wrong — lines
# of verse ("Voor de geen die ik bemin...", "Om daer te Trouwen zo 't
# behoort...") that happen to start with a trusted cue phrase, not recipe
# headers. That figure is statistically indistinguishable from the Van
# Lennep 1823 travel diary's 0.31 units/10k (a confirmed pure-narrative
# negative control, out of genre scope entirely). By contrast the three
# formulary-style documents that inspected cleanly on real text all have much
# higher density: `_pha002phar01` 6.8/10k (92/92 trusted, all genuine Latin
# preparation names), `krie024bata02` 15.7/10k, `verb122chir01` 11.0/10k.
# A per-unit cue-type check alone cannot tell a real header from an
# incidental phrase match in a sparse, low-structure stretch of a document —
# this gate adds that missing signal at the document level. Threshold set
# comfortably above the ~0.3-0.4/10k negative-control band and comfortably
# below the 6.8+/10k band genuinely-structured documents showed.
_MIN_TRUSTED_DENSITY_PER_10K = 2.0


@dataclass(frozen=True)
class DocumentUnit:
    """One structural unit of a document, with a trust/abstention verdict.

    `goal_text`/`goal_trusted` are deliberately separate from `header_text`:
    a unit can be confidently *detected* (a real boundary exists) while its
    goal extraction is not yet trusted — in that case `header_text` is still
    populated (always safe, diagnostic) but `goal_text` is None.
    """

    unit_id: str
    start: int
    end: int
    header_start: int
    header_end: int
    header_text: str
    signal: str
    inherits_goal: bool
    goal_text: str | None
    goal_trusted: bool
    goal_inherited: bool


def document_structural_units(text: str, *, language: str = "nl") -> list[DocumentUnit]:
    """Parse *text* into trust-gated structural units. No LLM calls.

    One call per source document, before any KWIC windowing — see
    `scan_text`'s `units` parameter in `scripts/build_colonial_kwic.py` for
    the ingestion-side half of the 2-way search.
    """
    spans = find_unit_boundaries(text, language=language)
    density = (len(spans) / (len(text) / 10_000)) if text else 0.0
    dense_enough = density >= _MIN_TRUSTED_DENSITY_PER_10K
    units: list[DocumentUnit] = []
    for index, span in enumerate(spans):
        goal_text, goal_trusted, goal_inherited = _resolve_goal(text, spans, index, span)
        goal_trusted = goal_trusted and dense_enough
        if not goal_trusted:
            goal_text = None
        units.append(
            DocumentUnit(
                unit_id=f"u{index}",
                start=span.start,
                end=span.end,
                header_start=span.header_start,
                header_end=span.header_end,
                header_text=text[span.header_start : span.header_end].strip(),
                signal=span.signal,
                inherits_goal=span.inherits_goal,
                goal_text=goal_text,
                goal_trusted=goal_trusted,
                goal_inherited=goal_inherited,
            )
        )
    return units


def _resolve_goal(
    text: str, spans: list[UnitSpan], index: int, span: UnitSpan
) -> tuple[str | None, bool, bool]:
    if span.inherits_goal:
        candidate = goal_with_inheritance(text, spans, index)
        if candidate is None:
            return None, False, False
        # An inherited goal is only as trustworthy as the unit it inherited
        # from — re-check that unit's own signal, not the inheriting unit's
        # ("Een ander"/"Item") signal, which carries no goal cue of its own.
        source_index = next(
            (i for i in range(index, -1, -1) if extract_unit_goal(text, spans[i]) is not None),
            None,
        )
        source_signal = spans[source_index].signal if source_index is not None else None
        trusted = source_signal in _TRUSTED_GOAL_SIGNALS
        return (candidate.text if trusted else None), trusted, True

    candidate = extract_unit_goal(text, span)
    if candidate is None:
        return None, False, False
    trusted = span.signal in _TRUSTED_GOAL_SIGNALS
    return (candidate.text if trusted else None), trusted, False


def unit_for_offset(units: list[DocumentUnit], offset: int) -> DocumentUnit | None:
    """The unit containing *offset*, if any — the "backward search" lookup.

    Thin wrapper so callers (ingestion scripts) don't need to know about
    `unit_segmentation.UnitSpan` at all, only `DocumentUnit`.
    """
    for unit in units:
        if unit.start <= offset < unit.end:
            return unit
    return None
