"""Mine food-target collocations from KWIC snippets (PMI + optional FastText)."""

from __future__ import annotations

import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from trifecta_annotation.adapters.food_snippets import (
    _corpus_from_filename,
    load_food_snippets_long_frame,
)
from trifecta_annotation.frame_verb_corpus import (
    VERB_DENYLIST,
    _looks_food_plural,
    _token_positions,
    is_corpus_verb_candidate,
)
from trifecta_annotation.frame_verbs import FrameVerbLexicon, get_frame_verb_lexicon
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import TrifectaFrame
from trifecta_annotation.text_regime import TextRegime, infer_text_regime
from trifecta_annotation.thesaurus import filter_long_snippets_frame
from trifecta_annotation.vocabulary import resolve_thesaurus_lookup

_TOKEN_RE = re.compile(r"\b[a-zA-Zà-ÿ][a-zA-Zà-ÿ\-]*\b")

_PREP_TERMS: frozenset[str] = frozenset(
    normalize_hist_dutch(term)
    for term in (
        "in",
        "op",
        "met",
        "van",
        "tot",
        "voor",
        "door",
        "aan",
        "uit",
        "bij",
        "naar",
        "binnen",
        "over",
        "onder",
        "tegen",
        "zonder",
        "om",
        "als",
        "na",
        "tusschen",
        "tussen",
    )
)

_COLLOCATION_DENYLIST: frozenset[str] = frozenset(
    normalize_hist_dutch(term)
    for term in (
        "samen",
        "allen",
        "anderen",
        "grooten",
        "kleinen",
        "goeden",
        "ouden",
        "nieuwen",
        "meloenen",
        "appelen",
        "citroenen",
        "stoelen",
        "tranen",
        "wangen",
        "men",
        "moet",
        # Function words / generic nouns that often end in "-en" historically.
        "sullen",
        "dingen",
    )
)

SKELETON_COLUMNS: tuple[str, ...] = (
    "target_norm",
    "target_lemma",
    "collocate_norm",
    "collocate_type",
    "text_regime",
    "cooc_count",
    "target_snippet_count",
    "collocate_global_count",
    "pmi",
    "frame_hint",
    "in_frame_lexicon",
    "fasttext_sim",
    "rank_within_target",
    "example_surface",
    "notes",
)


@dataclass(frozen=True)
class CollocationHit:
    target_norm: str
    target_lemma: str
    collocate_norm: str
    collocate_type: str
    text_regime: str
    cooc_count: int
    target_snippet_count: int
    collocate_global_count: int
    pmi: float
    frame_hint: str
    in_frame_lexicon: bool
    fasttext_sim: float | None
    rank_within_target: int
    example_surface: str
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "target_norm": self.target_norm,
            "target_lemma": self.target_lemma,
            "collocate_norm": self.collocate_norm,
            "collocate_type": self.collocate_type,
            "text_regime": self.text_regime,
            "cooc_count": self.cooc_count,
            "target_snippet_count": self.target_snippet_count,
            "collocate_global_count": self.collocate_global_count,
            "pmi": round(self.pmi, 4),
            "frame_hint": self.frame_hint,
            "in_frame_lexicon": "true" if self.in_frame_lexicon else "false",
            "fasttext_sim": "" if self.fasttext_sim is None else round(self.fasttext_sim, 4),
            "rank_within_target": self.rank_within_target,
            "example_surface": self.example_surface,
            "notes": self.notes,
        }


def _target_positions(snippet: str, target_terms: list[str]) -> list[tuple[int, str]]:
    lowered = snippet.lower()
    hits: list[tuple[int, str]] = []
    seen: set[str] = set()
    for term in sorted(target_terms, key=len, reverse=True):
        norm = normalize_hist_dutch(term)
        if not norm or norm in seen:
            continue
        for match in re.finditer(rf"\b{re.escape(term.lower())}\b", lowered):
            hits.append((match.start(), norm))
            seen.add(norm)
            break
        if norm in seen and not any(item[1] == norm for item in hits):
            for match in re.finditer(rf"\b{re.escape(norm)}\b", lowered):
                hits.append((match.start(), norm))
                seen.add(norm)
                break
    hits.sort(key=lambda item: item[0])
    return hits


