"""Historic Dutch frame triggers for verb-seeded KWIC discovery.

Crossbreed lexicon (manual → technique → corpus):
- hand-rolled ``FRAME_VERB_LEXICON`` for all macro-frames (CURE, INGESTION, …)
- optional ``technique_term_association.csv`` seeds (cort-voc-db) → PRESERVING
- optional ``trifecta_frame_verb_corpus.csv`` from corpus mining (see ``frame_verb_corpus``)

Manual entries win when the same normalized form maps to different frames.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import TrifectaFrame

DEFAULT_TECHNIQUE_ASSOC_PATH = Path(
    "/Users/rikhoekstra/develop/cort-voc-db/data/technique_term_association.csv",
)

# Preservation techniques from cort-voc-db → TRIFECTA macro-frame.
TECHNIQUE_TO_FRAME: dict[str, TrifectaFrame] = {
    "drying": TrifectaFrame.PRESERVING,
    "fermentation": TrifectaFrame.PRESERVING,
    "pickling": TrifectaFrame.PRESERVING,
    "salting": TrifectaFrame.PRESERVING,
    "smoking": TrifectaFrame.PRESERVING,
    "sugaring": TrifectaFrame.PRESERVING,
}

# Historic extras not yet in guideline NL LU list (pekelen, confijten, …).
FRAME_VERB_LEXICON: dict[TrifectaFrame, tuple[str, ...]] = {
    TrifectaFrame.PRESERVING: (
        "bewaren",
        "confijten",
        "konfijten",
        "inpakken",
        "legen",
        "paken",
        "pekelen",
        "stampen",
        "pruttelen",
    ),
    TrifectaFrame.CURE: (
        "heelen",
        "verheelen",
        "lenigen",
        "cureren",
        "medicineren",
    ),
    TrifectaFrame.COOKING_CREATION: (
        # ``brouwen``: food prep (bier uit koren) or industrial brouwerij discourse —
        # still a COOKING_CREATION *trigger* for mining; annotate NONE when only trade/
        # factory description with no transformation scenario (Layer 2 review).
        "brouwen",
        "malen",
        "zeven",
    ),
    TrifectaFrame.INGESTION: (
        "nuttigen",
        "smaken",
        "genieten",
        "proeven",
    ),
}

# Explicit verb-shaped technique seeds (when ``verbs_only`` is on).
_TECHNIQUE_VERB_SEEDS: frozenset[str] = frozenset(
    normalize_hist_dutch(term)
    for term in (
        "droogen",
        "drogen",
        "gisten",
        "zuren",
        "verzuren",
        "fermenteren",
        "gisting",
        "inleggen",
        "inmaken",
        "zouten",
        "pekelen",
        "roken",
        "suikeren",
    )
)


@dataclass(frozen=True)
class LexiconEntry:
    frame: TrifectaFrame
    sources: frozenset[str]
    technique: str | None = None
    canonical_lemma: str | None = None


@dataclass(frozen=True)
class VerbHit:
    verb: str
    frame: TrifectaFrame
    start: int
    end: int
    lexicon_sources: tuple[str, ...] = ()
    technique: str | None = None


def _is_verb_like(term: str) -> bool:
    """Rough filter: infinitives / clear verb forms, not noun preservation seeds."""
    norm = normalize_hist_dutch(term)
    if not norm or len(norm) < 4:
        return False
    if norm in _TECHNIQUE_VERB_SEEDS:
        return True
    if norm.startswith("ge") and len(norm) > 5:
        return False
    return len(norm) >= 5 and norm.endswith("en")


def _manual_lexicon() -> dict[str, LexiconEntry]:
    from trifecta_annotation.frame_verb_guidelines import guideline_verb_entries

    out: dict[str, LexiconEntry] = {}
    for norm, (frame, canonical) in guideline_verb_entries().items():
        out[norm] = LexiconEntry(
            frame=frame,
            sources=frozenset({"guideline"}),
            canonical_lemma=canonical,
        )
    for frame, verbs in FRAME_VERB_LEXICON.items():
        for verb in verbs:
            norm = normalize_hist_dutch(verb)
            if not norm:
                continue
            existing = out.get(norm)
            if existing is not None:
                out[norm] = LexiconEntry(
                    frame=existing.frame,
                    sources=existing.sources | {"manual"},
                    technique=existing.technique,
                    canonical_lemma=existing.canonical_lemma or norm,
                )
                continue
            out[norm] = LexiconEntry(
                frame=frame,
                sources=frozenset({"manual"}),
                canonical_lemma=norm,
            )
    return out


def load_technique_lexicon(
    path: str | Path | None = None,
    *,
    seeds_only: bool = True,
    verbs_only: bool = True,
    min_recipe_freq: int = 0,
) -> dict[str, LexiconEntry]:
    """Load cort-voc preservation technique terms as PRESERVING triggers."""
    resolved = Path(path or DEFAULT_TECHNIQUE_ASSOC_PATH).expanduser()
    if not resolved.exists():
        return {}

    frame = pd.read_csv(resolved)
    required = {"technique", "term"}
    if not required.issubset(frame.columns):
        return {}

    if "is_seed" in frame.columns:
        seed_mask = frame["is_seed"].astype(str).str.lower().isin({"true", "1", "yes"})
        if seeds_only:
            frame = frame[seed_mask]
        else:
            frame = frame[~seed_mask]
            if "recipe_freq" in frame.columns and min_recipe_freq > 0:
                frame = frame[frame["recipe_freq"].fillna(0).ge(min_recipe_freq)]

    out: dict[str, LexiconEntry] = {}
    for row in frame.itertuples(index=False):
        technique = str(getattr(row, "technique", "") or "").strip()
        term = str(getattr(row, "term", "") or "").strip()
        frame_hint = TECHNIQUE_TO_FRAME.get(technique)
        if frame_hint is None or not term:
            continue
        norm = normalize_hist_dutch(term)
        if not norm:
            continue
        if verbs_only and not _is_verb_like(term):
            continue
        recipe_freq = int(getattr(row, "recipe_freq", 0) or 0)
        if seeds_only:
            source = f"technique:{technique}"
        else:
            source = f"technique_expanded:{technique}:freq={recipe_freq}"
        existing = out.get(norm)
        if existing is None:
            out[norm] = LexiconEntry(
                frame=frame_hint,
                sources=frozenset({source}),
                technique=technique,
            )
        else:
            out[norm] = LexiconEntry(
                frame=existing.frame,
                sources=existing.sources | {source},
                technique=existing.technique or technique,
            )
    return out


def _merge_entries(
    merged: dict[str, LexiconEntry],
    additions: dict[str, LexiconEntry],
) -> dict[str, LexiconEntry]:
    for norm, entry in additions.items():
        existing = merged.get(norm)
        if existing is not None:
            merged[norm] = LexiconEntry(
                frame=existing.frame,
                sources=existing.sources | entry.sources,
                technique=existing.technique or entry.technique,
            )
            continue
        merged[norm] = entry
    return merged


def build_merged_lexicon(
    *,
    technique_assoc_path: str | Path | None = None,
    include_technique_seeds: bool = True,
    include_technique_expanded: bool = True,
    technique_verbs_only: bool = True,
    technique_min_recipe_freq: int = 5,
    corpus_lexicon_path: str | Path | None = None,
    include_corpus: bool = True,
    corpus_min_freq: int = 5,
    corpus_min_agreement: float = 0.75,
) -> dict[str, LexiconEntry]:
    """Merge manual, cort-voc technique, and optional corpus-grown triggers."""
    merged = _manual_lexicon()
    if include_technique_seeds:
        _merge_entries(
            merged,
            load_technique_lexicon(technique_assoc_path, verbs_only=technique_verbs_only),
        )
    if include_technique_expanded:
        _merge_entries(
            merged,
            load_technique_lexicon(
                technique_assoc_path,
                seeds_only=False,
                verbs_only=technique_verbs_only,
                min_recipe_freq=technique_min_recipe_freq,
            ),
        )
    if include_corpus:
        from trifecta_annotation.frame_verb_corpus import load_corpus_lexicon

        _merge_entries(
            merged,
            load_corpus_lexicon(
                corpus_lexicon_path,
                min_freq=corpus_min_freq,
                min_agreement=corpus_min_agreement,
            ),
        )
    return merged


def _compile_pattern(terms: list[str]) -> re.Pattern[str]:
    ordered = sorted(terms, key=len, reverse=True)
    return re.compile(
        r"\b(" + "|".join(re.escape(term) for term in ordered) + r")\b",
        re.IGNORECASE,
    )


class FrameVerbLexicon:
    """Merged trigger lexicon with optional reload for tests / custom paths."""

    def __init__(
        self,
        *,
        technique_assoc_path: str | Path | None = None,
        include_technique_seeds: bool = True,
        include_technique_expanded: bool = True,
        technique_verbs_only: bool = True,
        corpus_lexicon_path: str | Path | None = None,
        include_corpus: bool = True,
        corpus_min_freq: int = 5,
        corpus_min_agreement: float = 0.75,
    ) -> None:
        self._technique_assoc_path = technique_assoc_path
        self._include_technique_seeds = include_technique_seeds
        self._include_technique_expanded = include_technique_expanded
        self._technique_verbs_only = technique_verbs_only
        self._corpus_lexicon_path = corpus_lexicon_path
        self._include_corpus = include_corpus
        self._entries = build_merged_lexicon(
            technique_assoc_path=technique_assoc_path,
            include_technique_seeds=include_technique_seeds,
            include_technique_expanded=include_technique_expanded,
            technique_verbs_only=technique_verbs_only,
            corpus_lexicon_path=corpus_lexicon_path,
            include_corpus=include_corpus,
            corpus_min_freq=corpus_min_freq,
            corpus_min_agreement=corpus_min_agreement,
        )
        self._pattern = _compile_pattern(list(self._entries)) if self._entries else None

    @property
    def entries(self) -> dict[str, LexiconEntry]:
        return dict(self._entries)

    def frame_for(self, verb: str) -> TrifectaFrame | None:
        entry = self._entries.get(normalize_hist_dutch(verb))
        return entry.frame if entry else None

    def entry_for(self, verb: str) -> LexiconEntry | None:
        return self._entries.get(normalize_hist_dutch(verb))

    def find_in_text(self, text: str) -> list[VerbHit]:
        if self._pattern is None:
            return []
        hits: list[VerbHit] = []
        for match in self._pattern.finditer(text):
            surface = match.group(1)
            entry = self.entry_for(surface)
            if entry is None:
                continue
            hits.append(
                VerbHit(
                    surface,
                    entry.frame,
                    match.start(),
                    match.end(),
                    lexicon_sources=tuple(sorted(entry.sources)),
                    technique=entry.technique,
                ),
            )
        return hits

    def snippet_has_trigger(self, text: str) -> bool:
        return self._pattern.search(text) is not None if self._pattern else False

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"guideline": 0, "manual": 0, "technique": 0, "corpus": 0, "total": 0}
        for entry in self._entries.values():
            if "guideline" in entry.sources:
                counts["guideline"] += 1
            if "manual" in entry.sources:
                counts["manual"] += 1
            if any(source.startswith("technique:") for source in entry.sources):
                counts["technique"] += 1
            if any(source.startswith("corpus:") for source in entry.sources):
                counts["corpus"] += 1
        counts["total"] = len(self._entries)
        return counts


_DEFAULT_LEXICON = FrameVerbLexicon()


def get_frame_verb_lexicon(
    *,
    technique_assoc_path: str | Path | None = None,
    include_technique_seeds: bool = True,
    include_technique_expanded: bool = True,
    technique_verbs_only: bool = True,
    corpus_lexicon_path: str | Path | None = None,
    include_corpus: bool = True,
    reload: bool = False,
) -> FrameVerbLexicon:
    """Return the process-default lexicon, or build a custom one."""
    global _DEFAULT_LEXICON
    if (
        not reload
        and technique_assoc_path is None
        and corpus_lexicon_path is None
        and include_technique_seeds
        and include_technique_expanded
        and include_corpus
        and technique_verbs_only
    ):
        return _DEFAULT_LEXICON
    return FrameVerbLexicon(
        technique_assoc_path=technique_assoc_path,
        include_technique_seeds=include_technique_seeds,
        include_technique_expanded=include_technique_expanded,
        technique_verbs_only=technique_verbs_only,
        corpus_lexicon_path=corpus_lexicon_path,
        include_corpus=include_corpus,
    )


def frame_for_verb(verb: str) -> TrifectaFrame | None:
    return _DEFAULT_LEXICON.frame_for(verb)


def find_frame_verbs_in_text(text: str) -> list[VerbHit]:
    """Return frame-trigger hits in left-to-right order."""
    return _DEFAULT_LEXICON.find_in_text(text)


def snippet_has_frame_verb(text: str) -> bool:
    return _DEFAULT_LEXICON.snippet_has_trigger(text)


def lexicon_summary() -> dict[str, int]:
    return _DEFAULT_LEXICON.summary()


def term_positions(snippet: str, terms: list[str]) -> list[tuple[int, str]]:
    """Whole-word positions for *terms* in *snippet*."""
    lowered = snippet.lower()
    found: list[tuple[int, str]] = []
    seen: set[str] = set()
    for term in terms:
        norm = normalize_hist_dutch(term)
        if not norm or norm in seen or len(norm) < 3:
            continue
        match = re.search(rf"\b{re.escape(norm)}\b", lowered)
        if not match:
            match = re.search(rf"\b{re.escape(term.lower())}\b", lowered)
        if match:
            found.append((match.start(), term))
            seen.add(norm)
    found.sort(key=lambda item: item[0])
    return found


def pick_food_near_verb(
    verb_start: int,
    food_positions: list[tuple[int, str]],
) -> str | None:
    """Pick food closest to the verb; prefer tokens at/after the verb."""
    if not food_positions:
        return None
    after = [item for item in food_positions if item[0] >= verb_start]
    pool = after if after else food_positions
    return min(pool, key=lambda item: abs(item[0] - verb_start))[1]
