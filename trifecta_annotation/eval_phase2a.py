"""Phase 2a evaluation: human reviewed gold vs model predictions and verb priors."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from data_io import load_jsonl, resolve

from trifecta_annotation.eval import (
    STEP_C_FIELDS,
    _per_class_scores,
    normalize_qualia_value,
    soft_qualia_match,
)
from trifecta_annotation.schemas import TrifectaFrame


def _load_predictions_index(preds_path: Path | None) -> dict[str, dict[str, Any]]:
    """Index model predictions by multiple record_id variants for robust matching."""
    if preds_path is None or not preds_path.exists():
        return {}
    index: dict[str, dict[str, Any]] = {}
    for rec in load_jsonl(preds_path):
        prov = rec.get("provenance", {})
        rid = str(prov.get("record_id", "")).strip()
        if not rid:
            continue
        index[rid] = rec
        # Also index stripped ID if predictions were run with `_verbkwic_phase2a_` suffixes
        if "_verbkwic_phase2a_" in rid:
            base_id = rid.split("_verbkwic_phase2a_")[0]
            if base_id not in index:
                index[base_id] = rec
    return index


def extract_human_step_c(row: dict[str, Any], frame_name: str) -> dict[str, str]:
    """Extract normalized human Step C fields for the given frame."""
    if not frame_name or frame_name == "NONE":
        return {}
    try:
        frame_enum = TrifectaFrame(frame_name)
    except ValueError:
        return {}
    fields = STEP_C_FIELDS.get(frame_enum, ())
    return {field: normalize_qualia_value(row.get(field, "")) for field in fields}


def extract_pred_step_c(pred_rec: dict[str, Any] | None, frame_name: str) -> tuple[str | None, dict[str, str]]:
    """Extract model predicted frame and Step C field values for that frame."""
    if not pred_rec:
        return None, {}
    step_b = pred_rec.get("step_b") or {}
    pred_frame = step_b.get("selected_frame")
    step_c = pred_rec.get("step_c") or {}
    
    if not frame_name or frame_name == "NONE":
        return pred_frame, {}
    try:
        frame_enum = TrifectaFrame(frame_name)
    except ValueError:
        return pred_frame, {}
    fields = STEP_C_FIELDS.get(frame_enum, ())
    return pred_frame, {field: normalize_qualia_value(step_c.get(field, "")) for field in fields}


def evaluate_phase2a(
    gold_csv_path: str | Path | None = None,
    predictions_path: str | Path | None = None,
    output_json: str | Path | None = None,
    output_csv: str | Path | None = None,
    *,
    only_reviewed: bool = True,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Evaluate Phase 2a human reviews against source Step B, lexicon priors, and predictions."""
    path = Path(gold_csv_path).expanduser().resolve() if gold_csv_path else resolve("verb_phase2a_gold")
    if not path.exists():
        raise FileNotFoundError(f"Phase 2a gold worksheet not found: {path}")

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if only_reviewed:
        reviewed_mask = df["reviewed"].str.lower().eq("true") | df["reviewed_frame"].ne("")
        work_df = df[reviewed_mask].copy()
    else:
        work_df = df.copy()

    total_rows = len(work_df)
    if total_rows == 0:
        return {"total_rows": 0, "reviewed_rows": 0}, pd.DataFrame()

    # Load prediction records
    preds_file = Path(predictions_path).expanduser().resolve() if predictions_path else None
    if preds_file is None:
        try:
            cand = resolve("verb_phase2a_predictions")
            if cand.exists():
                preds_file = cand
        except Exception:
            preds_file = None
    if preds_file is None:
        try:
            cand = resolve("trifecta_annotations")
            if cand.exists():
                preds_file = cand
        except Exception:
            preds_file = None

    preds_index = _load_predictions_index(preds_file)

    # 1. Comparison: human reviewed_frame vs source_step_b
    source_b_matches = 0
    source_b_pairs: list[tuple[str, str]] = []
    source_b_mismatches: list[dict[str, Any]] = []

    # 2. Comparison: human reviewed_frame vs frame_verb_frame
    verb_lexicon_evaluated = 0
    verb_lexicon_matches = 0
    verb_lexicon_pairs: list[tuple[str, str]] = []
    verb_lexicon_mismatches: list[dict[str, Any]] = []

    # 3. Comparison: human Step C vs model Step C
    step_c_evaluated_rows = 0
    step_c_joint_exact_hits = 0
    step_c_joint_soft_hits = 0
    step_c_field_exact_hits: dict[str, int] = defaultdict(int)
    step_c_field_soft_hits: dict[str, int] = defaultdict(int)
    step_c_field_totals: dict[str, int] = defaultdict(int)
    step_c_discrepancies: list[dict[str, Any]] = []

    comparison_rows: list[dict[str, Any]] = []

    for _, row in work_df.iterrows():
        rid = str(row.get("record_id", "")).strip()
        target = str(row.get("target_word", "")).strip()
        verb = str(row.get("frame_verb", "")).strip()
        regime = str(row.get("text_regime", "UNKNOWN")).strip()
        human_frame = str(row.get("reviewed_frame", "")).strip()
        source_b = str(row.get("source_step_b", "")).strip()
        verb_frame = str(row.get("frame_verb_frame", "")).strip()
        human_lu = str(row.get("reviewed_lexical_unit", "")).strip()
        note = str(row.get("uncertainty_note", "")).strip()

        # Step B source comparison
        agree_source = bool(human_frame and source_b and human_frame == source_b)
        if agree_source:
            source_b_matches += 1
        if human_frame and source_b:
            source_b_pairs.append((human_frame, source_b))
            if not agree_source:
                source_b_mismatches.append({
                    "record_id": rid,
                    "target_word": target,
                    "human_frame": human_frame,
                    "source_step_b": source_b,
                    "uncertainty_note": note,
                })

        # Verb lexicon prior comparison
        agree_verb_lexicon = None
        if verb_frame:
            verb_lexicon_evaluated += 1
            agree_verb_lexicon = bool(human_frame and human_frame == verb_frame)
            if agree_verb_lexicon:
                verb_lexicon_matches += 1
            if human_frame:
                verb_lexicon_pairs.append((human_frame, verb_frame))
                if not agree_verb_lexicon:
                    verb_lexicon_mismatches.append({
                        "record_id": rid,
                        "target_word": target,
                        "frame_verb": verb,
                        "human_frame": human_frame,
                        "frame_verb_frame": verb_frame,
                        "uncertainty_note": note,
                    })

        # Step C comparison
        pred_rec = preds_index.get(rid)
        human_step_c = extract_human_step_c(row, human_frame)
        pred_frame, pred_step_c = extract_pred_step_c(pred_rec, human_frame)
        pred_lu = pred_rec.get("step_b", {}).get("lexical_unit", "") if pred_rec else ""

        joint_exact = None
        joint_soft = None

        if human_frame and human_frame != "NONE" and human_step_c:
            step_c_evaluated_rows += 1
            row_exact_hits: list[bool] = []
            row_soft_hits: list[bool] = []

            for field_name, human_val in human_step_c.items():
                pred_val = pred_step_c.get(field_name, "")
                step_c_field_totals[field_name] += 1
                
                exact = human_val == pred_val
                soft = soft_qualia_match(human_val, pred_val)

                if exact:
                    step_c_field_exact_hits[field_name] += 1
                if soft:
                    step_c_field_soft_hits[field_name] += 1
                
                row_exact_hits.append(exact)
                row_soft_hits.append(soft)

            joint_exact = all(row_exact_hits) if row_exact_hits else False
            joint_soft = all(row_soft_hits) if row_soft_hits else False

            if joint_exact:
                step_c_joint_exact_hits += 1
            if joint_soft:
                step_c_joint_soft_hits += 1

            if not joint_exact:
                step_c_discrepancies.append({
                    "record_id": rid,
                    "target_word": target,
                    "human_frame": human_frame,
                    "human_step_c": human_step_c,
                    "pred_step_c": pred_step_c,
                    "joint_soft_match": joint_soft,
                })

        comparison_rows.append({
            "record_id": rid,
            "target_word": target,
            "frame_verb": verb,
            "text_regime": regime,
            "reviewed_frame": human_frame,
            "source_step_b": source_b,
            "frame_verb_frame": verb_frame,
            "agree_source_step_b": agree_source,
            "agree_verb_lexicon": agree_verb_lexicon,
            "reviewed_lexical_unit": human_lu,
            "pred_lexical_unit": pred_lu,
            "human_step_c": json.dumps(human_step_c, ensure_ascii=False) if human_step_c else "",
            "pred_step_c": json.dumps(pred_step_c, ensure_ascii=False) if pred_step_c else "",
            "step_c_joint_exact": joint_exact,
            "step_c_joint_soft": joint_soft,
            "uncertainty_note": note,
        })

    # Metrics calculation
    human_labels = [p[0] for p in source_b_pairs]
    source_b_labels = [p[1] for p in source_b_pairs]
    source_b_scores = _per_class_scores(human_labels, source_b_labels)

    metrics = {
        "gold_file": str(path),
        "total_worksheet_rows": len(df),
        "evaluated_rows": total_rows,
        "predictions_file": str(preds_file) if preds_file else None,
        "predictions_matched": len(set(work_df["record_id"]) & set(preds_index)),
        "source_step_b_comparison": {
            "total_pairs": len(source_b_pairs),
            "agreement_count": source_b_matches,
            "agreement_rate": source_b_matches / len(source_b_pairs) if source_b_pairs else 0.0,
            "per_class": source_b_scores.to_dict(),
            "confusion_matrix": {f"{k[0]} -> {k[1]}": v for k, v in Counter(source_b_pairs).items()},
            "mismatches": source_b_mismatches,
        },
        "verb_lexicon_comparison": {
            "evaluated_pairs": verb_lexicon_evaluated,
            "agreement_count": verb_lexicon_matches,
            "agreement_rate": verb_lexicon_matches / verb_lexicon_evaluated if verb_lexicon_evaluated else 0.0,
            "confusion_matrix": {f"{k[0]} -> {k[1]}": v for k, v in Counter(verb_lexicon_pairs).items()},
            "mismatches": verb_lexicon_mismatches,
        },
        "step_c_comparison": {
            "evaluated_rows": step_c_evaluated_rows,
            "joint_exact_hits": step_c_joint_exact_hits,
            "joint_exact_accuracy": step_c_joint_exact_hits / step_c_evaluated_rows if step_c_evaluated_rows else None,
            "joint_soft_hits": step_c_joint_soft_hits,
            "joint_soft_accuracy": step_c_joint_soft_hits / step_c_evaluated_rows if step_c_evaluated_rows else None,
            "field_exact_accuracy": {
                k: step_c_field_exact_hits[k] / step_c_field_totals[k] for k in step_c_field_totals
            },
            "field_soft_accuracy": {
                k: step_c_field_soft_hits[k] / step_c_field_totals[k] for k in step_c_field_totals
            },
            "field_counts": {
                k: {
                    "exact_hits": step_c_field_exact_hits[k],
                    "soft_hits": step_c_field_soft_hits[k],
                    "total": step_c_field_totals[k],
                }
                for k in step_c_field_totals
            },
            "discrepancies": step_c_discrepancies,
        },
    }

    comp_df = pd.DataFrame(comparison_rows)

    if output_json:
        out_j = Path(output_json).expanduser().resolve()
        out_j.parent.mkdir(parents=True, exist_ok=True)
        out_j.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if output_csv:
        out_c = Path(output_csv).expanduser().resolve()
        out_c.parent.mkdir(parents=True, exist_ok=True)
        comp_df.to_csv(out_c, index=False)

    return metrics, comp_df


