"""Export COOKING_CREATION / PRESERVING / CURE sentences, ordered by year.

The agreed deliverable: a sizable set of usable Dutch sentences for these three
frames, 16th-19th century, ordered by year. The frame labelling already exists
in `trifecta_annotations` (10,537 records); this script adds the two things it
was missing — a per-record year (via `corpus_genre_join` / `dbnl_work_genre`)
and an actual sentence (via `unit_segmentation.target_sentence`) carved out of
the KWIC window rather than the raw ±180-char snippet.

Per `plans/steps/SENTENCE_HARVEST.md` H3, concatenates all four annotation
sources produced across this project — the original `trifecta_annotations`
plus the three go-forward batches (`colonial_annotations`,
`handdownload_annotations`, `dbnl_sweep_annotations`) — tagging each row with
`source_corpus` so the sidecar report can show the per-source breakdown. The
three new sources often fall outside `dbnl_work_genre`'s DBNL-only coverage
(colonial/handdownload works aren't DBNL `dbnl_ti_id` records at all), so two
fallbacks apply on top of the existing `corpus_genre_join` lookup:
- **Year**: when the genre join resolves no year, fall back to
  `int(provenance.date)` (every row from the three new sources carries one —
  see `dbnl_sweep_annotations_report.md`), tagged `year_source="provenance.date"`.
- **Category**: when the genre join resolves no category, fall back to
  `provenance.text_regime` directly, tagged `category_scheme="text_regime"`
  (already a valid scheme name in `corpus_genre_join._CATEGORY_SCHEME_ORDER`,
  this just covers the case where no genre record exists to carry it).

**Frame-scope caveat** (SENTENCE_HARVEST.md Background §2, PLAN.md
frame-overlap finding): COOKING_CREATION/PRESERVING/CURE boundary overlap is
known and deliberately not resolved here — this export carries the cascade's
labels as-is.

Nothing is silently dropped. A row with no resolvable year, where the target
word can't be found to anchor a sentence on, or dated 1900 or later (out of
this deliverable's 16th-19th century scope — modern KB catalogue/reprint
years, not the underlying work's era) is excluded from the main export but
counted in the sidecar report, not just discarded. A row whose sentence is
truncated by the KWIC window edge is KEPT, with `truncated_left`/
`truncated_right` flags — dropping those would lose real data (PLAN.md §9e:
gold context_text is often passage-length, so most sentences are complete, but
not all), and whoever uses the export can filter on those flags themselves.

Known, accepted limits (see docs/CORPUS_ACQUISITION.md):
- 7 of 63 original works never resolve a year (absent from the PD dump
  entirely, not a parsing gap) — decided not to chase further.
- One work (`Huishoudelyk woordboek`) dominates the original pool; the
  sidecar reports per-work counts so this stays visible rather than hidden.
- Two `colonial_annotations` PDF sources (`mmkb*_pdf.pdf`) have scrambled
  (not just noisy) OCR reading order — words correct, sequence nonsense. This
  self-filters mostly via `no_sentence` (no coherent punctuation to anchor
  on) rather than needing a separate exclusion here.
- This is LLM-assigned Step B/C silver, not hand gold — see `analysis_export.py`.

Per H4, also writes a flat `frame_sentences.csv` sibling (same rows/fields,
`STEP_C_FIELDS` flattened into a fixed superset of columns since they differ
per frame) for row-count parity with the JSONL.

    uv run python scripts/export_frame_sentences.py --summary
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from data_io import resolve
from data_io.jsonl_io import save_semi_structured
from data_io.provenance import ProvenanceRecord, git_commit_hash, write_sidecar

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

# All annotation sources produced across this project, per SENTENCE_HARVEST.md
# H3. Order matters only for the sort key tie-break below.
SOURCE_LOGICALS = (
    "trifecta_annotations",
    "colonial_annotations",
    "handdownload_annotations",
    "dbnl_sweep_annotations",
)

MAX_YEAR_EXCLUSIVE = 1900  # deliverable scope is 16th-19th century.

# H4 CSV sibling: fixed superset of columns, since STEP_C_FIELDS differs per
# frame (COOKING_CREATION_*/CURE_*/PR_*) — DictWriter fills a row's missing
# columns with "".
CSV_FIELDS = [
    "record_id",
    "source_corpus",
    "work_title",
    "year",
    "year_source",
    "category",
    "category_scheme",
    "frame",
    "target_word",
    "canonical_pref_label",
    "sentence",
    "sentence_truncated_left",
    "sentence_truncated_right",
    "lexical_unit",
    *(field for frame in THREE_FRAMES for field in STEP_C_FIELDS[frame]),
]


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


def build_export(
    annotations: list[tuple[str, dict]], genre_index: dict
) -> tuple[list[dict], Counter]:
    counts: Counter = Counter(total=len(annotations))
    rows: list[dict] = []
    for source_corpus, record in annotations:
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
        year, year_source = lookup.year, lookup.year_source
        if year is None:
            date = provenance.get("date")
            try:
                year = int(str(date)[:4]) if date else None
            except ValueError:
                year = None
            year_source = "provenance.date" if year is not None else year_source
        if year is None:
            counts["no_year"] += 1
            continue
        if year >= MAX_YEAR_EXCLUSIVE:
            counts["year_out_of_scope_1900plus"] += 1
            continue
        counts["has_year"] += 1

        category, category_scheme = lookup.category, lookup.category_scheme
        if category is None and provenance.get("text_regime"):
            category, category_scheme = provenance["text_regime"], "text_regime"

        hit = target_sentence(provenance.get("context_text") or "", provenance.get("target_word") or "")
        if hit is None:
            counts["no_sentence"] += 1
            continue
        counts["has_sentence"] += 1
        if hit.truncated_left or hit.truncated_right:
            counts["truncated"] += 1

        frame = _FRAME_BY_VALUE[frame_value]
        step_a = record.get("step_a") or {}
        step_c = record.get("step_c") or {}
        row = {
            "record_id": provenance.get("record_id"),
            "source_corpus": source_corpus,
            "work_title": provenance.get("title"),
            "year": year,
            "year_source": year_source,
            "category": category,
            "category_scheme": category_scheme,
            "frame": frame_value,
            "target_word": provenance.get("target_word"),
            "canonical_pref_label": step_a.get("canonical_pref_label")
            or provenance.get("target_word"),
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
    lines.append(
        "**Frame-scope caveat:** COOKING_CREATION/PRESERVING/CURE boundary overlap "
        "is known and deliberately not resolved by this export — see "
        "`plans/steps/SENTENCE_HARVEST.md` Background §2 and PLAN.md's "
        "frame-overlap finding. Counts below are the cascade's as-labelled output."
    )
    lines.append("")
    lines.append("## Filter funnel")
    for key in ("total", "dropped_or_error", "three_frame", "has_year", "no_year",
                "year_out_of_scope_1900plus", "has_sentence", "no_sentence", "truncated"):
        lines.append(f"- {key}: {counts[key]}")
    lines.append("")
    lines.append(f"## Exported rows: {len(rows)}")
    by_frame = Counter(r["frame"] for r in rows)
    for frame in THREE_FRAMES:
        lines.append(f"- {frame.value}: {by_frame[frame.value]}")
    lines.append("")
    lines.append("## Rows per source corpus")
    by_source = Counter(r["source_corpus"] for r in rows)
    total = len(rows) or 1
    for source, n in by_source.most_common():
        lines.append(f"- {source}: {n} ({100 * n / total:.0f}%)")
    lines.append("")
    lines.append("## Rows per work (concentration must stay visible — see PLAN.md §9e)")
    by_work = Counter(r["work_title"] for r in rows)
    for title, n in by_work.most_common(15):
        lines.append(f"- {title}: {n} ({100 * n / total:.0f}%)")
    lines.append("")
    years = [r["year"] for r in rows]
    if years:
        lines.append(f"## Year range: {min(years)}-{max(years)}")
        by_century = Counter((y // 100) * 100 for y in years)
        for century, n in sorted(by_century.items()):
            lines.append(f"- {century}s: {n}")
    lines.append("")
    lines.append("## Foodstuff x frame x century (top 20 canonical labels by row count)")
    by_label = Counter(r["canonical_pref_label"] for r in rows)
    lines.append("")
    lines.append("| canonical_pref_label | frame | century | n |")
    lines.append("|---|---|---:|---:|")
    label_frame_century: Counter = Counter()
    for r in rows:
        century = (r["year"] // 100) * 100
        label_frame_century[(r["canonical_pref_label"], r["frame"], century)] += 1
    top_labels = {label for label, _ in by_label.most_common(20)}
    for (label, frame, century), n in sorted(
        label_frame_century.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        if label in top_labels:
            lines.append(f"| {label} | {frame} | {century}s | {n} |")
    return "\n".join(lines) + "\n"


def save_csv(rows: list[dict], *, logical_name: str, description: str, script: str) -> Path:
    """H4: flat CSV sibling of the JSONL export, same fields, plain DictWriter."""
    path = resolve(logical_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})

    record = ProvenanceRecord(
        logical_name=logical_name,
        phase="semi",
        parent_sources=["frame_sentences"],
        description=description,
        created_by_script=script,
        record_count=len(rows),
        git_commit=git_commit_hash(path.parent),
    )
    write_sidecar(path, record)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    annotations: list[tuple[str, dict]] = []
    missing_sources: list[str] = []
    for logical in SOURCE_LOGICALS:
        try:
            path = Path(resolve(logical))
        except Exception:
            missing_sources.append(logical)
            continue
        if not path.exists():
            missing_sources.append(logical)
            continue
        annotations.extend((logical, record) for record in _read_jsonl(path))
    if missing_sources:
        print(f"Note: skipping unavailable sources: {', '.join(missing_sources)}")

    genre_index = build_genre_index()
    rows, counts = build_export(annotations, genre_index)

    out = save_semi_structured(
        rows,
        logical_name="frame_sentences",
        parent_sources=[*SOURCE_LOGICALS, "dbnl_work_genre"],
        description="COOKING_CREATION/PRESERVING/CURE sentences with year + category",
        script="scripts/export_frame_sentences.py",
    )
    report_path = out.parent / "frame_sentences_report.md"
    report_path.write_text(_report(rows, counts), encoding="utf-8")
    print(f"wrote {len(rows)} rows -> {out}")
    print(f"report -> {report_path}")

    csv_out = save_csv(
        rows,
        logical_name="frame_sentences_csv",
        description="Flat CSV sibling of frame_sentences",
        script="scripts/export_frame_sentences.py",
    )
    print(f"wrote {len(rows)} rows -> {csv_out}")
    if args.summary:
        print()
        print(_report(rows, counts))


if __name__ == "__main__":
    main()
