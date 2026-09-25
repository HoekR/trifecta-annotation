#!/usr/bin/env python3
"""Migrate corpus verb CSV to term_norm=modern + historic_forms layout."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import pandas as pd

from trifecta_annotation.frame_verb_corpus import CORPUS_COLUMNS, row_canonical_and_surfaces


def migrate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    buckets: dict[tuple[str, str], dict[str, object]] = defaultdict(
        lambda: {
            "surfaces": set(),
            "snippet_freq": 0,
            "anchor_agreement": 0.0,
            "anchor_frames": "",
            "keep": "",
            "notes": "",
            "term_example": "",
        },
    )
    for row in frame.itertuples(index=False):
        canonical, surfaces = row_canonical_and_surfaces(row)
        if not canonical:
            continue
        frame_hint = str(getattr(row, "frame_hint", "") or "").strip()
        if not frame_hint:
            continue
        key = (canonical, frame_hint)
        bucket = buckets[key]
        bucket["surfaces"].update(surfaces)
        bucket["snippet_freq"] = int(bucket["snippet_freq"]) + int(getattr(row, "snippet_freq", 0) or 0)
        bucket["anchor_agreement"] = max(
            float(bucket["anchor_agreement"]),
            float(getattr(row, "anchor_agreement", 0) or 0),
        )
        if not bucket["anchor_frames"]:
            bucket["anchor_frames"] = str(getattr(row, "anchor_frames", "") or "")
        if not bucket["keep"]:
            bucket["keep"] = str(getattr(row, "keep", "") or "")
        if not bucket["notes"]:
            bucket["notes"] = str(getattr(row, "notes", "") or "")
        example = str(getattr(row, "term_example", "") or "").strip()
        if example and not bucket["term_example"]:
            bucket["term_example"] = example

    rows: list[dict[str, object]] = []
    for (canonical, frame_hint), bucket in sorted(buckets.items()):
        surfaces = sorted(str(s) for s in bucket["surfaces"] if s and s != canonical)
        example = str(bucket["term_example"] or (surfaces[0] if surfaces else canonical))
        if example in surfaces:
            surfaces = [s for s in surfaces if s != example]
        rows.append(
            {
                "term_norm": canonical,
                "historic_forms": ",".join(surfaces),
                "term_example": example,
                "frame_hint": frame_hint,
                "snippet_freq": bucket["snippet_freq"],
                "anchor_agreement": bucket["anchor_agreement"],
                "anchor_frames": bucket["anchor_frames"],
                "keep": bucket["keep"],
                "notes": bucket["notes"],
            },
        )
    return pd.DataFrame(rows, columns=CORPUS_COLUMNS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--in-place", action="store_true")
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    migrated = migrate_frame(frame)
    out = args.input if args.in_place else (args.output or args.input.with_suffix(".migrated.csv"))
    migrated.to_csv(out, index=False)
    print(f"Wrote {len(migrated)} rows → {out}")


if __name__ == "__main__":
    main()
