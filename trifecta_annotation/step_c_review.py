"""Build Step C gold-vs-pred review rows for few-shot picking."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import pandas as pd
from data_io import load_jsonl, resolve

from trifecta_annotation.eval import (
    STEP_C_FIELDS,
    _score_step_c_pair,
    _step_c_values,
)
from trifecta_annotation.gold_io import load_gold_records
from trifecta_annotation.schemas import TrifectaAnnotation, TrifectaFrame

REVIEW_COLUMNS = [
    "tier",
    "hits",
    "n_fields",
    "joint",
    "gold_frame",
    "pred_frame",
    "gold_b_frame",
    "pred_b_frame",
    "frame_ok",
    "record_id",
    "target_word",
    "text_regime",
    "context_snippet",
    "field_hits",
    "gold_fields",
    "pred_fields",
    "fewshot_candidate",
]

DEFAULT_DISPLAY_COLUMNS = [
    "tier",
    "fewshot_candidate",
    "hits",
    "n_fields",
    "gold_frame",
    "pred_frame",
    "target_word",
    "text_regime",
    "context_snippet",
    "field_hits",
    "gold_fields",
    "pred_fields",
    "record_id",
]


@dataclass
class StepCReviewConfig:
    """Notebook / CLI knobs for Step C review (reuse across frames / batches)."""

    gold_path: Path | None = None
    predictions_path: Path | None = None
    output_path: Path | None = None
    # Empty = all frames; e.g. ("COOKING_CREATION",) for the pilot.
    frames: tuple[str, ...] = ()
    # Empty = all tiers; e.g. ("joint", "partial_strong").
    tiers: tuple[str, ...] = ()
    fewshot_only: bool = False
    # Include fewshot_candidate in {"yes", "maybe"} only when fewshot_only.
    fewshot_levels: tuple[str, ...] = ("yes", "maybe")
    min_hits: int = 0
    frame_ok_only: bool = False
    display_columns: tuple[str, ...] = field(default_factory=lambda: tuple(DEFAULT_DISPLAY_COLUMNS))

    def resolved_gold_path(self) -> Path:
        return Path(self.gold_path) if self.gold_path else Path(resolve("trifecta_gold"))

    def resolved_predictions_path(self) -> Path:
        if self.predictions_path:
            return Path(self.predictions_path)
        return self.resolved_gold_path().parent / "gold_predictions.jsonl"

    def resolved_output_path(self) -> Path:
        if self.output_path:
            return Path(self.output_path)
        return Path(resolve("eval_reports")) / "step_c_review.csv"


def _short_context(text: str, target: str, *, width: int = 160) -> str:
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


def _format_fields(values: dict[str, str]) -> str:
    parts = [f"{k}={v!r}" for k, v in values.items()]
    return "; ".join(parts)


def _tier(hits: int, n_fields: int, joint: bool, frame_ok: bool) -> str:
    if joint:
        return "joint"
    if hits >= 2:
        return "partial_strong"
    if hits == 1 and frame_ok:
        return "partial"
    if frame_ok and hits == 0:
        return "frame_ok_zero"
    return "miss"


def _fewshot_candidate(tier: str, gold_frame: str) -> str:
    """Flag rows useful as few-shot exemplars (gold side is the source of truth)."""
    if tier == "joint":
        return "yes"
    if tier == "partial_strong":
        return "yes"
    if tier == "partial" and gold_frame == TrifectaFrame.COOKING_CREATION.value:
        return "maybe"
    return ""


def build_step_c_review_rows(
    gold_records: list[dict[str, Any]],
    pred_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One row per gold annotation that has step_c."""
    pred_index = {
        str((r.get("provenance") or {}).get("record_id")): r
        for r in pred_records
        if (r.get("provenance") or {}).get("record_id")
    }

    rows: list[dict[str, Any]] = []
    for raw in gold_records:
        gold = TrifectaAnnotation.model_validate(raw)
        if gold.step_c is None:
            continue
        rid = str(gold.provenance.record_id)
        pred_raw = pred_index.get(rid)
        pred = TrifectaAnnotation.model_validate(pred_raw) if pred_raw else None

        field_hits, joint = _score_step_c_pair(
            gold.step_c,
            pred.step_c if pred else None,
        )
        gold_vals = _step_c_values(gold.step_c)
        pred_vals = _step_c_values(pred.step_c) if pred and pred.step_c else {}
        gold_frame = gold.step_c.frame.value
        pred_frame = pred.step_c.frame.value if pred and pred.step_c else ""
        gold_b = gold.step_b.selected_frame.value if gold.step_b else ""
        pred_b = pred.step_b.selected_frame.value if pred and pred.step_b else ""
        frame_ok = bool(pred and pred.step_c and pred.step_c.frame == gold.step_c.frame)
        hits = sum(1 for ok in field_hits.values() if ok)
        n_fields = len(STEP_C_FIELDS.get(gold.step_c.frame, ()))
        tier = _tier(hits, n_fields, joint, frame_ok)

        rows.append(
            {
                "tier": tier,
                "hits": hits,
                "n_fields": n_fields,
                "joint": "true" if joint else "false",
                "gold_frame": gold_frame,
                "pred_frame": pred_frame,
                "gold_b_frame": gold_b,
                "pred_b_frame": pred_b,
                "frame_ok": "true" if frame_ok else "false",
                "record_id": rid,
                "target_word": gold.provenance.target_word,
                "text_regime": (
                    gold.provenance.text_regime.value
                    if gold.provenance.text_regime is not None
                    else ""
                ),
                "context_snippet": _short_context(
                    gold.provenance.context_text,
                    gold.provenance.target_word,
                ),
                "field_hits": "; ".join(
                    f"{name.split('_')[-1]}={'✓' if ok else '✗'}"
                    for name, ok in field_hits.items()
                ),
                "gold_fields": _format_fields(gold_vals),
                "pred_fields": _format_fields(pred_vals),
                "fewshot_candidate": _fewshot_candidate(tier, gold_frame),
            },
        )

    tier_rank = {
        "joint": 0,
        "partial_strong": 1,
        "partial": 2,
        "frame_ok_zero": 3,
        "miss": 4,
    }
    rows.sort(
        key=lambda row: (
            tier_rank.get(str(row["tier"]), 9),
            -int(row["hits"]),
            str(row["gold_frame"]),
            str(row["target_word"]),
        ),
    )
    return rows


