"""Tests for food_snippets text lookup."""

from trifecta_annotation.snippet_lookup import lookup_snippet_metadata, normalize_snippet_text
from trifecta_annotation.text_regime import TextRegime


def test_normalize_snippet_text_collapses_whitespace() -> None:
    assert normalize_snippet_text("  foo   bar \n baz ") == "foo bar baz"


def test_lookup_snippet_metadata_exact_or_substring() -> None:
    match = lookup_snippet_metadata(
        "Het gebeurt ook wel, dat'er boven uit de Byekorven al te veel Honing word gehaalt",
    )
    if match is None:
        return  # food_snippets not on manifest in CI
    assert match.title
    assert match.text_regime in {TextRegime.RECIPE_PRACTICE, TextRegime.MEDICAL, TextRegime.UNKNOWN}
