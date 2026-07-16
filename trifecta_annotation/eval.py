"""Evaluation metrics for TRIFECTA annotations against a gold set."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from data_io import load_jsonl, resolve

from trifecta_annotation.gold_io import load_gold_records
from trifecta_annotation.schemas import (
    FrameQualia,
    TrifectaAnnotation,
    TrifectaFrame,
)

# Qualia role fields only (exclude frame discriminator + LU).
STEP_C_FIELDS: dict[TrifectaFrame, tuple[str, ...]] = {
    TrifectaFrame.COOKING_CREATION: (
        "COOKING_CREATION_Method",
        "COOKING_CREATION_Process",
        "COOKING_CREATION_Food_Product",
    ),
    TrifectaFrame.CURE: ("CURE_Affliction", "CURE_Food_Treatment"),
    TrifectaFrame.INGESTION: (
        "INGESTION_Context",
        "INGESTION_Ingestor",
        "INGESTION_Manner",
    ),
    TrifectaFrame.PRESERVING: ("PR_Technique", "PR_Medium", "PR_Food_Patient"),
}

_WS_RE = re.compile(r"\s+")


@dataclass
class PerClassScores:
    precision: dict[str, float] = field(default_factory=dict)
    recall: dict[str, float] = field(default_factory=dict)
    f1: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, dict[str, float]]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
        }


@dataclass
class EvalMetrics:
    total: int = 0
    step_a_entity_accuracy: float | None = None
    step_a_metaphor_accuracy: float | None = None
    step_b_accuracy: float | None = None
    step_b_per_frame_precision: dict[str, float] = field(default_factory=dict)
    step_b_per_frame_recall: dict[str, float] = field(default_factory=dict)
    step_b_per_frame_f1: dict[str, float] = field(default_factory=dict)
    dropout_agreement: float | None = None
    by_text_regime: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_century: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Step C — normalized exact match on qualia roles (gold rows with step_c).
    step_c_gold_rows: int = 0
    step_c_comparable_rows: int = 0
    step_c_joint_accuracy: float | None = None
    step_c_micro_accuracy: float | None = None
    step_c_field_accuracy: dict[str, float] = field(default_factory=dict)
    step_c_field_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    step_c_by_frame: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Soft: bidirectional substring containment after normalize (pred ⊃ gold ok).
    step_c_soft_joint_accuracy: float | None = None
    step_c_soft_micro_accuracy: float | None = None
    step_c_soft_field_accuracy: dict[str, float] = field(default_factory=dict)
    step_c_soft_field_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    step_c_soft_by_frame: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "step_a_entity_accuracy": self.step_a_entity_accuracy,
            "step_a_metaphor_accuracy": self.step_a_metaphor_accuracy,
            "step_b_accuracy": self.step_b_accuracy,
            "step_b_per_frame_precision": self.step_b_per_frame_precision,
            "step_b_per_frame_recall": self.step_b_per_frame_recall,
            "step_b_per_frame_f1": self.step_b_per_frame_f1,
            "dropout_agreement": self.dropout_agreement,
            "by_text_regime": self.by_text_regime,
            "by_century": self.by_century,
            "step_c_gold_rows": self.step_c_gold_rows,
            "step_c_comparable_rows": self.step_c_comparable_rows,
            "step_c_joint_accuracy": self.step_c_joint_accuracy,
            "step_c_micro_accuracy": self.step_c_micro_accuracy,
            "step_c_field_accuracy": self.step_c_field_accuracy,
            "step_c_field_counts": self.step_c_field_counts,
            "step_c_by_frame": self.step_c_by_frame,
            "step_c_soft_joint_accuracy": self.step_c_soft_joint_accuracy,
            "step_c_soft_micro_accuracy": self.step_c_soft_micro_accuracy,
            "step_c_soft_field_accuracy": self.step_c_soft_field_accuracy,
            "step_c_soft_field_counts": self.step_c_soft_field_counts,
            "step_c_soft_by_frame": self.step_c_soft_by_frame,
        }


def normalize_qualia_value(value: object) -> str:
    """Normalize free-text qualia for exact-match eval."""
    text = str(value or "").strip().lower()
    return _WS_RE.sub(" ", text)


def soft_qualia_match(gold: str, pred: str) -> bool:
    """
    Soft field match: exact, or bidirectional substring containment.

    Empty↔empty counts as a hit. One-sided empty does not.
    Prefer this when longer predictions that contain gold are acceptable.
    """
    if gold == pred:
        return True
    if not gold or not pred:
        return False
    return gold in pred or pred in gold


def _text_regime_label(provenance: dict[str, Any]) -> str:
    raw = provenance.get("text_regime")
    if raw is None or str(raw).strip() == "":
        return "UNKNOWN"
    return str(raw).strip()


def _century(date: str | None) -> str:
    if not date:
        return "unknown"
    digits = "".join(ch for ch in date if ch.isdigit())
    if len(digits) < 3:
        return "unknown"
    if len(digits) >= 4:
        return f"{digits[:2]}xx"
    return f"{digits[0]}xx"


def _per_class_scores(
    gold_labels: list[str],
    pred_labels: list[str],
) -> PerClassScores:
    labels = sorted(set(gold_labels) | set(pred_labels))
    precision: dict[str, float] = {}
    recall: dict[str, float] = {}
    f1: dict[str, float] = {}
    for label in labels:
        tp = sum(1 for g, p in zip(gold_labels, pred_labels, strict=False) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold_labels, pred_labels, strict=False) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold_labels, pred_labels, strict=False) if g == label and p != label)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        precision[label] = p
        recall[label] = r
        f1[label] = 2 * p * r / (p + r) if p + r else 0.0
    return PerClassScores(precision=precision, recall=recall, f1=f1)


def _per_class_f1(
    gold_labels: list[str],
    pred_labels: list[str],
) -> dict[str, float]:
    return _per_class_scores(gold_labels, pred_labels).f1


def _slice_metrics(
    pairs: list[tuple[str, str]],
) -> dict[str, Any]:
    gold_labels = [g for g, _ in pairs]
    pred_labels = [p for _, p in pairs]
    scores = _per_class_scores(gold_labels, pred_labels)
    return {
        "accuracy": sum(int(g == p) for g, p in pairs) / len(pairs),
        "count": float(len(pairs)),
        "per_frame_precision": scores.precision,
        "per_frame_recall": scores.recall,
        "per_frame_f1": scores.f1,
    }


def _index_by_record_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        provenance = record.get("provenance") or {}
        record_id = provenance.get("record_id")
        if record_id:
            indexed[str(record_id)] = record
    return indexed


def _step_c_frame(step_c: FrameQualia | None) -> TrifectaFrame | None:
    if step_c is None:
        return None
    return step_c.frame


def _step_c_values(step_c: FrameQualia | None) -> dict[str, str]:
    """Extract normalized qualia role values (empty string when missing)."""
    if step_c is None:
        return {}
    frame = step_c.frame
    fields = STEP_C_FIELDS.get(frame, ())
    data = step_c.model_dump(mode="json")
    return {name: normalize_qualia_value(data.get(name, "")) for name in fields}


def _score_step_c_pair(
    gold_c: FrameQualia,
    pred_c: FrameQualia | None,
    *,
    soft: bool = False,
) -> tuple[dict[str, bool], bool]:
    """
    Per-field match + joint match for one gold Step C record.

    Exact (default): string equality after normalize.
    Soft: ``soft_qualia_match`` (containment).
    Joint = all fields for the gold frame match (including empty↔empty).
    Pred on a different frame / missing → all fields miss.
    """
    gold_frame = gold_c.frame
    fields = STEP_C_FIELDS[gold_frame]
    gold_vals = _step_c_values(gold_c)
    pred_frame = _step_c_frame(pred_c)
    if pred_frame != gold_frame:
        return {name: False for name in fields}, False
    pred_vals = _step_c_values(pred_c)
    if soft:
        field_hits = {
            name: soft_qualia_match(gold_vals.get(name, ""), pred_vals.get(name, ""))
            for name in fields
        }
    else:
        field_hits = {
            name: gold_vals.get(name, "") == pred_vals.get(name, "") for name in fields
        }
    return field_hits, all(field_hits.values())


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
    regime_frames: dict[str, list[tuple[str, str]]] = defaultdict(list)

    step_c_field_hits: dict[str, int] = defaultdict(int)
    step_c_field_total: dict[str, int] = defaultdict(int)
    step_c_joint_hits = 0
    step_c_comparable = 0
    step_c_by_frame_hits: dict[str, dict[str, int]] = defaultdict(
        lambda: {"comparable": 0, "joint_hits": 0, "field_hits": 0, "field_total": 0},
    )
    soft_field_hits: dict[str, int] = defaultdict(int)
    soft_field_total: dict[str, int] = defaultdict(int)
    soft_joint_hits = 0
    soft_by_frame_hits: dict[str, dict[str, int]] = defaultdict(
        lambda: {"comparable": 0, "joint_hits": 0, "field_hits": 0, "field_total": 0},
    )

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
            regime = _text_regime_label(gold.provenance.model_dump(mode="json"))
            regime_frames[regime].append((gold_frame, pred_frame))

        if gold.step_c is not None:
            metrics.step_c_gold_rows += 1
            field_hits, joint = _score_step_c_pair(gold.step_c, pred.step_c)
            soft_hits, soft_joint = _score_step_c_pair(gold.step_c, pred.step_c, soft=True)
            step_c_comparable += 1
            frame_name = gold.step_c.frame.value
            frame_bucket = step_c_by_frame_hits[frame_name]
            soft_bucket = soft_by_frame_hits[frame_name]
            frame_bucket["comparable"] += 1
            soft_bucket["comparable"] += 1
            if joint:
                step_c_joint_hits += 1
                frame_bucket["joint_hits"] += 1
            if soft_joint:
                soft_joint_hits += 1
                soft_bucket["joint_hits"] += 1
            for field_name, hit in field_hits.items():
                step_c_field_total[field_name] += 1
                step_c_field_hits[field_name] += int(hit)
                frame_bucket["field_total"] += 1
                frame_bucket["field_hits"] += int(hit)
            for field_name, hit in soft_hits.items():
                soft_field_total[field_name] += 1
                soft_field_hits[field_name] += int(hit)
                soft_bucket["field_total"] += 1
                soft_bucket["field_hits"] += int(hit)

    metrics.step_a_entity_accuracy = entity_correct / len(shared_ids)
    metrics.step_a_metaphor_accuracy = metaphor_correct / len(shared_ids)
    metrics.dropout_agreement = dropout_correct / len(shared_ids)
    if gold_frames:
        metrics.step_b_accuracy = frame_correct / len(gold_frames)
        frame_scores = _per_class_scores(gold_frames, pred_frames)
        metrics.step_b_per_frame_precision = frame_scores.precision
        metrics.step_b_per_frame_recall = frame_scores.recall
        metrics.step_b_per_frame_f1 = frame_scores.f1

    for century, pairs in century_frames.items():
        metrics.by_century[century] = _slice_metrics(pairs)

    for regime, pairs in regime_frames.items():
        metrics.by_text_regime[regime] = _slice_metrics(pairs)

    metrics.step_c_comparable_rows = step_c_comparable
    if step_c_comparable:
        metrics.step_c_joint_accuracy = step_c_joint_hits / step_c_comparable
        micro_hits = sum(step_c_field_hits.values())
        micro_total = sum(step_c_field_total.values())
        metrics.step_c_micro_accuracy = micro_hits / micro_total if micro_total else None
        metrics.step_c_field_accuracy = {
            name: step_c_field_hits[name] / step_c_field_total[name]
            for name in sorted(step_c_field_total)
        }
        metrics.step_c_field_counts = {
            name: {"hits": step_c_field_hits[name], "n": step_c_field_total[name]}
            for name in sorted(step_c_field_total)
        }
        for frame_name, bucket in step_c_by_frame_hits.items():
            n = bucket["comparable"]
            ft = bucket["field_total"]
            metrics.step_c_by_frame[frame_name] = {
                "comparable": n,
                "joint_accuracy": bucket["joint_hits"] / n if n else None,
                "micro_accuracy": bucket["field_hits"] / ft if ft else None,
            }

        metrics.step_c_soft_joint_accuracy = soft_joint_hits / step_c_comparable
        soft_micro_hits = sum(soft_field_hits.values())
        soft_micro_total = sum(soft_field_total.values())
        metrics.step_c_soft_micro_accuracy = (
            soft_micro_hits / soft_micro_total if soft_micro_total else None
        )
        metrics.step_c_soft_field_accuracy = {
            name: soft_field_hits[name] / soft_field_total[name]
            for name in sorted(soft_field_total)
        }
        metrics.step_c_soft_field_counts = {
            name: {"hits": soft_field_hits[name], "n": soft_field_total[name]}
            for name in sorted(soft_field_total)
        }
        for frame_name, bucket in soft_by_frame_hits.items():
            n = bucket["comparable"]
            ft = bucket["field_total"]
            metrics.step_c_soft_by_frame[frame_name] = {
                "comparable": n,
                "joint_accuracy": bucket["joint_hits"] / n if n else None,
                "micro_accuracy": bucket["field_hits"] / ft if ft else None,
            }

    return metrics


def _format_per_frame_table(
    precision: dict[str, float],
    recall: dict[str, float],
    f1: dict[str, float],
) -> list[str]:
    frames = sorted(set(precision) | set(recall) | set(f1))
    if not frames:
        return []
    lines = [
        "",
        "| Frame | Precision | Recall | F1 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for frame in frames:
        lines.append(
            f"| {frame} | {precision.get(frame, 0.0):.3f} | "
            f"{recall.get(frame, 0.0):.3f} | {f1.get(frame, 0.0):.3f} |",
        )
    return lines


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
        "## Per-frame metrics (pooled)",
    ]
    lines.extend(
        _format_per_frame_table(
            metrics.step_b_per_frame_precision,
            metrics.step_b_per_frame_recall,
            metrics.step_b_per_frame_f1,
        ),
    )
    if metrics.by_text_regime:
        lines.extend(["", "## By text_regime (primary)"])
        for regime, stats in sorted(metrics.by_text_regime.items()):
            lines.append(
                f"- {regime}: accuracy={stats['accuracy']:.3f}, n={int(stats['count'])}",
            )
            lines.extend(
                _format_per_frame_table(
                    stats.get("per_frame_precision", {}),
                    stats.get("per_frame_recall", {}),
                    stats.get("per_frame_f1", {}),
                ),
            )
    if metrics.by_century:
        lines.extend(["", "## By century"])
        for century, stats in sorted(metrics.by_century.items()):
            lines.append(
                f"- {century}: accuracy={stats['accuracy']:.3f}, n={int(stats['count'])}",
            )

    lines.extend(
        [
            "",
            "## Step C — qualia field match (normalized exact)",
            "",
            f"- Gold rows with step_c: {metrics.step_c_gold_rows}",
            f"- Comparable (scored): {metrics.step_c_comparable_rows}",
            f"- Joint accuracy (all fields): {metrics.step_c_joint_accuracy}",
            f"- Micro accuracy (all field tokens): {metrics.step_c_micro_accuracy}",
        ],
    )
    if metrics.step_c_field_accuracy:
        lines.extend(
            [
                "",
                "| Field | Accuracy | Hits | n |",
                "| --- | ---: | ---: | ---: |",
            ],
        )
        for name, acc in metrics.step_c_field_accuracy.items():
            counts = metrics.step_c_field_counts.get(name, {})
            lines.append(
                f"| {name} | {acc:.3f} | {counts.get('hits', 0)} | {counts.get('n', 0)} |",
            )
    if metrics.step_c_by_frame:
        lines.extend(["", "### Step C by frame (exact)"])
        for frame_name, stats in sorted(metrics.step_c_by_frame.items()):
            lines.append(
                f"- {frame_name}: joint={stats.get('joint_accuracy')}, "
                f"micro={stats.get('micro_accuracy')}, n={stats.get('comparable')}",
            )

    lines.extend(
        [
            "",
            "## Step C — soft match (containment)",
            "",
            "Field hit when normalized strings are equal, or one contains the other "
            "(empty↔empty counts; one-sided empty does not).",
            "",
            f"- Soft joint accuracy: {metrics.step_c_soft_joint_accuracy}",
            f"- Soft micro accuracy: {metrics.step_c_soft_micro_accuracy}",
        ],
    )
    if metrics.step_c_soft_field_accuracy:
        lines.extend(
            [
                "",
                "| Field | Soft accuracy | Hits | n |",
                "| --- | ---: | ---: | ---: |",
            ],
        )
        for name, acc in metrics.step_c_soft_field_accuracy.items():
            counts = metrics.step_c_soft_field_counts.get(name, {})
            lines.append(
                f"| {name} | {acc:.3f} | {counts.get('hits', 0)} | {counts.get('n', 0)} |",
            )
    if metrics.step_c_soft_by_frame:
        lines.extend(["", "### Step C by frame (soft)"])
        for frame_name, stats in sorted(metrics.step_c_soft_by_frame.items()):
            lines.append(
                f"- {frame_name}: joint={stats.get('joint_accuracy')}, "
                f"micro={stats.get('micro_accuracy')}, n={stats.get('comparable')}",
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
