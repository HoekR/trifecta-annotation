"""Tests for remedy/recipe unit segmentation (feasibility-study tooling).

Fixtures are real passages surfaced while diagnosing Step C (PLAN.md §9b–§9d),
not invented text: the "Hulpmiddelen voor den Hik" header case, numbered
cookbook sections, and `Om … te <verb>` purpose headers from the secreet-boek.
"""

from __future__ import annotations

from trifecta_annotation.unit_segmentation import (
    extract_unit_goal,
    find_unit_boundaries,
    find_unit_signals,
    goal_with_inheritance,
    target_sentence,
)

HIK_HEADER = (
    "Hulpmiddelen voor den Hik. Wat den Hik aangaat, die van de hoedanigheid of "
    "scherpheid der vochten ontstaat, geeft men hen Poeijer van Rhabarber, of een "
    "once Siroop van Zuikery."
)

SECREET_BOEK = (
    "Om het Water onder den Wijn gemengt wesende, te doen boven komen. Neemt gedroogt "
    "Bloedt van eenen Haen, stootet kleyn, ende menget dat onder den Wijn, ende het "
    "water sal boven komen. uyt den mondt van eenen Monnick. Om den Wijn te beletten "
    "sijn kracht te verliesen. Soo verre als ghy geenen dienst daer van hebt."
)

NUMBERED_COOKBOOK = (
    "19. Ham, hoe men die stooven zal. Legt de Ham vier en twintig uuren in het water. "
    "20. Ontlediging van een Schaapen-achterbout. Neemt de bout en snyd hem open."
)

EEN_ANDER = (
    "Tegens de Dronckenschap. Men sal teghens de Dronckenschap nemen Kool-saet. "
    "Een ander. Neemt die bladeren van Kool, ende stootse kleyn."
)

PLAIN_PROSE = (
    "'k En wil niet in het wout, niet inde bosschen dwalen, 'k En wil geen slang of "
    "worm uyt diepe kuylen halen; Een beesje dient gewaecht; dat heeft een dubbel lijf, "
    "Het teelt, gelijck een man; het baert gelijck een wijf."
)


def test_remedy_header_signal_fires() -> None:
    kinds = {kind for _s, _e, kind in find_unit_signals(HIK_HEADER)}
    assert "remedy_header" in kinds


def test_remedy_header_goal_is_the_affliction() -> None:
    units = find_unit_boundaries(HIK_HEADER)
    assert units
    goal = extract_unit_goal(HIK_HEADER, units[0])
    assert goal is not None
    assert "hik" in goal.norm


def test_purpose_om_splits_two_units() -> None:
    units = find_unit_boundaries(SECREET_BOEK)
    purpose_units = [u for u in units if u.signal == "purpose_om"]
    assert len(purpose_units) == 2


def test_purpose_om_goal_excludes_the_infinitive() -> None:
    units = find_unit_boundaries(SECREET_BOEK)
    goal = extract_unit_goal(SECREET_BOEK, units[0])
    assert goal is not None
    # "Om het Water onder den Wijn gemengt wesende, te doen boven komen"
    assert "water" in goal.norm
    assert "doen" not in goal.norm


def test_numbered_sections_split() -> None:
    units = find_unit_boundaries(NUMBERED_COOKBOOK)
    numbered = [u for u in units if u.signal == "numbered"]
    assert len(numbered) == 2
    goal = extract_unit_goal(NUMBERED_COOKBOOK, numbered[0])
    assert goal is not None
    assert "ham" in goal.norm


def test_een_ander_marks_inheritance_and_carries_the_goal() -> None:
    units = find_unit_boundaries(EEN_ANDER)
    assert any(u.inherits_goal for u in units)
    inherit_index = next(i for i, u in enumerate(units) if u.inherits_goal)
    # "Een ander." states no goal of its own ...
    assert extract_unit_goal(EEN_ANDER, units[inherit_index]) is None
    # ... but inherits the preceding affliction header.
    carried = goal_with_inheritance(EEN_ANDER, units, inherit_index)
    assert carried is not None
    assert "dronckenschap" in carried.norm


FORMULARY = (
    "Emplastrum Meliloti. Neemt Lythargirium met de Sevum hircinum, en wat water, tot "
    "de dikte van een pleister. Sy is deftig om te doen cicatrizeren. "
    "Oleum Ovorum. Neemt de doren van hard gesoden eyeren."
)

DICTIONARY_DIVIDERS = (
    "O. Obligatie, een verbintenisse. Occasie, gelegenheyt. "
    "E. Ecclesiastijck, kerckelijck. Elaboreren, uytwercken."
)


def test_formulary_entries_are_found_by_latin_preparation_name() -> None:
    units = find_unit_boundaries(FORMULARY)
    preparations = [u for u in units if u.signal == "latin_preparation"]
    assert len(preparations) == 2
    goal = extract_unit_goal(FORMULARY, preparations[0])
    assert goal is not None
    # A formulary is organised by preparation, not by affliction — the goal here
    # is the product, with the indication sitting inside the body.
    assert "emplastrum" in goal.norm


def test_single_letter_dividers_are_not_unit_cues() -> None:
    """A dictionary's "O." / "E." alphabet dividers must not read as sections.

    Matching them made `Nederlandtsche woorden-schat` the highest-density work
    in the corpus (24 cues/10k) — a false positive, since dictionary headwords
    are lexical entries rather than goals.
    """
    kinds = {kind for _s, _e, kind in find_unit_signals(DICTIONARY_DIVIDERS)}
    assert "roman" not in kinds


def test_plain_prose_has_no_unit_structure() -> None:
    assert find_unit_boundaries(PLAIN_PROSE) == []


def test_empty_text_is_safe() -> None:
    assert find_unit_signals("") == []
    assert find_unit_boundaries("   ") == []


def test_target_sentence_finds_the_sentence_containing_the_target() -> None:
    context = "Men neemt de appelen. Men kookt ze met suycker. Daerna set mense wech."
    hit = target_sentence(context, "kookt")
    assert hit is not None
    assert hit.text == "Men kookt ze met suycker."
    assert hit.truncated_left is False
    assert hit.truncated_right is False


def test_target_sentence_flags_right_truncation() -> None:
    """A ±180-char KWIC window routinely cuts off mid-sentence on the right —
    the target's own sentence has no closing punctuation inside the window."""
    context = "kere boffchen,en diepe grachten. Men kookt den appel met suycker. Daerna set mense het wech"
    hit = target_sentence(context, "wech")
    assert hit is not None
    assert hit.truncated_left is False  # this sentence starts cleanly after the prior one
    assert hit.truncated_right is True  # no closing punctuation before the window ends


def test_target_sentence_flags_left_truncation() -> None:
    """The window can equally start mid-sentence, with no leading context."""
    context = "appel met suycker. Daerna set mense het wech"
    hit = target_sentence(context, "appel")
    assert hit is not None
    assert hit.truncated_left is True  # the sentence's own opening was cut off
    assert hit.truncated_right is False  # it does end cleanly at the period


def test_target_sentence_none_when_target_absent() -> None:
    assert target_sentence("Men kookt den appel.", "pekelharing") is None


def test_target_sentence_none_on_empty_input() -> None:
    assert target_sentence("", "kookt") is None
    assert target_sentence("Men kookt den appel.", "") is None
