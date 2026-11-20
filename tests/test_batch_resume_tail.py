"""Resume after a run was cut off mid-write (planned two-stretch routed run, 18 Nov 2026)."""

import json

from trifecta_annotation.batch import _load_existing_ids


def _row(rid: str, error: str | None = None) -> str:
    return json.dumps({"provenance": {"record_id": rid}, "error": error})


def test_half_written_last_line_is_cut_and_resume_continues(tmp_path):
    p = tmp_path / "ann.jsonl"
    p.write_text(_row("a") + "\n" + _row("b") + "\n" + _row("c")[:15], encoding="utf-8")
    assert _load_existing_ids(p) == {"a", "b"}
    assert p.read_text(encoding="utf-8") == _row("a") + "\n" + _row("b") + "\n"


def test_complete_last_line_without_newline_is_kept(tmp_path):
    p = tmp_path / "ann.jsonl"
    p.write_text(_row("a") + "\n" + _row("b"), encoding="utf-8")
    assert _load_existing_ids(p) == {"a", "b"}
    assert p.read_text(encoding="utf-8").endswith(_row("b") + "\n")


def test_only_line_broken(tmp_path):
    p = tmp_path / "ann.jsonl"
    p.write_text(_row("a")[:10], encoding="utf-8")
    assert _load_existing_ids(p) == set()
    assert p.read_text(encoding="utf-8") == ""


def test_clean_file_untouched_and_errors_not_counted(tmp_path):
    p = tmp_path / "ann.jsonl"
    text = _row("a") + "\n" + _row("b", error="timeout") + "\n"
    p.write_text(text, encoding="utf-8")
    assert _load_existing_ids(p) == {"a"}
    assert p.read_text(encoding="utf-8") == text


def test_errors_counted_as_done_when_not_retrying(tmp_path):
    p = tmp_path / "ann.jsonl"
    p.write_text(_row("a") + "\n" + _row("b", error="timeout") + "\n", encoding="utf-8")
    assert _load_existing_ids(p, include_errors=True) == {"a", "b"}
