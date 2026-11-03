#!/usr/bin/env python3
"""Build gold lemma priors JSON from labelled gold (G2)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from data_io import resolve
from data_io.provenance import ProvenanceRecord, git_commit_hash, write_sidecar

from trifecta_annotation.gold_lemma_priors import (
    DEFAULT_DISAMBIG_MIN_MIX_RATE,
    DEFAULT_DISAMBIG_MIN_N,
    DEFAULT_MAX_FOOD_PASS_RATE,
    DEFAULT_MIN_DROP_RATE,
    DEFAULT_MIN_N,
    DEFAULT_MIN_OTHER_SENSE_RATE,
    DEFAULT_SOFT_FOOD_PASS_CAP,
    PriorThresholds,
    build_priors_payload,
    offenders_summary_lines,
)


def _default_labelling_csv() -> Path:
    parent = Path(resolve("trifecta_gold")).parent
    merged = parent / "gold_labelling_all.csv"
    if merged.exists():
        return merged
    return Path(resolve("trifecta_gold_csv"))


def _load_rows(csv_path: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    return frame.to_dict(orient="records")


def _write_priors_json(
    payload: dict[str, Any],
    *,
    logical_name: str | None,
    out_path: Path | None,
    script: str,
) -> Path:
    if logical_name:
        path = Path(resolve(logical_name))
        manager_desc = ""
        parent_sources: list[str] = []
        try:
            from data_io import get_manager

            dataset = get_manager().dataset(logical_name)
            manager_desc = dataset.description or ""
            if dataset.parent:
                parent_sources = [dataset.parent]
        except Exception:
            parent_sources = ["trifecta_gold"]
    elif out_path is not None:
        path = Path(out_path).expanduser().resolve()
        manager_desc = "Gold lemma priors (ad-hoc path)"
        parent_sources = ["trifecta_gold"]
    else:
        raise SystemExit("Provide --output-logical or --output-path")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    record = ProvenanceRecord(
        logical_name=logical_name or path.stem,
        phase="semi",
        parent_sources=parent_sources,
        description=manager_desc
        or "Lemma priors from labelled gold (hard-block + soft signals)",
        created_by_script=script,
        record_count=int(meta.get("n_lemmas") or len(payload.get("lemmas") or {})),
        git_commit=git_commit_hash(path.parent),
    )
    write_sidecar(path, record)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build lemma priors from labelled gold_labelling_all.csv (or gold CSV). "
            "Hard-blocks lemmas with high drop / low food-pass (threshold-gated). "
            "Output JSON is consumed by gold_target_filter (G3)."
        )
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=None,
        help="Labelling CSV (default: gold_labelling_all.csv beside trifecta_gold)",
    )
    parser.add_argument(
        "--output-logical",
        default="gold_lemma_priors",
        help="Manifest logical name (default: gold_lemma_priors)",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Write JSON here instead of manifest logical path",
    )
    parser.add_argument("--min-n", type=int, default=DEFAULT_MIN_N)
    parser.add_argument(
        "--max-food-pass-rate",
        type=float,
        default=DEFAULT_MAX_FOOD_PASS_RATE,
        help="Hard-block only if food_pass_rate <= this (with min-drop-rate)",
    )
    parser.add_argument("--min-drop-rate", type=float, default=DEFAULT_MIN_DROP_RATE)
    parser.add_argument(
        "--min-other-sense-rate",
        type=float,
        default=DEFAULT_MIN_OTHER_SENSE_RATE,
        help="Hard-block if other_sense_rate >= this (when homonym_check filled)",
    )
    parser.add_argument(
        "--soft-food-pass-cap",
        type=int,
        default=DEFAULT_SOFT_FOOD_PASS_CAP,
        help="Soft-deprioritize lemmas with food_pass >= this",
    )
    parser.add_argument("--disambig-min-n", type=int, default=DEFAULT_DISAMBIG_MIN_N)
    parser.add_argument(
        "--disambig-min-mix-rate",
        type=float,
        default=DEFAULT_DISAMBIG_MIN_MIX_RATE,
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print top offenders and blocked list",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="Offender rows to print with --summary (default: 15)",
    )
    args = parser.parse_args()

    csv_path = args.csv_path or _default_labelling_csv()
    if not csv_path.exists():
        raise SystemExit(f"Gold labelling CSV not found: {csv_path}")

    thresholds = PriorThresholds(
        min_n=args.min_n,
        max_food_pass_rate=args.max_food_pass_rate,
        min_drop_rate=args.min_drop_rate,
        min_other_sense_rate=args.min_other_sense_rate,
        soft_food_pass_cap=args.soft_food_pass_cap,
        disambig_min_n=args.disambig_min_n,
        disambig_min_mix_rate=args.disambig_min_mix_rate,
    )
    rows = _load_rows(csv_path)
    payload = build_priors_payload(
        rows,
        thresholds=thresholds,
        source=str(csv_path),
    )

    logical = None if args.output_path is not None else args.output_logical
    path = _write_priors_json(
        payload,
        logical_name=logical,
        out_path=args.output_path,
        script=__file__,
    )

    if args.summary:
        for line in offenders_summary_lines(payload, limit=args.top):
            print(line)
        print(f"wrote -> {path}")
    else:
        print(path)


if __name__ == "__main__":
    main()
