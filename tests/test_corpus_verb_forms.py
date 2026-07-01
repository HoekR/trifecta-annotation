"""Historic form parsing for corpus verb CSV."""

from types import SimpleNamespace

from trifecta_annotation.frame_verb_corpus import parse_historic_forms, row_canonical_and_surfaces


def test_parse_historic_forms() -> None:
    assert parse_historic_forms("sieden, syeden;medesieden") == [
        "sieden",
        "syeden",
        "medesieden",
    ]


def test_row_modern_plus_historic_forms() -> None:
    row = SimpleNamespace(
        term_norm="koken",
        historic_forms="sieden,syeden,medesieden",
        term_example="sieden",
        canonical_lemma="",
        variants="",
    )
    canonical, surfaces = row_canonical_and_surfaces(row)
    assert canonical == "koken"
    assert surfaces == {"sieden", "syeden", "medesieden"}


def test_row_empty_canonical_is_not_nan() -> None:
    row = SimpleNamespace(
        term_norm="stoven",
        historic_forms="",
        term_example="stoven",
        canonical_lemma=float("nan"),
        variants="",
    )
    canonical, surfaces = row_canonical_and_surfaces(row)
    assert canonical == "stoven"
    assert surfaces == set()


def test_row_legacy_canonical_lemma() -> None:
    row = SimpleNamespace(
        term_norm="sieden",
        historic_forms="",
        term_example="sieden",
        canonical_lemma="koken",
        variants="",
    )
    canonical, surfaces = row_canonical_and_surfaces(row)
    assert canonical == "koken"
    assert surfaces == {"sieden"}
