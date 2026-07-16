"""Mine high-confidence COOKING_CREATION / INGESTION examples from food snippets.

Uses guideline frame verbs + food proximity + regime fit. Intended for silver
augmentation, few-shot pools, or pre-filled gold batches — not auto-merge.
"""

from __future__ import annotations

import random
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from trifecta_annotation.adapters.food_snippets import load_food_snippets_frame
from trifecta_annotation.frame_verbs import (
    find_frame_verbs_in_text,
    pick_food_near_verb,
    term_positions,
)
from trifecta_annotation.homonym_context import (
    HomonymAssessment,
    assess_homonym_context,
    homonym_blocks_clear_example,
)
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import KwicInput, TrifectaFrame
from trifecta_annotation.text_regime import TextRegime, infer_text_regime
from trifecta_annotation.verb_kwic import iter_verb_kwic_candidates
from trifecta_annotation.vocabulary import resolve_thesaurus_lookup

PREFERRED_REGIMES: dict[TrifectaFrame, frozenset[TextRegime]] = {
    TrifectaFrame.COOKING_CREATION: frozenset(
        {
            TextRegime.RECIPE_PRACTICE,
            TextRegime.MEDICAL,
            TextRegime.SCIENTIFIC,
        },
    ),
    TrifectaFrame.INGESTION: frozenset(
        {
            TextRegime.LITERARY,
            TextRegime.TRAVEL,
            TextRegime.ADMIN_TRADE,
            TextRegime.RECIPE_PRACTICE,
        },
    ),
}

CORE_VERBS: dict[TrifectaFrame, frozenset[str]] = {
    TrifectaFrame.COOKING_CREATION: frozenset(
        normalize_hist_dutch(v)
        for v in (
            "koken",
            "sieden",
            "bakken",
            "braden",
            "mengen",
            "bereiden",
            "stoven",
            "smoren",
            "stampen",
            "kloppen",
        )
    ),
    TrifectaFrame.INGESTION: frozenset(
        normalize_hist_dutch(v)
        for v in (
            "eten",
            "drinken",
            "smaken",
            "proeven",
            "nuttigen",
            "genieten",
        )
    ),
}

CONFLICT_FRAMES: dict[TrifectaFrame, frozenset[TrifectaFrame]] = {
    TrifectaFrame.COOKING_CREATION: frozenset({TrifectaFrame.CURE}),
    TrifectaFrame.INGESTION: frozenset(
        {TrifectaFrame.CURE, TrifectaFrame.COOKING_CREATION},
    ),
}

DEFAULT_NEAR_WINDOW = 80
DEFAULT_CONFLICT_WINDOW = 120


@dataclass(frozen=True)
class ClearFrameCandidate:
    record: KwicInput
    suggested_frame: TrifectaFrame
    discovery_verb: str
    verb_distance: int
    confidence_score: int
    confidence_tier: str
    reasons: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    homonym: HomonymAssessment | None = None


def _infer_regime(record: KwicInput) -> TextRegime:
    if record.text_regime is not None:
        return record.text_regime
    return infer_text_regime(
        corpus=record.corpus,
        title=record.title,
        source_path=record.source_path,
    )


def _hits_in_window(
    hits: list,
    *,
    center: int,
    window: int,
) -> list:
    return [hit for hit in hits if abs(hit.start - center) <= window]