def _token_index(pos: int, token_positions: list[tuple[int, str, str]]) -> int | None:
    for idx, (start, _, _) in enumerate(token_positions):
        if start >= pos:
            return idx
    return len(token_positions) - 1 if token_positions else None


def collocates_near_target(
    snippet: str,
    *,
    target_norm: str,
    window_tokens: int,
    food_terms: frozenset[str],
    seed_terms: frozenset[str],
) -> list[tuple[str, str]]:
    """Return (collocate_norm, surface) within ±window_tokens of *target_norm*."""
    token_positions = _token_positions(snippet)
    if not token_positions:
        return []

    target_idxs = [
        idx
        for idx, (_, _, norm) in enumerate(token_positions)
        if norm == target_norm
    ]
    if not target_idxs:
        return []

    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for target_idx in target_idxs:
        lo = max(0, target_idx - window_tokens)
        hi = min(len(token_positions), target_idx + window_tokens + 1)
        for idx in range(lo, hi):
            if idx == target_idx:
                continue
            _, surface, norm = token_positions[idx]
            if not norm or norm == target_norm or norm in food_terms:
                continue
            if norm in seen:
                continue
            seen.add(norm)
            found.append((norm, surface))
    return found


def _is_food_token(norm: str, food_lookup: dict[str, str]) -> bool:
    food_terms = frozenset(food_lookup.keys())
    if norm in food_terms or norm in set(food_lookup.values()):
        return True
    return _looks_food_plural(norm, food_terms)


def classify_collocate(
    norm: str,
    *,
    lexicon: FrameVerbLexicon,
    food_lookup: dict[str, str],
    seed_terms: frozenset[str],
) -> str:
    food_terms = frozenset(food_lookup.keys())
    if _is_food_token(norm, food_lookup) or norm in _COLLOCATION_DENYLIST:
        return "stop"
    if lexicon.frame_for(norm) is not None:
        return "verb"
    if norm in _PREP_TERMS:
        return "prep"
    if is_corpus_verb_candidate(norm, food_terms=food_terms, seed_terms=seed_terms):
        return "verb"
    if norm in VERB_DENYLIST:
        return "stop"
    if len(norm) >= 4 and norm.endswith(("ig", "lijk", "achtig", "isch")):
        return "adj"
    return "other"


def _pmi(
    cooc: int,
    target_count: int,
    collocate_count: int,
    total: int,
    *,
    smoothing: float = 0.5,
) -> float:
    if cooc <= 0 or target_count <= 0 or collocate_count <= 0 or total <= 0:
        return 0.0
    joint = (cooc + smoothing) / (total + smoothing)
    p_target = (target_count + smoothing) / (total + smoothing)
    p_coll = (collocate_count + smoothing) / (total + smoothing)
    return math.log2(joint / (p_target * p_coll))


def _infer_row_regime(row: pd.Series) -> str:
    filename = str(row.get("filename") or "")
    title = str(row.get("title") or "") or None
    source_path = filename or None
    regime = infer_text_regime(
        corpus=_corpus_from_filename(filename),
        title=title,
        source_path=source_path,
    )
    return regime.value


