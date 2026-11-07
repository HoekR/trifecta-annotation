"""Harvest sieve: kwic_mode tagging + verb-food-only default (PLAN.md §9i)."""

from __future__ import annotations

import re
from unittest.mock import patch

from scripts.build_colonial_kwic import (
    _parse_allowed_regimes,
    capped_candidates,
    scan_text,
    stratify_by_position,
)
from trifecta_annotation.text_regime import TextRegime


def test_scan_text_tags_regime_and_noun_fallback_mode() -> None:
    pattern = re.compile(r"(?i)\b(brood)\b")
    rows = scan_text(
        "Neem brood met boter.",
        pattern=pattern,
        canonical={"brood": "brood"},
        source_path="example.xml",
        title="Kookboek",
        corpus="test_corpus",
        date="1700",
        regime=TextRegime.RECIPE_PRACTICE,
    )
    assert len(rows) == 1
    assert rows[0]["text_regime"] == TextRegime.RECIPE_PRACTICE.value
    assert rows[0]["kwic_mode"] == "noun_fallback"
    assert rows[0]["target_char_offset"] == 5


def test_stratify_by_position_keeps_best_per_bin() -> None:
    doc_length = 100
    candidates = [
        (1.0, {"target_char_offset": 5, "id": "a"}),
        (5.0, {"target_char_offset": 8, "id": "b"}),  # same early bin, higher score
        (3.0, {"target_char_offset": 90, "id": "c"}),
    ]
    kept = stratify_by_position(candidates, cap=2, doc_length=doc_length)
    assert [row["id"] for row in kept] == ["b", "c"]


def test_capped_candidates_defaults_to_verb_food_only() -> None:
    verb_row = {
        "target_char_offset": 10,
        "kwic_mode": "verb_food",
        "text_regime": TextRegime.RECIPE_PRACTICE.value,
    }
    noun_row = {
        "target_char_offset": 80,
        "kwic_mode": "noun_fallback",
        "text_regime": TextRegime.RECIPE_PRACTICE.value,
    }
    with (
        patch(
            "scripts.build_colonial_kwic.infer_text_regime",
            return_value=TextRegime.RECIPE_PRACTICE,
        ),
        patch(
            "scripts.build_colonial_kwic.verb_first_hits",
            return_value=[(2.0, verb_row)],
        ),
        patch(
            "scripts.build_colonial_kwic.scan_text",
            return_value=[noun_row],
        ) as scan_mock,
    ):
        out = capped_candidates(
            "x" * 100,
            pattern=re.compile(r"x"),
            canonical={},
            food_terms_list=[],
            source_path="ex.xml",
            title="Kookboek",
            corpus="voc_recipes",
            date="1700",
            cap=2,
        )
        assert scan_mock.call_count == 0
        assert len(out) == 1
        assert out[0]["kwic_mode"] == "verb_food"

        out_with_nouns = capped_candidates(
            "x" * 100,
            pattern=re.compile(r"x"),
            canonical={},
            food_terms_list=[],
            source_path="ex.xml",
            title="Kookboek",
            corpus="voc_recipes",
            date="1700",
            cap=2,
            include_noun_fallback=True,
        )
        assert scan_mock.call_count == 1
        modes = {row["kwic_mode"] for row in out_with_nouns}
        assert modes == {"verb_food", "noun_fallback"}


def test_capped_candidates_regime_allow_list() -> None:
    with patch(
        "scripts.build_colonial_kwic.infer_text_regime",
        return_value=TextRegime.LITERARY,
    ):
        out = capped_candidates(
            "text",
            pattern=re.compile(r"x"),
            canonical={},
            food_terms_list=[],
            source_path="ex.xml",
            title="Roman",
            corpus="other",
            date="1800",
            cap=5,
            allowed_regimes=frozenset({TextRegime.RECIPE_PRACTICE, TextRegime.MEDICAL}),
        )
    assert out == []


def test_parse_allowed_regimes() -> None:
    assert _parse_allowed_regimes(None) is None
    assert _parse_allowed_regimes("") is None
    parsed = _parse_allowed_regimes("RECIPE_PRACTICE,MEDICAL")
    assert parsed == frozenset({TextRegime.RECIPE_PRACTICE, TextRegime.MEDICAL})


def _entry(head: str):
    from types import SimpleNamespace
    return SimpleNamespace(head=head, scope_head=None)


def test_entry_scope_routes_only_structured_recipe_medical_works() -> None:
    verb_row = {"target_char_offset": 10, "kwic_mode": "verb_food", "source_path": "ex.xml"}
    nouns = [
        {"target_char_offset": o, "kwic_mode": "noun_fallback", "source_path": "ex.xml",
         "candidate_terms": ["boter"], "record_id": f"n{o}"}
        for o in (10, 30, 60, 80)
    ]
    # entry 1 (offset 0-49) has a recipe head, entry 2 (50-) does not
    located = [(0, _entry("Om Boter te maken")), (50, _entry("Van den Oorlog"))]
    kwargs = dict(pattern=re.compile(r"x"), canonical={}, food_terms_list=[],
                  source_path="ex.xml", title="Kookboek", corpus="c", date=None, cap=5)
    for regime, expect_scope in ((TextRegime.RECIPE_PRACTICE, True), (TextRegime.LITERARY, False)):
        with (
            patch("scripts.build_colonial_kwic.infer_text_regime", return_value=regime),
            patch("scripts.build_colonial_kwic.verb_first_hits", return_value=[(2.0, verb_row)]),
            patch("scripts.build_colonial_kwic.scan_text", return_value=nouns),
            patch("trifecta_annotation.regime_routing.regime_from_tei_scope_head",
                  side_effect=lambda h: TextRegime.RECIPE_PRACTICE if h and "maken" in h else None),
        ):
            out = capped_candidates("x" * 100, located=located, **kwargs)
        scoped = [r for r in out if r["kwic_mode"] == "entry_scope"]
        if expect_scope:
            # offset 10 is verb-reachable -> excluded; 30 is in the recipe entry; 60/80 are not
            assert [r["target_char_offset"] for r in scoped] == [30]
            assert "__scope__" in scoped[0]["record_id"]
        else:
            assert scoped == []
