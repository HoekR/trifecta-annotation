"""Bilingual glossary for high-frequency thesaurus pref_labels (reviewer-facing)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field

from trifecta_annotation.llm import structured_completion
from trifecta_annotation.thesaurus import snippet_term_frequencies

GLOSSARY_COLUMNS = [
    "pref_label",
    "pref_label_en",
    "gloss_en",
    "semantic_type",
    "snippet_freq",
    "example_aliases",
    "reviewed",
    "review_notes",
]

GLOSSARY_OPTIONAL_COLUMNS = ("food_type", "keep")


def read_glossary_csv(path: str | Path) -> pd.DataFrame:
    """Load reviewed glossary; tolerates literal ``\\t`` from Edit CSV exports."""
    text = Path(path).read_text(encoding="utf-8")
    first = text.splitlines()[0] if text else ""
    if "\\t" in first and "\t" not in first:
        text = text.replace("\\t", "\t")
    sep = "\t" if "\t" in (text.splitlines()[0] if text else "") else ","
    return pd.read_csv(pd.io.common.StringIO(text), sep=sep)


def glossary_en_lookup(glossary: pd.DataFrame) -> dict[str, str]:
    """Map Dutch pref_label or alias token → English pref_label."""
    lookup: dict[str, str] = {}
    for _, row in glossary.iterrows():
        en = str(row.get("pref_label_en") or "").strip()
        if not en:
            continue
        nl = str(row.get("pref_label") or "").strip().lower()
        if nl:
            lookup[nl] = en
        aliases = str(row.get("example_aliases") or "")
        for part in aliases.split(","):
            alias = part.strip().strip('"').lower()
            if alias:
                lookup[alias] = en
    return lookup


def english_hint_for_term(term: str, lookup: dict[str, str]) -> str:
    key = (term or "").strip().lower()
    return lookup.get(key, "")


class GlossaryTranslation(BaseModel):
    pref_label_nl: str = Field(description="Dutch pref_label, unchanged from input.")
    pref_label_en: str = Field(description="Short English equivalent (1–4 words).")
    gloss_en: str = Field(
        description="Brief gloss for annotators (5–15 words); historic Dutch food context.",
    )


class GlossaryTranslationBatch(BaseModel):
    entries: list[GlossaryTranslation]


def build_glossary_candidates(
    thesaurus: pd.DataFrame,
    *,
    snippets: pd.DataFrame | None = None,
    limit: int = 100,
    kept_only: bool = True,
) -> pd.DataFrame:
    """Rank pref_labels by snippet frequency; return top *limit* for translation."""
    frame = thesaurus.copy()
    if kept_only and "keep_for_trifecta" in frame.columns:
        frame = frame[frame["keep_for_trifecta"].eq("yes")]

    if "snippet_freq" not in frame.columns:
        freq = snippet_term_frequencies(snippets)
        frame["snippet_freq"] = frame["alias_norm"].map(freq).fillna(0).astype(int)
    else:
        frame["snippet_freq"] = frame["snippet_freq"].fillna(0).astype(int)

    frame = frame[frame["snippet_freq"].gt(0)]
    if frame.empty:
        return pd.DataFrame(columns=GLOSSARY_COLUMNS)

    grouped = (
        frame.groupby("pref_label", sort=False)
        .agg(
            snippet_freq=("snippet_freq", "max"),
            semantic_type=("semantic_type", "first"),
            example_aliases=(
                "alias_norm",
                lambda values: ", ".join(
                    sorted(
                        {str(v) for v in values if str(v).strip()},
                        key=str.lower,
                    )[:5],
                ),
            ),
        )
        .reset_index()
        .sort_values(["snippet_freq", "pref_label"], ascending=[False, True])
        .head(limit)
        .reset_index(drop=True)
    )
    grouped["pref_label_en"] = ""
    grouped["gloss_en"] = ""
    grouped["reviewed"] = ""
    grouped["review_notes"] = ""
    return grouped[GLOSSARY_COLUMNS]


def translate_glossary_candidates(
    candidates: pd.DataFrame,
    *,
    batch_size: int = 20,
    model: str | None = None,
    base_url: str | None = None,
    backend: Literal["llm", "none"] = "llm",
) -> pd.DataFrame:
    """Fill pref_label_en and gloss_en; leaves review columns empty."""
    if candidates.empty or backend == "none":
        return candidates

    out = candidates.copy()
    system_prompt = (
        "You translate historic Dutch food ontology labels for English-speaking TRIFECTA "
        "annotators. Use culinary terminology appropriate to early modern recipes "
        "(16th–19th c.). Keep pref_label_en short. gloss_en explains the Dutch term in "
        "plain English (include archaic spellings when helpful, e.g. sout = salt). "
        "Do not translate geographic or non-food noise terms literally if they are "
        "place names or function words."
    )

    for start in range(0, len(out), batch_size):
        batch = out.iloc[start : start + batch_size]
        lines = []
        for _, row in batch.iterrows():
            sem = row.get("semantic_type") or ""
            aliases = row.get("example_aliases") or ""
            lines.append(
                f"- pref_label: {row['pref_label']!r}; semantic_type: {sem!r}; "
                f"example_aliases: {aliases!r}; snippet_freq: {row['snippet_freq']}",
            )
        user_prompt = "Translate each pref_label:\n" + "\n".join(lines)
        result = structured_completion(
            GlossaryTranslationBatch,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            base_url=base_url,
        )
        by_nl = {entry.pref_label_nl.strip(): entry for entry in result.entries}
        for idx in batch.index:
            nl = str(out.at[idx, "pref_label"]).strip()
            entry = by_nl.get(nl)
            if entry is None:
                continue
            out.at[idx, "pref_label_en"] = entry.pref_label_en.strip()
            out.at[idx, "gloss_en"] = entry.gloss_en.strip()
    return out
