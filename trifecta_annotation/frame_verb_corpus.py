"""Mine and load frame-verb candidates from food-snippet corpus."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from trifecta_annotation.adapters.food_snippets import parse_found_terms
from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import TrifectaFrame

DEFAULT_CORPUS_LEXICON_PATH = Path(__file__).resolve().parent.parent / "trifecta_frame_verb_corpus.csv"

_TOKEN_RE = re.compile(r"\b[a-zA-Zà-ÿ][a-zA-Zà-ÿ\-]*\b")

# Modals, auxiliaries, and high-frequency generic verbs — not frame triggers.
VERB_DENYLIST: frozenset[str] = frozenset(
    normalize_hist_dutch(term)
    for term in (
        "zijn",
        "was",
        "waren",
        "worden",
        "werd",
        "hebben",
        "had",
        "hadden",
        "moeten",
        "kunnen",
        "zullen",
        "mogen",
        "willen",
        "laten",
        "gaan",
        "komen",
        "doen",
        "geven",
        "nemen",
        "zien",
        "weten",
        "zeggen",
        "maken",
        "staan",
        "liggen",
        "zitten",
        "leggen",
        "brengen",
        "halen",
        "vinden",
        "houden",
        "brengen",
        "schijnen",
        "blijven",
        "denken",
        "spreken",
        "schrijven",
        "lezen",
        "hooren",
        "horen",
        "weten",
        "scheppen",
        "werken",
        "leven",
        "sterven",
        "gaan",
        "krijgen",
        "brengen",
        "moesten",
        "konden",
        "zouden",
        "werden",
        "waren",
        "hadden",
        "wisten",
        "wisten",
        "tegen",
        "indien",
        "dagen",
        "morgen",
        "allen",
        "anderen",
        "menschen",
        "vrouwen",
        "kinderen",
        "heeren",
        "vrienden",
        "woorden",
        "steden",
        "huizen",
        "rivieren",
        "hunnen",
        "zijnen",
        "hetgeen",
        "grooten",
        "luiden",
        "kennen",
        "slapen",
        "leeren",
        "scheen",
        "voeden",
        "vangen",
        "eenen",
    )
)

CORPUS_COLUMNS = [
    "term_norm",
    "historic_forms",
    "term_example",
    "frame_hint",
    "snippet_freq",
    "anchor_agreement",
    "anchor_frames",
    "keep",
    "notes",
]

# Deprecated columns still read when present: ``canonical_lemma``, ``variants``


@dataclass(frozen=True)
class CorpusCandidate:
    term_norm: str
    term_example: str
    frame: TrifectaFrame | None
    snippet_freq: int
    anchor_agreement: float
    anchor_frames: str


def _anchor_positions(snippet: str, anchor_terms: list[str]) -> list[tuple[int, str]]:
    lowered = snippet.lower()
    hits: list[tuple[int, str]] = []
    for term in sorted(anchor_terms, key=len, reverse=True):
        for match in re.finditer(rf"\b{re.escape(term)}\b", lowered):
            hits.append((match.start(), term))
    hits.sort(key=lambda item: item[0])
    return hits


def _token_positions(snippet: str) -> list[tuple[int, str, str]]:
    found: list[tuple[int, str, str]] = []
    for match in _TOKEN_RE.finditer(snippet):
        surface = match.group(0)
        norm = normalize_hist_dutch(surface)
        if norm:
            found.append((match.start(), surface, norm))
    return found


def _looks_food_plural(norm: str, food_terms: frozenset[str]) -> bool:
    """Reject tokens that are likely plural food nouns (``appelen``, ``meloenen``)."""
    if len(norm) < 5 or not norm.endswith("en"):
        return False
    for stem in (norm[:-2], norm[:-1]):
        if stem in food_terms:
            return True
    return False


def is_corpus_verb_candidate(
    norm: str,
    *,
    food_terms: frozenset[str],
    seed_terms: frozenset[str],
) -> bool:
    from trifecta_annotation.frame_verbs import _is_verb_like

    if not norm or norm in food_terms or norm in seed_terms:
        return False
    if norm in VERB_DENYLIST:
        return False
    if _looks_food_plural(norm, food_terms):
        return False
    if norm.endswith("eren") and norm not in {
        "fermenteren",
        "verteren",
        "bereiden",
        "conserveren",
        "medicineren",
        "verzekeren",
    }:
        return False
    return _is_verb_like(norm)


def frequent_food_matched_terms(
    snippets_long: pd.DataFrame,
    *,
    min_freq: int = 15,
) -> frozenset[str]:
    """Tokens that appear often as food keywords — unlikely frame-verb triggers."""
    if "matched_term" not in snippets_long.columns:
        return frozenset()
    counts = (
        snippets_long["matched_term"]
        .astype(str)
        .map(normalize_hist_dutch)
        .value_counts()
    )
    return frozenset(term for term, freq in counts.items() if freq >= min_freq and term)


def mine_frame_verb_candidates(
    snippets: pd.DataFrame,
    *,
    food_lookup: dict[str, str],
    anchor_lexicon: dict | None = None,
    exclude_terms: frozenset[str] | None = None,
    max_window: int = 120,
) -> list[CorpusCandidate]:
    """
    Discover verb-like tokens co-occurring with food terms near seed frame triggers.

    Uses manual+technique anchors only (not corpus-grown terms) to vote on frame.
    """
    if anchor_lexicon is None:
        from trifecta_annotation.frame_verbs import build_merged_lexicon

        anchor_lexicon = build_merged_lexicon(include_corpus=False)
    anchors = anchor_lexicon
    anchor_terms = list(anchors.keys())
    seed_terms = frozenset(anchors.keys())
    food_terms = frozenset(food_lookup.keys())
    blocked = food_terms | (exclude_terms or frozenset())

    from trifecta_annotation.frame_verbs import term_positions

    stats: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "example": "",
            "frame_votes": Counter(),
            "snippet_ids": set(),
        },
    )

    snippet_col = snippets["snippet"].astype(str)
    for row_idx, snippet in snippet_col.items():
        snippet = snippet.strip()
        if not snippet:
            continue

        row = snippets.loc[row_idx]
        found_food = [
            term
            for term in parse_found_terms(row.get("original_found_terms"))
            if normalize_hist_dutch(term) in food_terms
        ]
        if not found_food:
            continue

        anchor_hits = _anchor_positions(snippet, anchor_terms)
        if not anchor_hits:
            continue

        food_positions = term_positions(snippet, found_food)

        anchor_frames_near: list[tuple[int, TrifectaFrame]] = []
        for pos, term in anchor_hits:
            entry = anchors.get(term)
            if entry is not None:
                anchor_frames_near.append((pos, entry.frame))

        for pos, surface, norm in _token_positions(snippet):
            if not is_corpus_verb_candidate(
                norm,
                food_terms=blocked,
                seed_terms=seed_terms,
            ):
                continue

            nearby_frames = [
                frame
                for anchor_pos, frame in anchor_frames_near
                if abs(anchor_pos - pos) <= max_window
            ]
            if not nearby_frames:
                continue
            if not any(abs(food_pos - pos) <= max_window for food_pos, _ in food_positions):
                continue

            bucket = stats[norm]
            if not bucket["example"]:
                bucket["example"] = surface
            bucket["snippet_ids"].add(str(row.get("doc_id", row_idx)))
            bucket["frame_votes"].update(nearby_frames)

    candidates: list[CorpusCandidate] = []
    for norm, bucket in stats.items():
        votes: Counter = bucket["frame_votes"]
        if not votes:
            continue
        frame, top_count = votes.most_common(1)[0]
        agreement = top_count / sum(votes.values())
        candidates.append(
            CorpusCandidate(
                term_norm=norm,
                term_example=str(bucket["example"]),
                frame=frame,
                snippet_freq=len(bucket["snippet_ids"]),
                anchor_agreement=round(agreement, 3),
                anchor_frames=",".join(
                    f"{name}={count}"
                    for name, count in sorted(votes.items(), key=lambda item: (-item[1], item[0].value))
                ),
            ),
        )

    candidates.sort(key=lambda item: (-item.snippet_freq, -item.anchor_agreement, item.term_norm))
    return candidates


def collapse_candidates_by_lemma(
    candidates: list[CorpusCandidate],
) -> list[CorpusCandidate]:
    """Merge spelling variants (``sieden``/``syeden``) under one canonical lemma."""
    from trifecta_annotation.frame_verb_guidelines import suggested_canonical_lemma

    buckets: dict[tuple[str, str], dict[str, object]] = {}
    for item in candidates:
        if item.frame is None:
            continue
        lemma = suggested_canonical_lemma(item.term_norm)
        key = (lemma, item.frame.value)
        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = {
                "example": item.term_example,
                "freq": item.snippet_freq,
                "votes": item.snippet_freq,
                "agreement_sum": item.anchor_agreement * item.snippet_freq,
                "frames": item.anchor_frames,
                "variants": {item.term_norm},
            }
            continue
        bucket["freq"] = int(bucket["freq"]) + item.snippet_freq
        bucket["votes"] = int(bucket["votes"]) + item.snippet_freq
        bucket["agreement_sum"] = float(bucket["agreement_sum"]) + item.anchor_agreement * item.snippet_freq
        bucket["variants"].add(item.term_norm)
        if item.snippet_freq > int(bucket.get("best_freq", 0)):
            bucket["example"] = item.term_example
            bucket["best_freq"] = item.snippet_freq

    collapsed: list[CorpusCandidate] = []
    for (lemma, frame_name), bucket in buckets.items():
        freq = int(bucket["freq"])
        agreement = float(bucket["agreement_sum"]) / freq if freq else 0.0
        variants = sorted(bucket["variants"])
        collapsed.append(
            CorpusCandidate(
                term_norm=lemma,
                term_example=str(bucket["example"]),
                frame=TrifectaFrame(frame_name),
                snippet_freq=freq,
                anchor_agreement=round(agreement, 3),
                anchor_frames=f'variants:{",".join(variants)}',
            ),
        )
    collapsed.sort(key=lambda item: (-item.snippet_freq, -item.anchor_agreement, item.term_norm))
    return collapsed


def _csv_cell(row: object, name: str) -> str:
    val = getattr(row, name, "")
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def parse_historic_forms(raw: object) -> list[str]:
    """Split comma/semicolon/pipe-separated historic surface forms."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    found: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,;|]", str(raw)):
        norm = normalize_hist_dutch(part.strip())
        if not norm:
            continue
        for variant in (norm, norm.replace(" ", "")):
            if variant and variant not in seen:
                found.append(variant)
                seen.add(variant)
    return found


