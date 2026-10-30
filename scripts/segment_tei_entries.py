"""Dump the declared entry structure of a DBNL TEI work, for human review.

Read-only in both directions: reads one XML out of the `dbnl_xml` zip without
extracting it, and writes nothing unless `--out-dir` is given explicitly. It
makes no frame judgements and changes no `record_id`s — re-deriving the corpus
at entry granularity is a separate, sign-off-gated step, because ids like
`chom003huis01_01.xml__ch20__amandelen` are referenced from
`trifecta_annotation/fewshot_export.py` and `scripts/merge_verb_phase2a_gold.py`.

The point is the head inventory: 4,794 short declared heads for Chomel, which
a person can read through before anything downstream assigns meaning to them.
See PLAN.md §9h for why the heads matter — the entry head determines the frame
and no local-window method recovers it.

Usage:
    python scripts/segment_tei_entries.py --work chomel
    python scripts/segment_tei_entries.py --work secreet --sample 20
    python scripts/segment_tei_entries.py --xml-name bate002secr02_01.xml
    python scripts/segment_tei_entries.py --work chomel --out-dir /tmp/tei
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from data_io import resolve

from trifecta_annotation.tei_segmentation import (
    head_inventory,
    parse_entries,
    read_work_xml,
)

# The four works inspected in PLAN.md §9h. --xml-name takes any other.
WORKS: dict[str, str] = {
    "chomel": "chom003huis01_01.xml",
    "secreet": "bate002secr02_01.xml",
    "pharm_ams": "_pha001phar02_01.xml",
    "pharm_rot": "_pha002phar01_01.xml",
}


def summarize(entries: list[dict[str, object]], *, sample: int) -> None:
    total = len(entries)
    print(f"entries: {total}")
    if not total:
        return

    units = Counter(str(r["unit_kind"]) for r in entries)
    print("unit kinds:", ", ".join(f"{k}={v}" for k, v in units.most_common()))
    kinds = Counter(str(r["head_kind"]) for r in entries)
    print("head kinds:", ", ".join(f"{k}={v}" for k, v in kinds.most_common()))
    inherited = sum(1 for r in entries if r["scope_inherited"])
    print(f"scope inherited via carry-forward: {inherited}")

    carriers = Counter(str(r["carriers"]) or "(none)" for r in entries)
    print("content carriers:", ", ".join(f"{k}={v}" for k, v in carriers.most_common(5)))

    with_anchors = sum(1 for r in entries if r["anchors"])
    with_rubrics = sum(1 for r in entries if r["rubrics"])
    print(f"entries with keyword anchors: {with_anchors} | with rubrics: {with_rubrics}")

    if with_rubrics:
        seqs = Counter(str(r["rubrics"]) for r in entries if r["rubrics"])
        print("top rubric sequences:")
        for seq, count in seqs.most_common(5):
            print(f"   {count:>4}  {seq}")

    print(f"\n--- first {sample} heads ---")
    for row in entries[:sample]:
        flag = " [inherited]" if row["scope_inherited"] else ""
        anchors = f"  anchors={row['anchors']}" if row["anchors"] else ""
        print(f"  {row['entry_id']}  {row['head']!r}{flag}{anchors}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--work", choices=sorted(WORKS))
    group.add_argument("--xml-name", help="Any .xml member of the dbnl_xml zip")
    parser.add_argument("--sample", type=int, default=12, help="Heads to print")
    parser.add_argument(
        "--out-dir",
        help="Write entries.jsonl + heads.csv here. Omitted: print only, write nothing.",
    )
    args = parser.parse_args()

    xml_name = WORKS[args.work] if args.work else args.xml_name
    work_id = Path(xml_name).name
    xml = read_work_xml(resolve("dbnl_xml"), xml_name)
    entries = parse_entries(xml, work_id=work_id)
    rows = head_inventory(entries)

    print(f"{work_id}  ({len(xml):,} chars of XML)")
    summarize(rows, sample=args.sample)

    if not args.out_dir:
        print("\n(no --out-dir given; nothing written)")
        return

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jsonl_path = out / f"{Path(work_id).stem}_entries.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps({
                "entry_id": entry.entry_id,
                "chapter_index": entry.chapter_index,
                "chapter_head": entry.chapter_head,
                "section_index": entry.section_index,
                "head": entry.head,
                "head_kind": entry.head_kind,
                "unit_kind": entry.unit_kind,
                "scope_head": entry.scope_head,
                "scope_inherited": entry.scope_inherited,
                "carriers": list(entry.carriers),
                "keyword_anchors": [
                    {"term": a.term, "offset": a.offset} for a in entry.keyword_anchors
                ],
                "rubrics": list(entry.rubrics),
                "text": entry.text,
            }, ensure_ascii=False) + "\n")

    heads_path = out / f"{Path(work_id).stem}_heads.csv"
    with heads_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nwrote {len(entries)} entries -> {jsonl_path}")
    print(f"wrote head inventory -> {heads_path}")


if __name__ == "__main__":
    main()
