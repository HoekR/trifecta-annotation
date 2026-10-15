#!/usr/bin/env python3
"""Tag gold CSV rows with inferred text_regime from title / source_path."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from data_io import resolve

from trifecta_annotation.gold_io import GOLD_CSV_COLUMNS, export_gold_csv
from trifecta_annotation.snippet_lookup import lookup_snippet_metadata
from trifecta_annotation.text_regime import TextRegime, infer_text_regime


def _infer_regime_for_row(
    row: dict,
    *,
    titles: dict[str, str],
) -> TextRegime:
    source = str(row.get("source_path") or "").strip()
    title = titles.get(source, "")
    if not title and row.get("notes"):
        note = str(row["notes"]).split(";")[0].strip()
        if len(note) > 12:
            title = note
    regime = infer_text_regime(
        corpus=str(row.get("corpus") or ""),
        title=title,
        source_path=source,
    )
    if regime == TextRegime.UNKNOWN:
        context = str(row.get("context_text") or "").strip()
        if context:
            match = lookup_snippet_metadata(context)
            if match is not None:
                return match.text_regime
    return regime


def tag_dataframe(
    frame: pd.DataFrame,
    *,
    titles: dict[str, str],
    overwrite: bool = False,
    refresh_unknown: bool = False,
) -> tuple[pd.DataFrame, dict[str, int]]:
    counts: dict[str, int] = {regime.value: 0 for regime in TextRegime}
    rows: list[dict] = []
    for record in frame.to_dict(orient="records"):
        row = dict(record)
        existing = str(row.get("text_regime") or "").strip()
        should_refresh = (
            overwrite
            or not existing
            or (refresh_unknown and existing == TextRegime.UNKNOWN.value)
        )
        if should_refresh:
            regime = _infer_regime_for_row(row, titles=titles)
            row["text_regime"] = regime.value
        else:
            regime = infer_text_regime(text_regime=existing)
        counts[row.get("text_regime", regime.value)] = counts.get(row.get("text_regime", regime.value), 0) + 1
        rows.append(row)
    out = pd.DataFrame(rows).reindex(columns=GOLD_CSV_COLUMNS, fill_value="")
    return out, counts


def _title_lookup(snippets_csv: Path) -> dict[str, str]:
    if not snippets_csv.exists():
        return {}
    frame = pd.read_csv(snippets_csv, usecols=["filename", "title"], dtype=str)
    return {
        str(row["filename"]): str(row["title"])
        for row in frame.drop_duplicates("filename").to_dict(orient="records")
        if str(row.get("filename", "")).strip()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-path", type=Path, default=None)
    parser.add_argument("--snippets-path", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--refresh-unknown",
        action="store_true",
        help="Re-infer only rows with text_regime=UNKNOWN (uses snippet text lookup)",
    )
    parser.add_argument("--import-after", action="store_true", help="Re-import gold.parquet after tagging")
    args = parser.parse_args()

    csv_path = args.csv_path or Path(resolve("trifecta_gold")).parent / "gold_labelling_all.csv"
    if not csv_path.exists():
        csv_path = Path(resolve("trifecta_gold_csv"))
    snippets_path = args.snippets_path or Path(resolve("food_snippets"))

    frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    tagged, counts = tag_dataframe(
        frame,
        titles=_title_lookup(snippets_path),
        overwrite=args.overwrite,
        refresh_unknown=args.refresh_unknown,
    )
    export_gold_csv(tagged.to_dict(orient="records"), output_path=csv_path)
    print(f"Tagged: {csv_path}")
    for regime, count in sorted(counts.items()):
        if count:
            print(f"  {regime}: {count}")
    if args.import_after:
        from trifecta_annotation.gold_io import import_gold_csv

        n, parquet_path, _ = import_gold_csv(input_path=csv_path, script=__file__)
        print(f"Imported {n} labelled rows → {parquet_path}")


if __name__ == "__main__":
    main()
