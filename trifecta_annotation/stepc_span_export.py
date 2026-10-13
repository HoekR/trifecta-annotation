"""Export TRIFECTA gold Step C qualia fields to span-extraction (BERT-QA) training format.

Unlike GijsBERT's frame classifier (``gijsbert_export.py``), there is no trustworthy
silver source for Step C fields — the only candidate silver is the LLM's own Step C
generations, which is the unreliable signal this prototype exists to replace. So this
export is gold-only: hand-labelled rows are split into train/dev ourselves.

Each gold Step C field becomes a QA-style example: ``context_text`` is the passage,
``field_query`` is a fixed natural-language cue per field (not per-row — the same
query is reused across every row for a given field so one shared encoder handles
all frames/fields jointly), and the answer is a literal character span when the gold
value is a verbatim substring of the context, or "unanswerable" when the gold value
is genuinely empty. Gold values that are non-empty but *not* a literal substring
(paraphrase/gloss, not a wording variant — see the CURE grounding-prototype finding)
cannot be supervised as a span and are excluded, with counts logged for visibility.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from trifecta_annotation.schemas import TrifectaAnnotation, TrifectaFrame

FRAME_FIELD_QUERIES: dict[str, dict[str, str]] = {
    TrifectaFrame.CURE.value: {
        "CURE_Affliction": "Welke kwaal of klacht wordt hier behandeld?",
        "CURE_Food_Treatment": "Hoe wordt het voedingsmiddel hier als behandeling gebruikt?",
    },
    TrifectaFrame.COOKING_CREATION.value: {
        "COOKING_CREATION_Method": "Welke bereidingswijze of receptstap wordt hier genoemd?",
        "COOKING_CREATION_Process": "Welk thermisch of mechanisch proces wordt hier toegepast?",
        "COOKING_CREATION_Food_Product": "Welk eindproduct ontstaat hier na de bereiding?",
    },
    TrifectaFrame.PRESERVING.value: {
        "PR_Technique": "Welke bewaartechniek wordt hier gebruikt?",
        "PR_Medium": "Welk bewaarmiddel of welke stof wordt hier gebruikt om te bewaren?",
        "PR_Food_Patient": "Welk voedingsmiddel wordt hier bewaard?",
    },
    TrifectaFrame.INGESTION.value: {
        "INGESTION_Context": "In welke situatie of omgeving vindt de consumptie hier plaats?",
        "INGESTION_Ingestor": "Wie consumeert hier het voedsel of de drank?",
        "INGESTION_Manner": "Op welke manier wordt hier geconsumeerd?",
        "INGESTION_Food_Patient": "Welk specifiek gerecht, drank of voedingsmiddel wordt hier geconsumeerd?",
        "INGESTION_Purpose": "Met welk doel of bij welke gelegenheid wordt hier geconsumeerd?",
    },
}

DEFAULT_MODEL_BASE = "globalise/GloBERTise"


def find_span(context_text: str, value: str) -> tuple[int, int] | None:
    """Return (start_char, end_char) of the first case-insensitive match of *value*
    in *context_text*, or None if *value* is not a literal substring."""
    needle = value.strip()
    if not needle:
        return None
    idx = context_text.lower().find(needle.lower())
    if idx == -1:
        return None
    return idx, idx + len(needle)


def _iter_field_examples(
    record: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (examples, skipped) for one gold record's Step C fields."""
    ann = TrifectaAnnotation.model_validate(record)
    examples: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    if ann.step_b is None or ann.step_c is None:
        return examples, skipped

    frame = ann.step_b.selected_frame.value
    field_queries = FRAME_FIELD_QUERIES.get(frame)
    if not field_queries:
        return examples, skipped

    record_id = ann.provenance.record_id
    context_text = ann.provenance.context_text
    step_c_dict = ann.step_c.model_dump(mode="json")

    for field_name, field_query in field_queries.items():
        raw_value = step_c_dict.get(field_name) or ""
        value = str(raw_value).strip()
        if not value:
            examples.append(
                {
                    "record_id": record_id,
                    "frame": frame,
                    "field_name": field_name,
                    "field_query": field_query,
                    "context_text": context_text,
                    "answer_text": "",
                    "answer_start_char": None,
                    "answer_end_char": None,
                }
            )
            continue
        span = find_span(context_text, value)
        if span is None:
            skipped.append(
                {
                    "record_id": record_id,
                    "frame": frame,
                    "field_name": field_name,
                    "gold_value": value,
                }
            )
            continue
        start_char, end_char = span
        examples.append(
            {
                "record_id": record_id,
                "frame": frame,
                "field_name": field_name,
                "field_query": field_query,
                "context_text": context_text,
                "answer_text": context_text[start_char:end_char],
                "answer_start_char": start_char,
                "answer_end_char": end_char,
            }
        )
    return examples, skipped


