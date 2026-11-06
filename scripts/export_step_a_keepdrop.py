#!/usr/bin/env python3
"""Export binary Step A KEEP/DROP splits from cascade annotations.

Merges the four annotation sources used in PLAN.md §9i. Labels are Step A's
own keep/drop verdict — not Step-B-collapsed NONE.

    uv run python scripts/export_step_a_keepdrop.py --summary
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from data_io import load_jsonl, resolve

from trifecta_annotation.step_a_keepdrop import export_keepdrop_splits

DEFAULT_SOURCES = (
    "trifecta_annotations",
    "dbnl_sweep_annotations",
    "colonial_annotations",
    "handdownload_annotations",
)


def _load_optional(logical: str) -> list[dict]:
    try:
        path = resolve(logical)
    except Exception as exc:  # noqa: BLE001 — missing scratch mount is expected locally
        print(f"skip {logical}: {exc}", flush=True)
        return []
    if not Path(path).exists():
        print(f"skip {logical}: missing {path}", flush=True)
        return []
    rows = load_jsonl(path)
    print(f"loaded {logical}: {len(rows)} rows", flush=True)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources",
        nargs="*",
        default=list(DEFAULT_SOURCES),
        help="Manifest logical names to merge (default: four cascade sources)",
    )
    parser.add_argument("--output-dir", default=None, help="Default: scratch trifecta/step_a_keepdrop")
    parser.add_argument("--model-base", default="emanjavacas/globertise")
    parser.add_argument("--dev-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    records: list[dict] = []
    for logical in args.sources:
        records.extend(_load_optional(logical))

    out = args.output_dir
    if out is None:
        try:
            out = resolve("trifecta_step_a_keepdrop")
        except Exception:
            out = "trifecta/step_a_keepdrop"

    paths = export_keepdrop_splits(
        records,
        out,
        dev_fraction=args.dev_fraction,
        seed=args.seed,
        model_base=args.model_base,
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))
    if args.summary:
        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        print(json.dumps(manifest["counts"], indent=2))


if __name__ == "__main__":
    main()
