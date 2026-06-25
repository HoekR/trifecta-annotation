"""Evaluation metrics for TRIFECTA annotations against a gold set."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from data_io import load_jsonl, resolve

from trifecta_annotation.gold_io import load_gold_records
from trifecta_annotation.schemas import TrifectaAnnotation


@dataclass
class EvalMetrics:
    total: int = 0
    step_a_entity_accuracy: float | None = None
    step_a_metaphor_accuracy: float | None = None
    step_b_accuracy: float | None = None
    step_b_per_frame_f1: dict[str, float] = field(default_factory=dict)
    dropout_agreement: float | None = None
    by_century: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "step_a_entity_accuracy": self.step_a_entity_accuracy,
            "step_a_metaphor_accuracy": self.step_a_metaphor_accuracy,
            "step_b_accuracy": self.step_b_accuracy,
            "step_b_per_frame_f1": self.step_b_per_frame_f1,
            "dropout_agreement": self.dropout_agreement,
            "by_century": self.by_century,
        }


def _century(date: str | None) -> str:
    if not date:
        return "unknown"
    digits = "".join(ch for ch in date if ch.isdigit())
    if len(digits) < 3:
        return "unknown"
    if len(digits) >= 4:
        return f"{digits[:2]}xx"
    return f"{digits[0]}xx"


def _per_class_f1(
    gold_labels: list[str],
    pred_labels: list[str],
) -> dict[str, float]:
    labels = sorted(set(gold_labels) | set(pred_labels))
    scores: dict[str, float] = {}
    for label in labels:
        tp = sum(1 for g, p in zip(gold_labels, pred_labels, strict=False) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold_labels, pred_labels, strict=False) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold_labels, pred_labels, strict=False) if g == label and p != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores[label] = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
    return scores


def _index_by_record_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        provenance = record.get("provenance") or {}
        record_id = provenance.get("record_id")
        if record_id:
            indexed[str(record_id)] = record
    return indexed


def evaluate(
    gold_records: list[dict[str, Any]],
    pred_records: list[dict[str, Any]],
) -> EvalMetrics:
    """Compare predictions to gold annotations keyed by record_id."""
    gold_index = _index_by_record_id(gold_records)
    pred_index = _index_by_record_id(pred_records)
    shared_ids = sorted(set(gold_index) & set(pred_index))
    metrics = EvalMetrics(total=len(shared_ids))

    if not shared_ids:
        return metrics

    entity_correct = 0
    metaphor_correct = 0
    frame_correct = 0
    dropout_correct = 0
    gold_frames: list[str] = []
    pred_frames: list[str] = []
    century_frames: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for record_id in shared_ids:
        gold = TrifectaAnnotation.model_validate(gold_index[record_id])
        pred = TrifectaAnnotation.model_validate(pred_index[record_id])

        if gold.step_a and pred.step_a:
            entity_correct += int(gold.step_a.is_food_entity == pred.step_a.is_food_entity)
            metaphor_correct += int(gold.step_a.is_metaphor == pred.step_a.is_metaphor)
        dropout_correct += int(gold.dropped == pred.dropped)

        if gold.step_b and pred.step_b:
            gold_frame = gold.step_b.selected_frame.value
            pred_frame = pred.step_b.selected_frame.value
            frame_correct += int(gold_frame == pred_frame)
            gold_frames.append(gold_frame)
            pred_frames.append(pred_frame)
            century = _century(gold.provenance.date)
            century_frames[century].append((gold_frame, pred_frame))

    metrics.step_a_entity_accuracy = entity_correct / len(shared_ids)
    metrics.step_a_metaphor_accuracy = metaphor_correct / len(shared_ids)
    metrics.dropout_agreement = dropout_correct / len(shared_ids)
    if gold_frames:
        metrics.step_b_accuracy = frame_correct / len(gold_frames)
        metrics.step_b_per_frame_f1 = _per_class_f1(gold_frames, pred_frames)

    for century, pairs in century_frames.items():
        gold_c = [g for g, _ in pairs]
        pred_c = [p for _, p in pairs]
        metrics.by_century[century] = {
            "accuracy": sum(int(g == p) for g, p in pairs) / len(pairs),
            "count": float(len(pairs)),
            "per_frame_f1": _per_class_f1(gold_c, pred_c),
        }
    return metrics


def render_report(metrics: EvalMetrics) -> str:
    lines = [
        "# TRIFECTA evaluation report",
        "",
        f"- Records evaluated: {metrics.total}",
        f"- Step A entity accuracy: {metrics.step_a_entity_accuracy}",
        f"- Step A metaphor accuracy: {metrics.step_a_metaphor_accuracy}",
        f"- Dropout agreement: {metrics.dropout_agreement}",
        f"- Step B frame accuracy: {metrics.step_b_accuracy}",
        "",
        "## Per-frame F1",
    ]
    for frame, score in sorted(metrics.step_b_per_frame_f1.items()):
        lines.append(f"- {frame}: {score:.3f}")
    if metrics.by_century:
        lines.extend(["", "## By century"])
        for century, stats in sorted(metrics.by_century.items()):
            lines.append(
                f"- {century}: accuracy={stats['accuracy']:.3f}, n={int(stats['count'])}",
            )
    return "\n".join(lines)


def run_eval(
    *,
    gold_logical: str = "trifecta_gold",
    predictions_logical: str = "trifecta_annotations",
    gold_path: str | Path | None = None,
    predictions_path: str | Path | None = None,
    report_logical: str = "eval_reports",
    script: str | None = None,
) -> tuple[EvalMetrics, Path]:
    if gold_path is None:
        gold_records = load_gold_records(gold_logical=gold_logical)
    else:
        gold_records = load_gold_records(gold_path=gold_path)

    if not gold_records:
        raise ValueError(
            "Gold set is empty. Label rows in trifecta_gold_csv (labelled=true), "
            "then run: uv run python scripts/import_gold_csv.py",
        )

    if predictions_path is None:
        pred_records = load_jsonl(resolve(predictions_logical))
    else:
        pred_records = load_jsonl(Path(predictions_path))

    metrics = evaluate(gold_records, pred_records)
    report = render_report(metrics)
    out_dir = resolve(report_logical)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "metrics.json"
    md_path = out_dir / "report.md"
    md_path.write_text(report, encoding="utf-8")
    json_path.write_text(json.dumps(metrics.to_dict(), indent=2), encoding="utf-8")
    return metrics, md_path