def build_stepc_span_examples(
    gold_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (examples, skipped_ungrounded) across all gold records."""
    all_examples: list[dict[str, Any]] = []
    all_skipped: list[dict[str, Any]] = []
    for record in gold_records:
        examples, skipped = _iter_field_examples(record)
        all_examples.extend(examples)
        all_skipped.extend(skipped)
    return all_examples, all_skipped


def _split_record_ids(
    examples: list[dict[str, Any]],
    *,
    dev_fraction: float,
    seed: int,
) -> set[str]:
    """Pick dev record_ids, stratified by frame, from the example pool."""
    by_frame: dict[str, list[str]] = {}
    seen: set[str] = set()
    for ex in examples:
        rid = str(ex["record_id"])
        if rid in seen:
            continue
        seen.add(rid)
        by_frame.setdefault(ex["frame"], []).append(rid)

    rng = random.Random(seed)
    dev_ids: set[str] = set()
    for frame, ids in by_frame.items():
        ids = sorted(ids)
        rng.shuffle(ids)
        n_dev = max(1, round(len(ids) * dev_fraction)) if ids else 0
        dev_ids.update(ids[:n_dev])
    return dev_ids


def _write_jsonl(rows: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def export_stepc_span_splits(
    *,
    gold_records: list[dict[str, Any]],
    output_dir: str | Path,
    model_base: str = DEFAULT_MODEL_BASE,
    dev_fraction: float = 0.2,
    seed: int = 42,
) -> dict[str, Path]:
    """Write train/dev JSONL + field manifest for the Step C span-extraction prototype."""
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    examples, skipped = build_stepc_span_examples(gold_records)
    dev_ids = _split_record_ids(examples, dev_fraction=dev_fraction, seed=seed)

    train_rows = [ex for ex in examples if str(ex["record_id"]) not in dev_ids]
    dev_rows = [ex for ex in examples if str(ex["record_id"]) in dev_ids]

    paths = {
        "train": _write_jsonl(train_rows, out / "train.jsonl"),
        "dev": _write_jsonl(dev_rows, out / "dev.jsonl"),
        "skipped_ungrounded": _write_jsonl(skipped, out / "skipped_ungrounded.jsonl"),
    }

    skipped_by_field: dict[str, int] = {}
    for row in skipped:
        skipped_by_field[row["field_name"]] = skipped_by_field.get(row["field_name"], 0) + 1

    fields = sorted({f for queries in FRAME_FIELD_QUERIES.values() for f in queries})
    manifest = {
        "frames": sorted(FRAME_FIELD_QUERIES),
        "fields": fields,
        "field_queries": {
            field: query
            for queries in FRAME_FIELD_QUERIES.values()
            for field, query in queries.items()
        },
        "field_to_frame": {
            field: frame for frame, queries in FRAME_FIELD_QUERIES.items() for field in queries
        },
        "model_base": model_base,
        "counts": {
            "train": len(train_rows),
            "dev": len(dev_rows),
            "skipped_ungrounded": len(skipped),
            "skipped_ungrounded_by_field": skipped_by_field,
        },
    }
    manifest_path = out / "field_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    paths["manifest"] = manifest_path
    return paths


def load_stepc_span_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
