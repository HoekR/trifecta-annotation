"""Export PRESERVING gold candidates from recepten-preservare-analysis recipes."""

from __future__ import annotations

import random
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from trifecta_annotation.clear_frame_examples import target_centered_snippet
from trifecta_annotation.frame_verbs import FrameVerbLexicon, pick_food_near_verb, term_positions
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import KwicInput, TrifectaFrame
from trifecta_annotation.text_regime import TextRegime
from trifecta_annotation.vocabulary import resolve_thesaurus_lookup

DEFAULT_PRESERVARE_ROOT = Path(
    "~/develop/recepten-preservare-analysis",
).expanduser()

DEFAULT_RECIPE_DATASET = DEFAULT_PRESERVARE_ROOT / "source_data" / "recipe_dataset_2.csv"
DEFAULT_TECHNIQUE_ASSOC = DEFAULT_PRESERVARE_ROOT / "data" / "technique_term_association.csv"
DEFAULT_PRES_FEATURES = DEFAULT_PRESERVARE_ROOT / "data" / "pres_features.csv"

_TECHNIQUE_QUOTA_DEFAULT: dict[str, int] = {
    "salting": 2,
    "smoking": 2,
    "drying": 2,
    "pickling": 2,
    "sugaring": 1,
    "fermentation": 1,
}


@dataclass(frozen=True)
class PreservareCandidate:
    record: KwicInput
    technique: str
    discovery_verb: str
    technique_score: float
    pres_features_recipe_id: str

    @property
    def record_id(self) -> str:
        return self.record.record_id


def _parse_food_mentions(raw: str, *, lookup: dict[str, str]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,;]", str(raw or "")):
        term = part.strip()
        if not term:
            continue
        norm = normalize_hist_dutch(term)
        if norm in lookup and norm not in seen:
            terms.append(term)
            seen.add(norm)
    return terms


