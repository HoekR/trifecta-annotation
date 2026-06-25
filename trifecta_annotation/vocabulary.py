"""Load food vocabulary from manifest-registered Food_terms.csv."""

from __future__ import annotations

import pandas as pd
from data_io import resolve


def load_food_terms() -> pd.DataFrame:
    """Load the TRIFECTA food ontology table."""
    return pd.read_csv(resolve("food_terms"))


def alt_label_index(df: pd.DataFrame) -> dict[str, str]:
    """Map variant spellings (lowercase) to canonical Pref_label."""
    index: dict[str, str] = {}
    for _, row in df.iterrows():
        canonical = str(row["Pref_label"]).strip()
        if not canonical or canonical == "nan":
            continue
        index[canonical.lower()] = canonical
        alt = row.get("Alt_label")
        if pd.isna(alt):
            continue
        for variant in str(alt).split(","):
            variant = variant.strip().lower()
            if variant:
                index[variant] = canonical
    return index