def row_canonical_and_surfaces(row: object) -> tuple[str, set[str]]:
    """
    Resolve modern lemma + historic trigger surfaces from a review CSV row.

    **Preferred columns**
    - ``term_norm`` — modern spelling (``koken``, ``stampen``)
    - ``historic_forms`` — extra historic spellings (comma-separated)
    - ``term_example`` — one witnessed historic form in text

    **Legacy** (still supported): ``canonical_lemma`` = modern, ``term_norm`` = historic.
    """
    modern = normalize_hist_dutch(_csv_cell(row, "term_norm"))
    legacy_canon = normalize_hist_dutch(_csv_cell(row, "canonical_lemma"))
    surfaces: set[str] = set()

    if legacy_canon:
        canonical = legacy_canon
        if modern and modern != canonical:
            surfaces.add(modern)
    else:
        canonical = modern

    surfaces.update(parse_historic_forms(getattr(row, "historic_forms", "")))
    surfaces.update(parse_historic_forms(getattr(row, "variants", "")))

    example = normalize_hist_dutch(_csv_cell(row, "term_example"))
    if example:
        surfaces.add(example)

    surfaces.discard("")
    if canonical:
        surfaces.discard(canonical)
    return canonical, surfaces


def candidates_to_dataframe(candidates: list[CorpusCandidate]) -> pd.DataFrame:
    from trifecta_annotation.frame_verb_guidelines import suggested_canonical_lemma

    rows = []
    for item in candidates:
        surface = normalize_hist_dutch(item.term_norm)
        modern = suggested_canonical_lemma(surface)
        rows.append(
            {
                "term_norm": modern,
                "historic_forms": "" if modern == surface else surface,
                "term_example": item.term_example or surface,
                "frame_hint": item.frame.value if item.frame else "",
                "snippet_freq": item.snippet_freq,
                "anchor_agreement": item.anchor_agreement,
                "anchor_frames": item.anchor_frames,
                "keep": "",
                "notes": "",
            },
        )
    return pd.DataFrame(rows, columns=CORPUS_COLUMNS)


