"""Threshold sweep for the Step A keep/drop sieve on the dev split.

Accuracy is the wrong number for a sieve: a false DROP loses a real finding,
a false KEEP costs one LLM call. So per regime and per DROP threshold this
reports keep-recall (share of true KEEPs that survive) and the share of rows
the sieve removes (LLM Step A calls saved). Pick the threshold where
keep-recall stays acceptable for the regimes that are actually sieved.

    uv run python scripts/sweep_step_a_keepdrop.py
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from trifecta_annotation.hf_cache import configure_hf_hub_cache

configure_hf_hub_cache()

import torch  # noqa: E402
from transformers import AutoModelForSequenceClassification, AutoTokenizer  # noqa: E402

from data_io import resolve  # noqa: E402

THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98)


def main() -> None:
    base = Path(resolve("trifecta_step_a_keepdrop"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", default=str(base / "dev.jsonl"))
    parser.add_argument("--model-dir", default=str(base / "models" / "globertise-keepdrop" / "model"))
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--out", default=str(base / "models" / "globertise-keepdrop" / "threshold_sweep.json"))
    args = parser.parse_args()

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(args.model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(args.model_dir).to(device).eval()
    drop_id = {v: int(k) for k, v in model.config.id2label.items()}["DROP"]

    rows = [json.loads(l) for l in Path(args.dev).read_text(encoding="utf-8").splitlines() if l.strip()]
    p_drop: list[float] = []
    with torch.no_grad():
        for i in range(0, len(rows), args.batch_size):
            batch = [r["text"] for r in rows[i : i + args.batch_size]]
            enc = tok(batch, truncation=True, max_length=256, padding=True, return_tensors="pt").to(device)
            probs = torch.softmax(model(**enc).logits, dim=-1)[:, drop_id]
            p_drop.extend(probs.tolist())
            if (i // args.batch_size) % 20 == 0:
                print(f"  {i + len(batch)}/{len(rows)}", flush=True)

    by_regime: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for r, p in zip(rows, p_drop):
        by_regime[r.get("text_regime") or "absent"].append((r["label"], p))
        by_regime["ALL"].append((r["label"], p))

    result: dict[str, dict] = {}
    print(f"\n{'regime':<16}{'n':>6}{'thr':>6}{'keep-recall':>13}{'calls saved':>13}{'drop-prec':>11}")
    for regime, items in sorted(by_regime.items(), key=lambda kv: -len(kv[1])):
        keeps = sum(1 for lab, _ in items if lab == "KEEP")
        result[regime] = {}
        for t in THRESHOLDS:
            dropped = [(lab, p) for lab, p in items if p >= t]
            lost_keeps = sum(1 for lab, _ in dropped if lab == "KEEP")
            recall = 1 - lost_keeps / keeps if keeps else float("nan")
            saved = len(dropped) / len(items)
            prec = 1 - lost_keeps / len(dropped) if dropped else float("nan")
            result[regime][str(t)] = {"n": len(items), "keep_recall": recall, "calls_saved": saved, "drop_precision": prec}
            print(f"{regime:<16}{len(items):>6}{t:>6}{recall:>13.3f}{saved:>13.3f}{prec:>11.3f}")
        print()

    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
