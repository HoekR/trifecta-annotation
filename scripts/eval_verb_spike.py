#!/usr/bin/env python3
"""Evaluate verb-first POC results against ground truth and baselines.

Metrics:
1. Step A dropout rate (should be ~0% for lexicon verbs)
2. Step B accuracy (compare predicted frame to expected/gold frame)
3. Collocation alignment (do nearby words match lexicon hints?)
4. Step C coherence (spot check 5 samples)
"""

from __future__ import annotations

import json
from collections import defaultdict, Counter
from pathlib import Path

from data_io import load_jsonl
from trifecta_annotation.frame_verbs import FrameVerbLexicon


def load_verb_candidates() -> dict[str, list[dict]]:
    """Load the original verb candidates (discovery output)."""
    with open("/tmp/verb_candidates.json") as f:
        return json.load(f)


def evaluate_verb_spike(
    pred_path: str | Path,
    output_json: str | Path | None = None,
) -> dict:
    """Evaluate verb-first POC results.
    
    Returns evaluation metrics dict.
    """
    pred_path = Path(pred_path)
    if not pred_path.exists():
        raise FileNotFoundError(f"Predictions not found: {pred_path}")

    # Load predictions
    predictions = {rec["provenance"]["record_id"]: rec for rec in load_jsonl(pred_path)}
    
    # Load ground truth candidates
    candidates_by_frame = load_verb_candidates()
    candidates = []
    for frame, items in candidates_by_frame.items():
        candidates.extend(items)
    
    # Create mapping: original record_id → candidate (for frame expectations)
    candidate_map = {}
    for cand in candidates:
        # The record_id pattern from staging: {original}_verbkwic_{i}
        for i in range(10):  # assume max 10 candidates
            key = f"{cand['record_id']}_verbkwic_{i}"
            if key in predictions:
                candidate_map[key] = cand
                break
    
    # Metrics
    metrics = {
        "total": len(predictions),
        "step_a": {},
        "step_b": {},
        "collocation": {},
        "step_c": {},
    }
    
    # Step A: dropout rate
    dropped = sum(1 for rec in predictions.values() if rec.get("dropped"))
    metrics["step_a"]["total"] = len(predictions)
    metrics["step_a"]["dropped"] = dropped
    metrics["step_a"]["passed"] = len(predictions) - dropped
    metrics["step_a"]["dropout_rate"] = dropped / len(predictions) if predictions else 0
    
    # Step B: frame accuracy
    step_b_by_frame = defaultdict(lambda: {"total": 0, "correct": 0})
    frame_confusion = defaultdict(Counter)  # expected_frame → {predicted_frame: count}
    
    for pred_id, pred_rec in predictions.items():
        if pred_rec.get("dropped"):
            continue
        
        step_b = pred_rec.get("step_b")
        if not step_b:
            continue
        
        pred_frame = step_b.get("selected_frame")
        
        # Get expected frame from candidate
        cand = candidate_map.get(pred_id)
        expected_frame = cand.get("frame_verb_frame") if cand else None
        
        if expected_frame:
            step_b_by_frame[expected_frame]["total"] += 1
            if pred_frame == expected_frame:
                step_b_by_frame[expected_frame]["correct"] += 1
            frame_confusion[expected_frame][pred_frame] += 1
    
    metrics["step_b"]["by_frame"] = {}
    total_correct = 0
    total_predictions = 0
    for frame, counts in sorted(step_b_by_frame.items()):
        acc = counts["correct"] / counts["total"] if counts["total"] > 0 else 0
        metrics["step_b"]["by_frame"][frame] = {
            "total": counts["total"],
            "correct": counts["correct"],
            "accuracy": round(acc, 3),
        }
        total_correct += counts["correct"]
        total_predictions += counts["total"]
    
    metrics["step_b"]["overall_accuracy"] = round(
        total_correct / total_predictions if total_predictions > 0 else 0, 3
    )
    metrics["step_b"]["confusion"] = {}
    for expected, pred_counts in frame_confusion.items():
        metrics["step_b"]["confusion"][expected] = dict(pred_counts)
    
    # Collocation alignment: check if predicted frame matches lexicon
    lex = FrameVerbLexicon()
    collocation_matches = 0
    collocation_total = 0
    
    for pred_id, pred_rec in predictions.items():
        if pred_rec.get("dropped"):
            continue
        
        step_b = pred_rec.get("step_b")
        if not step_b:
            continue
        
        target_verb = pred_rec["provenance"]["target_word"]
        pred_frame = step_b.get("selected_frame")
        entry = lex.entry_for(target_verb)
        
        if entry:
            collocation_total += 1
            if entry.frame.value == pred_frame:
                collocation_matches += 1
    
    metrics["collocation"]["matches"] = collocation_matches
    metrics["collocation"]["total"] = collocation_total
    metrics["collocation"]["alignment"] = round(
        collocation_matches / collocation_total if collocation_total > 0 else 0, 3
    )
    
    # Step C: presence check (binary: has qualia or not)
    step_c_with_data = sum(
        1 for rec in predictions.values()
        if rec.get("step_c") and rec["step_c"].get("frame")
    )
    metrics["step_c"]["with_data"] = step_c_with_data
    metrics["step_c"]["total"] = len(predictions)
    
    # Print summary
    print("=" * 70)
    print("VERB-FIRST POC EVALUATION RESULTS")
    print("=" * 70)
    
    print(f"\nStep A — Entity Validation (verb lexicon check)")
    print(f"  Passed:         {metrics['step_a']['passed']} / {metrics['step_a']['total']}")
    print(f"  Dropped:        {metrics['step_a']['dropped']}")
    print(f"  Dropout rate:   {metrics['step_a']['dropout_rate']:.1%}")
    
    print(f"\nStep B — Frame Classification")
    print(f"  Overall accuracy: {metrics['step_b']['overall_accuracy']:.1%}")
    print(f"  By frame:")
    for frame, counts in metrics["step_b"]["by_frame"].items():
        print(
            f"    {frame:20} {counts['correct']:2}/{counts['total']:2} = "
            f"{counts['accuracy']:.1%}"
        )
    
    print(f"\nStep B — Confusion Matrix (predicted vs expected)")
    for expected, pred_counts in metrics["step_b"]["confusion"].items():
        print(f"  Expected {expected}:")
        for pred, count in sorted(pred_counts.items(), key=lambda x: -x[1]):
            print(f"    → {pred}: {count}")
    
    print(f"\nCollocation Alignment (verb lexicon prior)")
    print(f"  Matches lexicon:  {metrics['collocation']['matches']} / "
          f"{metrics['collocation']['total']}")
    print(f"  Alignment:        {metrics['collocation']['alignment']:.1%}")
    
    print(f"\nStep C — Qualia Output")
    print(f"  With qualia data: {metrics['step_c']['with_data']} / "
          f"{metrics['step_c']['total']}")
    
    # Sample 5 Step C outputs
    print(f"\nStep C Sample Review (first 5 with qualia):")
    count = 0
    for pred_id, pred_rec in sorted(predictions.items()):
        if count >= 5:
            break
        step_c = pred_rec.get("step_c")
        if step_c and step_c.get("frame"):
            count += 1
            frame = step_c["frame"]
            target_verb = pred_rec["provenance"]["target_word"]
            pred_frame = pred_rec.get("step_b", {}).get("selected_frame", "?")
            print(f"\n  [{count}] Verb: {target_verb} | Predicted frame: {pred_frame}")
            print(f"      Qualia frame: {frame}")
            # Print first few qualia fields
            for key in list(step_c.keys())[:3]:
                if key not in ("frame",):
                    val = step_c[key]
                    if isinstance(val, str) and len(val) > 60:
                        val = val[:60] + "…"
                    print(f"        {key}: {val}")
    
    # Save JSON
    if output_json:
        output_json = Path(output_json).expanduser()
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"\n✓ Metrics saved to {output_json}")
    
    return metrics


if __name__ == "__main__":
    import sys
    
    pred_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/verb_spike_preds.jsonl"
    output_json = sys.argv[2] if len(sys.argv) > 2 else "/tmp/verb_spike_metrics.json"
    
    metrics = evaluate_verb_spike(pred_path, output_json)
