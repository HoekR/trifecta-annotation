"""Tests for text-regime inference."""

from trifecta_annotation.text_regime import TextRegime, infer_text_regime


def test_corpus_overrides_to_recipe() -> None:
    assert infer_text_regime(corpus="voc_recipes") == TextRegime.RECIPE_PRACTICE


def test_title_recipe_pattern() -> None:
    assert (
        infer_text_regime(
            corpus="cort_voc_db",
            title="Huishoudelyk woordboek",
        )
        == TextRegime.RECIPE_PRACTICE
    )


def test_title_literary_pattern() -> None:
    assert (
        infer_text_regime(
            corpus="cort_voc_db",
            title="Vaderlandsche Letteroefeningen Jaargang 1833",
        )
        == TextRegime.LITERARY
    )


def test_title_medical_pattern() -> None:
    assert (
        infer_text_regime(
            title="Pharmacopoea Amstelredamensis, of d' Amsterdammer apotheek",
        )
        == TextRegime.MEDICAL
    )
