"""Homograph / polysemy context heuristics."""

from trifecta_annotation.homonym_context import (
    assess_homonym_context,
    homonym_blocks_clear_example,
)
from trifecta_annotation.schemas import TrifectaFrame


def test_biet_literary_verb_not_food() -> None:
    snippet = (
        "Een man die sich noeyt vreucht en biet Daer aen sijn vrouwe leet geschiet."
    )
    assessment = assess_homonym_context("biet", snippet)
    assert assessment.risk == "high"
    assert homonym_blocks_clear_example(assessment)


def test_boter_trade_list_not_ingestion() -> None:
    snippet = (
        "Plakaat tegen den uitvoer van vleesch, visch, boter, kaas en andere mondbehoeften."
    )
    assessment = assess_homonym_context(
        "boter",
        snippet,
        suggested_frame=TrifectaFrame.INGESTION,
        discovery_verb="nuttigen",
    )
    assert assessment.risk == "high"
    assert homonym_blocks_clear_example(assessment)


def test_boter_nuttigen_arbeid_misattachment() -> None:
    snippet = (
        "waarvan zij de melk en boter aan de Europesche ingezetenen slijten. "
        "Tot aanmoediging van nuttigen arbeid, en vooral van landbouw"
    )
    assessment = assess_homonym_context(
        "boter",
        snippet,
        suggested_frame=TrifectaFrame.INGESTION,
        discovery_verb="nuttigen",
    )
    assert homonym_blocks_clear_example(assessment)


def test_water_flood_not_food() -> None:
    snippet = (
        "den dreigenden aanwas van het water, voor zoo verre hij zelf daarmede bekend is"
    )
    assessment = assess_homonym_context("water", snippet)
    assert assessment.risk == "high"


def test_water_cooking_context_cleared() -> None:
    snippet = (
        "Neem een pond gemeen water, doe daar in drie dagen weeken, een once Brasielhout."
    )
    assessment = assess_homonym_context(
        "water",
        snippet,
        suggested_frame=TrifectaFrame.COOKING_CREATION,
        discovery_verb="weeken",
    )
    assert assessment.food_practice_likely
    assert not homonym_blocks_clear_example(assessment)


def test_vleesch_cooking_low_risk() -> None:
    snippet = "Neem het vleesch en laat het koken in water tot het gaar is."
    assessment = assess_homonym_context(
        "vleesch",
        snippet,
        suggested_frame=TrifectaFrame.COOKING_CREATION,
        discovery_verb="koken",
    )
    assert assessment.risk == "low"
