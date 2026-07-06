"""Tests for regime-stratified sampling."""

from pathlib import Path

from trifecta_annotation.regime_sampling import (
    enrich_kwic_regime,
    parse_regime_quotas,
    refresh_labelling_regimes,
    sample_inception_silver,
    sample_kwic_by_regime,
)
from trifecta_annotation.schemas import KwicInput
from trifecta_annotation.text_regime import TextRegime


def test_parse_regime_quotas() -> None:
    quotas = parse_regime_quotas("RECIPE_PRACTICE:25,MEDICAL:10")
    assert quotas[TextRegime.RECIPE_PRACTICE] == 25
    assert quotas[TextRegime.MEDICAL] == 10


def test_enrich_kwic_regime_from_title() -> None:
    record = KwicInput(
        record_id="a",
        corpus="cort_voc_db",
        target_word="boter",
        context_text="boter",
        source_path="recepten.txt",
    )
    out = enrich_kwic_regime(
        record,
        titles={"recepten.txt": "Nieuwe recepten voor de keuken"},
    )
    assert out.text_regime == TextRegime.RECIPE_PRACTICE
    assert out.title == "Nieuwe recepten voor de keuken"


def test_sample_kwic_by_regime_respects_target_cap(tmp_path: Path) -> None:
    pool = [
        KwicInput(
            record_id=f"r{i}",
            corpus="c",
            target_word="water",
            context_text=f"ctx {i}",
            text_regime=TextRegime.RECIPE_PRACTICE,
        )
        for i in range(5)
    ]

    def fake_pool(**_kwargs):  # noqa: ANN003
        return pool

    import trifecta_annotation.regime_sampling as mod

    original = mod._load_candidate_pool
    mod._load_candidate_pool = fake_pool  # type: ignore[assignment]
    try:
        records, filled = sample_kwic_by_regime(
            {TextRegime.RECIPE_PRACTICE: 5},
            max_per_target=2,
            seed=0,
        )
    finally:
        mod._load_candidate_pool = original

    assert filled["RECIPE_PRACTICE"] == 2
    assert len(records) == 2


def test_sample_inception_silver_by_regime(tmp_path: Path) -> None:
    import pandas as pd

    from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS

    rows = []
    for i, (title, frame) in enumerate(
        [
            ("De volmaakte Hollandsche keuken-meid", "COOKING_CREATION"),
            ("Nieuwe recepten voor de keuken", "INGESTION"),
            ("Pharmacopoea Amstelredamensis", "CURE"),
        ],
    ):
        row = {col: "" for col in GOLD_CSV_COLUMNS}
        row.update(
            {
                "record_id": f"inc_{i}",
                "corpus": "cort_voc_db",
                "target_word": f"term{i}",
                "context_text": "ctx",
                "selected_frame": frame,
                "labelled": "true",
                "text_regime": (
                    TextRegime.MEDICAL.value
                    if "Pharmacopoea" in title
                    else TextRegime.RECIPE_PRACTICE.value
                ),
            },
        )
        rows.append(row)
    silver_path = tmp_path / "inception_silver_labelling.csv"
    pd.DataFrame(rows, columns=GOLD_CSV_COLUMNS).to_csv(silver_path, index=False)

    selected, filled = sample_inception_silver(
        {TextRegime.RECIPE_PRACTICE: 1, TextRegime.MEDICAL: 1},
        silver_path=silver_path,
        seed=0,
    )
    assert filled["RECIPE_PRACTICE"] == 1
    assert filled["MEDICAL"] == 1
    assert len(selected) == 2
    regimes = {str(row["text_regime"]) for row in selected}
    assert regimes == {"RECIPE_PRACTICE", "MEDICAL"}


def test_refresh_labelling_regimes() -> None:
    rows = refresh_labelling_regimes(
        [
            {
                "corpus": "cort_voc_db",
                "title": "De volmaakte Hollandsche keuken-meid",
                "text_regime": "UNKNOWN",
            },
        ],
    )
    assert rows[0]["text_regime"] == TextRegime.RECIPE_PRACTICE.value
