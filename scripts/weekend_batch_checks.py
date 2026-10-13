#!/usr/bin/env python3
"""Exit-code checks for run_weekend_batch.sh chains."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from data_io import resolve


def _annotation_path() -> Path:
    return Path(resolve("trifecta_annotations"))


def cmd_annotation_rows(_: argparse.Namespace) -> int:
    path = _annotation_path()
    if not path.is_file():
        print(f"Missing {path}", file=sys.stderr)
        return 1
    count = sum(1 for _ in path.open(encoding="utf-8"))
    print(count)
    return 0


def cmd_rerank_new(_: argparse.Namespace) -> int:
    ann_path = _annotation_path()
    rer_path = Path(resolve("embedding_kwic_reranked"))
    if not rer_path.is_file():
        print(f"Missing {rer_path}", file=sys.stderr)
        return 1
    ann: set[str] = set()
    if ann_path.is_file():
        for line in ann_path.open(encoding="utf-8"):
            ann.add(json.loads(line)["provenance"]["record_id"])
    rer = [json.loads(line) for line in rer_path.open(encoding="utf-8")]
    new = [r for r in rer if r["record_id"] not in ann]
    print(len(rer), len(new))
    return 0


def cmd_assert_annotation_growth(args: argparse.Namespace) -> int:
    path = _annotation_path()
    if not path.is_file():
        print(f"Missing {path}", file=sys.stderr)
        return 1
    after = sum(1 for _ in path.open(encoding="utf-8"))
    delta = after - args.before
    if delta < args.min_delta:
        print(
            f"Batch did not grow annotations: before={args.before} after={after} "
            f"delta={delta} required>={args.min_delta}",
            file=sys.stderr,
        )
        return 1
    print(f"ok delta={delta} (after={after})")
    return 0


def cmd_assert_file(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"Missing file: {path}", file=sys.stderr)
        return 1
    if args.min_bytes and path.stat().st_size < args.min_bytes:
        print(f"File too small: {path} ({path.stat().st_size} bytes)", file=sys.stderr)
        return 1
    print(f"ok {path}")
    return 0


def cmd_assert_gijsbert_export(_: argparse.Namespace) -> int:
    root = Path(resolve("trifecta_gijsbert"))
    train = root / "train.jsonl"
    dev = root / "dev.jsonl"
    manifest = root / "label_manifest.json"
    for path in (train, dev, manifest):
        if not path.is_file() or path.stat().st_size == 0:
            print(f"Invalid GijsBERT export: {path}", file=sys.stderr)
            return 1
    train_n = sum(1 for _ in train.open(encoding="utf-8"))
    dev_n = sum(1 for _ in dev.open(encoding="utf-8"))
    if train_n < 10 or dev_n < 5:
        print(f"GijsBERT export too small: train={train_n} dev={dev_n}", file=sys.stderr)
        return 1
    print(f"ok train={train_n} dev={dev_n}")
    return 0


def cmd_assert_train_run(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    metrics = run_dir / "dev_metrics.json"
    report = run_dir / "report.md"
    for path in (metrics, report):
        if not path.is_file():
            print(f"Missing train output: {path}", file=sys.stderr)
            return 1
    print(f"ok {run_dir}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("annotation-rows", help="Print trifecta_annotations line count")

    sub.add_parser("rerank-new", help="Print: reranked_total new_vs_annotations")

    p = sub.add_parser("assert-annotation-growth")
    p.add_argument("--before", type=int, required=True)
    p.add_argument("--min-delta", type=int, required=True)

    p = sub.add_parser("assert-file")
    p.add_argument("path")
    p.add_argument("--min-bytes", type=int, default=1)

    sub.add_parser("assert-gijsbert-export")

    p = sub.add_parser("assert-train-run")
    p.add_argument("run_dir")

    args = parser.parse_args()
    handlers = {
        "annotation-rows": cmd_annotation_rows,
        "rerank-new": cmd_rerank_new,
        "assert-annotation-growth": cmd_assert_annotation_growth,
        "assert-file": cmd_assert_file,
        "assert-gijsbert-export": cmd_assert_gijsbert_export,
        "assert-train-run": cmd_assert_train_run,
    }
    sys.exit(handlers[args.cmd](args))


if __name__ == "__main__":
    main()