def score_snippet_for_frame(
    snippet: str,
    food_terms: list[str],
    target_frame: TrifectaFrame,
    *,
    regime: TextRegime,
    near_window: int = DEFAULT_NEAR_WINDOW,
    conflict_window: int = DEFAULT_CONFLICT_WINDOW,
    guideline_only: bool = True,
    require_homonym_clear: bool = False,
) -> ClearFrameCandidate | None:
    """Score one snippet for a target frame; return None if not clear enough."""
    hits = find_frame_verbs_in_text(snippet)
    if not hits:
        return None

    food_positions = term_positions(snippet, food_terms)
    if not food_positions:
        return None

    frame_hits = [hit for hit in hits if hit.frame == target_frame]
    if not frame_hits:
        return None

    best: ClearFrameCandidate | None = None
    for hit in frame_hits:
        if guideline_only and "guideline" not in hit.lexicon_sources:
            continue

        verb_norm = normalize_hist_dutch(hit.verb)
        food_target = pick_food_near_verb(hit.start, food_positions)
        if food_target is None:
            continue

        food_pos = next(pos for pos, term in food_positions if term == food_target)
        verb_distance = abs(food_pos - hit.start)
        if verb_distance > near_window:
            continue

        nearby = _hits_in_window(hits, center=hit.start, window=conflict_window)
        conflicts: list[str] = []
        for other in nearby:
            if other.frame == target_frame:
                continue
            if other.frame in CONFLICT_FRAMES.get(target_frame, frozenset()):
                conflicts.append(f"{other.verb}:{other.frame.value}")

        score = 0
        reasons: list[str] = []

        score += 4
        reasons.append("guideline_verb")

        if verb_distance <= 40:
            score += 2
            reasons.append("food_near_verb")
        elif verb_distance <= near_window:
            score += 1
            reasons.append("food_in_window")

        if regime in PREFERRED_REGIMES.get(target_frame, frozenset()):
            score += 2
            reasons.append(f"regime_{regime.value}")
        elif regime == TextRegime.UNKNOWN:
            score -= 1
            reasons.append("regime_UNKNOWN")
        else:
            score -= 2
            reasons.append(f"regime_mismatch_{regime.value}")

        if verb_norm in CORE_VERBS.get(target_frame, frozenset()):
            score += 2
            reasons.append("core_verb")

        if conflicts:
            score -= 4 * len(conflicts)
            reasons.append("conflicting_verbs")

        homonym = assess_homonym_context(
            food_target,
            snippet,
            suggested_frame=target_frame,
            discovery_verb=hit.verb,
        )
        if homonym.risk == "high":
            score -= 6
            reasons.append("homonym_high")
        elif homonym.risk == "medium" and not homonym.food_practice_likely:
            score -= 3
            reasons.append("homonym_medium")
        elif homonym.food_practice_likely:
            score += 1
            reasons.append("homonym_cleared")

        if require_homonym_clear and homonym_blocks_clear_example(homonym):
            continue

        tier = "high" if score >= 7 and not conflicts else "medium" if score >= 5 else "low"
        if tier == "low":
            continue

        doc_id = "unknown"
        record = KwicInput(
            record_id=f"clear__{doc_id}",
            corpus="cort_voc_db",
            target_word=food_target,
            context_text=snippet,
            discovery_verb=hit.verb,
            frame_hint=target_frame.value,
            kwic_mode="verb_food",
            text_regime=regime,
        )
        candidate = ClearFrameCandidate(
            record=record,
            suggested_frame=target_frame,
            discovery_verb=hit.verb,
            verb_distance=verb_distance,
            confidence_score=score,
            confidence_tier=tier,
            reasons=tuple(reasons),
            conflicts=tuple(conflicts),
            homonym=homonym,
        )
        if best is None or candidate.confidence_score > best.confidence_score:
            best = candidate

    return best


def _enrich_from_kwic(record: KwicInput, scored: ClearFrameCandidate) -> ClearFrameCandidate:
    regime = _infer_regime(record)
    enriched = KwicInput(
        record_id=record.record_id,
        corpus=record.corpus,
        target_word=record.target_word,
        context_text=record.context_text,
        date=record.date,
        source_path=record.source_path,
        title=record.title,
        candidate_terms=record.candidate_terms,
        discovery_verb=scored.discovery_verb,
        frame_hint=scored.suggested_frame.value,
        kwic_mode=record.kwic_mode or "verb_food",
        text_regime=regime,
    )
    return ClearFrameCandidate(
        record=enriched,
        suggested_frame=scored.suggested_frame,
        discovery_verb=scored.discovery_verb,
        verb_distance=scored.verb_distance,
        confidence_score=scored.confidence_score,
        confidence_tier=scored.confidence_tier,
        reasons=scored.reasons,
        conflicts=scored.conflicts,
        homonym=scored.homonym,
    )


def mine_clear_frame_candidates(
    *,
    frames: tuple[TrifectaFrame, ...] = (
        TrifectaFrame.COOKING_CREATION,
        TrifectaFrame.INGESTION,
    ),
    exclude_record_ids: set[str] | None = None,
    min_score: int = 5,
    high_only: bool = False,
    guideline_only: bool = True,
    logical_name: str = "food_snippets",
    path: str | Path | None = None,
    thesaurus_path: str | None = None,
    near_window: int = DEFAULT_NEAR_WINDOW,
    conflict_window: int = DEFAULT_CONFLICT_WINDOW,
    require_homonym_clear: bool = False,
) -> list[ClearFrameCandidate]:
    """Scan verb-seeded KWIC pool; keep rows that pass clarity filters."""
    lookup = resolve_thesaurus_lookup(thesaurus_path=thesaurus_path)
    if not lookup:
        return []

    snippets = load_food_snippets_frame(logical_name=logical_name, path=path)
    pool = iter_verb_kwic_candidates(snippets, lookup=lookup, require_food=True)
    blocked = exclude_record_ids or set()

    found: list[ClearFrameCandidate] = []
    for record in pool:
        if record.record_id in blocked:
            continue
        hint = record.frame_hint
        if hint is None:
            continue
        try:
            hit_frame = TrifectaFrame(hint)
        except ValueError:
            continue
        if hit_frame not in frames:
            continue

        regime = _infer_regime(record)
        food_terms = list(record.candidate_terms or [record.target_word])
        scored = score_snippet_for_frame(
            record.context_text,
            food_terms,
            hit_frame,
            regime=regime,
            near_window=near_window,
            conflict_window=conflict_window,
            guideline_only=guideline_only,
            require_homonym_clear=require_homonym_clear,
        )
        if scored is None:
            continue
        if scored.confidence_score < min_score:
            continue
        if high_only and scored.confidence_tier != "high":
            continue
        found.append(_enrich_from_kwic(record, scored))

    found.sort(
        key=lambda item: (
            -item.confidence_score,
            item.confidence_tier != "high",
            item.verb_distance,
            item.record.record_id,
        ),
    )
    return found