def _recipe_title(row: pd.Series) -> str:
    for key in ("Preprocessed_title", "Title", "title"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _recipe_text(row: pd.Series) -> str:
    for key in ("Preprocessed_content", "Content", "content"):
        value = str(row.get(key) or "").strip()
        if value:
            return re.sub(r"\s+", " ", value)
    return ""


def _recipe_id(row: pd.Series) -> str:
    for key in ("id", "ID", "recipe_id"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _recipe_date(row: pd.Series) -> str:
    for key in ("Date (yyyy-mm-dd)", "year", "date"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _kwic_window(text: str, start: int, end: int, *, radius: int = 140) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    snippet = text[left:right].strip()
    prefix = "…" if left else ""
    suffix = "…" if right < len(text) else ""
    return prefix + snippet + suffix


def load_preservation_scores(path: str | Path | None = None) -> dict[str, dict[str, float]]:
    """recipe_id -> technique -> score from pres_features.csv."""
    resolved = Path(path or DEFAULT_PRES_FEATURES).expanduser()
    if not resolved.exists():
        return {}

    frame = pd.read_csv(resolved, dtype=str, keep_default_na=False)
    if "recipe_id" not in frame.columns:
        return {}

    techniques = [c for c in frame.columns if c not in {"recipe_id", "title", "collection", "year", "period_label"}]
    out: dict[str, dict[str, float]] = {}
    for row in frame.itertuples(index=False):
        recipe_id = str(getattr(row, "recipe_id", "") or "").strip()
        if not recipe_id:
            continue
        scores: dict[str, float] = {}
        for technique in techniques:
            raw = getattr(row, technique, "")
            try:
                scores[technique] = float(raw)
            except (TypeError, ValueError):
                scores[technique] = 0.0
        out[recipe_id] = scores
    return out


def mine_preservare_candidates(
    *,
    recipe_path: str | Path | None = None,
    technique_assoc_path: str | Path | None = None,
    pres_features_path: str | Path | None = None,
    exclude_record_ids: set[str] | None = None,
    min_technique_score: float = 0.0,
    kwic_radius: int = 140,
    max_hits_per_recipe: int = 2,
) -> list[PreservareCandidate]:
    """Mine PRESERVING KWIC rows from preservare recipe dataset + technique seeds."""
    recipes_path = Path(recipe_path or DEFAULT_RECIPE_DATASET).expanduser()
    if not recipes_path.exists():
        return []

    lookup = resolve_thesaurus_lookup()
    if not lookup:
        return []

    lexicon = FrameVerbLexicon(
        technique_assoc_path=technique_assoc_path or DEFAULT_TECHNIQUE_ASSOC,
        include_technique_seeds=True,
        include_technique_expanded=False,
        include_corpus=False,
    )
    scores_by_recipe = load_preservation_scores(pres_features_path)
    blocked = exclude_record_ids or set()

    recipes = pd.read_csv(recipes_path, dtype=str, keep_default_na=False)
    found: list[PreservareCandidate] = []

    for _, row_series in recipes.iterrows():
        recipe_id = _recipe_id(row_series)
        text = _recipe_text(row_series)
        if not recipe_id or not text:
            continue

        food_terms = _parse_food_mentions(
            str(row_series.get("MENTIONS (Foods)", "")),
            lookup=lookup,
        )
        if not food_terms:
            continue

        hits = lexicon.find_in_text(text)
        if not hits:
            continue

        recipe_scores = scores_by_recipe.get(recipe_id, {})
        title = _recipe_title(row_series)
        date = _recipe_date(row_series)

        seen_keys: set[tuple[str, str, str]] = set()
        for hit in hits[:max_hits_per_recipe]:
            if hit.frame != TrifectaFrame.PRESERVING or not hit.technique:
                continue
            technique_score = recipe_scores.get(hit.technique, 0.0)
            if technique_score < min_technique_score:
                continue

            left = max(0, hit.start - kwic_radius)
            snippet = _kwic_window(text, hit.start, hit.end, radius=kwic_radius)
            verb_in_snippet = hit.start - left
            food_positions = term_positions(snippet, food_terms)
            target = pick_food_near_verb(verb_in_snippet, food_positions)
            if not target:
                target = food_terms[0]

            target_norm = normalize_hist_dutch(target)
            record_id = f"preservare_{recipe_id}__{hit.technique}__{target_norm}"
            key = (recipe_id, hit.technique, target_norm)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if record_id in blocked:
                continue

            record = KwicInput(
                record_id=record_id,
                corpus="preservare",
                target_word=target,
                context_text=snippet,
                date=date,
                title=title,
                source_path=str(recipes_path.name),
                text_regime=TextRegime.RECIPE_PRACTICE,
                discovery_verb=hit.verb,
                frame_hint=TrifectaFrame.PRESERVING.value,
                kwic_mode="preservare_technique",
                candidate_terms=food_terms,
            )
            found.append(
                PreservareCandidate(
                    record=record,
                    technique=hit.technique,
                    discovery_verb=hit.verb,
                    technique_score=technique_score,
                    pres_features_recipe_id=recipe_id,
                ),
            )

    found.sort(
        key=lambda item: (
            -item.technique_score,
            item.technique,
            item.record.record_id,
        ),
    )
    return found


def parse_technique_quotas(spec: str) -> dict[str, int]:
    if not spec.strip():
        return dict(_TECHNIQUE_QUOTA_DEFAULT)
    out: dict[str, int] = {}
    for part in spec.split(","):
        name, _, count = part.partition(":")
        out[name.strip()] = int(count.strip())
    return out


def sample_preservare_candidates(
    candidates: list[PreservareCandidate],
    *,
    limit: int = 10,
    seed: int = 7,
    technique_quotas: dict[str, int] | None = None,
    max_per_target: int = 2,
    max_per_work: int = 3,
) -> list[PreservareCandidate]:
    if not candidates:
        return []

    quotas = technique_quotas or dict(_TECHNIQUE_QUOTA_DEFAULT)
    by_technique: dict[str, list[PreservareCandidate]] = defaultdict(list)
    for item in candidates:
        by_technique[item.technique].append(item)

    rng = random.Random(seed)
    for bucket in by_technique.values():
        rng.shuffle(bucket)

    selected: list[PreservareCandidate] = []
    target_counts: dict[str, int] = defaultdict(int)
    work_counts: dict[str, int] = defaultdict(int)

    for technique, quota in quotas.items():
        bucket = by_technique.get(technique, [])
        picked = 0
        while bucket and picked < quota and len(selected) < limit:
            idx = rng.randrange(len(bucket))
            item = bucket.pop(idx)
            target_key = normalize_hist_dutch(item.record.target_word)
            work_key = (item.record.title or item.record.source_path or "unknown")[:80]
            if target_counts[target_key] >= max_per_target:
                continue
            if work_counts[work_key] >= max_per_work:
                continue
            selected.append(item)
            target_counts[target_key] += 1
            work_counts[work_key] += 1
            picked += 1

    if len(selected) < limit:
        remainder = [item for bucket in by_technique.values() for item in bucket]
        rng.shuffle(remainder)
        for item in remainder:
            if len(selected) >= limit:
                break
            target_key = normalize_hist_dutch(item.record.target_word)
            work_key = (item.record.title or item.record.source_path or "unknown")[:80]
            if target_key in {normalize_hist_dutch(s.record.target_word) for s in selected}:
                if target_counts[target_key] >= max_per_target:
                    continue
            if work_counts[work_key] >= max_per_work:
                continue
            if item in selected:
                continue
            selected.append(item)
            target_counts[target_key] += 1
            work_counts[work_key] += 1

    return selected


def preservare_summary(candidates: list[PreservareCandidate]) -> dict[str, object]:
    by_technique: dict[str, int] = defaultdict(int)
    for item in candidates:
        by_technique[item.technique] += 1
    return {
        "total": len(candidates),
        "by_technique": dict(sorted(by_technique.items())),
    }