def format_phase2a_report(metrics: dict[str, Any]) -> str:
    """Render a clean markdown/terminal evaluation report."""
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("PHASE 2a EVALUATION: HUMAN GOLD VS MODEL & VERB PRIORS")
    lines.append("=" * 78)
    lines.append(f"Gold file:        {metrics.get('gold_file')}")
    lines.append(f"Evaluated rows:   {metrics.get('evaluated_rows')} / {metrics.get('total_worksheet_rows')}")
    if metrics.get("predictions_file"):
        lines.append(f"Predictions file: {metrics.get('predictions_file')}")
        lines.append(f"Matched preds:    {metrics.get('predictions_matched')} records")
    else:
        lines.append("Predictions file: (none matched — Step C comparison skipped)")

    # 1. Source Step B Comparison
    sb = metrics.get("source_step_b_comparison", {})
    lines.append("\n" + "-" * 78)
    lines.append("1. HUMAN REVIEWED_FRAME VS SOURCE_STEP_B (Prior Model Annotation)")
    lines.append("-" * 78)
    lines.append(f"  Agreement rate: {sb.get('agreement_rate', 0.0):.1%} ({sb.get('agreement_count', 0)} / {sb.get('total_pairs', 0)})")
    
    per_cls = sb.get("per_class", {})
    prec = per_cls.get("precision", {})
    rec = per_cls.get("recall", {})
    f1 = per_cls.get("f1", {})
    if prec:
        lines.append("\n  Per-frame metrics (Human = Gold, Source = Pred):")
        for frame in sorted(prec):
            lines.append(f"    {frame:<18} Precision: {prec[frame]:.2f}  Recall: {rec.get(frame, 0.0):.2f}  F1: {f1.get(frame, 0.0):.2f}")

    if sb.get("mismatches"):
        lines.append("\n  Mismatches (Human ≠ Source Step B):")
        for m in sb["mismatches"][:8]:
            note_str = f" [note: {m['uncertainty_note']}]" if m.get("uncertainty_note") else ""
            lines.append(f"    • {m['record_id']} ({m['target_word']}): human={m['human_frame']} vs source={m['source_step_b']}{note_str}")

    # 2. Verb Lexicon Frame Comparison
    vl = metrics.get("verb_lexicon_comparison", {})
    lines.append("\n" + "-" * 78)
    lines.append("2. HUMAN REVIEWED_FRAME VS FRAME_VERB_FRAME (Verb Lexicon Prior)")
    lines.append("-" * 78)
    lines.append(f"  Agreement rate: {vl.get('agreement_rate', 0.0):.1%} ({vl.get('agreement_count', 0)} / {vl.get('evaluated_pairs', 0)})")
    if vl.get("mismatches"):
        lines.append("\n  Mismatches (Human Frame ≠ Verb Lexicon Frame):")
        for m in vl["mismatches"][:8]:
            note_str = f" [note: {m['uncertainty_note']}]" if m.get("uncertainty_note") else ""
            lines.append(f"    • {m['record_id']} (target: {m['target_word']}, verb: {m['frame_verb']}): human={m['human_frame']} vs verb_lexicon={m['frame_verb_frame']}{note_str}")

    # 3. Step C Qualia Comparison
    sc = metrics.get("step_c_comparison", {})
    lines.append("\n" + "-" * 78)
    lines.append("3. HUMAN STEP C QUALIA VS MODEL PREDICTIONS")
    lines.append("-" * 78)
    if sc.get("evaluated_rows", 0) > 0:
        j_ex = sc.get("joint_exact_accuracy")
        j_sf = sc.get("joint_soft_accuracy")
        lines.append(f"  Evaluated framed rows: {sc.get('evaluated_rows')}")
        lines.append(f"  Joint exact accuracy:  {j_ex:.1%}" if j_ex is not None else "  Joint exact accuracy:  N/A")
        lines.append(f"  Joint soft accuracy:   {j_sf:.1%}" if j_sf is not None else "  Joint soft accuracy:   N/A")
        
        counts = sc.get("field_counts", {})
        if counts:
            lines.append("\n  Field-level accuracy:")
            for field, c in sorted(counts.items()):
                ex_rate = c["exact_hits"] / c["total"] if c["total"] else 0.0
                sf_rate = c["soft_hits"] / c["total"] if c["total"] else 0.0
                lines.append(f"    {field:<30} exact: {ex_rate:.1%} ({c['exact_hits']}/{c['total']})  soft: {sf_rate:.1%} ({c['soft_hits']}/{c['total']})")
    else:
        lines.append("  (No matched framed Step C prediction records to evaluate)")

    lines.append("=" * 78)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Phase 2a human gold vs model predictions and verb priors.")
    parser.add_argument("--gold-csv", default=None, help="Path to Phase 2a gold CSV (default: verb_phase2a_gold)")
    parser.add_argument("--predictions", default=None, help="Path to predictions JSONL")
    parser.add_argument("--output-json", default=None, help="Path to export evaluation JSON")
    parser.add_argument("--output-csv", default=None, help="Path to export side-by-side comparison CSV")
    parser.add_argument("--all-rows", action="store_true", help="Evaluate all rows instead of only reviewed rows")
    parser.add_argument("--quiet", action="store_true", help="Do not print terminal report")
    args = parser.parse_args()

    metrics, _df = evaluate_phase2a(
        gold_csv_path=args.gold_csv,
        predictions_path=args.predictions,
        output_json=args.output_json,
        output_csv=args.output_csv,
        only_reviewed=not args.all_rows,
    )

    if not args.quiet:
        print(format_phase2a_report(metrics))


if __name__ == "__main__":
    main()