#!/usr/bin/env python3
"""Compare TRIFECTA LLM models on the same gold eval slice.

Run batch for each model (optional) and write a side-by-side metrics report.

Examples::

    # Run two models on full gold eval set (100 rows)
    uv run python scripts/compare_llm_models.py --run-batch \\
      --models qwen2.5-coder:latest llama3.1:8b

    # Compare existing prediction files only
    uv run python scripts/compare_llm_models.py \\
      --predictions qwen=/Volumes/.../gold_predictions.jsonl \\
                  llama=/Volumes/.../gold_predictions_llama3_1_8b.jsonl

    # Disagreement slice with English hints
    uv run python scripts/compare_llm_models.py --run-batch --slice disagreements \\
      --english-hint --models qwen2.5-coder:latest mistral:7b
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from data_io import load_jsonl, resolve

from trifecta_annotation.batch import load_inputs, run_batch
from trifecta_annotation.gold_io import load_gold_records
from trifecta_annotation.model_compare import (
    compare_runs,
    predictions_path_for_model,
    render_comparison_markdown,
)


def _scratch_root() -> Path:
    try:
        return Path(resolve("trifecta_gold")).parent
    except Exception:
        return Path("/Volumes/Extreme SSD/scratch/trifecta")


def _eval_dir() -> Path:
    try:
        return Path(resolve("eval_reports"))
    except Exception:
        return _scratch_root() / "eval"


def _parse_predictions_arg(items: list[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected name=path, got: {item}")
        name, path = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Empty prediction name in: {item}")
        mapping[name] = Path(path).expanduser()
    return mapping


def _load_record_ids(fixes_csv: Path) -> list[str]:
    frame = pd.read_csv(fixes_csv)
    return sorted({str(rid).strip() for rid in frame["record_id"].dropna() if str(rid).strip()})


def _filter_records(records: list[dict], record_ids: set[str]) -> list[dict]:
    out: list[dict] = []
    for record in records:
        rid = str(record.get("record_id") or (record.get("provenance") or {}).get("record_id") or "")
        if rid in record_ids:
            out.append(record)
    return out


def _jsonl_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def _prediction_complete(path: Path, *, min_rows: int) -> bool:
    return _jsonl_row_count(path) >= min_rows


def main(argv: list[str] | None = None) -> int:
    root = _scratch_root()
    eval_dir = _eval_dir()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="*", default=[], help="Ollama model tags to batch")
    parser.add_argument(
        "--predictions",
        nargs="*",
        default=[],
        metavar="NAME=PATH",
        help="Named prediction JSONL files (compare-only or override auto paths)",
    )
    parser.add_argument("--inputs-path", type=Path, default=root / "gold_eval_inputs.jsonl")
    parser.add_argument("--gold-path", type=Path, default=root / "gold.parquet")
    parser.add_argument("--fixes-csv", type=Path, default=eval_dir / "gold_fixes.csv")
    parser.add_argument("--report-json", type=Path, default=eval_dir / "model_comparison.json")
    parser.add_argument("--report-md", type=Path, default=eval_dir / "model_comparison.md")
    parser.add_argument(
        "--slice",
        choices=("full", "disagreements"),
        default="full",
        help="full = all gold eval inputs; disagreements = gold_fixes record_ids",
    )
    parser.add_argument("--english-hint", action="store_true")
    parser.add_argument("--run-batch", action="store_true")
    parser.add_argument("--skip-existing", action="store_true", help="Do not re-run batch if output exists")
    parser.add_argument("--model", default=None, help="Default model when a run has no explicit tag")
    parser.add_argument("--base-url", default=None, help="OpenAI-compatible endpoint (local Ollama or remote vLLM)")
    parser.add_argument("--api-key", default=None, help="API key (default: TRIFECTA_API_KEY or OPENAI_API_KEY)")
    parser.add_argument("--run-label", default=None, help="Report label when model tag is unwieldy (single-model runs)")
    parser.add_argument("--output-path", type=Path, default=None, help="Output JSONL (single-model runs)")
    parser.add_argument(
        "--min-rows",
        type=int,
        default=None,
        help="With --skip-existing, require this many JSONL rows (default: slice size)",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Compare only prediction files that exist (final reports)",
    )
    args = parser.parse_args(argv)

    pred_map = _parse_predictions_arg(args.predictions)
    models = list(args.models)
    if not models and not pred_map:
        print("Provide --models and/or --predictions name=path", file=sys.stderr)
        return 1

    run_label = args.run_label
    if run_label and len(models) != 1:
        print("--run-label requires exactly one --models entry", file=sys.stderr)
        return 1

    for model in models:
        key = run_label or model
        if key not in pred_map:
            if args.output_path is not None and len(models) == 1:
                pred_map[key] = args.output_path.expanduser()
            elif run_label and len(models) == 1:
                pred_map[key] = root / f"gold_predictions_{run_label}.jsonl"
            else:
                pred_map[key] = predictions_path_for_model(
                    root,
                    model,
                    english_hint=args.english_hint,
                )

    all_inputs = load_inputs(input_path=args.inputs_path)
    record_ids: list[str] | None = None
    if args.slice == "disagreements":
        if not args.fixes_csv.exists():
            print(f"Missing {args.fixes_csv}; run eval_disagreements.py first", file=sys.stderr)
            return 1
        record_ids = _load_record_ids(args.fixes_csv)
    if args.limit is not None and record_ids is not None:
        record_ids = record_ids[: args.limit]
    elif args.limit is not None:
        record_ids = [str(row.get("record_id", "")) for row in all_inputs[: args.limit]]

    if record_ids is not None:
        id_set = set(record_ids)
        inputs = _filter_records(all_inputs, id_set)
    else:
        inputs = all_inputs
        record_ids = [str(row.get("record_id", "")) for row in inputs]

    if not inputs:
        print("No inputs for selected slice", file=sys.stderr)
        return 1

    min_rows = args.min_rows if args.min_rows is not None else len(inputs)

    if args.run_batch:
        for model in models:
            key = run_label or model
            out_path = pred_map[key]
            if args.skip_existing and _prediction_complete(out_path, min_rows=min_rows):
                print(f"Skip complete ({min_rows} rows): {out_path}", file=sys.stderr)
                continue
            print(f"Batch {model} -> {out_path}", file=sys.stderr)
            if out_path.exists() and not _prediction_complete(out_path, min_rows=min_rows):
                print(f"Replacing partial output ({_jsonl_row_count(out_path)} rows): {out_path}", file=sys.stderr)
                out_path.unlink()
            run_batch(
                inputs,
                output_path=out_path,
                model=model or args.model,
                base_url=args.base_url,
                api_key=args.api_key,
                english_hint=args.english_hint,
                description=f"TRIFECTA model compare ({key})",
                script=__file__,
            )

    missing = [name for name, path in pred_map.items() if not path.exists()]
    if missing and args.allow_missing:
        for name in missing:
            print(f"Omit missing: {name} ({pred_map[name]})", file=sys.stderr)
            del pred_map[name]
        missing = []
    if missing:
        for name in missing:
            print(f"Missing predictions for {name}: {pred_map[name]}", file=sys.stderr)
        if not args.run_batch:
            print("Pass --run-batch or provide existing --predictions paths", file=sys.stderr)
            return 1

    gold_all = load_gold_records(gold_path=args.gold_path)
    if record_ids is not None:
        gold = _filter_records(gold_all, set(record_ids))
    else:
        gold = gold_all

    runs: list[tuple[str, list[dict]]] = []
    for name, path in pred_map.items():
        preds = load_jsonl(path)
        if record_ids is not None:
            preds = _filter_records(preds, set(record_ids))
        runs.append((name, preds))

    comparison = compare_runs(gold, runs)
    report = {
        "slice": args.slice,
        "record_count": len(record_ids),
        "english_hint": args.english_hint,
        "base_url": args.base_url,
        "predictions": {name: str(path) for name, path in pred_map.items()},
        **comparison,
    }

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.report_md.write_text(render_comparison_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"JSON: {args.report_json}", file=sys.stderr)
    print(f"Markdown: {args.report_md}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
