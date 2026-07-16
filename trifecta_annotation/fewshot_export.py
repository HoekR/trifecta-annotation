"""Build Step B few-shot examples from manual review CSVs."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from trifecta_annotation.schemas import TrifectaFrame

DEFAULT_STEP_B_FEWSHOT_RECORDS: tuple[str, ...] = (
    "cats001houw01_01.xml__ch16__biet",
    "_vad003185501_01.xml__ch139__noot",
    "_vad003183301_01.xml__ch379__bloem",
    "_tij008186501_01.xml__ch19__uijen",
    "meer017tone02_01.xml__ch86__v_nuttigen__erwten",
    "_vad003183301_01.xml__ch281__v_verzorgen__suiker",
    "joos025kley01_01.xml__ch6__brooden",
    "_vad003183901_01.xml__ch389__v_nuttigen__boter",
    "wolf016hist01_01.xml__ch147__v_zuren__appel",
    "inception_nl__selected_texts_txt__dekker__s30__9204__wyn",
    "pica002naau05_01.xml__ch30__v_eeten__brood",
    "breu012dagv01_01.xml__ch3__v_genezen__thee",
)

# Curated LU fixes where spot-check CSV columns are noisy or NONE frames need no LU.
LEXICAL_UNIT_OVERRIDES: dict[str, str] = {
    "cats001houw01_01.xml__ch16__biet": "",
    "_vad003185501_01.xml__ch139__noot": "",
    "_vad003183301_01.xml__ch379__bloem": "",
    "_tij008186501_01.xml__ch19__uijen": "neus optrokken",
    "meer017tone02_01.xml__ch86__v_nuttigen__erwten": "nuttigen",
    "_vad003183301_01.xml__ch281__v_verzorgen__suiker": "hebben",
    "joos025kley01_01.xml__ch6__brooden": "eten kondt",
    "_vad003183901_01.xml__ch389__v_nuttigen__boter": "slijten",
    "wolf016hist01_01.xml__ch147__v_zuren__appel": "gebeten",
    "inception_nl__selected_texts_txt__dekker__s30__9204__wyn": "weken",
    "pica002naau05_01.xml__ch30__v_eeten__brood": "uitdeelt",
    "breu012dagv01_01.xml__ch3__v_genezen__thee": "drinken",
}

_TGT_RE = re.compile(r"\[/?TGT\]")


def strip_tgt_markup(text: str) -> str:
    """Remove [TGT] markup from review snippets."""
    return _TGT_RE.sub("", str(text or "")).strip()


def _normalize_frame_label(frame: str) -> str:
    label = str(frame or "").strip()
    if label in {"", "DROPPED"}:
        return TrifectaFrame.NONE.value
    if label == "NONE":
        return TrifectaFrame.NONE.value
    return label


def frame_for_review_row(
    *,
    verdict: str,
    gold_frame: str,
    pred_frame: str,
) -> str:
    """Pick the frame label to teach from a spot-check verdict."""
    verdict = str(verdict or "").strip().lower()
    if verdict == "a":
        return _normalize_frame_label(pred_frame)
    return _normalize_frame_label(gold_frame)


def lexical_unit_for_row(row: dict[str, str], *, frame: str) -> str:
    """Prefer gold LU; fall back to pred LU when adopting prediction."""
    verdict = str(row.get("verdict") or "").strip().lower()
    gold_lu = str(row.get("gold_lexical_unit") or "").strip()
    pred_lu = str(row.get("pred_lexical_unit") or "").strip()
    if verdict == "a" and pred_lu:
        return pred_lu
    if gold_lu:
        return gold_lu
    if pred_lu:
        return pred_lu
    if frame == TrifectaFrame.NONE.value:
        return ""
    return ""


def reasoning_for_row(row: dict[str, str]) -> str:
    note = str(row.get("review_notes") or row.get("homonym_note") or "").strip()
    if note:
        return note
    gold = str(row.get("gold_frame") or "")
    pred = str(row.get("pred_frame") or "")
    verdict = str(row.get("verdict") or "").strip().lower()
    if verdict == "a" and pred:
        return f"Adopt prediction: {pred} (gold was {gold})."
    if gold == "DROPPED":
        return "Homograph or non-practice referent; no TRIFECTA food frame."
    return ""


def spotcheck_row_to_fewshot(row: dict[str, str]) -> dict[str, str] | None:
    """Convert one spot-check CSV row to a Step B few-shot example."""
    target = str(row.get("target_word") or "").strip()
    if not target:
        return None

    context = strip_tgt_markup(
        row.get("context_marked") or row.get("context_snippet") or "",
    )
    if not context:
        return None

    frame = frame_for_review_row(
        verdict=str(row.get("verdict") or ""),
        gold_frame=str(row.get("gold_frame") or ""),
        pred_frame=str(row.get("pred_frame") or ""),
    )
    reasoning = reasoning_for_row(row)
    if not reasoning:
        return None

    lexical_unit = lexical_unit_for_row(row, frame=frame)
    record_id = str(row.get("record_id") or "")
    if record_id in LEXICAL_UNIT_OVERRIDES:
        lexical_unit = LEXICAL_UNIT_OVERRIDES[record_id]
    output = json.dumps(
        {
            "selected_frame": frame,
            "lexical_unit": lexical_unit,
            "reasoning": reasoning,
        },
        ensure_ascii=False,
    )
    return {
        "target_word": target,
        "context_text": context,
        "output": output,
        "record_id": str(row.get("record_id") or ""),
        "source": "spotcheck",
    }


def gallery_row_to_fewshot(row: dict[str, str]) -> dict[str, str] | None:
    """Convert a reviewed target-reference gallery row when homonym_note is set."""
    note = str(row.get("homonym_note") or "").strip()
    if not note:
        return None

    target = str(row.get("target_word") or "").strip()
    context = strip_tgt_markup(str(row.get("review_snippet") or ""))
    if not target or not context:
        return None

    frame = _normalize_frame_label(str(row.get("gold_frame") or ""))
    reasoning = note
    gold_reasoning = str(row.get("gold_step_b_reasoning") or "").strip()
    if gold_reasoning and gold_reasoning not in reasoning:
        reasoning = f"{note} ({gold_reasoning})"

    output = json.dumps(
        {
            "selected_frame": frame,
            "lexical_unit": "",
            "reasoning": reasoning,
        },
        ensure_ascii=False,
    )
    return {
        "target_word": target,
        "context_text": context,
        "output": output,
        "record_id": str(row.get("record_id") or ""),
        "source": "gallery",
    }


def _read_csv_rows(path: Path, *, delimiter: str | None = None) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    if delimiter is None:
        delimiter = ";" if text.count(";") > text.count(",") else ","
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def build_step_b_fewshots(
    *,
    spotcheck_path: Path | None = None,
    gallery_path: Path | None = None,
    record_ids: list[str] | None = None,
    include_gallery_notes: bool = True,
) -> list[dict[str, str]]:
    """Merge curated spot-check rows and optional gallery homonym notes."""
    wanted = {rid.strip() for rid in (record_ids or DEFAULT_STEP_B_FEWSHOT_RECORDS)}
    examples: list[dict[str, str]] = []
    seen: set[str] = set()

    if spotcheck_path and spotcheck_path.exists():
        by_id = {
            str(row.get("record_id") or ""): row
            for row in _read_csv_rows(spotcheck_path)
        }
        for record_id in record_ids or DEFAULT_STEP_B_FEWSHOT_RECORDS:
            row = by_id.get(record_id)
            if not row:
                continue
            example = spotcheck_row_to_fewshot(row)
            if example is None:
                continue
            key = example["record_id"] or f"{example['target_word']}:{example['context_text'][:40]}"
            if key in seen:
                continue
            seen.add(key)
            examples.append(
                {
                    "target_word": example["target_word"],
                    "context_text": example["context_text"],
                    "output": example["output"],
                },
            )

    if include_gallery_notes and gallery_path and gallery_path.exists():
        for row in _read_csv_rows(gallery_path):
            if str(row.get("record_id") or "") in wanted:
                continue
            example = gallery_row_to_fewshot(row)
            if example is None:
                continue
            key = example["record_id"] or f"{example['target_word']}:{example['context_text'][:40]}"
            if key in seen:
                continue
            seen.add(key)
            examples.append(
                {
                    "target_word": example["target_word"],
                    "context_text": example["context_text"],
                    "output": example["output"],
                },
            )

    return examples


def fewshots_document(
    examples: list[dict[str, str]],
    *,
    notes: str = "",
) -> dict[str, Any]:
    doc: dict[str, Any] = {"examples": examples}
    if notes:
        doc["notes"] = notes
    return doc
