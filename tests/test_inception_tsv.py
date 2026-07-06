"""Tests for INCEpTION WebAnno TSV adapter."""

from pathlib import Path

from trifecta_annotation.adapters.inception_tsv import (
    load_inception_annotations,
    load_inception_kwic_inputs,
    parse_webanno_tsv,
    sentence_food_targets,
)
from trifecta_annotation.schemas import TrifectaFrame

FIXTURE = Path(__file__).parent / "fixtures" / "inception_sample.tsv"


def test_parse_webanno_tsv_food_and_frame_layers() -> None:
    sentences = parse_webanno_tsv(FIXTURE)
    assert len(sentences) == 1
    sentence = sentences[0]
    assert "Honing" in sentence.text
    targets = sentence_food_targets(sentence)
    assert len(targets) == 1
    assert targets[0].surface == "Honing"


def test_load_inception_annotations_from_export(tmp_path: Path) -> None:
    export_root = tmp_path / "export"
    tsv_dir = export_root / "annotation" / "sample.txt"
    tsv_dir.mkdir(parents=True)
    tsv_dir.joinpath("reviewer.tsv").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    annotations, skipped = load_inception_annotations(export_root)
    assert skipped == []
    assert len(annotations) == 1
    ann = annotations[0]
    assert ann.provenance.target_word == "Honing"
    assert ann.step_a is not None
    assert ann.step_a.is_food_entity is True
    assert ann.step_b is not None
    assert ann.step_b.selected_frame == TrifectaFrame.CURE


def test_load_inception_kwic_inputs_from_export(tmp_path: Path) -> None:
    export_root = tmp_path / "export"
    tsv_dir = export_root / "annotation" / "sample.txt"
    tsv_dir.mkdir(parents=True)
    tsv_dir.joinpath("reviewer.tsv").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    records, skipped = load_inception_kwic_inputs(export_root)
    assert skipped == []
    assert len(records) == 1
    assert records[0].corpus in {"inception_snippets", "cort_voc_db"}
    assert records[0].record_id.startswith("inception_nl__sample_txt__reviewer__")
