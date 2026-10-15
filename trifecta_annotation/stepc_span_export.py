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

from trifecta_annotation.homonym_context import local_context_window
from trifecta_annotation.schemas import TrifectaAnnotation, TrifectaFrame

# Dutch gold context_text is often passage-length (unclipped `--source long` KWIC
# build); English IAA context_text is already sentence-scoped. Clip everything to
# a target-word-centered window before span-matching so training/eval match what
# Step C would see in production (target_word is always known before Step C runs).
DEFAULT_CONTEXT_RADIUS = 180

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


# Curated/easy source tags to keep OUT of dev by default — see
# project_frame_split_options / mBERT-XLM-R comparison memory for why: these
# sources are either short-by-curation (INCEpTION) or English (structurally
# easier per this project's own eval), and let one dominate dev-by-count once
# already (blended metric looked like a win that was really just composition).
EASY_SOURCE_TAGS = frozenset(
    {"english_iaa", "english_in_nl_export", "inception_legacy", "dutch_inception_agreed"}
)

_KNOWN_SOURCE_CSVS: dict[str, str] = {
    "english_iaa": "inception_en_iaa_agreed_gold.csv",
    "dutch_inception_agreed": "inception_nl_v2_iaa_agreed_gold.csv",
}
# Documents inside the nominally-Dutch INCEpTION export that are actually
# English-language source text (checked by hand — e.g. "Example (1).txt" is
# an English passage), so they shouldn't be lumped in as "Dutch" evidence.
_ENGLISH_DOCS_IN_NL_EXPORT = frozenset({"example_1_txt"})


def _load_known_source_id_tags() -> dict[str, str]:
    """record_id -> source_tag for the two IAA-agreed batches merged today.

    Needed because both batches were imported before inception_tsv.py's
    record_id_prefix fix, so their record_ids all share the ambiguous
    "inception_nl__" prefix regardless of actual source language — can't
    tell them apart by string pattern alone, only by which CSV they're in.
    """
    import csv as _csv

    from data_io import resolve as _resolve

    scratch = Path(_resolve("trifecta_gold")).parent
    tags: dict[str, str] = {}
    for tag, filename in _KNOWN_SOURCE_CSVS.items():
        path = scratch / filename
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as handle:
            for row in _csv.DictReader(handle):
                rid = row.get("record_id", "")
                if not rid:
                    continue
                if tag == "dutch_inception_agreed":
                    parts = rid.split("__")
                    doc = parts[1] if len(parts) > 1 else ""
                    if doc in _ENGLISH_DOCS_IN_NL_EXPORT:
                        tags[rid] = "english_in_nl_export"
                        continue
                tags[rid] = tag
    return tags


def _infer_source_tag(record_id: str, corpus: str, known_ids: dict[str, str]) -> str:
    if record_id.startswith("inception_nl_v2__"):
        # Correctly self-identifying (post-fix import) — still check the
        # English-doc exception inside this export.
        parts = record_id.split("__")
        doc = parts[1] if len(parts) > 1 else ""
        if doc in _ENGLISH_DOCS_IN_NL_EXPORT:
            return "english_in_nl_export"
        return "dutch_inception_agreed"
    if record_id in known_ids:
        return known_ids[record_id]
    if corpus in {"inception_selected_texts", "inception_cookbooks_1"}:
        return "inception_legacy"
    return corpus or "cort_voc_db"


def _iter_field_examples(
    record: dict[str, Any],
    *,
    context_radius: int | None = DEFAULT_CONTEXT_RADIUS,
    known_source_ids: dict[str, str] | None = None,
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
    if context_radius is not None and context_radius > 0 and ann.provenance.target_word:
        context_text = local_context_window(
            context_text, ann.provenance.target_word, radius=context_radius
        )
    step_c_dict = ann.step_c.model_dump(mode="json")
    source_tag = _infer_source_tag(record_id, ann.provenance.corpus, known_source_ids or {})

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
                    "source_tag": source_tag,
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
                "source_tag": source_tag,
            }
        )
    return examples, skipped


def build_stepc_span_examples(
    gold_records: list[dict[str, Any]],
    *,
    context_radius: int | None = DEFAULT_CONTEXT_RADIUS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (examples, skipped_ungrounded) across all gold records."""
    known_source_ids = _load_known_source_id_tags()
    all_examples: list[dict[str, Any]] = []
    all_skipped: list[dict[str, Any]] = []
    for record in gold_records:
        examples, skipped = _iter_field_examples(
            record, context_radius=context_radius, known_source_ids=known_source_ids
        )
        all_examples.extend(examples)
        all_skipped.extend(skipped)
    return all_examples, all_skipped


def _split_record_ids(
    examples: list[dict[str, Any]],
    *,
    dev_fraction: float,
    seed: int,
    dev_exclude_tags: frozenset[str] = EASY_SOURCE_TAGS,
) -> set[str]:
    """Pick dev record_ids, stratified by frame, from the example pool.

    record_ids whose source_tag is in dev_exclude_tags are never placed in
    dev (forced to train) — see EASY_SOURCE_TAGS docstring for why: curated/
    short/English sources dominating dev by count previously made a blended
    metric look like broad progress when it was really composition.
    """
    excluded_ids: set[str] = {
        str(ex["record_id"]) for ex in examples if ex.get("source_tag") in dev_exclude_tags
    }
    by_frame: dict[str, list[str]] = {}
    seen: set[str] = set()
    for ex in examples:
        rid = str(ex["record_id"])
        if rid in seen or rid in excluded_ids:
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
    context_radius: int | None = DEFAULT_CONTEXT_RADIUS,
    dev_exclude_tags: frozenset[str] = EASY_SOURCE_TAGS,
) -> dict[str, Path]:
    """Write train/dev JSONL + field manifest for the Step C span-extraction prototype."""
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    examples, skipped = build_stepc_span_examples(gold_records, context_radius=context_radius)
    dev_ids = _split_record_ids(
        examples, dev_fraction=dev_fraction, seed=seed, dev_exclude_tags=dev_exclude_tags
    )

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

    def _tag_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        seen_rids: set[str] = set()
        for row in rows:
            rid = str(row["record_id"])
            if rid in seen_rids:
                continue
            seen_rids.add(rid)
            tag = row.get("source_tag", "unknown")
            counts[tag] = counts.get(tag, 0) + 1
        return counts

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
        "context_radius": context_radius,
        "dev_exclude_tags": sorted(dev_exclude_tags),
        "counts": {
            "train": len(train_rows),
            "dev": len(dev_rows),
            "skipped_ungrounded": len(skipped),
            "skipped_ungrounded_by_field": skipped_by_field,
            # Source-composition audit trail — check this before trusting any
            # blended dev metric. See EASY_SOURCE_TAGS for which tags are kept
            # out of dev by construction.
            "train_by_source_tag": _tag_counts(train_rows),
            "dev_by_source_tag": _tag_counts(dev_rows),
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
