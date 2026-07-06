"""Tests for corpus overview export."""

from pathlib import Path

import pandas as pd

from trifecta_annotation.corpus_overview import build_corpus_overview, overview_summary
from trifecta_annotation.text_regime import TextRegime


def test_build_corpus_overview(tmp_path: Path) -> None:
    snippets = tmp_path / "snippets.csv"
    pd.DataFrame(
        [
            {
                "filename": "recepten.txt",
                "title": "De volmaakte Hollandsche keuken-meid",
                "snippet": "kook de boter",
                "doc_id": "a__ch1",
            },
            {
                "filename": "recepten.txt",
                "title": "De volmaakte Hollandsche keuken-meid",
                "snippet": "bak het brood",
                "doc_id": "a__ch2",
            },
            {
                "filename": "pharm.txt",
                "title": "Pharmacopoea Amstelredamensis",
                "snippet": "genees met honing",
                "doc_id": "b__ch1",
            },
        ],
    ).to_csv(snippets, index=False)

    gold = tmp_path / "gold.csv"
    pd.DataFrame(
        [
            {
                "record_id": "1",
                "source_path": "recepten.txt",
                "labelled": "true",
            },
        ],
    ).to_csv(gold, index=False)

    frame = build_corpus_overview(snippets_path=snippets, gold_csv_path=gold)
    assert len(frame) == 2
    assert frame.loc[frame["filename"] == "recepten.txt", "snippet_rows"].iloc[0] == 2
    assert frame.loc[frame["filename"] == "recepten.txt", "gold_rows"].iloc[0] == 1
    assert (
        frame.loc[frame["filename"] == "recepten.txt", "text_regime"].iloc[0]
        == TextRegime.RECIPE_PRACTICE.value
    )
    summary = overview_summary(frame)
    assert summary["works"] == 2
    assert summary["works_in_gold"] == 1
