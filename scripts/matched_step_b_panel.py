#!/usr/bin/env python3
"""Matched Step B panel: one gold freeze, same metrics for LLM (+ optional encoders).

Freeze rule (agreed): ``labelled=true`` ∧ non-empty ``selected_frame``.

Metrics per system (on freeze ∩ available preds):
  - n
  - accuracy (all)
  - accuracy (frames-only: gold ≠ NONE)
  - macro-F1 over frames present in gold on that panel

Usage:
  uv run python scripts/matched_step_b_panel.py
  uv run python scripts/matched_step_b_panel.py --predict-encoders
  uv run python scripts/matched_step_b_panel.py --write-md --article-ready
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
from data_io import resolve
from trifecta_annotation.eval import _per_class_f1
from trifecta_annotation.gijsbert_export import FRAME_LABELS

NONE_LABEL = "NONE"
FREEZE_RULE = "labelled ∧ non-empty selected_frame"


def load_freeze_frames(gold_csv: Path) -> dict[str, str]:
    """record_id → selected_frame for the matched freeze."""
    frame = pd.read_csv(gold_csv, dtype=str, keep_default_na=False)
    if "labelled" in frame.columns:
        frame = frame[frame["labelled"].str.lower().isin(["true", "1", "yes"])]
    if "record_id" not in frame.columns or "selected_frame" not in frame.columns:
        raise SystemExit(f"gold CSV missing record_id/selected_frame: {gold_csv}")
    frame = frame[frame["selected_frame"].astype(str).str.strip().ne("")]
    # last row wins if duplicates
    out: dict[str, str] = {}
    for row in frame.itertuples(index=False):
        rid = str(getattr(row, "record_id")).strip()
        lab = str(getattr(row, "selected_frame")).strip()
        if rid and lab:
            out[rid] = lab
    return out


def score_step_b_panel(
    gold_by_id: dict[str, str],
    pred_by_id: dict[str, str],
) -> dict[str, Any]:
    """Score preds against freeze gold; only IDs in both maps."""
    shared = sorted(set(gold_by_id) & set(pred_by_id))
    if not shared:
        return {
            "n": 0,
            "n_frames_only": 0,
            "accuracy_all": None,
            "accuracy_frames_only": None,
            "macro_f1": None,
            "per_frame_f1": {},
            "missing_pred": len(set(gold_by_id) - set(pred_by_id)),
        }

    gold = [gold_by_id[i] for i in shared]
    pred = [pred_by_id[i] for i in shared]
    acc_all = sum(g == p for g, p in zip(gold, pred, strict=True)) / len(shared)

    frame_pairs = [(g, p) for g, p in zip(gold, pred, strict=True) if g != NONE_LABEL]
    if frame_pairs:
        fg = [g for g, _ in frame_pairs]
        fp = [p for _, p in frame_pairs]
        acc_fo = sum(g == p for g, p in frame_pairs) / len(frame_pairs)
    else:
        fg, fp, acc_fo = [], [], None

    per_f1 = _per_class_f1(gold, pred)
    # macro over labels that appear in gold (stable when a class is absent)
    gold_labels = sorted({g for g in gold if g})
    macro = (
        sum(per_f1.get(lab, 0.0) for lab in gold_labels) / len(gold_labels)
        if gold_labels
        else None
    )

    return {
        "n": len(shared),
        "n_frames_only": len(frame_pairs),
        "accuracy_all": acc_all,
        "accuracy_frames_only": acc_fo,
        "macro_f1": macro,
        "per_frame_f1": {k: per_f1[k] for k in FRAME_LABELS if k in per_f1},
        "missing_pred": len(set(gold_by_id) - set(pred_by_id)),
    }


def _frame_from_annotation(record: dict[str, Any]) -> str | None:
    if record.get("dropped"):
        # dropped rows may still carry step_b; prefer explicit frame if present
        pass
    step_b = record.get("step_b") or {}
    frame = step_b.get("selected_frame")
    if frame is None or str(frame).strip() == "":
        return None
    return str(frame).strip()


def load_llm_pred_frames(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        rid = (record.get("provenance") or {}).get("record_id")
        if not rid:
            continue
        frame = _frame_from_annotation(record)
        if frame is None:
            continue
        out[str(rid)] = frame
    return out


def discover_llm_prediction_files(scratch: Path) -> list[Path]:
    files = sorted(scratch.glob("gold_predictions*.jsonl"))
    return [p for p in files if p.is_file()]


def llm_system_name(path: Path) -> str:
    stem = path.stem  # gold_predictions or gold_predictions_qwen…
    if stem == "gold_predictions":
        return "llm:default_qwen_family"
    prefix = "gold_predictions_"
    if stem.startswith(prefix):
        return f"llm:{stem[len(prefix):]}"
    return f"llm:{stem}"


def published_encoder_rows(models_root: Path) -> list[dict[str, Any]]:
    """Aggregate metrics from report/dev_metrics — not freeze-matched."""
    rows: list[dict[str, Any]] = []
    for metrics_path in sorted(models_root.glob("*/dev_metrics.json")):
        meta = json.loads(metrics_path.read_text(encoding="utf-8"))
        dev = meta.get("dev_metrics") or {}
        frame = meta.get("dev_metrics_frame_only") or {}
        per = (dev.get("per_frame_f1") or {}) if isinstance(dev, dict) else {}
        gold_labels = [lab for lab in FRAME_LABELS if lab in per]
        macro = (
            sum(float(per[lab]) for lab in gold_labels) / len(gold_labels)
            if gold_labels
            else None
        )
        rows.append(
            {
                "system": f"encoder:{metrics_path.parent.name}",
                "matched": False,
                "n": meta.get("dev_rows"),
                "n_frames_only": (frame or {}).get("total"),
                "accuracy_all": (dev or {}).get("accuracy"),
                "accuracy_frames_only": (frame or {}).get("accuracy"),
                "macro_f1": macro,
                "note": "published full-dev aggregate; not freeze-matched",
                "model_base": meta.get("model_base"),
            },
        )
    return rows


def predict_encoder_on_freeze(
    run_dir: Path,
    *,
    freeze: dict[str, str],
    dev_jsonl: Path,
    max_length: int = 256,
    device: str | None = None,
) -> dict[str, Any] | None:
    """Run a saved HF classification head on freeze texts from gijsbertdev.jsonl."""
    model_dir = run_dir / "model"
    if not model_dir.is_dir():
        return None

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    from trifecta_annotation.gijsbert_train import _resolve_device

    resolved = _resolve_device(device)
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
    model.to(resolved)
    model.eval()
    id2label = {int(k): str(v) for k, v in model.config.id2label.items()}

    texts: dict[str, str] = {}
    for line in dev_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rid = str(row.get("record_id") or "")
        if rid in freeze:
            texts[rid] = str(row.get("text") or "")

    pred_by_id: dict[str, str] = {}
    ordered = sorted(set(freeze) & set(texts))
    batch_size = 8
    with torch.inference_mode():
        for start in range(0, len(ordered), batch_size):
            chunk = ordered[start : start + batch_size]
            enc = tokenizer(
                [texts[i] for i in chunk],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            enc = {k: v.to(resolved) for k, v in enc.items()}
            logits = model(**enc).logits
            pred_ids = logits.argmax(dim=-1).tolist()
            for rid, pid in zip(chunk, pred_ids, strict=True):
                pred_by_id[rid] = id2label[int(pid)]

    scored = score_step_b_panel(freeze, pred_by_id)
    scored["system"] = f"encoder:{run_dir.name}"
    scored["matched"] = True
    scored["note"] = "predicted on freeze texts from gijsbert/dev.jsonl"
    meta_path = run_dir / "dev_metrics.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        scored["model_base"] = meta.get("model_base")
    return scored


def _fmt(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


ARTICLE_SYSTEM_LABELS = {
    "llm:default_qwen_family": "LLM default qwen family",
    "encoder:globertise-balanced-none": "GloBERTise",
    "encoder:gysbert-v2-balanced-none-weekend": "GysBERT weekend",
    "encoder:bertje-balanced-none": "BERTje",
    "encoder:mbert-balanced-none": "mBERT",
}


def article_ready_rows(
    rows: list[dict[str, Any]],
    *,
    min_n: int = 200,
) -> list[dict[str, Any]]:
    """Same-ID compare: matched rows with enough coverage; drop tiny LLM slices."""
    kept = [
        row
        for row in rows
        if row.get("matched") and (row.get("n") or 0) >= min_n
    ]
    # Prefer encoder/LLM headline systems when present; else all that pass min_n
    preferred = set(ARTICLE_SYSTEM_LABELS)
    preferred_rows = [row for row in kept if row.get("system") in preferred]
    return preferred_rows or kept


def rows_to_markdown(
    rows: list[dict[str, Any]],
    *,
    freeze_n: int,
    article: bool = False,
) -> str:
    if article:
        lines = [
            "# Matched Step B panel (article-ready)",
            "",
            f"- Freeze rule: `{FREEZE_RULE}`",
            f"- Freeze size: **{freeze_n}**",
            "- Same-ID compare; tiny LLM pilot slices (n≈38–46) omitted",
            "- Metrics: accuracy (all), accuracy (frames-only), macro-F1",
            "",
            "| System | n | Acc all | Acc frames | Macro-F1 |",
            "|--------|--:|--------:|-----------:|---------:|",
        ]
        for row in rows:
            system = ARTICLE_SYSTEM_LABELS.get(
                str(row.get("system", "?")),
                str(row.get("system", "?")),
            )
            lines.append(
                "| {system} | {n} | {acc} | {fo} | {macro} |".format(
                    system=system,
                    n=row.get("n") if row.get("n") is not None else "—",
                    acc=_fmt(row.get("accuracy_all")),
                    fo=_fmt(row.get("accuracy_frames_only")),
                    macro=_fmt(row.get("macro_f1")),
                ),
            )
        lines.append("")
        return "\n".join(lines)

    lines = [
        "# Matched Step B panel",
        "",
        f"- Freeze rule: `{FREEZE_RULE}`",
        f"- Freeze size: **{freeze_n}**",
        "- Metrics: accuracy (all), accuracy (frames-only), macro-F1 (mean F1 over labels in gold)",
        "",
        "| System | Matched | n | Acc all | Acc frames | Macro-F1 | Note |",
        "|--------|---------|--:|--------:|-----------:|---------:|------|",
    ]
    for row in rows:
        lines.append(
            "| {system} | {matched} | {n} | {acc} | {fo} | {macro} | {note} |".format(
                system=row.get("system", "?"),
                matched="yes" if row.get("matched") else "no",
                n=row.get("n") if row.get("n") is not None else "—",
                acc=_fmt(row.get("accuracy_all")),
                fo=_fmt(row.get("accuracy_frames_only")),
                macro=_fmt(row.get("macro_f1")),
                note=(row.get("note") or "").replace("|", "/"),
            ),
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gold-csv",
        type=Path,
        default=None,
        help="Default: gold_labelling_all.csv beside trifecta_gold",
    )
    parser.add_argument(
        "--pred-glob",
        type=Path,
        default=None,
        help="Directory containing gold_predictions*.jsonl (default: scratch)",
    )
    parser.add_argument(
        "--predict-encoders",
        action="store_true",
        help="Run saved encoder heads on freeze (slow; needs model weights)",
    )
    parser.add_argument(
        "--encoder-runs",
        nargs="*",
        default=None,
        help="Optional subset of encoder run dir names under gijsbert/models",
    )
    parser.add_argument(
        "--write-md",
        action="store_true",
        help="Write eval/matched_step_b_panel.md",
    )
    parser.add_argument(
        "--article-ready",
        action="store_true",
        help="Print/write article table only (matched, min-n; drop tiny LLM slices)",
    )
    parser.add_argument(
        "--min-n",
        type=int,
        default=200,
        help="With --article-ready: keep rows with n >= this (default 200)",
    )
    parser.add_argument(
        "--write-freeze",
        action="store_true",
        help="Write eval/matched_step_b_freeze.json (id→frame)",
    )
    args = parser.parse_args()

    scratch = Path(resolve("trifecta_gold")).parent
    eval_dir = Path(resolve("eval_reports"))
    gold_csv = args.gold_csv or (scratch / "gold_labelling_all.csv")
    if not gold_csv.is_file():
        gold_csv = Path(resolve("trifecta_gold_csv"))

    freeze = load_freeze_frames(gold_csv)
    print(f"freeze_rule={FREEZE_RULE!r} n={len(freeze)} gold_csv={gold_csv}")

    pred_dir = args.pred_glob or scratch
    rows: list[dict[str, Any]] = []

    for path in discover_llm_prediction_files(pred_dir):
        preds = load_llm_pred_frames(path)
        scored = score_step_b_panel(freeze, preds)
        scored["system"] = llm_system_name(path)
        scored["matched"] = True
        scored["note"] = str(path.name)
        scored["path"] = str(path)
        rows.append(scored)
        print(
            f"{scored['system']}: n={scored['n']} "
            f"acc={_fmt(scored['accuracy_all'])} "
            f"frames={_fmt(scored['accuracy_frames_only'])} "
            f"macroF1={_fmt(scored['macro_f1'])} "
            f"missing={scored['missing_pred']}",
        )

    models_root = Path(resolve("trifecta_gijsbert_models"))
    if args.predict_encoders:
        dev_jsonl = Path(resolve("trifecta_gijsbert")) / "dev.jsonl"
        if not dev_jsonl.is_file():
            raise SystemExit(f"Missing {dev_jsonl} for encoder texts")
        run_dirs = sorted(p for p in models_root.glob("*") if p.is_dir())
        if args.encoder_runs:
            wanted = set(args.encoder_runs)
            run_dirs = [p for p in run_dirs if p.name in wanted]
        for run_dir in run_dirs:
            print(f"predict encoder {run_dir.name} …")
            scored = predict_encoder_on_freeze(
                run_dir,
                freeze=freeze,
                dev_jsonl=dev_jsonl,
            )
            if scored is None:
                print(f"  skip (no model/): {run_dir.name}")
                continue
            rows.append(scored)
            print(
                f"  n={scored['n']} acc={_fmt(scored['accuracy_all'])} "
                f"frames={_fmt(scored['accuracy_frames_only'])} "
                f"macroF1={_fmt(scored['macro_f1'])}",
            )
    else:
        for pub in published_encoder_rows(models_root):
            rows.append(pub)
            print(
                f"{pub['system']}: published n={pub['n']} "
                f"acc={_fmt(pub['accuracy_all'])} "
                f"frames={_fmt(pub['accuracy_frames_only'])} "
                f"(not matched)",
            )

    # Prefer matched rows first, then by frames-only acc
    def sort_key(row: dict[str, Any]) -> tuple:
        return (
            0 if row.get("matched") else 1,
            -(row.get("accuracy_frames_only") or -1.0),
            -(row.get("accuracy_all") or -1.0),
        )

    rows_sorted = sorted(rows, key=sort_key)
    article_rows = sorted(
        article_ready_rows(rows_sorted, min_n=args.min_n),
        key=lambda row: (
            -(row.get("accuracy_all") or -1.0),
            -(row.get("macro_f1") or -1.0),
        ),
    )
    md_full = rows_to_markdown(rows_sorted, freeze_n=len(freeze))
    md_article = rows_to_markdown(
        article_rows,
        freeze_n=len(freeze),
        article=True,
    )
    print("\n" + (md_article if args.article_ready else md_full))
    if args.article_ready:
        print("\n--- full panel (for reference) ---\n" + md_full)

    if args.write_md:
        out = eval_dir / "matched_step_b_panel.md"
        out.write_text(md_full, encoding="utf-8")
        print(f"wrote {out}")
        out_a = eval_dir / "matched_step_b_panel_article.md"
        out_a.write_text(md_article, encoding="utf-8")
        print(f"wrote {out_a}")
    if args.write_freeze:
        out_f = eval_dir / "matched_step_b_freeze.json"
        out_f.write_text(
            json.dumps(
                {"rule": FREEZE_RULE, "n": len(freeze), "frames": freeze},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {out_f}")

    # machine-readable stdout companion
    print(
        json.dumps(
            {
                "freeze_n": len(freeze),
                "article_ready": article_rows,
                "rows": rows_sorted,
            },
            indent=2,
        ),
    )


if __name__ == "__main__":
    main()
