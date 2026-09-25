"""Load food vocabulary and merged thesaurus lookups."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from data_io import resolve
from data_io.manifest import DatasetNotFoundError, TierUnavailableError

from trifecta_annotation.thesaurus import alt_label_index as thesaurus_alt_index


def load_food_terms() -> pd.DataFrame:
    """Load the TRIFECTA food ontology table."""
    fallback_paths = (
        Path("/Volumes/Extreme SSD/scratch/reference/Food_terms.csv"),
        Path("/Volumes/2tb disk/reference/Food_terms.csv"),
        Path("/Users/rikhoekstra/Downloads/recepten_preservare/Food_terms.csv"),
        Path(
            "/Users/rikhoekstra/develop/recepten-preservare-analysis/source_data/Food_terms.csv",
        ),
    )
    try:
        path = resolve("food_terms")
        if path.is_file():
            return pd.read_csv(path)
    except (DatasetNotFoundError, TierUnavailableError, KeyError, FileNotFoundError, OSError):
        pass
    for fallback_path in fallback_paths:
        if fallback_path.exists():
            return pd.read_csv(fallback_path)
    raise FileNotFoundError(
        "Food_terms.csv not found — copy to scratch/reference/Food_terms.csv "
        "or set [datasets.food_terms] in data_manifest.toml",
    )


def alt_label_index(df: pd.DataFrame) -> dict[str, str]:
    """Map variant spellings (lowercase) to canonical Pref_label from Food_terms."""
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


def load_thesaurus(path: str | Path | None = None) -> pd.DataFrame:
    """Load merged thesaurus CSV when built via scripts/build_trifecta_thesaurus.py."""
    resolved = Path(path).expanduser().resolve() if path else resolve("trifecta_thesaurus")
    return pd.read_csv(resolved)


def alt_label_index_from_thesaurus(
    thesaurus: pd.DataFrame,
    *,
    kept_only: bool = True,
) -> dict[str, str]:
    """Prefer merged thesaurus lookup over raw Food_terms rows."""
    return thesaurus_alt_index(thesaurus, kept_only=kept_only)


def resolve_thesaurus_lookup(
    *,
    thesaurus_path: str | Path | None = None,
    kept_only: bool = True,
    fallback_food_terms: bool = True,
) -> dict[str, str]:
    """Load kept thesaurus aliases; fall back to Food_terms when thesaurus is missing."""
    if thesaurus_path is not None:
        path = Path(thesaurus_path).expanduser()
        if path.exists():
            return alt_label_index_from_thesaurus(load_thesaurus(path), kept_only=kept_only)

    try:
        return alt_label_index_from_thesaurus(load_thesaurus(), kept_only=kept_only)
    except (DatasetNotFoundError, TierUnavailableError, KeyError, FileNotFoundError):
        pass

    if fallback_food_terms:
        try:
            return alt_label_index(load_food_terms())
        except (DatasetNotFoundError, TierUnavailableError, KeyError, FileNotFoundError, OSError):
            for food_path in (
                Path("/Volumes/Extreme SSD/scratch/reference/Food_terms.csv"),
                Path("/Volumes/2tb disk/reference/Food_terms.csv"),
                Path("/Users/rikhoekstra/Downloads/recepten_preservare/Food_terms.csv"),
                Path(
                    "/Users/rikhoekstra/develop/recepten-preservare-analysis/source_data/Food_terms.csv",
                ),
            ):
                if food_path.exists():
                    return alt_label_index(pd.read_csv(food_path))
    return {}
