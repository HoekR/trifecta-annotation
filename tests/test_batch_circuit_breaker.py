"""A model server that is down must stop the run, not fill the output with error rows (21 Nov 2026)."""

import json

import pytest

import trifecta_annotation.batch as batch

DOWN = "Error code: 500 - model path missing"


def _run(tmp_path, monkeypatch, errors, concurrency=1):
    p = tmp_path / "ann.jsonl"
    monkeypatch.setattr(batch, "make_instructor_client", lambda **k: None)
    monkeypatch.setattr(batch, "_write_batch_sidecar", lambda *a, **k: None)
    monkeypatch.setattr(batch, "_annotate_one", lambda rec, **k: {
        "provenance": {"record_id": rec["record_id"]}, "error": errors.get(rec["record_id"])})
    inputs = [{"record_id": str(i)} for i in range(30)]
    try:
        batch.run_batch(inputs, output_path=p, concurrency=concurrency)
    finally:
        rows = [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
        monkeypatch.setattr(_run, "rows", rows, raising=False)
    return rows


@pytest.mark.parametrize("concurrency", [1, 2])
def test_stops_after_consecutive_server_errors_and_writes_none(tmp_path, monkeypatch, concurrency):
    with pytest.raises(batch.ServerDownError):
        _run(tmp_path, monkeypatch, {str(i): DOWN for i in range(30)}, concurrency)
    assert _run.rows == []


def test_good_rows_before_the_outage_are_kept(tmp_path, monkeypatch):
    with pytest.raises(batch.ServerDownError):
        _run(tmp_path, monkeypatch, {str(i): DOWN for i in range(5, 30)})
    assert [r["provenance"]["record_id"] for r in _run.rows] == ["0", "1", "2", "3", "4"]


def test_short_blip_is_recorded_and_run_continues(tmp_path, monkeypatch):
    rows = _run(tmp_path, monkeypatch, {str(i): DOWN for i in range(3, 12)})
    assert len(rows) == 30 and sum(bool(r["error"]) for r in rows) == 9


def test_timeouts_do_not_trip_it(tmp_path, monkeypatch):
    rows = _run(tmp_path, monkeypatch, {str(i): "Request timed out." for i in range(30)})
    assert len(rows) == 30