def mine_collocations(
    snippets_long: pd.DataFrame,
    *,
    food_lookup: dict[str, str],
    lexicon: FrameVerbLexicon | None = None,
    window_tokens: int = 5,
    min_cooc: int = 3,
    min_pmi: float = 0.0,
    by_regime: bool = False,
    dedupe_doc_term: bool = True,
    collocate_types: frozenset[str] | None = None,
) -> list[CollocationHit]:
    """
    Count target–collocate pairs in KWIC windows and score with PMI.

    Default ``by_regime=False`` pools all snippets under ``text_regime=ALL``.
    """
    lexicon = lexicon or get_frame_verb_lexicon()
    food_terms = frozenset(food_lookup.keys())
    seed_terms = frozenset(lexicon.entries.keys())
    allowed_types = collocate_types or frozenset({"verb", "prep", "adj"})

    cooc: Counter[tuple[str, str, str, str]] = Counter()
    target_counts: Counter[tuple[str, str]] = Counter()
    collocate_global: Counter[tuple[str, str]] = Counter()
    examples: dict[tuple[str, str, str, str], str] = {}
    seen_doc_term: set[str] = set()
    total_rows = 0

    snippet_col = snippets_long["snippet"].astype(str)
    for row_idx, snippet in snippet_col.items():
        snippet = snippet.strip()
        if not snippet:
            continue

        row = snippets_long.loc[row_idx]
        matched = normalize_hist_dutch(str(row.get("matched_term") or ""))
        if not matched or matched not in food_terms:
            continue

        doc_id = str(row.get("doc_id", row_idx))
        doc_term_key = f"{doc_id}__{matched}"
        if dedupe_doc_term:
            if doc_term_key in seen_doc_term:
                continue
            seen_doc_term.add(doc_term_key)

        regime = _infer_row_regime(row) if by_regime else TextRegime.UNKNOWN.value
        regime_key = regime if by_regime else "ALL"
        total_rows += 1
        target_counts[(matched, regime_key)] += 1

        for coll_norm, surface in collocates_near_target(
            snippet,
            target_norm=matched,
            window_tokens=window_tokens,
            food_terms=food_terms,
            seed_terms=seed_terms,
        ):
            coll_type = classify_collocate(
                coll_norm,
                lexicon=lexicon,
                food_lookup=food_lookup,
                seed_terms=seed_terms,
            )
            if coll_type == "stop" or coll_type not in allowed_types:
                continue
            key = (matched, coll_norm, coll_type, regime_key)
            cooc[key] += 1
            collocate_global[(coll_norm, regime_key)] += 1
            if key not in examples:
                examples[key] = surface

    hits: list[CollocationHit] = []
    for (target_norm, coll_norm, coll_type, regime_key), count in cooc.items():
        if count < min_cooc:
            continue
        target_count = target_counts[(target_norm, regime_key)]
        coll_count = collocate_global[(coll_norm, regime_key)]
        pmi = _pmi(count, target_count, coll_count, total_rows)
        if pmi < min_pmi:
            continue
        frame = lexicon.frame_for(coll_norm)
        target_lemma = food_lookup.get(target_norm, target_norm)
        hits.append(
            CollocationHit(
                target_norm=target_norm,
                target_lemma=target_lemma,
                collocate_norm=coll_norm,
                collocate_type=coll_type,
                text_regime=regime_key,
                cooc_count=count,
                target_snippet_count=target_count,
                collocate_global_count=coll_count,
                pmi=pmi,
                frame_hint=frame.value if frame else "",
                in_frame_lexicon=frame is not None,
                fasttext_sim=None,
                rank_within_target=0,
                example_surface=examples.get((target_norm, coll_norm, coll_type, regime_key), coll_norm),
            ),
        )

    return rank_collocations(hits)


def rank_collocations(
    hits: list[CollocationHit],
    *,
    prefer_verbs: bool = True,
) -> list[CollocationHit]:
    """Assign ``rank_within_target`` and sort."""
    buckets: dict[tuple[str, str], list[CollocationHit]] = defaultdict(list)
    for hit in hits:
        buckets[(hit.target_norm, hit.text_regime)].append(hit)

    ranked: list[CollocationHit] = []
    for bucket in buckets.values():
        bucket.sort(
            key=lambda item: (
                -(item.fasttext_sim or 0.0),
                -item.pmi,
                -item.cooc_count,
                0 if prefer_verbs and item.collocate_type == "verb" else 1,
                item.collocate_norm,
            ),
        )
        for rank, item in enumerate(bucket, start=1):
            ranked.append(
                CollocationHit(
                    target_norm=item.target_norm,
                    target_lemma=item.target_lemma,
                    collocate_norm=item.collocate_norm,
                    collocate_type=item.collocate_type,
                    text_regime=item.text_regime,
                    cooc_count=item.cooc_count,
                    target_snippet_count=item.target_snippet_count,
                    collocate_global_count=item.collocate_global_count,
                    pmi=item.pmi,
                    frame_hint=item.frame_hint,
                    in_frame_lexicon=item.in_frame_lexicon,
                    fasttext_sim=item.fasttext_sim,
                    rank_within_target=rank,
                    example_surface=item.example_surface,
                    notes=item.notes,
                ),
            )

    ranked.sort(
        key=lambda item: (
            item.target_norm,
            item.text_regime,
            item.rank_within_target,
        ),
    )
    return ranked


