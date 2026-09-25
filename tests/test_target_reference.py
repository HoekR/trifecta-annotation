"""Target sense gallery tests."""

import pandas as pd

from trifecta_annotation.target_reference import (
    bucket_key_for,
    collect_gallery_pool,
    gold_frame_label,
    stratify_gallery,
)


def test_bucket_key() -> None:
    assert bucket_key_for("bloem", "LITERARY", "DROPPED") == "bloem|LITERARY|DROPPED"
    assert bucket_key_for("water", "RECIPE_PRACTICE", "") == "water|RECIPE_PRACTICE|CORPUS"


def test_gold_frame_label_dropped() -> None:
    assert gold_frame_label({"dropped": True}) == "DROPPED"
    assert gold_frame_label({"step_b": {"selected_frame": "INGESTION"}}) == "INGESTION"


def test_stratify_pins_gold_and_caps_corpus() -> None:
    from trifecta_annotation.target_reference import GalleryRow

    def row(
        rid: str,
        *,
        regime: str = "LITERARY",
        gold: bool = False,
        frame: str = "",
    ) -> GalleryRow:
        bucket = bucket_key_for("bloem", regime, frame)
        return GalleryRow(
            target_word="bloem",
            target_norm="bloem",
            bucket_key=bucket,
            text_regime=regime,
            gold_frame=frame,
            gold_drop_reason="",
            in_gold=gold,
            record_id=rid,
            doc_id=rid,
            title="",
            source_path="",
            bucket_pool_size=0,
            review_snippet="snippet",
            sense_bucket="",
            homonym_check="",
            homonym_note="",
            gold_step_b_reasoning="",
        )

    pool = [
        row("gold1", gold=True, frame="DROPPED"),
        row("c1"),
        row("c2"),
        row("c3"),
        row("c4"),
    ]
    picked = stratify_gallery(pool, max_per_bucket=3, seed=0)
    ids = {item.record_id for item in picked}
    assert "gold1" in ids
    assert len(ids) == 4  # 1 gold + 3 corpus cap


def test_collect_gallery_pool_filters_targets() -> None:
    frame = pd.DataFrame(
        [
            {
                "doc_id": "d1",
                "snippet": "Men neemt bloem en meel voor het deeg.",
                "matched_term": "bloem",
                "filename": "recipe.xml",
                "title": "Koekboek",
            },
            {
                "doc_id": "d2",
                "snippet": "De geurige bloem der roos is schoon.",
                "matched_term": "bloem",
                "filename": "lit.xml",
                "title": "Letteroefeningen",
            },
            {
                "doc_id": "d3",
                "snippet": "Neem zout en peper.",
                "matched_term": "peper",
                "filename": "recipe.xml",
                "title": "Koekboek",
            },
        ],
    )
    rows = collect_gallery_pool(
        targets={"bloem"},
        path=frame,
        thesaurus_filter=False,
        gold_lookup={},
    )
    assert len(rows) == 2
    assert {row.target_norm for row in rows} == {"bloem"}