def auto_keep_mask(
    frame: pd.DataFrame,
    *,
    min_freq: int = 5,
    min_agreement: float = 0.75,
) -> pd.Series:
    keep_col = frame["keep"].astype(str).str.strip().str.lower() if "keep" in frame.columns else pd.Series(dtype=str)
    manual_yes = keep_col.isin({"yes", "y", "1", "true"})
    manual_no = keep_col.isin({"no", "n", "0", "false"})
    auto = (
        frame["frame_hint"].astype(str).str.strip().ne("")
        & frame["snippet_freq"].ge(min_freq)
        & frame["anchor_agreement"].ge(min_agreement)
    )
    return manual_yes | (auto & ~manual_no)


def load_corpus_lexicon(
    path: str | Path | None = None,
    *,
    approved_only: bool = True,
    min_freq: int = 5,
    min_agreement: float = 0.75,
) -> dict[str, object]:
    """Load corpus-grown triggers.

    By default only rows with ``keep=yes`` are loaded — prose-mined noise is opt-in.
    """
    from trifecta_annotation.frame_verbs import LexiconEntry

    resolved = Path(path or DEFAULT_CORPUS_LEXICON_PATH).expanduser()
    if not resolved.exists():
        return {}

    frame = pd.read_csv(resolved)
    if frame.empty or "term_norm" not in frame.columns:
        return {}

    keep_col = frame["keep"].astype(str).str.strip().str.lower()
    if approved_only:
        mask = keep_col.isin({"yes", "y", "1", "true"})
    else:
        mask = auto_keep_mask(frame, min_freq=min_freq, min_agreement=min_agreement)
    out: dict[str, object] = {}
    for row in frame[mask].itertuples(index=False):
        canonical, surfaces = row_canonical_and_surfaces(row)
        if not canonical:
            continue
        frame_name = str(getattr(row, "frame_hint", "") or "").strip()
        if not frame_name:
            continue
        try:
            frame_hint = TrifectaFrame(frame_name)
        except ValueError:
            continue
        freq = int(getattr(row, "snippet_freq", 0) or 0)
        keep = str(getattr(row, "keep", "") or "").strip().lower()
        source = "corpus:review" if keep in {"yes", "y", "true", "1"} else f"corpus:freq={freq}"
        entry = LexiconEntry(
            frame=frame_hint,
            sources=frozenset({source}),
            canonical_lemma=canonical,
        )
        triggers = surfaces | {canonical}
        for trigger in triggers:
            out[trigger] = entry
    return out
