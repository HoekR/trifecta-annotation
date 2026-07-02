#!/usr/bin/env python3
"""English-hint scratch experiment on gold disagreement rows.

Runs batch with ``--english-hint`` on the disagreement slice (from ``gold_fixes.csv``)
and compares metrics to an existing Dutch-only baseline on the same record_ids.

Example::

    export TRIFECTA_MODEL=qwen2.5-coder:latest
    uv run python scripts/batch_english_hint_pilot.py --run-batch
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from data_io import load_jsonl, resolve

from trifecta_annotation.batch import load_inputs, run_batch
from trifecta_annotation.english_hint import default_review_hint_lookup, review_hint_for_term
from trifecta_annotation.eval import evaluate
from trifecta_annotation.gold_io import load_gold_records


def _scratch_eval_dir() -> Path:
    try:
        return Path(resolve("eval_reports"))
    except Exception:
        return Path("/Volumes/Extreme SSD/scratch/trifecta/eval")


def _default_paths() -> dict[str, Path]:
    eval_dir = _scratch_eval_dir()
    root = eval_dir.parent
    return {
        "fixes_csv": eval_dir / "gold_fixes.csv",
        "inputs": root / "gold_eval_inputs.jsonl",
        "baseline_preds": root / "gold_predictions.jsonl",
        "en_preds": root / "gold_predictions_en_hint.jsonl",
        "gold": root / "gold.parquet",
        "report": eval_dir / "english_hint_pilot.json",
    }


def _load_record_ids(fixes_csv: Path) -> list[str]:
    if not fixes_csv.exists():
        raise FileNotFoundError(f"Missing disagreement export: {fixes_csv}")
    frame = pd.read_csv(fixes_csv)
    if "record_id" not in frame.columns:
        raise ValueError(f"No record_id column in {fixes_csv}")
    return sorted({str(rid).strip() for rid in frame["record_id"].dropna() if str(rid).strip()})


def _filter_records(records: list[dict], record_ids: set[str]) -> list[dict]:
    out: list[dict] = []
    for record in records:
        rid = str((record.get("record_id") or (record.get("provenance") or {}).get("record_id") or ""))
        if rid in record_ids:
            out.append(record)
    return out


def _hint_coverage(inputs: list[dict], lookup: dict[str, str]) -> dict[str, int]:
    covered = sum(1 for row in inputs if review_hint_for_term(str(row.get("target_word", "")), lookup))
    return {"inputs": len(inputs), "with_english_hint": covered}


def _metrics_block(label: str, metrics) -> dict:
    return {
        "label": label,
        "total": metrics.total,
        "step_a_entity_accuracy": metrics.step_a_entity_accuracy,
        "step_a_metaphor_accuracy": metrics.step_a_metaphor_accuracy,
        "dropout_agreement": metrics.dropout_agreement,
        "step_b_accuracy": metrics.step_b_accuracy,
        "step_b_per_frame_f1": metrics.step_b_per_frame_f1,
    }


def main(argv: list[str] | None = None) -> int:
    defaults = _default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixes-csv", type=Path, default=defaults["fixes_csv"])
    parser.add_argument("--inputs-path", type=Path, default=defaults["inputs"])
    parser.add_argument("--baseline-predictions", type=Path, default=defaults["baseline_preds"])
    parser.add_argument("--output-path", type=Path, default=defaults["en_preds"])
    parser.add_argument("--gold-path", type=Path, default=defaults["gold"])
    parser.add_argument("--report-path", type=Path, default=defaults["report"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--limit", type=int, default=None, help="Cap rows for a quick smoke run")
    parser.add_argument(
        "--run-batch",
        action="store_true",
        help="Call Ollama batch with english hints (otherwise compare existing files only)",
    )
    args = parser.parse_args(argv)

    record_ids = _load_record_ids(args.fixes_csv)
    if args.limit is not None:
        record_ids = record_ids[: args.limit]
    id_set = set(record_ids)

    all_inputs = load_inputs(input_path=args.inputs_path)
    inputs = _filter_records(all_inputs, id_set)
    if not inputs:
        print("No matching inputs for disagreement record_ids", file=sys.stderr)
        return 1

    lookup = default_review_hint_lookup()
    coverage = _hint_coverage(inputs, lookup)
    print(
        f"Disagreement slice: {len(record_ids)} record_ids, "
        f"{coverage['inputs']} inputs, "
        f"{coverage['with_english_hint']} with English glossary hint",
        file=sys.stderr,
    )

    if args.run_batch:
        run_batch(
            inputs,
            output_path=args.output_path,
            model=args.model,
            base_url=args.base_url,
            english_hint=True,
            description="TRIFECTA English-hint pilot (disagreement slice)",
            script=__file__,
        )
        print(f"Wrote {args.output_path}", file=sys.stderr)
    elif not args.output_path.exists():
        print(
            f"Missing {args.output_path}; pass --run-batch or create predictions first.",
            file=sys.stderr,
        )
        return 1

    gold_all = load_gold_records(gold_path=args.gold_path)
    gold = _filter_records(gold_all, id_set)
    baseline_preds = _filter_records(load_jsonl(args.baseline_predictions), id_set)
    en_preds = _filter_records(load_jsonl(args.output_path), id_set)

    baseline_metrics = evaluate(gold, baseline_preds)
    en_metrics = evaluate(gold, en_preds)

    report = {
        "record_ids": record_ids,
        "hint_coverage": coverage,
        "baseline": _metrics_block("dutch_only", baseline_metrics),
        "english_hint": _metrics_block("english_hint", en_metrics),
        "delta": {
            "step_b_accuracy": (en_metrics.step_b_accuracy or 0) - (baseline_metrics.step_b_accuracy or 0),
            "dropout_agreement": (en_metrics.dropout_agreement or 0)
            - (baseline_metrics.dropout_agreement or 0),
        },
    }
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Report: {args.report_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
