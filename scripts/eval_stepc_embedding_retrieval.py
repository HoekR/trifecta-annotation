#!/usr/bin/env python3
"""Leave-one-out eval of the Step C embedding-exemplar-retrieval prototype.

No training step — see trifecta_annotation/stepc_embedding_retrieval.py module
docstring for the method and why it beats the ruled-out GloBERTise BERT-QA
span extractor on this data (PLAN.md §9c).
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from trifecta_annotation.embedding_candidates import GysbertEmbedder
from trifecta_annotation.stepc_embedding_retrieval import (
    SUBWORD_SCORE_PENALTY,
    load_positive_pool,
    run_loo_eval,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="LOO-eval Step C embedding retrieval.")
    parser.add_argument("--data-dir", default=None, help="Default: resolve('trifecta_stepc_span')")
    parser.add_argument("--output-dir", default=None, help="Default: <data-dir>/runs/embedding_retrieval")
    parser.add_argument("--subword-penalty", type=float, default=SUBWORD_SCORE_PENALTY)
    args = parser.parse_args()

    data_dir = args.data_dir or _resolve_data_dir()
    pool = load_positive_pool(data_dir)

    embedder = GysbertEmbedder()
    result = run_loo_eval(pool, embedder=embedder, subword_penalty=args.subword_penalty)

    out = Path(args.output_dir or (Path(data_dir) / "runs" / "embedding_retrieval"))
    out.mkdir(parents=True, exist_ok=True)

    metrics_path = out / "loo_metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "method": "embedding_exemplar_retrieval",
                "data_dir": str(data_dir),
                "subword_penalty": args.subword_penalty,
                "finished_at": datetime.now(UTC).isoformat(),
                "loo_metrics": result.to_dict(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report_lines = [
        "# Step C embedding-exemplar-retrieval (LOO) report",
        "",
        "No fine-tuning — scores candidate spans against embeddings of every other",
        "gold answer span for the field (`emanjavacas/gysbert`, mean-pooled).",
        "",
        f"- Rows (LOO, positive-only): {result.total}",
        f"- Exact match: **{result.exact_match:.3f}**",
        f"- Token F1: **{result.token_f1:.3f}**",
        f"- Soft/containment match: **{result.soft_match:.3f}**",
        "",
        "## Per field",
        "",
        "| Field | n | EM | F1 | soft |",
        "|---|---:|---:|---:|---:|",
    ]
    for field, stats in sorted(result.per_field.items()):
        report_lines.append(
            f"| {field} | {int(stats['n'])} | {stats['exact_match']:.3f} "
            f"| {stats['token_f1']:.3f} | {stats['soft_match']:.3f} |"
        )
    report_path = out / "loo_report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(json.dumps({"metrics": str(metrics_path), "report": str(report_path)}, indent=2))


def _resolve_data_dir() -> str:
    from data_io import resolve

    return resolve("trifecta_stepc_span")


if __name__ == "__main__":
    main()
