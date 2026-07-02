"""Helpers for comparing multiple LLM prediction runs on the same gold set."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from trifecta_annotation.eval import EvalMetrics, evaluate


def safe_model_slug(model: str) -> str:
    """Filesystem-safe slug from an Ollama model tag."""
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", model.strip())
    return slug.strip("_") or "model"


def predictions_path_for_model(
    root: Path,
    model: str,
    *,
    english_hint: bool = False,
) -> Path:
    suffix = "_en_hint" if english_hint else ""
    return root / f"gold_predictions_{safe_model_slug(model)}{suffix}.jsonl"


def compare_runs(
    gold_records: list[dict[str, Any]],
    runs: list[tuple[str, list[dict[str, Any]]]],
) -> dict[str, Any]:
    """Evaluate named prediction runs against the same gold records."""
    compared: list[dict[str, Any]] = []
    for name, preds in runs:
        metrics = evaluate(gold_records, preds)
        compared.append({"name": name, **_metrics_block(metrics)})
    ranked = sorted(
        compared,
        key=lambda row: (
            row.get("step_b_accuracy") or 0.0,
            row.get("step_a_entity_accuracy") or 0.0,
        ),
        reverse=True,
    )
    return {"runs": compared, "ranked_by_step_b": [row["name"] for row in ranked]}


def _metrics_block(metrics: EvalMetrics) -> dict[str, Any]:
    return {
        "total": metrics.total,
        "step_a_entity_accuracy": metrics.step_a_entity_accuracy,
        "step_a_metaphor_accuracy": metrics.step_a_metaphor_accuracy,
        "dropout_agreement": metrics.dropout_agreement,
        "step_b_accuracy": metrics.step_b_accuracy,
        "step_b_per_frame_f1": metrics.step_b_per_frame_f1,
    }


def render_comparison_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# TRIFECTA model comparison",
        "",
        f"- Slice: {report.get('slice', 'full')} ({report.get('record_count', '?')} records)",
        f"- English hints: {report.get('english_hint', False)}",
        "",
        "| Model | Step B acc | Step A entity | Metaphor | Dropout |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("runs", []):
        lines.append(
            "| {name} | {b:.3f} | {e:.3f} | {m:.3f} | {d:.3f} |".format(
                name=row["name"],
                b=row.get("step_b_accuracy") or 0.0,
                e=row.get("step_a_entity_accuracy") or 0.0,
                m=row.get("step_a_metaphor_accuracy") or 0.0,
                d=row.get("dropout_agreement") or 0.0,
            )
        )
    ranked = report.get("ranked_by_step_b") or []
    if ranked:
        lines.extend(["", "## Ranked by Step B accuracy", ""])
        for index, name in enumerate(ranked, start=1):
            lines.append(f"{index}. {name}")
    return "\n".join(lines)