def top_collocations_per_target(
    hits: list[CollocationHit],
    *,
    max_per_target: int = 20,
    verbs_only: bool = False,
) -> list[CollocationHit]:
    out: list[CollocationHit] = []
    buckets: dict[tuple[str, str], list[CollocationHit]] = defaultdict(list)
    for hit in hits:
        if verbs_only and hit.collocate_type != "verb":
            continue
        buckets[(hit.target_norm, hit.text_regime)].append(hit)

    for bucket in buckets.values():
        bucket.sort(key=lambda item: item.rank_within_target)
        out.extend(bucket[:max_per_target])
    out.sort(
        key=lambda item: (
            item.target_norm,
            item.text_regime,
            item.rank_within_target,
        ),
    )
    return out


def snippets_to_sentences(snippets_long: pd.DataFrame) -> list[list[str]]:
    sentences: list[list[str]] = []
    seen: set[str] = set()
    for snippet in snippets_long["snippet"].astype(str):
        text = snippet.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        tokens = [
            normalize_hist_dutch(match.group(0))
            for match in _TOKEN_RE.finditer(text)
            if normalize_hist_dutch(match.group(0))
        ]
        if tokens:
            sentences.append(tokens)
    return sentences


def train_fasttext_model(
    sentences: list[list[str]],
    *,
    vector_size: int = 100,
    window: int = 5,
    min_count: int = 5,
    epochs: int = 5,
    seed: int = 11,
):
    """Train a lightweight FastText model on KWIC snippets."""
    try:
        from gensim.models import FastText
    except ImportError as exc:
        raise ImportError(
            "FastText support requires gensim: uv sync --extra collocations",
        ) from exc

    return FastText(
        sentences=sentences,
        vector_size=vector_size,
        window=window,
        min_count=min_count,
        workers=1,
        sg=1,
        seed=seed,
        epochs=epochs,
    )


def load_fasttext_vectors(path: str | Path):
    """Load a saved ``.vec`` or ``.bin`` FastText / word2vec model."""
    try:
        from gensim.models import FastText, KeyedVectors
    except ImportError as exc:
        raise ImportError(
            "FastText support requires gensim: uv sync --extra collocations",
        ) from exc

    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise FileNotFoundError(resolved)
    if resolved.suffix == ".bin":
        return FastText.load(str(resolved))
    return KeyedVectors.load_word2vec_format(str(resolved))


def _vector_similarity(vectors, left: str, right: str) -> float | None:
    left_norm = normalize_hist_dutch(left)
    right_norm = normalize_hist_dutch(right)
    if not left_norm or not right_norm:
        return None
    wv = getattr(vectors, "wv", vectors)
    if left_norm not in wv.key_to_index or right_norm not in wv.key_to_index:
        return None
    return float(wv.similarity(left_norm, right_norm))


def frame_seed_terms(frame: TrifectaFrame) -> list[str]:
    from trifecta_annotation.frame_verb_guidelines import GUIDELINE_VERB_LEXICON

    seeds = list(GUIDELINE_VERB_LEXICON.get(frame, ()))
    if frame == TrifectaFrame.PRESERVING:
        seeds.extend(("pekelen", "bewaren", "confijten"))
    if frame == TrifectaFrame.INGESTION:
        seeds.extend(("nuttigen", "proeven", "smaken"))
    return [normalize_hist_dutch(term) for term in seeds if normalize_hist_dutch(term)]


