"""Tests for INCEpTION WebAnno TSV adapter."""

from pathlib import Path

from trifecta_annotation.adapters.inception_tsv import (
    load_inception_annotations,
    load_inception_kwic_inputs,
    parse_webanno_tsv,
    sentence_coarse_targets,
    sentence_food_targets,
)
from trifecta_annotation.coarse_frames import CoarseFrame, coarse_frame_from_fine
from trifecta_annotation.schemas import TrifectaFrame

FIXTURE = Path(__file__).parent / "fixtures" / "inception_sample.tsv"
COARSE_FIXTURE = Path(__file__).parent / "fixtures" / "inception_coarse_sample.tsv"


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
    assert ann.annotation_type == "fine_inception"
    assert ann.coarse_frame == CoarseFrame.MEDICAL_CURE.value


def test_coarse_fixture_imports_without_food_lu(tmp_path: Path) -> None:
    export_root = tmp_path / "export"
    tsv_dir = export_root / "annotation" / "sample.txt"
    tsv_dir.mkdir(parents=True)
    tsv_dir.joinpath("reviewer.tsv").write_text(
        COARSE_FIXTURE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    annotations, skipped = load_inception_annotations(export_root, granularity="coarse")
    assert skipped == []
    assert len(annotations) == 4
    types = {ann.annotation_type for ann in annotations}
    assert types == {"coarse_inception"}
    frames = {ann.coarse_frame for ann in annotations}
    assert CoarseFrame.FOOD_TRANSFORM.value in frames


def test_both_granularity_prefers_fine_over_coarse(tmp_path: Path) -> None:
    export_root = tmp_path / "export"
    tsv_dir = export_root / "annotation" / "sample.txt"
    tsv_dir.mkdir(parents=True)
    tsv_dir.joinpath("reviewer.tsv").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")

    annotations, _ = load_inception_annotations(export_root, granularity="both")
    assert len(annotations) == 1
    assert annotations[0].annotation_type == "fine_inception"


def test_coarse_frame_mapping() -> None:
    assert coarse_frame_from_fine(TrifectaFrame.COOKING_CREATION) == CoarseFrame.FOOD_TRANSFORM
    assert coarse_frame_from_fine(TrifectaFrame.PRESERVING) == CoarseFrame.FOOD_TRANSFORM
    assert coarse_frame_from_fine(TrifectaFrame.CURE) == CoarseFrame.MEDICAL_CURE
    assert coarse_frame_from_fine(TrifectaFrame.INGESTION) == CoarseFrame.CONSUMPTION
    assert coarse_frame_from_fine(TrifectaFrame.NONE) == CoarseFrame.OUT_OF_SCOPE


def test_sentence_coarse_targets_finds_formal_spans() -> None:
    sentences = parse_webanno_tsv(COARSE_FIXTURE)
    ingredient_sentence = sentences[1]
    targets = sentence_coarse_targets(ingredient_sentence)
    assert [token.surface for token in targets] == ["keizersbloem", "boter"]


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