def filter_review_rows(
    rows: Sequence[dict[str, Any]],
    config: StepCReviewConfig,
) -> list[dict[str, Any]]:
    """Apply config filters (frame, tier, few-shot, min hits)."""
    out: list[dict[str, Any]] = []
    frames = {f.strip() for f in config.frames if str(f).strip()}
    tiers = {t.strip() for t in config.tiers if str(t).strip()}
    few_levels = {x.strip() for x in config.fewshot_levels if str(x).strip()}
    for row in rows:
        if frames and str(row.get("gold_frame", "")) not in frames:
            continue
        if tiers and str(row.get("tier", "")) not in tiers:
            continue
        if config.fewshot_only:
            level = str(row.get("fewshot_candidate", "")).strip()
            if level not in few_levels:
                continue
        if int(row.get("hits", 0)) < config.min_hits:
            continue
        if config.frame_ok_only and str(row.get("frame_ok", "")) != "true":
            continue
        out.append(dict(row))
    return out


def load_review_frame(config: StepCReviewConfig | None = None) -> pd.DataFrame:
    """Load gold + predictions, build and filter review table."""
    cfg = config or StepCReviewConfig()
    gold_records = load_gold_records(gold_path=cfg.resolved_gold_path())
    pred_records = load_jsonl(cfg.resolved_predictions_path())
    rows = filter_review_rows(build_step_c_review_rows(gold_records, pred_records), cfg)
    return pd.DataFrame(rows, columns=REVIEW_COLUMNS)


def save_review_frame(frame: pd.DataFrame, config: StepCReviewConfig | None = None) -> Path:
    cfg = config or StepCReviewConfig()
    out = cfg.resolved_output_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.reindex(columns=REVIEW_COLUMNS, fill_value="").to_csv(out, index=False)
    return out


def review_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"rows": 0, "tiers": {}, "fewshot_flagged": 0, "by_frame": {}}
    few = frame["fewshot_candidate"].astype(str).str.len().gt(0)
    return {
        "rows": int(len(frame)),
        "tiers": frame["tier"].value_counts().to_dict(),
        "fewshot_flagged": int(few.sum()),
        "by_frame": frame["gold_frame"].value_counts().to_dict(),
    }


def review_view(frame: pd.DataFrame, config: StepCReviewConfig | None = None) -> pd.DataFrame:
    """Column subset for display (works in Cursor without itables)."""
    cfg = config or StepCReviewConfig()
    cols = [c for c in cfg.display_columns if c in frame.columns]
    return frame[cols] if cols else frame


def show_review(
    frame: pd.DataFrame,
    config: StepCReviewConfig | None = None,
    *,
    prefer_itables: bool = False,
) -> pd.DataFrame:
    """
    Display review table.

    Default: plain pandas (works in Cursor / VS Code notebooks).
    Set prefer_itables=True only when running classic Jupyter with itables.
    """
    view = review_view(frame, config)
    if prefer_itables:
        try:
            from itables import init_notebook_mode, show

            init_notebook_mode(all_interactive=True)
            show(view, column_filters="header", maxBytes=0, classes="display compact")
            return view
        except Exception:
            pass
    with pd.option_context(
        "display.max_rows",
        200,
        "display.max_colwidth",
        120,
        "display.width",
        200,
    ):
        try:
            from IPython.display import display

            display(view)
        except Exception:
            print(view.to_string())
    return view


def print_row_detail(frame: pd.DataFrame, index: int = 0) -> None:
    """Print one review row as readable blocks (gold vs pred)."""
    if frame.empty:
        print("(empty)")
        return
    idx = max(0, min(index, len(frame) - 1))
    row = frame.iloc[idx]
    print(f"=== row {idx + 1}/{len(frame)} · {row.get('tier')} · {row.get('target_word')} ===")
    print(f"record_id: {row.get('record_id')}")
    print(f"frame gold/pred: {row.get('gold_frame')} / {row.get('pred_frame')}  (B: {row.get('gold_b_frame')}→{row.get('pred_b_frame')})")
    print(f"hits: {row.get('hits')}/{row.get('n_fields')}  field_hits: {row.get('field_hits')}")
    print(f"snippet: {row.get('context_snippet')}")
    print(f"GOLD: {row.get('gold_fields')}")
    print(f"PRED: {row.get('pred_fields')}")
    print(f"fewshot_candidate: {row.get('fewshot_candidate')!r}")


def walk_details(frame: pd.DataFrame, *, start: int = 0, n: int = 5) -> None:
    """Print several rows in detail for offline reading."""
    if frame.empty:
        print("(empty)")
        return
    end = min(len(frame), start + n)
    for i in range(start, end):
        print_row_detail(frame, i)
        print()
