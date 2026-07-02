#!/usr/bin/env python3
"""Export gold vs prediction disagreements for manual review (CSV-first)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.gold_io import (
    GOLD_FIXES_SHEET_COLUMNS,
    build_gold_fixes_rows,
    carry_forward_gold_fixes,
    load_gold_fixes_frame,
    load_gold_records,
)

KINDS = ("frame", "dropout", "step_a")


def _eval_dir() -> Path:
    return Path(resolve("eval_reports"))


def _default_gold_path() -> Path:
    return Path(resolve("trifecta_gold"))


def _default_predictions_path() -> Path:
    return _default_gold_path().parent / "gold_predictions.jsonl"


def _default_fixes_csv() -> Path:
    return _eval_dir() / "gold_fixes.csv"


def _frame(record: dict) -> str:
    step_b = record.get("step_b") or {}
    frame = step_b.get("selected_frame")
    if frame is None:
        return ""
    return frame if isinstance(frame, str) else str(frame)


def _short_context(text: str, target: str, *, width: int = 120) -> str:
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


def build_disagreement_rows(
    gold_records: list[dict],
    pred_records: list[dict],
    *,
    kind: str,
) -> list[dict[str, object]]:
    gold_index = {
        str((r.get("provenance") or {}).get("record_id")): r
        for r in gold_records
        if (r.get("provenance") or {}).get("record_id")
    }
    pred_index = {
        str((r.get("provenance") or {}).get("record_id")): r
        for r in pred_records
        if (r.get("provenance") or {}).get("record_id")
    }
    shared = sorted(set(gold_index) & set(pred_index))
    rows: list[dict[str, object]] = []

    for record_id in shared:
        gold = gold_index[record_id]
        pred = pred_index[record_id]
        prov = gold.get("provenance") or {}
        target = str(prov.get("target_word") or "")
        context = str(prov.get("context_text") or "")

        gold_drop = bool(gold.get("dropped"))
        pred_drop = bool(pred.get("dropped"))
        gold_frame = _frame(gold)
        pred_frame = _frame(pred)

        gold_a = gold.get("step_a") or {}
        pred_a = pred.get("step_a") or {}

        mismatch = False
        issue = ""
        if kind == "dropout":
            mismatch = gold_drop != pred_drop
            issue = (
                f"gold dropped={gold_drop} ({gold.get('drop_reason') or ''}); "
                f"pred dropped={pred_drop} ({pred.get('drop_reason') or ''})"
            )
        elif kind == "step_a":
            if gold_a and pred_a:
                mismatch = (
                    gold_a.get("is_food_entity") != pred_a.get("is_food_entity")
                    or gold_a.get("is_metaphor") != pred_a.get("is_metaphor")
                )
            issue = (
                f"gold food={gold_a.get('is_food_entity')} metaphor={gold_a.get('is_metaphor')}; "
                f"pred food={pred_a.get('is_food_entity')} metaphor={pred_a.get('is_metaphor')}"
            )
        else:
            if gold_drop or pred_drop:
                continue
            mismatch = gold_frame != pred_frame
            issue = f"gold={gold_frame or '—'}; pred={pred_frame or '—'}"

        if not mismatch:
            continue

        rows.append(
            {
                "record_id": record_id,
                "target_word": target,
                "gold_frame": gold_frame,
                "pred_frame": pred_frame,
                "gold_dropped": gold_drop,
                "pred_dropped": pred_drop,
                "gold_drop_reason": gold.get("drop_reason") or "",
                "pred_drop_reason": pred.get("drop_reason") or "",
                "gold_lexical_unit": (gold.get("step_b") or {}).get("lexical_unit", ""),
                "pred_lexical_unit": (pred.get("step_b") or {}).get("lexical_unit", ""),
                "issue": issue,
                "context_snippet": _short_context(context, target),
            },
        )
    return rows


def load_predictions(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def write_disagreement_exports(
    *,
    gold_path: Path,
    predictions_path: Path,
    fixes_csv_path: Path,
    kinds: tuple[str, ...] = KINDS,
    limit: int | None = None,
    workbook_path: Path | None = None,
) -> dict[str, int]:
    gold = load_gold_records(gold_path=gold_path)
    preds = load_predictions(predictions_path)

    all_disagreements: list[dict[str, object]] = []
    counts: dict[str, int] = {}
    out_dir = fixes_csv_path.parent

    existing_fixes = pd.DataFrame()
    if fixes_csv_path.exists():
        existing_fixes = load_gold_fixes_frame(fixes_csv_path)

    for kind in kinds:
        rows = build_disagreement_rows(gold, preds, kind=kind)
        if limit is not None:
            rows = rows[:limit]
        counts[kind] = len(rows)
        all_disagreements.extend(rows)
        _write_csv(pd.DataFrame(rows), out_dir / f"{kind}_disagreements.csv")

    fixes = build_gold_fixes_rows(all_disagreements)
    fixes = carry_forward_gold_fixes(fixes, existing_fixes)
    fixes_frame = pd.DataFrame(fixes, columns=GOLD_FIXES_SHEET_COLUMNS)
    _write_csv(fixes_frame, fixes_csv_path)
    counts["gold_fixes"] = len(fixes)

    if workbook_path is not None:
        with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
            for kind in kinds:
                pd.read_csv(out_dir / f"{kind}_disagreements.csv").to_excel(
                    writer,
                    sheet_name=kind,
                    index=False,
                )
            fixes_frame.to_excel(writer, sheet_name="gold_fixes", index=False)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export disagreements as CSV (edit gold_fixes.csv; Excel optional).",
    )
    parser.add_argument("--gold-path", type=Path, default=None)
    parser.add_argument("--predictions-path", type=Path, default=None)
    parser.add_argument(
        "--kind",
        choices=[*KINDS, "all"],
        default="all",
    )
    parser.add_argument(
        "--fixes-csv",
        type=Path,
        default=None,
        help="Editable review file (default: eval/gold_fixes.csv)",
    )
    parser.add_argument(
        "--workbook",
        action="store_true",
        help="Also write gold_disagreements.xlsx for skim-only (do not import from Excel)",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    gold_path = args.gold_path or _default_gold_path()
    predictions_path = args.predictions_path or _default_predictions_path()
    fixes_csv = args.fixes_csv or _default_fixes_csv()
    workbook = _eval_dir() / "gold_disagreements.xlsx" if args.workbook else None
    kinds = KINDS if args.kind == "all" else (args.kind,)

    if not gold_path.exists():
        raise SystemExit(f"Gold not found: {gold_path}")
    if not predictions_path.exists():
        raise SystemExit(f"Predictions not found: {predictions_path}")

    counts = write_disagreement_exports(
        gold_path=gold_path,
        predictions_path=predictions_path,
        fixes_csv_path=fixes_csv,
        kinds=kinds,
        limit=args.limit,
        workbook_path=workbook,
    )
    print(f"Wrote {fixes_csv}")
    print(f"Skim: {fixes_csv.parent}/frame_disagreements.csv (and dropout, step_a)", file=sys.stderr)
    if workbook:
        print(f"Workbook (skim only): {workbook}", file=sys.stderr)
    summary = ", ".join(f"{kind}={counts[kind]}" for kind in (*kinds, "gold_fixes"))
    print(summary, file=sys.stderr)


if __name__ == "__main__":
    main()
