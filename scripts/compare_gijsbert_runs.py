#!/usr/bin/env python3
"""Summarize GijsBERT fine-tune runs into one comparison table."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_run(path: Path) -> dict | None:
    metrics_path = path / "dev_metrics.json"
    if not metrics_path.exists():
        return None
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare GijsBERT fine-tune runs.")
    parser.add_argument(
        "--runs-dir",
        default=None,
        help="Root with runs/ and models/ subdirs (default: trifecta_gijsbert manifest)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Markdown output (default: runs-dir/model_comparison.md)",
    )
    args = parser.parse_args()

    if args.runs_dir:
        root = Path(args.runs_dir).expanduser().resolve()
    else:
        from data_io import resolve

        root = Path(resolve("trifecta_gijsbert"))
    candidates: list[Path] = []
    for pattern in ("runs/*", "models/*"):
        candidates.extend(p for p in root.glob(pattern) if p.is_dir())

    rows: list[dict] = []
    for run_dir in sorted(candidates):
        meta = _load_run(run_dir)
        if meta is None:
            continue
        dev = meta.get("dev_metrics") or {}
        frame = meta.get("dev_metrics_frame_only") or {}
        rows.append(
            {
                "run": run_dir.name,
                "model": meta.get("model_base", "?"),
                "dev_all": dev.get("accuracy"),
                "dev_frames": frame.get("accuracy"),
                "path": str(run_dir),
            }
        )

    out = Path(args.output) if args.output else root / "model_comparison.md"
    lines = [
        "# GijsBERT model comparison",
        "",
        "| Run | Model | Dev acc (all) | Dev acc (frames only) |",
        "|-----|-------|---------------|------------------------|",
    ]
    for row in sorted(rows, key=lambda r: (r["dev_frames"] or 0, r["dev_all"] or 0), reverse=True):
        all_acc = f"{row['dev_all']:.3f}" if row["dev_all"] is not None else "—"
        frame_acc = f"{row['dev_frames']:.3f}" if row["dev_frames"] is not None else "—"
        lines.append(f"| {row['run']} | `{row['model']}` | {all_acc} | {frame_acc} |")
    lines.extend(
        [
            "",
            "Baseline: qwen2.5-coder Step B **0.750** (157 gold rows).",
            "Frames-only = dev rows excluding NONE (fairer when train lacks dropout).",
        ]
    )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
