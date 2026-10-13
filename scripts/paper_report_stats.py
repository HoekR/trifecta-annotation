#!/usr/bin/env python3
"""Print frozen tables for docs/PAPER_REPORT.md (read-only; no file writes).

Usage:
  uv run python scripts/paper_report_stats.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from data_io import resolve

RECIPE_MEDICAL = frozenset({"RECIPE_PRACTICE", "MEDICAL"})
LITERARY_TRAVEL = frozenset({"LITERARY", "TRAVEL"})
STEP_C_PREFIXES = ("COOKING_", "CURE_", "INGESTION_", "PR_")


def _bucket(regime: object) -> str:
    r = str(regime or "")
    if r in RECIPE_MEDICAL:
        return "recipe_medical"
    if r in LITERARY_TRAVEL:
        return "literary_travel"
    return r or "MISSING"


def _is_pair(gold: object, pred: object, a: str, b: str) -> bool:
    return {str(gold), str(pred)} == {a, b}


def _pct(n: int, total: int) -> str:
    if total <= 0:
        return "—"
    return f"{100.0 * n / total:.1f}%"


def main() -> None:
    eval_dir = Path(resolve("eval_reports"))
    scratch = Path(resolve("trifecta_gold")).parent
    metrics_path = eval_dir / "metrics.json"
    report_path = eval_dir / "report.md"
    frame_csv = eval_dir / "frame_disagreements.csv"
    gold_path = scratch / "gold_labelling_all.csv"
    if not gold_path.is_file():
        gold_path = Path(resolve("trifecta_gold_csv"))

    print("=== sources ===")
    print("metrics", metrics_path)
    print("report ", report_path)
    print("frames ", frame_csv)
    print("gold   ", gold_path)

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    print("\n=== stage metrics ===")
    for key in (
        "total",
        "step_a_entity_accuracy",
        "step_a_metaphor_accuracy",
        "dropout_agreement",
        "step_b_accuracy",
        "step_c_gold_rows",
        "step_c_comparable_rows",
        "step_c_joint_accuracy",
        "step_c_micro_accuracy",
        "step_c_soft_joint_accuracy",
        "step_c_soft_micro_accuracy",
    ):
        print(f"{key}: {metrics.get(key)}")

    print("\n=== Step B per-frame P / R / F1 ===")
    prec = metrics.get("step_b_per_frame_precision") or {}
    rec = metrics.get("step_b_per_frame_recall") or {}
    f1 = metrics.get("step_b_per_frame_f1") or {}
    for frame in sorted(set(prec) | set(rec) | set(f1)):
        print(
            f"{frame}: P={prec.get(frame)} R={rec.get(frame)} F1={f1.get(frame)}",
        )

    print("\n=== Step B by text_regime ===")
    by_reg = metrics.get("by_text_regime") or {}
    for regime, blob in sorted(by_reg.items()):
        if isinstance(blob, dict):
            print(
                f"{regime}: accuracy={blob.get('accuracy')} "
                f"count={blob.get('count')}",
            )
        else:
            print(f"{regime}: {blob}")

    print("\n=== Step C by frame ===")
    soft = metrics.get("step_c_soft_by_frame") or metrics.get("step_c_by_frame") or {}
    for frame, blob in sorted(soft.items()):
        print(f"{frame}: {blob}")

    gold = pd.read_csv(gold_path, dtype=str, keep_default_na=False)
    if "labelled" in gold.columns:
        lab = gold[gold["labelled"].str.lower().isin(["true", "1", "yes"])]
    else:
        lab = gold
    print("\n=== gold inventory ===")
    print("labelled_rows", len(lab))
    if "selected_frame" in lab.columns:
        print(lab["selected_frame"].value_counts().to_string())
    if "text_regime" in lab.columns:
        print("--- regimes ---")
        print(lab["text_regime"].value_counts().to_string())
    sc_cols = [c for c in lab.columns if c.startswith(STEP_C_PREFIXES)]
    if sc_cols:
        has_c = lab[sc_cols].apply(
            lambda row: any(str(x).strip() for x in row),
            axis=1,
        ).sum()
        print("rows_with_any_step_c_field", int(has_c))

    if not frame_csv.is_file():
        print("\n(missing frame_disagreements.csv — run eval_disagreements.py)")
        return

    frames = pd.read_csv(frame_csv, dtype=str, keep_default_na=False)
    slim_cols = [c for c in ("record_id", "text_regime") if c in lab.columns]
    slim = lab[slim_cols].drop_duplicates(subset=["record_id"], keep="last")
    df = frames.merge(slim, on="record_id", how="left")
    df["bucket"] = (
        df["text_regime"].map(_bucket) if "text_regime" in df.columns else "MISSING"
    )

    print("\n=== frame disagreement confusion (gold × pred) ===")
    print(pd.crosstab(df["gold_frame"], df["pred_frame"]).to_string())

    df["COOKING_CURE"] = [
        _is_pair(g, p, "COOKING_CREATION", "CURE")
        for g, p in zip(df["gold_frame"], df["pred_frame"], strict=True)
    ]
    df["CURE_INGESTION"] = [
        _is_pair(g, p, "CURE", "INGESTION")
        for g, p in zip(df["gold_frame"], df["pred_frame"], strict=True)
    ]
    df["INGESTION_NONE"] = [
        _is_pair(g, p, "INGESTION", "NONE")
        for g, p in zip(df["gold_frame"], df["pred_frame"], strict=True)
    ]
    df["COOKING_INGESTION"] = [
        _is_pair(g, p, "COOKING_CREATION", "INGESTION")
        for g, p in zip(df["gold_frame"], df["pred_frame"], strict=True)
    ]

    print("\n=== regime × boundary rates (among frame disagreements) ===")
    print(f"{'bucket':<18} {'n':>4}  COOKING↔CURE  CURE↔ING  ING↔NONE  COOK↔ING")
    for bucket in ("recipe_medical", "literary_travel"):
        sub = df[df["bucket"] == bucket]
        n = len(sub)
        print(
            f"{bucket:<18} {n:>4}  "
            f"{sub['COOKING_CURE'].sum():>3} ({_pct(int(sub['COOKING_CURE'].sum()), n):>6})  "
            f"{sub['CURE_INGESTION'].sum():>3} ({_pct(int(sub['CURE_INGESTION'].sum()), n):>6})  "
            f"{sub['INGESTION_NONE'].sum():>3} ({_pct(int(sub['INGESTION_NONE'].sum()), n):>6})  "
            f"{sub['COOKING_INGESTION'].sum():>3} ({_pct(int(sub['COOKING_INGESTION'].sum()), n):>6})",
        )

    print("\n=== COOKING↔CURE directionality (recipe_medical) ===")
    sub = df[(df["bucket"] == "recipe_medical") & df["COOKING_CURE"]]
    if sub.empty:
        print("(none)")
    else:
        print(pd.crosstab(sub["gold_frame"], sub["pred_frame"]).to_string())

    _print_model_comparisons(eval_dir)


def _print_model_comparisons(eval_dir: Path) -> None:
    print("\n=== LLM model_comparison*.md (paths) ===")
    for path in sorted(eval_dir.glob("model_comparison*.md")):
        print(path)
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines()[:20]:
            print(" ", line)

    models_root = Path(resolve("trifecta_gijsbert_models"))
    print("\n=== encoder fine-tune reports (dev accuracy) ===")
    print(f"root {models_root}")
    if not models_root.is_dir():
        print("(missing trifecta_gijsbert_models)")
        return
    rows: list[tuple[float, str, str]] = []
    for report in sorted(models_root.glob("*/report.md")):
        text = report.read_text(encoding="utf-8")
        acc = ""
        frames = ""
        base = ""
        for line in text.splitlines():
            if line.startswith("- Model:"):
                base = line.split("`", 1)[-1].rstrip("`")
            if "Dev accuracy (all)" in line:
                acc = line.split("**")[-2] if "**" in line else line
            if "Dev accuracy (frames only" in line:
                frames = line.split("**")[-2] if "**" in line else line
        try:
            sort_key = float(acc) if acc else -1.0
        except ValueError:
            sort_key = -1.0
        rows.append((sort_key, report.parent.name, f"all={acc} frames={frames} base={base}"))
    for _, name, summary in sorted(rows, reverse=True):
        print(f"{name}: {summary}")


if __name__ == "__main__":
    main()
