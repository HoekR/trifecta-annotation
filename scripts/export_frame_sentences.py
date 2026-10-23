"""Export COOKING_CREATION / PRESERVING / CURE sentences, ordered by year.

The agreed deliverable: a sizable set of usable Dutch sentences for these three
frames, 16th-19th century, ordered by year. The frame labelling already exists
in `trifecta_annotations` (10,537 records); this script adds the two things it
was missing — a per-record year (via `corpus_genre_join` / `dbnl_work_genre`)
and an actual sentence (via `unit_segmentation.target_sentence`) carved out of
the KWIC window rather than the raw ±180-char snippet.

Nothing is silently dropped. A row with no resolvable year, or where the
target word can't be found to anchor a sentence on, is excluded from the main
export but counted in the sidecar report, not just discarded. A row whose
sentence is truncated by the KWIC window edge is KEPT, with `truncated_left`/
`truncated_right` flags — dropping those would lose real data (PLAN.md §9e:
gold context_text is often passage-length, so most sentences are complete, but
not all), and whoever uses the export can filter on those flags themselves.

Known, accepted limits (see docs/CORPUS_ACQUISITION.md):
- 7 of 63 works never resolve a year (absent from the PD dump entirely, not a
  parsing gap) — decided not to chase further.
- One work (`Huishoudelyk woordboek`) dominates the pool; the sidecar reports
  per-work counts so this stays visible rather than hidden in a total.
- This is LLM-assigned Step B/C silver, not hand gold — see `analysis_export.py`.

    uv run python scripts/export_frame_sentences.py --summary
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from data_io import resolve
from data_io.jsonl_io import save_semi_structured

from trifecta_annotation.corpus_genre_join import build_genre_index, lookup_for_filename
from trifecta_annotation.eval import STEP_C_FIELDS
from trifecta_annotation.schemas import TrifectaFrame
from trifecta_annotation.unit_segmentation import target_sentence

THREE_FRAMES = (
    TrifectaFrame.COOKING_CREATION,
    TrifectaFrame.PRESERVING,
    TrifectaFrame.CURE,
)
_FRAME_BY_VALUE = {f.value: f for f in THREE_FRAMES}


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("---"):
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def build_export(annotations: list[dict], genre_index: dict) -> tuple[list[dict], Counter]:
    counts: Counter = Counter(total=len(annotations))
    rows: list[dict] = []
    for record in annotations:
        if record.get("dropped") or record.get("error"):
            counts["dropped_or_error"] += 1
            continue
        step_b = record.get("step_b") or {}
        frame_value = step_b.get("selected_frame")
        if frame_value not in _FRAME_BY_VALUE:
            counts["other_frame"] += 1
            continue
        counts["three_frame"] += 1

        provenance = record.get("provenance") or {}
        lookup = lookup_for_filename(genre_index, provenance.get("source_path") or "")
        if lookup.year is None:
            counts["no_year"] += 1
            continue
        counts["has_year"] += 1

        hit = target_sentence(provenance.get("context_text") or "", provenance.get("target_word") or "")
        if hit is None:
            counts["no_sentence"] += 1
            continue
        counts["has_sentence"] += 1
        if hit.truncated_left or hit.truncated_right:
            counts["truncated"] += 1

        frame = _FRAME_BY_VALUE[frame_value]
        step_c = record.get("step_c") or {}
        row = {
            "record_id": provenance.get("record_id"),
            "work_title": provenance.get("title"),
            "year": lookup.year,
            "year_source": lookup.year_source,
            "category": lookup.category,
            "category_scheme": lookup.category_scheme,
            "frame": frame_value,
            "target_word": provenance.get("target_word"),
            "sentence": hit.text,
            "sentence_truncated_left": hit.truncated_left,
            "sentence_truncated_right": hit.truncated_right,
            "lexical_unit": step_b.get("lexical_unit"),
        }
        for field in STEP_C_FIELDS[frame]:
            row[field] = step_c.get(field, "")
        rows.append(row)

    rows.sort(key=lambda r: (r["year"], r["work_title"] or "", r["record_id"] or ""))
    return rows, counts


def _report(rows: list[dict], counts: Counter) -> str:
    lines = ["# frame_sentences export report", ""]
    lines.append("## Filter funnel")
    for key in ("total", "dropped_or_error", "three_frame", "has_year", "no_year",
                "has_sentence", "no_sentence", "truncated"):
        lines.append(f"- {key}: {counts[key]}")
    lines.append("")
    lines.append(f"## Exported rows: {len(rows)}")
    by_frame = Counter(r["frame"] for r in rows)
    for frame in THREE_FRAMES:
        lines.append(f"- {frame.value}: {by_frame[frame.value]}")
    lines.append("")
    lines.append("## Rows per work (concentration must stay visible — see PLAN.md §9e)")
    by_work = Counter(r["work_title"] for r in rows)
    total = len(rows) or 1
    for title, n in by_work.most_common(15):
        lines.append(f"- {title}: {n} ({100 * n / total:.0f}%)")
    lines.append("")
    years = [r["year"] for r in rows]
    if years:
        lines.append(f"## Year range: {min(years)}-{max(years)}")
        by_century = Counter((y // 100) * 100 for y in years)
        for century, n in sorted(by_century.items()):
            lines.append(f"- {century}s: {n}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    annotations = _read_jsonl(Path(resolve("trifecta_annotations")))
    genre_index = build_genre_index()
    rows, counts = build_export(annotations, genre_index)

    out = save_semi_structured(
        rows,
        logical_name="frame_sentences",
        parent_sources=["trifecta_annotations", "dbnl_work_genre"],
        description="COOKING_CREATION/PRESERVING/CURE sentences with year + category",
        script="scripts/export_frame_sentences.py",
    )
    report_path = out.parent / "frame_sentences_report.md"
    report_path.write_text(_report(rows, counts), encoding="utf-8")
    print(f"wrote {len(rows)} rows -> {out}")
    print(f"report -> {report_path}")
    if args.summary:
        print()
        print(_report(rows, counts))


if __name__ == "__main__":
    main()
