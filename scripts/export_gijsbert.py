#!/usr/bin/env python3
"""Export GijsBERT train/dev JSONL from silver + gold annotations."""

from __future__ import annotations

import argparse
import json

from data_io import load_jsonl, resolve

from trifecta_annotation.gijsbert_export import export_gijsbert_splits
from trifecta_annotation.gold_io import load_gold_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Export GijsBERT frame-classification splits.")
    parser.add_argument(
        "--silver-logical",
        default="trifecta_annotations",
        help="Silver/batch JSONL logical name",
    )
    parser.add_argument("--silver-path", default=None)
    parser.add_argument("--gold-logical", default="trifecta_gold")
    parser.add_argument("--gold-path", default=None)
    parser.add_argument("--output-dir", default=None, help="Default: scratch trifecta/gijsbert")
    parser.add_argument(
        "--mark-mode",
        choices=["food", "verb", "both"],
        default="both",
        help="food=[TGT] on food; verb=[VRB] on trigger; both=mark food and verb",
    )
    args = parser.parse_args()

    if args.silver_path:
        silver = load_jsonl(args.silver_path)
    else:
        silver = load_jsonl(resolve(args.silver_logical))

    gold = load_gold_records(
        gold_logical=args.gold_logical,
        gold_path=args.gold_path,
    )

    out = args.output_dir
    if out is None:
        out = resolve("trifecta_gijsbert") if _has_manifest_dataset() else "trifecta/gijsbert"

    paths = export_gijsbert_splits(
        silver_records=silver,
        gold_records=gold,
        output_dir=out,
        mark_mode=args.mark_mode,
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2))


def _has_manifest_dataset() -> bool:
    try:
        resolve("trifecta_gijsbert")
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()
