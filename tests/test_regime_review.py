"""Tests for regime review helpers."""

import pandas as pd

from trifecta_annotation.regime_review import apply_regime_review, build_review_rows
from trifecta_annotation.text_regime import TextRegime


def test_build_review_rows_unknown_only() -> None:
    frame = pd.DataFrame(
        [
            {
                "record_id": "a",
                "target_word": "boter",
                "corpus": "cort_voc_db",
                "source_path": "recept.txt",
                "text_regime": "UNKNOWN",
                "context_text": "boter in de keuken",
                "notes": "",
            },
            {
                "record_id": "b",
                "target_word": "reis",
                "corpus": "cort_voc_db",
                "source_path": "x.txt",
                "text_regime": "TRAVEL",
                "context_text": "op reis",
                "notes": "",
            },
        ],
    )
    rows = build_review_rows(frame, titles={"recept.txt": "Keuken en recepten"})
    assert len(rows) == 1
    assert rows[0]["record_id"] == "a"
    assert rows[0]["suggested_text_regime"] == TextRegime.RECIPE_PRACTICE.value


def test_apply_regime_review_updates_gold() -> None:
    gold = pd.DataFrame(
        [
            {"record_id": "a", "text_regime": "UNKNOWN"},
            {"record_id": "b", "text_regime": "UNKNOWN"},
        ],
    )
    review = pd.DataFrame(
        [
            {"record_id": "a", "review_text_regime": "MEDICAL"},
        ],
    )
    merged, applied = apply_regime_review(gold, review)
    assert applied == 1
    assert merged.loc[merged["record_id"] == "a", "text_regime"].iloc[0] == "MEDICAL"
