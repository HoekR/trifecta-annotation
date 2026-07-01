"""Recipe gloss frame-verb tests."""

from trifecta_annotation.frame_verb_recipes import (
    extract_gloss_pairs,
    gloss_to_frame,
    mine_recipe_gloss_verbs,
)
from trifecta_annotation.schemas import TrifectaFrame
import pandas as pd


def test_extract_gloss_pairs() -> None:
    pairs = extract_gloss_pairs("laten sieden [koken] tot het gaar is")
    assert ("sieden", "koken") in pairs or any(p[0] == "sieden" for p in pairs)


def test_gloss_to_frame() -> None:
    assert gloss_to_frame("koken") == TrifectaFrame.COOKING_CREATION
    assert gloss_to_frame("droogen in de zon") == TrifectaFrame.PRESERVING


def test_mine_recipe_gloss_verbs() -> None:
    recipes = pd.DataFrame(
        [
            {
                "recipe_id": 1,
                "Recipe": "Neemt vleesch ende laet sieden [koken] in water.",
                "title": "Om te sieden [koken] carpers",
            },
            {
                "recipe_id": 2,
                "Recipe": "Laet droogen [droogen] in de sonne.",
                "title": "Om vleesch te droogen",
            },
        ],
    )
    found = {item.term_norm: item for item in mine_recipe_gloss_verbs(recipes)}
    assert "sieden" in found
    assert found["sieden"].frame == TrifectaFrame.COOKING_CREATION
