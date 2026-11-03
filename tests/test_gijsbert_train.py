"""GijsBERT training helpers."""

from trifecta_annotation.gijsbert_train import (
    classification_metrics,
    compute_class_weights,
    oversample_none_rows,
    remap_rows_for_frames_only,
)


def test_classification_metrics() -> None:
    gold = ["INGESTION", "NONE", "CURE", "INGESTION"]
    pred = ["INGESTION", "INGESTION", "CURE", "NONE"]
    result = classification_metrics(gold, pred)
    assert result.total == 4
    assert result.accuracy == 0.5
    assert "INGESTION" in result.per_frame_f1
    assert "NONE" in result.per_frame_f1


def test_oversample_none_rows() -> None:
    rows = [
        {"label": "NONE", "label_id": 4, "text": "a"},
        {"label": "CURE", "label_id": 1, "text": "b"},
    ]
    out = oversample_none_rows(rows, factor=3, seed=0)
    assert len(out) == 4
    assert sum(1 for row in out if row["label"] == "NONE") == 3


def test_compute_class_weights_none_boost() -> None:
    weights = compute_class_weights([0, 1, 1, 1], num_labels=2, none_label_id=0, none_boost=2.0)
    assert weights[0] > weights[1]


def test_remap_rows_for_frames_only() -> None:
    rows = [
        {"label": "NONE", "label_id": 4, "text": "a"},
        {"label": "CURE", "label_id": 1, "text": "b"},
    ]
    label2id = {"CURE": 0, "INGESTION": 1, "COOKING_CREATION": 2, "PRESERVING": 3}
    out = remap_rows_for_frames_only(rows, label2id)
    assert len(out) == 1
    assert out[0]["label_id"] == 0