def sample_clear_frame_candidates(
    candidates: list[ClearFrameCandidate],
    *,
    limit: int,
    seed: int = 0,
    max_per_target: int = 2,
    max_per_work: int = 3,
    frame_quotas: dict[TrifectaFrame, int] | None = None,
) -> list[ClearFrameCandidate]:
    """Stratified sample with per-lemma and per-work caps."""
    if not candidates:
        return []

    by_frame: dict[str, list[ClearFrameCandidate]] = defaultdict(list)
    for item in candidates:
        by_frame[item.suggested_frame.value].append(item)

    rng = random.Random(seed)
    for bucket in by_frame.values():
        rng.shuffle(bucket)

    quotas = frame_quotas or {}
    default_per_frame = max(1, limit // max(len(by_frame), 1))
    frame_order = list(by_frame.keys())
    rng.shuffle(frame_order)

    selected: list[ClearFrameCandidate] = []
    target_counts: dict[str, int] = defaultdict(int)
    work_counts: dict[str, int] = defaultdict(int)

    def work_key(record: KwicInput) -> str:
        return (record.title or record.source_path or record.corpus or "unknown")[:80]

    for frame_name in frame_order:
        quota = quotas.get(TrifectaFrame(frame_name), default_per_frame)
        bucket = by_frame[frame_name]
        picked = 0
        while bucket and picked < quota and len(selected) < limit:
            idx = rng.randrange(len(bucket))
            item = bucket.pop(idx)
            target = normalize_hist_dutch(item.record.target_word)
            work = work_key(item.record)
            if target_counts[target] >= max_per_target:
                continue
            if work_counts[work] >= max_per_work:
                continue
            selected.append(item)
            target_counts[target] += 1
            work_counts[work] += 1
            picked += 1

    return selected[:limit]


def find_target_match(
    context_text: str,
    target_word: str,
    *,
    near_verb: str | None = None,
) -> re.Match[str] | None:
    """Locate the target token; when repeated, prefer the occurrence nearest the frame verb."""
    text = context_text or ""
    if not text or not target_word:
        return None

    pattern = re.compile(rf"\b{re.escape(target_word)}\b", re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches:
        return re.search(re.escape(target_word), text, re.IGNORECASE)
    if len(matches) == 1:
        return matches[0]

    verb = str(near_verb or "").strip()
    if not verb:
        return matches[0]

    from trifecta_annotation.frame_verbs import pick_food_near_verb

    verb_hits = [
        m.start()
        for m in re.finditer(rf"\b{re.escape(verb)}\b", text, re.IGNORECASE)
    ]
    if not verb_hits:
        return matches[0]

    food_positions = [(m.start(), m.group(0)) for m in matches]
    picked = pick_food_near_verb(min(verb_hits), food_positions)
    if not picked:
        return matches[0]
    for match in matches:
        if match.group(0).lower() == str(picked).lower():
            return match
    return matches[0]


def target_centered_snippet(
    context_text: str,
    target_word: str,
    *,
    radius: int = 220,
    before_radius: int | None = None,
    after_radius: int | None = None,
    near_verb: str | None = None,
) -> str:
    """Snippet excerpt centered on target (for human review exports)."""
    text = context_text or ""
    if not text or not target_word:
        return text[: radius * 2]

    before = radius if before_radius is None else before_radius
    after = radius if after_radius is None else after_radius
    match = find_target_match(text, target_word, near_verb=near_verb)
    if not match:
        return text[: before + after]

    start = max(0, match.start() - before)
    end = min(len(text), match.end() + after)
    snippet = text[start:end]
    rel_start = match.start() - start
    rel_end = match.end() - start
    marked = f"{snippet[:rel_start]}[TGT]{snippet[rel_start:rel_end]}[/TGT]{snippet[rel_end:]}"
    if start > 0:
        marked = f"…{marked}"
    if end < len(text):
        marked = f"{marked}…"
    return marked


def clear_frame_summary(candidates: list[ClearFrameCandidate]) -> dict[str, object]:
    by_frame: dict[str, int] = defaultdict(int)
    by_tier: dict[str, int] = defaultdict(int)
    by_regime: dict[str, int] = defaultdict(int)
    by_verb: dict[str, int] = defaultdict(int)
    by_homonym_risk: dict[str, int] = defaultdict(int)
    for item in candidates:
        by_frame[item.suggested_frame.value] += 1
        by_tier[item.confidence_tier] += 1
        regime = _infer_regime(item.record)
        by_regime[regime.value] += 1
        by_verb[normalize_hist_dutch(item.discovery_verb)] += 1
        if item.homonym is not None:
            by_homonym_risk[item.homonym.risk] += 1
    top_verbs = sorted(by_verb.items(), key=lambda pair: (-pair[1], pair[0]))[:12]
    return {
        "total": len(candidates),
        "by_frame": dict(sorted(by_frame.items())),
        "by_tier": dict(sorted(by_tier.items())),
        "by_regime": dict(sorted(by_regime.items())),
        "by_homonym_risk": dict(sorted(by_homonym_risk.items())),
        "top_verbs": top_verbs,
    }
