#!/usr/bin/env python3
"""Export regime-focused disagreement rows for manual spot-check review."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from data_io import load_jsonl, resolve

from trifecta_annotation.gijsbert_export import mark_target_in_context
from trifecta_annotation.gold_io import load_gold_records
from trifecta_annotation.review_columns import HOMONYM_REVIEW_COLUMNS, empty_homonym_review_row


def _frame(record: dict) -> str:
    if record.get("dropped"):
        return "DROPPED"
    step_b = record.get("step_b") or {}
    frame = step_b.get("selected_frame")
    return str(frame) if frame else "NONE"


def _regime(record: dict) -> str:
    return str((record.get("provenance") or {}).get("text_regime") or "UNKNOWN")


def short_context(text: str, target: str, *, width: int = 240) -> str:
    """Center snippet on target word (same logic as eval_disagreements)."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return ""
    needle = str(target or "").strip()
    if needle:
        match = re.search(re.escape(needle), text, flags=re.IGNORECASE)
        if match:
            start = max(0, match.start() - width // 3)
            end = min(len(text), match.end() + (2 * width) // 3)
            snippet = text[start:end]
            return ("…" if start else "") + snippet + ("…" if end < len(text) else "")
    return text[:width] + ("…" if len(text) > width else "")


def target_in_context(text: str, target: str) -> bool:
    if not text or not target:
        return False
    return bool(re.search(rf"\b{re.escape(target)}\b", text, flags=re.IGNORECASE))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-path", type=Path, default=None)
    parser.add_argument("--predictions-path", type=Path, default=None)
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument(
        "--regime",
        action="append",
        default=[],
        help="Filter text_regime (repeatable). Default: LITERARY + any INGESTION row",
    )
    parser.add_argument("--frame", default="", help="Optional gold/pred frame filter substring")
    args = parser.parse_args()

    scratch = Path(resolve("trifecta_gold")).parent
    gold_path = args.gold_path or scratch / "gold.parquet"
    pred_path = args.predictions_path or scratch / "gold_predictions.jsonl"
    out = args.output_path or scratch / "eval" / "spotcheck_disagreements.csv"

    gold = load_gold_records(gold_path=gold_path)
    preds = {
        str((r.get("provenance") or {}).get("record_id")): r
        for r in load_jsonl(pred_path)
    }

    rows: list[dict[str, str]] = []
    for record in gold:
        rid = str((record.get("provenance") or {}).get("record_id"))
        pred = preds.get(rid)
        if pred is None:
            continue
        gf, pf = _frame(record), _frame(pred)
        if gf == pf:
            continue
        regime = _regime(record)
        if args.regime and regime not in args.regime:
            if gf != "INGESTION" and pf != "INGESTION":
                continue
        elif not args.regime:
            if regime != "LITERARY" and gf != "INGESTION" and pf != "INGESTION":
                continue
        if args.frame and args.frame not in {gf, pf}:
            continue

        prov = record["provenance"]
        target = str(prov.get("target_word") or "")
        context = str(prov.get("context_text") or "")
        marked = mark_target_in_context(context, target)
        rows.append(
            {
                "text_regime": regime,
                "record_id": rid,
                "target_word": target,
                "gold_frame": gf,
                "pred_frame": pf,
                "gold_lexical_unit": str((record.get("step_b") or {}).get("lexical_unit") or ""),
                "pred_lexical_unit": str((pred.get("step_b") or {}).get("lexical_unit") or ""),
                "target_in_context": "true" if target_in_context(context, target) else "false",
                "context_snippet": short_context(context, target),
                "context_marked": short_context(marked, "[TGT]"),
                "verdict": "",
                "review_notes": "",
                **empty_homonym_review_row(),
            }
        )

    fieldnames = (
        [
            "text_regime",
            "record_id",
            "target_word",
            "gold_frame",
            "pred_frame",
            "gold_lexical_unit",
            "pred_lexical_unit",
            "target_in_context",
            "context_snippet",
            "context_marked",
            "verdict",
            "review_notes",
        ]
        + list(HOMONYM_REVIEW_COLUMNS)
    )

    rows.sort(key=lambda r: (r["text_regime"], r["gold_frame"], r["pred_frame"], r["record_id"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows → {out}")


if __name__ == "__main__":
    main()
