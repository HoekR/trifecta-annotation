#!/usr/bin/env python3
"""Export comprehensive statistics report for 20th-century cookbooks (LDK2025)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from data_io import resolve


def generate_stats_markdown(df: pd.DataFrame) -> str:
    lines: list[str] = [
        "# 20th-Century Cookbook Corpus Statistics (1910–1940)",
        "",
        f"- **Total annotated recipes:** {len(df):,}",
        f"- **Corpus source:** `ldk2025_cookbooks` (`cookbook_1910.txt`, `1912`, `1925`, `1940`)",
        f"- **Analysis table:** `ldk2025_analysis` (parquet)",
        "",
        "---",
        "",
        "## 1. Timeline & Volume Breakdown",
        "",
        "| Year / Date | Recipes | Unique Targets | COOKING_CREATION | PRESERVING | CURE | NONE | Unassigned / Dropped |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for date, group in df.groupby("date"):
        total = len(group)
        n_targets = group["target_word"].nunique()
        n_cooking = (group["selected_frame"] == "COOKING_CREATION").sum()
        n_pres = (group["selected_frame"] == "PRESERVING").sum()
        n_cure = (group["selected_frame"] == "CURE").sum()
        n_none = (group["selected_frame"] == "NONE").sum()
        n_unassigned = total - (n_cooking + n_pres + n_cure + n_none)
        lines.append(
            f"| {date} | {total:,} | {n_targets:,} | {n_cooking:,} ({n_cooking/total:.1%}) | {n_pres} | {n_cure} | {n_none} | {n_unassigned} |"
        )

    # Totals
    total_all = len(df)
    n_targets_all = df["target_word"].nunique()
    n_cooking_all = (df["selected_frame"] == "COOKING_CREATION").sum()
    n_pres_all = (df["selected_frame"] == "PRESERVING").sum()
    n_cure_all = (df["selected_frame"] == "CURE").sum()
    n_none_all = (df["selected_frame"] == "NONE").sum()
    n_unassigned_all = total_all - (n_cooking_all + n_pres_all + n_cure_all + n_none_all)
    lines.append(
        f"| **Total** | **{total_all:,}** | **{n_targets_all:,}** | **{n_cooking_all:,} ({n_cooking_all/total_all:.1%})** | **{n_pres_all}** | **{n_cure_all}** | **{n_none_all}** | **{n_unassigned_all}** |"
    )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Top 25 Food Ingredients & Dominant Preparation Triggers",
            "",
            "| Ingredient (`target_word`) | Count | Dominant Governing Verbs (`lexical_unit`) | Top Methods (`COOKING_CREATION_Method`) |",
            "|---|---:|---|---|",
        ]
    )

    top_targets = df["target_word"].value_counts().head(25).index
    for target in top_targets:
        sub = df[df["target_word"] == target]
        top_verbs = sub["lexical_unit"].str.lower().value_counts().head(3).index.tolist()
        top_methods = (
            sub[sub["COOKING_CREATION_Method"] != ""]["COOKING_CREATION_Method"]
            .str.lower()
            .value_counts()
            .head(2)
            .index.tolist()
        )
        verbs_str = ", ".join(top_verbs)
        methods_str = ", ".join(top_methods[:2])
        lines.append(f"| {target} | {len(sub):,} | {verbs_str} | {methods_str} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 3. Step C Qualia Role Fill Rates",
            "",
            "| Qualia Role Field | Frame | Filled Count | Coverage |",
            "|---|---|---:|---:|",
        ]
    )

    qualia_fields = [
        ("COOKING_CREATION_Method", "COOKING_CREATION"),
        ("COOKING_CREATION_Process", "COOKING_CREATION"),
        ("COOKING_CREATION_Food_Product", "COOKING_CREATION"),
        ("PR_Technique", "PRESERVING"),
        ("PR_Medium", "PRESERVING"),
        ("PR_Food_Patient", "PRESERVING"),
        ("CURE_Affliction", "CURE"),
        ("CURE_Food_Treatment", "CURE"),
        ("INGESTION_Context", "INGESTION"),
        ("INGESTION_Ingestor", "INGESTION"),
        ("INGESTION_Manner", "INGESTION"),
        ("INGESTION_Food_Patient", "INGESTION"),
        ("INGESTION_Purpose", "INGESTION"),
    ]

    for col, frame in qualia_fields:
        non_empty = (df[col].astype(str).str.strip() != "").sum()
        frame_total = (df["selected_frame"] == frame).sum() if frame != "INGESTION" else total_all
        rate = non_empty / total_all
        lines.append(f"| `{col}` | {frame} | {non_empty:,} | {rate:.1%} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Top 20 Extracted Food Products (`COOKING_CREATION_Food_Product`)",
            "",
            "| Resulting Dish / Food Product | Count |",
            "|---|---:|",
        ]
    )

    products = (
        df[df["COOKING_CREATION_Food_Product"] != ""]["COOKING_CREATION_Food_Product"]
        .value_counts()
        .head(20)
    )
    for prod, cnt in products.items():
        lines.append(f"| {prod} | {cnt:,} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## 5. Preservation Practices (`PRESERVING`)",
            "",
            "| Technique (`PR_Technique`) | Medium (`PR_Medium`) | Preserved Food (`PR_Food_Patient`) | Trigger Verb | Date |",
            "|---|---|---|---|---|",
        ]
    )

    pres_df = df[df["selected_frame"] == "PRESERVING"]
    for _, row in pres_df.iterrows():
        lines.append(
            f"| {row['PR_Technique']} | {row['PR_Medium']} | {row['PR_Food_Patient']} | {row['lexical_unit']} | {row['date']} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-path", type=Path, default=None)
    parser.add_argument(
        "--output-doc",
        type=Path,
        default=Path("docs/LDK2025_COOKBOOK_STATS.md"),
    )
    args = parser.parse_args()

    input_path = args.input_path or Path(resolve("ldk2025_analysis"))
    df = pd.read_parquet(input_path)

    md = generate_stats_markdown(df)
    args.output_doc.parent.mkdir(parents=True, exist_ok=True)
    args.output_doc.write_text(md, encoding="utf-8")
    print(f"Wrote statistics report to {args.output_doc}")


if __name__ == "__main__":
    main()
