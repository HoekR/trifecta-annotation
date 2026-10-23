"""Grow frame verbs from historic recipe bracket glosses (``sieden [koken]``)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from trifecta_annotation.frame_verb_corpus import CorpusCandidate
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import TrifectaFrame

DEFAULT_RECIPE_DATASET_PATH = Path(
    "/Users/rikhoekstra/develop/recepten-preservare-analysis/source_data/recipe_dataset_2.csv",
)

DEFAULT_RECIPE_TEXT_COLUMNS: tuple[str, ...] = (
    "Content",
    "Title",
    "Preprocessed_content",
    "Recipe",
)

_GLOSS_PAIR_RE = re.compile(r"(\w[\w\-]*)\s*\[([^\]]+)\]")

_GLOSS_WORD_MAP: dict[str, TrifectaFrame] = {
    "koken": TrifectaFrame.COOKING_CREATION,
    "sieden": TrifectaFrame.COOKING_CREATION,
    "bakken": TrifectaFrame.COOKING_CREATION,
    "braden": TrifectaFrame.COOKING_CREATION,
    "stoven": TrifectaFrame.COOKING_CREATION,
    "roosteren": TrifectaFrame.COOKING_CREATION,
    "bereiden": TrifectaFrame.COOKING_CREATION,
    "mengen": TrifectaFrame.COOKING_CREATION,
    "stampen": TrifectaFrame.COOKING_CREATION,
    "droogen": TrifectaFrame.PRESERVING,
    "zouten": TrifectaFrame.PRESERVING,
    "pekelen": TrifectaFrame.PRESERVING,
    "roken": TrifectaFrame.PRESERVING,
    "bewaren": TrifectaFrame.PRESERVING,
    "eten": TrifectaFrame.INGESTION,
    "eet": TrifectaFrame.INGESTION,
    "drinken": TrifectaFrame.INGESTION,
    "genezen": TrifectaFrame.CURE,
    "heelen": TrifectaFrame.CURE,
}

# Modern gloss keywords → macro-frame (checked on full gloss phrase).
_GLOSS_FRAME_RULES: tuple[tuple[tuple[str, ...], TrifectaFrame], ...] = (
    (("droog", "zout", "pek", "rook", "bewaar", "inleg", "inmak", "confij", "conserve"), TrifectaFrame.PRESERVING),
    (("genees", "heel", "medic", "cur", "verzacht", "lenig"), TrifectaFrame.CURE),
    (("eet", "drink", "nuttig", "proef", "smak", "verteer", "slik"), TrifectaFrame.INGESTION),
    (
        ("koken", "sieden", "bakken", "braden", "stoven", "smoren", "bereiden", "roosteren", "mengen", "stampen", "zeef", "kneed", "klop", "binden", "pruttelen"),
        TrifectaFrame.COOKING_CREATION,
    ),
)


def gloss_to_frame(gloss: str) -> TrifectaFrame | None:
    text = normalize_hist_dutch(gloss)
    if not text:
        return None
    head = text.split()[0]
    if head in _GLOSS_WORD_MAP:
        return _GLOSS_WORD_MAP[head]
    for keywords, frame in _GLOSS_FRAME_RULES:
        if any(keyword in text for keyword in keywords):
            return frame
    return None


def extract_gloss_pairs(text: str) -> list[tuple[str, str]]:
    if not text or not isinstance(text, str):
        return []
    pairs: list[tuple[str, str]] = []
    for historic, gloss in _GLOSS_PAIR_RE.findall(text):
        historic_norm = normalize_hist_dutch(historic)
        if historic_norm and len(historic_norm) >= 4:
            pairs.append((historic_norm, gloss.strip()))
    return pairs


def mine_recipe_gloss_verbs(
    recipes: pd.DataFrame,
    *,
    text_columns: tuple[str, ...] = DEFAULT_RECIPE_TEXT_COLUMNS,
) -> list[CorpusCandidate]:
    """Historic cooking/preservation verbs from annotator bracket glosses in recipe text."""
    from trifecta_annotation.frame_verbs import _is_verb_like

    def _keep_historic(norm: str) -> bool:
        return norm in _GLOSS_WORD_MAP or _is_verb_like(norm)

    stats: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "example": "",
            "frame_votes": Counter(),
            "recipe_ids": set(),
            "gloss_examples": Counter(),
        },
    )

    recipe_id_col = "recipe_id" if "recipe_id" in recipes.columns else None
    for row_idx, row in recipes.iterrows():
        recipe_id = str(row[recipe_id_col]) if recipe_id_col else str(row_idx)
        for column in text_columns:
            if column not in recipes.columns:
                continue
            for historic, gloss in extract_gloss_pairs(str(row.get(column, ""))):
                if not _keep_historic(historic):
                    continue
                frame = gloss_to_frame(gloss)
                if frame is None:
                    continue
                bucket = stats[historic]
                if not bucket["example"]:
                    bucket["example"] = historic
                bucket["recipe_ids"].add(recipe_id)
                bucket["frame_votes"][frame] += 1
                bucket["gloss_examples"][gloss[:40]] += 1

    candidates: list[CorpusCandidate] = []
    for norm, bucket in stats.items():
        votes: Counter = bucket["frame_votes"]
        if not votes:
            continue
        frame, top = votes.most_common(1)[0]
        agreement = top / sum(votes.values())
        top_gloss = bucket["gloss_examples"].most_common(1)[0][0]
        candidates.append(
            CorpusCandidate(
                term_norm=norm,
                term_example=str(bucket["example"]),
                frame=frame,
                snippet_freq=len(bucket["recipe_ids"]),
                anchor_agreement=round(agreement, 3),
                anchor_frames=f"gloss:{top_gloss}",
            ),
        )

    candidates.sort(key=lambda item: (-item.snippet_freq, -item.anchor_agreement, item.term_norm))
    return candidates


def load_recipe_dataset(path: str | Path | None = None) -> pd.DataFrame:
    resolved = Path(path or DEFAULT_RECIPE_DATASET_PATH).expanduser()
    return pd.read_csv(resolved)
