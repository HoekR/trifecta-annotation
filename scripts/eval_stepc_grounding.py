#!/usr/bin/env python3
"""Calibrate + verify Step C grounding by re-scoring existing LLM predictions.

No new LLM calls: re-scores the already-generated gold_predictions.jsonl
(scored for the current ~23.7% soft-micro production baseline) with
grounding applied post-hoc at a sweep of thresholds, through the same
trifecta_annotation/eval.py scoring used for every other Step C number in
PLAN.md / docs/GOLD_LABELLING.md. See plans/steps/STEPC_GROUNDING.md (G0/G1).
"""

from __future__ import annotations

import argparse
import copy
import json

from data_io import load_jsonl, resolve

from trifecta_annotation.embedding_candidates import GysbertEmbedder
from trifecta_annotation.eval import STEP_C_FIELDS, evaluate
from trifecta_annotation.gold_io import load_gold_records
from trifecta_annotation.schemas import TrifectaFrame
from trifecta_annotation.step_c_grounding import ground_step_c_dict

DEFAULT_THRESHOLDS = [None, 0.75, 0.80, 0.85, 0.90, 0.92, 0.95]  # None = ungrounded baseline


def ground_predictions(
    pred_records: list[dict],
    *,
    embedder: GysbertEmbedder,
    threshold: float,
) -> tuple[list[dict], int, int]:
    """Return (grounded records, n_fields_checked, n_fields_replaced)."""
    out = copy.deepcopy(pred_records)
    n_checked = 0
    n_replaced = 0
    for record in out:
        step_c = record.get("step_c")
        if not step_c:
            continue
        frame_str = step_c.get("frame")
        if not frame_str:
            continue
        try:
            frame = TrifectaFrame(frame_str)
        except ValueError:
            continue
        fields = STEP_C_FIELDS.get(frame)
        if not fields:
            continue
        provenance = record.get("provenance") or {}
        context_text = str(provenance.get("context_text") or "")
        target_word = str(provenance.get("target_word") or "")
        if not context_text:
            continue
        before = {f: step_c.get(f) for f in fields}
        step_c, audit = ground_step_c_dict(
            step_c, fields, context_text, target_word, embedder=embedder, threshold=threshold
        )
        for f in fields:
            if before.get(f):  # only counts fields that had a non-empty draft value
                n_checked += 1
                if step_c.get(f) != before.get(f):
                    n_replaced += 1
    return out, n_checked, n_replaced


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate + verify Step C grounding.")
    parser.add_argument("--gold-logical", default="trifecta_gold")
    parser.add_argument("--predictions-logical", default="gold_predictions")
    parser.add_argument(
        "--thresholds",
        type=str,
        default=None,
        help="Comma-separated thresholds to sweep (default: built-in sweep incl. ungrounded baseline)",
    )
    args = parser.parse_args()

    gold_records = load_gold_records(gold_logical=args.gold_logical)
    pred_records = load_jsonl(resolve(args.predictions_logical))

    thresholds: list[float | None] = (
        [None, *[float(t) for t in args.thresholds.split(",")]]
        if args.thresholds
        else DEFAULT_THRESHOLDS
    )

    embedder = GysbertEmbedder()

    print(f"{'threshold':>10} {'joint':>7} {'micro':>7} {'soft_joint':>10} {'soft_micro':>10} {'checked':>8} {'replaced':>9}")
    for threshold in thresholds:
        if threshold is None:
            scored = pred_records
            n_checked = n_replaced = 0
        else:
            scored, n_checked, n_replaced = ground_predictions(
                pred_records, embedder=embedder, threshold=threshold
            )
        metrics = evaluate(gold_records, scored)
        label = "ungrounded" if threshold is None else f"{threshold:.2f}"
        print(
            f"{label:>10} "
            f"{metrics.step_c_joint_accuracy or 0:>7.3f} "
            f"{metrics.step_c_micro_accuracy or 0:>7.3f} "
            f"{metrics.step_c_soft_joint_accuracy or 0:>10.3f} "
            f"{metrics.step_c_soft_micro_accuracy or 0:>10.3f} "
            f"{n_checked:>8} {n_replaced:>9}"
        )

    print(json.dumps({"note": "pick the threshold with best soft_micro without checked/replaced going to 0"}, indent=2))


if __name__ == "__main__":
    main()
