#!/usr/bin/env python3
"""Export manual .v LU list as reference CSV for canonical_lemma review."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from trifecta_annotation.frame_verb_guidelines import (
    GUIDELINE_USING_VERBS,
    GUIDELINE_VERB_LEXICON,
)
from trifecta_annotation.normalize import normalize_hist_dutch

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "trifecta_frame_verb_guidelines.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Export guideline verb LU reference CSV.")
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    for frame, verbs in GUIDELINE_VERB_LEXICON.items():
        for verb in verbs:
            rows.append(
                {
                    "canonical_lemma": normalize_hist_dutch(verb),
                    "frame_hint": frame.value,
                    "source": "guideline_nl_v3",
                    "notes": "manual .v LU",
                },
            )
    for verb in GUIDELINE_USING_VERBS:
        rows.append(
            {
                "canonical_lemma": normalize_hist_dutch(verb),
                "frame_hint": "USING_PROTOTYPE",
                "source": "guideline_nl_v3",
                "notes": "GEBRUIK prototype — not a macro-frame trigger",
            },
        )

    out = Path(args.output_path).expanduser().resolve()
    pd.DataFrame(rows).drop_duplicates(subset=["canonical_lemma", "frame_hint"]).sort_values(
        ["frame_hint", "canonical_lemma"],
    ).to_csv(out, index=False)
    print(out)


if __name__ == "__main__":
    main()