def apply_fasttext_scores(
    hits: list[CollocationHit],
    model,
    *,
    use_frame_seeds: bool = True,
) -> list[CollocationHit]:
    """Fill ``fasttext_sim`` using collocate↔target or collocate↔frame-seed similarity."""
    wv = getattr(model, "wv", model)
    updated: list[CollocationHit] = []
    for hit in hits:
        sim = _vector_similarity(wv, hit.target_norm, hit.collocate_norm)
        if use_frame_seeds and hit.frame_hint:
            try:
                frame = TrifectaFrame(hit.frame_hint)
            except ValueError:
                frame = None
            if frame is not None:
                seed_sims = [
                    s
                    for seed in frame_seed_terms(frame)
                    if (s := _vector_similarity(wv, hit.collocate_norm, seed)) is not None
                ]
                if seed_sims:
                    seed_sim = max(seed_sims)
                    sim = seed_sim if sim is None else max(sim, seed_sim)
        updated.append(
            CollocationHit(
                target_norm=hit.target_norm,
                target_lemma=hit.target_lemma,
                collocate_norm=hit.collocate_norm,
                collocate_type=hit.collocate_type,
                text_regime=hit.text_regime,
                cooc_count=hit.cooc_count,
                target_snippet_count=hit.target_snippet_count,
                collocate_global_count=hit.collocate_global_count,
                pmi=hit.pmi,
                frame_hint=hit.frame_hint,
                in_frame_lexicon=hit.in_frame_lexicon,
                fasttext_sim=sim,
                rank_within_target=hit.rank_within_target,
                example_surface=hit.example_surface,
                notes=hit.notes,
            ),
        )
    return rank_collocations(updated)


def collect_collocation_skeleton(
    *,
    path: str | Path | None = None,
    logical_name: str = "food_snippets_long",
    thesaurus_path: str | Path | None = None,
    thesaurus_filter: bool = True,
    targets: set[str] | None = None,
    limit: int | None = None,
    window_tokens: int = 5,
    min_cooc: int = 3,
    min_pmi: float = 0.0,
    by_regime: bool = False,
    max_per_target: int = 20,
    verbs_only: bool = False,
    fasttext_model_path: str | Path | None = None,
    train_fasttext: bool = False,
    fasttext_train_limit: int = 40_000,
    fasttext_epochs: int = 5,
    seed: int = 11,
) -> list[CollocationHit]:
    """End-to-end skeleton from manifest-backed ``food_snippets_long``."""
    frame = load_food_snippets_long_frame(logical_name=logical_name, path=path)
    if thesaurus_filter:
        lookup = resolve_thesaurus_lookup(thesaurus_path=thesaurus_path)
        frame = filter_long_snippets_frame(frame, lookup)
    else:
        lookup = resolve_thesaurus_lookup(thesaurus_path=thesaurus_path)

    if targets:
        target_norms = {normalize_hist_dutch(term) for term in targets}
        frame = frame[
            frame["matched_term"].astype(str).map(normalize_hist_dutch).isin(target_norms)
        ]
    if limit is not None:
        frame = frame.head(limit)

    hits = mine_collocations(
        frame,
        food_lookup=lookup,
        window_tokens=window_tokens,
        min_cooc=min_cooc,
        min_pmi=min_pmi,
        by_regime=by_regime,
    )
    hits = top_collocations_per_target(
        hits,
        max_per_target=max_per_target,
        verbs_only=verbs_only,
    )

    model = None
    if fasttext_model_path:
        model = load_fasttext_vectors(fasttext_model_path)
    elif train_fasttext:
        sentences = snippets_to_sentences(frame)
        if len(sentences) > fasttext_train_limit:
            rng = random.Random(seed)
            sentences = rng.sample(sentences, fasttext_train_limit)
        model = train_fasttext_model(sentences, epochs=fasttext_epochs, seed=seed)

    if model is not None:
        hits = apply_fasttext_scores(hits, model)

    return hits


def skeleton_summary(hits: list[CollocationHit]) -> dict[str, object]:
    targets = {hit.target_norm for hit in hits}
    verbs = sum(1 for hit in hits if hit.collocate_type == "verb")
    in_lex = sum(1 for hit in hits if hit.in_frame_lexicon)
    return {
        "rows": len(hits),
        "targets": len(targets),
        "verb_collocations": verbs,
        "in_frame_lexicon": in_lex,
        "regimes": sorted({hit.text_regime for hit in hits}),
    }
