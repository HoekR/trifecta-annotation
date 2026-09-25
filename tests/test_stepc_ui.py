"""Step C labelling UI save behaviour."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from gold_labeller.app import create_stepc_app
from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS


def _batch_csv(tmp_path: Path) -> Path:
    row = {col: "" for col in GOLD_CSV_COLUMNS}
    row.update(
        {
            "record_id": "r1",
            "corpus": "cort_voc_db",
            "target_word": "bier",
            "context_text": "zij drinken bier",
            "selected_frame": "INGESTION",
            "lexical_unit": "drinken",
            "labelled": "false",
            "dropped": "false",
            "review_snippet": "zij drinken [TGT]bier[/TGT]",
        },
    )
    path = tmp_path / "batch.csv"
    pd.DataFrame([row]).to_csv(path, index=False)
    return path


def test_stepc_save_next_marks_labelled(tmp_path: Path) -> None:
    path = _batch_csv(tmp_path)
    app = create_stepc_app(csv_file=path)
    client = app.test_client()
    response = client.post(
        "/save/r1",
        data={
            "action": "save_next",
            "selected_frame": "INGESTION",
            "lexical_unit": "drinken",
            "is_food_entity": "True",
            "INGESTION_Food_Patient": "bier",
            "next_record_id": "r1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert frame.iloc[0]["labelled"] == "True"
    assert frame.iloc[0]["INGESTION_Food_Patient"] == "bier"
    assert frame.iloc[0]["dropped"] == "False"


def test_stepc_drop_next_marks_dropped_and_labelled(tmp_path: Path) -> None:
    path = _batch_csv(tmp_path)
    app = create_stepc_app(csv_file=path)
    client = app.test_client()
    response = client.post(
        "/save/r1",
        data={
            "action": "drop_next",
            "selected_frame": "INGESTION",
            "lexical_unit": "drinken",
            "is_food_entity": "False",
            "next_record_id": "r1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert frame.iloc[0]["labelled"] == "True"
    assert frame.iloc[0]["dropped"] == "True"


def test_stepc_label_shows_centered_snippet(tmp_path: Path) -> None:
    path = _batch_csv(tmp_path)
    app = create_stepc_app(csv_file=path)
    client = app.test_client()
    response = client.get("/label/r1")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Centered on target" in body
    assert 'data-frame="INGESTION"' in body
    assert "stepc_label.js" in body
    assert "<mark" in body
