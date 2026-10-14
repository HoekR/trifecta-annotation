#!/usr/bin/env python3
"""Inter-annotator agreement report + adjudication export for INCEpTION silver annotations.

Groups per-annotator TrifectaAnnotation records (from import_inception_tsv.py) by the
underlying (doc, sentence, token) target, splits Step B frame and Step C qualia field
comparisons into agree / disagree / one_blank / both_blank (blank fields are sparse-layer
coverage, not disagreement), prints a summary, and writes an adjudication CSV for the
targets that need a human call.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from data_io import resolve

from trifecta_annotation.gijsbert_export import mark_target_in_context

AGREE = "agree"
DISAGREE = "disagree"
ONE_BLANK = "one_blank"
BOTH_BLANK = "both_blank"


def _scratch_root() -> Path:
    return Path(resolve("trifecta_gold")).parent


@dataclass
class TargetEntry:
    annotator: str
    frame: str | None
    dropped: bool
    step_c: dict[str, str]
    target_word: str
    context_text: str


def _parse_record_id(record_id: str) -> tuple[str, str, str]:
    """doc, annotator, sentence_id from the inception_tsv adapter's record_id scheme."""
    parts = record_id.split("__")
    return parts[1], parts[2], parts[3]


def load_targets(path: Path) -> dict[tuple[str, str, str], list[TargetEntry]]:
    by_key: dict[tuple[str, str, str], list[TargetEntry]] = defaultdict(list)
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            prov = record.get("provenance") or {}
            rid = str(prov.get("record_id") or "")
            if not rid:
                continue
            doc, annotator, sid = _parse_record_id(rid)
            begin = rid.split("__")[4]
            step_b = record.get("step_b") or {}
            step_c = {
                k: v
                for k, v in (record.get("step_c") or {}).items()
                if k not in {"lexical_unit", "frame"}
            }
            by_key[(doc, sid, begin)].append(
                TargetEntry(
                    annotator=annotator,
                    frame=step_b.get("selected_frame"),
                    dropped=bool(record.get("dropped")),
                    step_c=step_c,
                    target_word=str(prov.get("target_word") or ""),
                    context_text=str(prov.get("context_text") or ""),
                ),
            )
    return by_key


def _field_status(values: list[str]) -> str:
    filled = [v for v in values if v]
    if not filled:
        return BOTH_BLANK
    if len(filled) < len(values):
        return ONE_BLANK
    if len(set(filled)) == 1:
        return AGREE
    return DISAGREE


def short_context(text: str, *, width: int = 240) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:width] + ("…" if len(text) > width else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--annotations-path",
        type=Path,
        default=None,
        help="Silver annotations JSONL from import_inception_tsv.py (default: scratch/<prefix>_annotations.jsonl)",
    )
    parser.add_argument("--prefix", default="inception_en", help="Matches --output-prefix used on import")
    parser.add_argument("--output-path", type=Path, default=None)
    args = parser.parse_args()

    scratch = _scratch_root()
    annotations_path = args.annotations_path or scratch / f"{args.prefix}_annotations.jsonl"
    output_path = args.output_path or scratch / f"{args.prefix}_iaa_adjudication.csv"

    by_key = load_targets(annotations_path)
    overlap = {k: v for k, v in by_key.items() if len(v) > 1}

    frame_status_counts: Counter[str] = Counter()
    field_status_counts: dict[str, Counter[str]] = defaultdict(Counter)
    rows: list[dict[str, str]] = []

    for (doc, sid, _begin), entries in overlap.items():
        dropped_flags = {e.dropped for e in entries}
        frames = {e.frame for e in entries if not e.dropped and e.frame}

        if len(dropped_flags) > 1:
            frame_status = "dropped_split"
        elif len(frames) == 0:
            frame_status = "all_dropped"
        elif len(frames) == 1:
            frame_status = AGREE
        else:
            frame_status = DISAGREE
        frame_status_counts[frame_status] += 1

        field_rows: dict[str, str] = {}
        if frame_status == AGREE:
            all_fields = {k for e in entries for k in e.step_c}
            for field in all_fields:
                values = [e.step_c.get(field, "") for e in entries]
                status = _field_status(values)
                field_status_counts[field][status] += 1
                if status in {DISAGREE, ONE_BLANK}:
                    field_rows[field] = " | ".join(
                        f"{e.annotator}={e.step_c.get(field, '')!r}" for e in entries
                    )

        needs_adjudication = frame_status in {DISAGREE, "dropped_split"} or bool(field_rows)
        if not needs_adjudication:
            continue

        target_word = entries[0].target_word
        context = entries[0].context_text
        rows.append(
            {
                "doc": doc,
                "sentence_id": sid,
                "target_word": target_word,
                "context_snippet": short_context(mark_target_in_context(context, target_word)),
                "frame_status": frame_status,
                "frame_values": " | ".join(
                    f"{e.annotator}={'DROPPED' if e.dropped else (e.frame or 'NONE')}" for e in entries
                ),
                "step_c_disagreements": "; ".join(f"{field}: {val}" for field, val in field_rows.items()),
                "gold_frame": "",
                "gold_step_c_json": "",
                "review_notes": "",
            },
        )

    rows.sort(key=lambda r: (r["frame_status"], r["doc"], int(r["sentence_id"].lstrip("s") or 0)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "doc",
                "sentence_id",
                "target_word",
                "context_snippet",
                "frame_status",
                "frame_values",
                "step_c_disagreements",
                "gold_frame",
                "gold_step_c_json",
                "review_notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Overlapping targets (2+ annotators): {len(overlap)}")
    print(f"Frame status: {dict(frame_status_counts)}")
    print()
    print(f"{'field':30s} {'agree':>6s} {'disagree':>9s} {'one_blank':>10s} {'both_blank':>11s}  agree-rate(filled)")
    for field, counts in field_status_counts.items():
        filled = counts[AGREE] + counts[DISAGREE]
        rate = f"{counts[AGREE] / filled * 100:.0f}%" if filled else "n/a"
        print(
            f"{field:30s} {counts[AGREE]:6d} {counts[DISAGREE]:9d} {counts[ONE_BLANK]:10d} "
            f"{counts[BOTH_BLANK]:11d}  {rate}",
        )
    print(f"\nAdjudication rows: {len(rows)} -> {output_path}")


if __name__ == "__main__":
    main()
