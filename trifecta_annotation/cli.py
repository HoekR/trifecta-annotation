"""CLI entry points for TRIFECTA pipeline tools."""

from __future__ import annotations

import argparse
import json
import sys

from data_io import load_jsonl

from trifecta_annotation.batch import load_inputs, run_batch
from trifecta_annotation.eval import run_eval
from trifecta_annotation.pipeline import annotate_record
from trifecta_annotation.schemas import KwicInput
from trifecta_annotation.step_b import classify_context


def _cmd_classify(args: argparse.Namespace) -> None:
    result = classify_context(
        args.target,
        args.context,
        model=args.model,
        base_url=args.base_url,
    )
    print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))


def _cmd_annotate(args: argparse.Namespace) -> None:
    inp = KwicInput(
        record_id=args.record_id or f"cli:{args.target}",
        corpus=args.corpus,
        target_word=args.target,
        context_text=args.context,
        date=args.date,
    )
    result = annotate_record(
        inp,
        model=args.model,
        base_url=args.base_url,
        technique_hint=args.technique_hint,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


def _cmd_batch(args: argparse.Namespace) -> None:
    inputs = load_inputs(
        input_logical=args.input_logical,
        input_path=args.input_path,
    )
    path = run_batch(
        inputs,
        output_logical=args.output_logical,
        output_path=args.output_path,
        model=args.model,
        base_url=args.base_url,
        resume=args.resume,
        concurrency=args.concurrency,
        parent_sources=args.parent_sources,
        description=args.description,
        script=__file__,
        english_hint=args.english_hint,
    )
    records = load_jsonl(path)
    ok = sum(1 for record in records if not record.get("error"))
    step_c = sum(1 for record in records if record.get("step_c"))
    print(f"Done: {path} ({len(records)} rows, {ok} ok, {step_c} with step_c)")


def _cmd_eval(args: argparse.Namespace) -> None:
    metrics, report_path = run_eval(
        gold_logical=args.gold,
        predictions_logical=args.predictions,
        gold_path=args.gold_path,
        predictions_path=args.predictions_path,
        script=__file__,
    )
    print(json.dumps(metrics.to_dict(), indent=2))
    print(f"Report: {report_path}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRIFECTA annotation tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    classify = subparsers.add_parser("classify", help="Step B macro-frame classification")
    classify.add_argument("--target", required=True)
    classify.add_argument("--context", required=True)
    classify.add_argument("--model", default=None)
    classify.add_argument("--base-url", default=None)
    classify.set_defaults(func=_cmd_classify)

    annotate = subparsers.add_parser("annotate", help="Full A→B→C pipeline")
    annotate.add_argument("--target", required=True)
    annotate.add_argument("--context", required=True)
    annotate.add_argument("--corpus", default="manual")
    annotate.add_argument("--record-id", default=None)
    annotate.add_argument("--date", default=None)
    annotate.add_argument("--technique-hint", default=None)
    annotate.add_argument("--model", default=None)
    annotate.add_argument("--base-url", default=None)
    annotate.set_defaults(func=_cmd_annotate)

    batch = subparsers.add_parser("batch", help="Batch annotate JSONL inputs")
    batch.add_argument("--input-logical", default=None)
    batch.add_argument("--input-path", default=None)
    batch.add_argument("--output-logical", default="trifecta_annotations")
    batch.add_argument("--output-path", default=None)
    batch.add_argument("--model", default=None)
    batch.add_argument("--base-url", default=None)
    batch.add_argument("--resume", action="store_true")
    batch.add_argument("--concurrency", type=int, default=1)
    batch.add_argument("--english-hint", action="store_true")
    batch.add_argument("--parent-sources", nargs="*", default=None)
    batch.add_argument("--description", default="TRIFECTA batch annotation run")
    batch.set_defaults(func=_cmd_batch)

    evaluate = subparsers.add_parser("eval", help="Evaluate predictions against gold")
    evaluate.add_argument("--gold", default="trifecta_gold")
    evaluate.add_argument("--predictions", default="trifecta_annotations")
    evaluate.add_argument("--gold-path", default=None)
    evaluate.add_argument("--predictions-path", default=None)
    evaluate.set_defaults(func=_cmd_eval)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


def main_classify() -> None:
    main(["classify", *sys.argv[1:]])


def main_annotate() -> None:
    main(["annotate", *sys.argv[1:]])


def main_batch() -> None:
    main(["batch", *sys.argv[1:]])


def main_eval() -> None:
    main(["eval", *sys.argv[1:]])


if __name__ == "__main__":
    main()
