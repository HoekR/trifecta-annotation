"""Shadow run of the Step A keep/drop sieve against real LLM verdicts.

Uses only rows annotated AFTER the sieve was trained (entry-scope production
run + both selection-mode experiments), minus any whose text is in the
training split, so this is a held-out check rather than a replay of training
data. Rows from works the sieve saw in training are reported separately from
unseen works (the split is by work).

For each threshold, per stratum: calls the sieve would save (DROP), Step A
KEEPs it would wrongly drop, and real frames it would lose. Production only
applies the sieve to weak regimes (`should_apply_sieve_to_input`); both the
as-routed and the apply-to-all views are reported.

    uv run python scripts/shadow_step_a_sieve.py
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from data_io import resolve

from trifecta_annotation.gijsbert_export import mark_kwic_context
from trifecta_annotation.step_a_keepdrop import (
    DROP_LABEL,
    KEEP_LABEL,
    HfStepAKeepDropSieve,
    should_apply_sieve_to_input,
    step_a_keep_label,
)

EXP = Path("/Volumes/Extreme SSD/scratch/trifecta/experiments")
OUT_DIR = EXP / "sieve_shadow"
THRESHOLDS = (0.90, 0.95, 0.98, 0.99)
MODEL_DIR = Path(resolve("trifecta_step_a_keepdrop_models")) / "globertise-keepdrop" / "model"
SPLIT_DIR = Path(resolve("trifecta_step_a_keepdrop"))


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def load_rows() -> list[dict]:
    current = {r["record_id"] for r in _jsonl(Path(resolve("entry_scope_kwic_inputs")))}
    sources = [
        ("entry_scope", Path(resolve("entry_scope_annotations")), current),
        ("selection_v1", EXP / "selection_modes" / "annotations.jsonl", None),
        ("selection_v2", EXP / "selection_modes_v2" / "annotations.jsonl", None),
    ]
    train_texts = {r["text"] for r in _jsonl(SPLIT_DIR / "train.jsonl")}
    train_works = {r["source_path"] for r in _jsonl(SPLIT_DIR / "train.jsonl")}
    seen_ctx: set[str] = set()
    rows, skipped_train, skipped_dup = [], 0, 0
    for name, path, keep_ids in sources:
        if not path.exists():
            print(f"missing {path}")
            continue
        for rec in _jsonl(path):
            pv = rec["provenance"]
            if keep_ids is not None and pv["record_id"] not in keep_ids:
                continue
            label = step_a_keep_label(rec)
            if label is None:
                continue
            text = mark_kwic_context(pv["context_text"], target_word=pv["target_word"], mark_mode="food")
            if text in train_texts:
                skipped_train += 1
                continue
            if pv["context_text"] in seen_ctx:
                skipped_dup += 1
                continue
            seen_ctx.add(pv["context_text"])
            frame = (rec.get("step_b") or {}).get("selected_frame")
            rows.append({
                "source": name, "text": text, "llm": label,
                "real_frame": label == KEEP_LABEL and frame not in (None, "NONE"),
                "regime": pv.get("text_regime") or "absent",
                "routed": should_apply_sieve_to_input(rec, sieve_enabled=True),
                "work_seen": pv.get("source_path") in train_works,
            })
    print(f"{len(rows)} held-out rows ({skipped_train} skipped: text in train split; {skipped_dup} duplicates)")
    return rows


def main() -> None:
    rows = load_rows()
    sieve = HfStepAKeepDropSieve(MODEL_DIR)
    torch = sieve._torch
    drop_id = next(i for i, lab in sieve.id2label.items() if lab == DROP_LABEL)
    for start in range(0, len(rows), 32):
        batch = rows[start:start + 32]
        enc = sieve.tokenizer([r["text"] for r in batch], return_tensors="pt", truncation=True,
                              max_length=sieve.max_length, padding=True)
        enc = {k: v.to(sieve.device) for k, v in enc.items()}
        with torch.no_grad():
            probs = torch.softmax(sieve.model(**enc).logits, dim=-1)[:, drop_id].tolist()
        for r, p in zip(batch, probs):
            r["p_drop"] = p
        if (start // 32) % 20 == 0:
            print(f"  scored {start + len(batch)}/{len(rows)}", flush=True)

    def strata(r: dict) -> list[str]:
        keys = ["ALL", f"regime={r['regime']}", f"work_seen={r['work_seen']}"]
        if r["routed"]:
            keys += ["ROUTED (production)", f"ROUTED regime={r['regime']}"]
        return keys

    table: dict[tuple[str, float], list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0])
    for r in rows:
        for key in strata(r):
            for t in THRESHOLDS:
                s = table[(key, t)]
                drop = r["p_drop"] >= t
                s[0] += 1                                   # n
                s[1] += drop                                # calls saved
                s[2] += drop and r["llm"] == KEEP_LABEL     # Step A keeps lost
                s[3] += drop and r["real_frame"]            # real frames lost
                s[4] += r["real_frame"]                     # real frames total

    lines = [
        "# Step A sieve: shadow run on held-out rows", "",
        f"{len(rows)} rows annotated after training (entry-scope run, selection v1/v2), "
        "minus texts in the training split. `work_seen` = the work was in the training split (split is by work).",
        "Production applies the sieve only to ROUTED rows (weak regimes); RECIPE/MEDICAL go straight to the LLM.", "",
        "| stratum | threshold | n | calls saved | Step A keeps lost | real frames lost | of real frames |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for (key, t), (n, saved, keeps, frames, total) in sorted(table.items()):
        lines.append(f"| {key} | {t:.2f} | {n} | {saved / n:.0%} ({saved}) | {keeps} | {frames} | "
                     f"{frames / total:.1%} of {total} |" if total else
                     f"| {key} | {t:.2f} | {n} | {saved / n:.0%} ({saved}) | {keeps} | {frames} | - |")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (OUT_DIR / "scores.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({k: v for k, v in r.items() if k != "text"}, ensure_ascii=False) + "\n")
    print("\n".join(l for l in lines if "0.98" in l or l.startswith("|---") or l.startswith("| stratum")))
    print(f"wrote {OUT_DIR / 'report.md'}")


if __name__ == "__main__":
    main()
