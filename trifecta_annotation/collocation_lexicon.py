"""Promote collocation-mined verbs into the frame-verb corpus lexicon."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from trifecta_annotation.adapters.food_snippets import load_food_snippets_long_frame
from trifecta_annotation.collocation_skeleton import (
    classify_collocate,
    collocates_near_target,
)
from trifecta_annotation.frame_verb_corpus import (
    CorpusCandidate,
    _anchor_positions,
    _token_positions,
    auto_keep_mask,
    candidates_to_dataframe,
    frequent_food_matched_terms,
)
from trifecta_annotation.frame_verbs import FrameVerbLexicon, get_frame_verb_lexicon
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import TrifectaFrame
from trifecta_annotation.thesaurus import filter_long_snippets_frame
from trifecta_annotation.vocabulary import resolve_thesaurus_lookup


def mine_collocation_verb_candidates(
    snippets_long: pd.DataFrame,
    *,
    food_lookup: dict[str, str],
    lexicon: FrameVerbLexicon | None = None,
    anchor_lexicon: dict | None = None,
    collocation_window: int = 5,
    anchor_window: int = 120,
    exclude_terms: frozenset[str] | None = None,
    min_snippet_freq: int = 1,
) -> list[CorpusCandidate]:
    """
    Discover verb collocates of food targets and vote macro-frame from nearby anchors.

    Uses ``food_snippets_long`` (target-centred KWICs). Skips verbs already present in
    the **full** merged lexicon (guideline + manual + technique + approved corpus).
    """
    if anchor_lexicon is None:
        from trifecta_annotation.frame_verbs import build_merged_lexicon

        anchor_lexicon = build_merged_lexicon(include_corpus=False)

    lexicon = lexicon or get_frame_verb_lexicon()
    anchor_terms = list(anchor_lexicon.keys())
    seed_terms = frozenset(anchor_terms)
    food_terms = frozenset(food_lookup.keys()) | (exclude_terms or frozenset())

    stats: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "example": "",
            "frame_votes": Counter(),
            "snippet_ids": set(),
            "food_targets": Counter(),
        },
    )

    seen_doc_term: set[str] = set()
    snippet_col = snippets_long["snippet"].astype(str)
    for row_idx, snippet in snippet_col.items():
        snippet = snippet.strip()
        if not snippet:
            continue

        row = snippets_long.loc[row_idx]
        target_norm = normalize_hist_dutch(str(row.get("matched_term") or ""))
        if not target_norm or target_norm not in food_terms:
            continue

        doc_id = str(row.get("doc_id", row_idx))
        doc_term_key = f"{doc_id}__{target_norm}"
        if doc_term_key in seen_doc_term:
            continue
        seen_doc_term.add(doc_term_key)

        anchor_hits = _anchor_positions(snippet, anchor_terms)
        if not anchor_hits:
            continue

        anchor_frames_near: list[tuple[int, TrifectaFrame]] = []
        for pos, term in anchor_hits:
            entry = anchor_lexicon.get(term)
            if entry is not None:
                anchor_frames_near.append((pos, entry.frame))

        token_positions = _token_positions(snippet)
        verb_positions: dict[str, int] = {}
        for pos, surface, norm in token_positions:
            if lexicon.frame_for(norm) is not None:
                continue
            if (
                classify_collocate(
                    norm,
                    lexicon=lexicon,
                    food_lookup=food_lookup,
                    seed_terms=seed_terms,
                )
                != "verb"
            ):
                continue
            verb_positions[norm] = pos
        if not verb_positions:
            continue

        target_near = {
            coll_norm
            for coll_norm, _ in collocates_near_target(
                snippet,
                target_norm=target_norm,
                window_tokens=collocation_window,
                food_terms=food_terms,
                seed_terms=seed_terms,
            )
        }

        for coll_norm, surface in (
            (norm, surf)
            for pos, surf, norm in token_positions
            if norm in verb_positions and norm in target_near
        ):
            verb_pos = verb_positions[coll_norm]
            nearby_frames = [
                frame
                for anchor_pos, frame in anchor_frames_near
                if abs(anchor_pos - verb_pos) <= anchor_window
            ]
            if not nearby_frames:
                continue

            bucket = stats[coll_norm]
            if not bucket["example"]:
                bucket["example"] = surface
            bucket["snippet_ids"].add(doc_term_key)
            bucket["food_targets"][target_norm] += 1
            bucket["frame_votes"].update(nearby_frames)

    candidates: list[CorpusCandidate] = []
    for norm, bucket in stats.items():
        votes: Counter = bucket["frame_votes"]
        if not votes:
            continue
        freq = len(bucket["snippet_ids"])
        if freq < min_snippet_freq:
            continue
        frame, top_count = votes.most_common(1)[0]
        agreement = top_count / sum(votes.values())
        top_targets = bucket["food_targets"].most_common(5)
        target_note = ",".join(f"{name}={count}" for name, count in top_targets)
        candidates.append(
            CorpusCandidate(
                term_norm=norm,
                term_example=str(bucket["example"]),
                frame=frame,
                snippet_freq=freq,
                anchor_agreement=round(agreement, 3),
                anchor_frames=f"targets:{target_note}",
            ),
        )

    candidates.sort(key=lambda item: (-item.snippet_freq, -item.anchor_agreement, item.term_norm))
    return candidates


def collocation_candidates_to_dataframe(
    candidates: list[CorpusCandidate],
    *,
    min_freq: int = 5,
    min_agreement: float = 0.75,
) -> pd.DataFrame:
    """Convert candidates to review CSV rows with auto ``keep=yes`` when thresholds pass."""
    frame = candidates_to_dataframe(candidates)
    if frame.empty:
        return frame
    frame["notes"] = "collocation_miner"
    auto = auto_keep_mask(frame, min_freq=min_freq, min_agreement=min_agreement)
    frame.loc[auto, "keep"] = "yes"
    return frame


def collect_collocation_lexicon_candidates(
    *,
    path: str | Path | None = None,
    logical_name: str = "food_snippets_long",
    thesaurus_path: str | Path | None = None,
    thesaurus_filter: bool = True,
    collocation_window: int = 5,
    anchor_window: int = 120,
    min_freq: int = 5,
    min_agreement: float = 0.75,
    limit: int | None = None,
) -> pd.DataFrame:
    """Mine collocation verb candidates and return a corpus-review dataframe."""
    snippets = load_food_snippets_long_frame(logical_name=logical_name, path=path)
    lookup = resolve_thesaurus_lookup(thesaurus_path=thesaurus_path)
    if thesaurus_filter:
        snippets = filter_long_snippets_frame(snippets, lookup)
    if limit is not None:
        snippets = snippets.head(limit)

    exclude = frequent_food_matched_terms(snippets)
    candidates = mine_collocation_verb_candidates(
        snippets,
        food_lookup=lookup,
        collocation_window=collocation_window,
        anchor_window=anchor_window,
        exclude_terms=exclude,
    )
    return collocation_candidates_to_dataframe(
        candidates,
        min_freq=min_freq,
        min_agreement=min_agreement,
    )


def collocation_lexicon_summary(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {"rows": 0, "auto_keep": 0, "review": 0}
    keep = frame["keep"].astype(str).str.strip().str.lower()
    auto_yes = keep.isin({"yes", "y", "true", "1"}).sum()
    return {
        "rows": len(frame),
        "auto_keep": int(auto_yes),
        "review": int(len(frame) - auto_yes),
        "frames": sorted(frame["frame_hint"].astype(str).unique().tolist()),
        "top": frame.sort_values(["snippet_freq", "anchor_agreement"], ascending=False)
        .head(12)[["term_norm", "frame_hint", "snippet_freq", "anchor_agreement", "keep"]]
        .to_dict(orient="records"),
    }
