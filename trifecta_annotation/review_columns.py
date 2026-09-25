"""Shared optional columns for manual review CSVs (spot-check, clear-frame batch)."""

from __future__ import annotations

# Fill during review when the target spelling is polysemous / homographic.
#   food_sense   — confirmed edible referent in this snippet
#   other_sense  — different word or referent (drop: not_food_entity / ambiguous)
#   metaphor     — figurative use of a food term
HOMONYM_CHECK_VALUES: frozenset[str] = frozenset(
    {"", "food_sense", "other_sense", "metaphor"},
)

HOMONYM_REVIEW_COLUMNS: tuple[str, ...] = (
    "homonym_check",
    "homonym_note",
)

HOMONYM_REVIEW_HELP = (
    "homonym_check: food_sense | other_sense | metaphor (empty = unchecked); "
    "homonym_note: e.g. bloem=flower, noot=footnote, appel=beroep"
)


def empty_homonym_review_row() -> dict[str, str]:
    return {"homonym_check": "", "homonym_note": ""}
