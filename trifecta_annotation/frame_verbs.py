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
    # From the reviewed list: ambiguous (homograph / probe verb share < 0.8), aux-ambiguous, multi-frame,
    # no-frame, check (Rik to confirm).
    flags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class VerbHit:
    verb: str
    frame: TrifectaFrame
    start: int
    end: int
    lexicon_sources: tuple[str, ...] = ()
    technique: str | None = None
    lemma: str | None = None
    flags: tuple[str, ...] = ()


# The reviewed trigger list (plans/steps/VERB_LEXICON.md V3), written by `scripts/verb_lexicon.py export`
# from Rik's review. Package-relative, so it travels with the code.
REVIEWED_LEXICON_PATH = Path(__file__).resolve().parent / "assets" / "verb_lexicon.csv"

# Enclitic pronouns written onto a verb form: kooktse = kookt ze, doetmen = doet men, doet'er = doet er.
# Only split when the host is a known form ending in -t/-dt/-en (tested on 4 works, 16 Nov:
# docs/evidence/verb_lexicon/c3_patterns.md); bare -er after -t also makes nouns, hence the stop list.
ENCLITICS: tuple[str, ...] = ("men", "ze", "se", "er")
ENCLITIC_STOP: frozenset[str] = frozenset({"gieter", "gieters"})


def load_reviewed_lexicon(path: str | Path | None = None) -> tuple[dict[str, LexiconEntry], frozenset[str]]:
    """(kept form -> entry, dropped forms). Missing file -> ({}, frozenset())."""
    resolved = Path(path) if path else REVIEWED_LEXICON_PATH
    if not resolved.exists():
        return {}, frozenset()
    frame = pd.read_csv(resolved, dtype=str).fillna("")
    kept: dict[str, LexiconEntry] = {}
    dropped: set[str] = set()
    for row in frame.itertuples(index=False):
        norm = normalize_hist_dutch(row.form)
        if not norm:
            continue
        if row.decision == "drop":
            dropped.add(norm)
            continue
        kept[norm] = LexiconEntry(
            frame=TrifectaFrame(row.frame or "NONE"),
            sources=frozenset({"reviewed"}),
            canonical_lemma=row.lemma or None,
            flags=frozenset(x for x in row.flags.split(";") if x and not x.startswith("shared:")),
        )
    return kept, frozenset(dropped - set(kept))


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
                canonical_lemma=existing.canonical_lemma or entry.canonical_lemma,
                flags=existing.flags | entry.flags,
            )
            continue
        merged[norm] = entry
    return merged


def _apply_reviewed(
    merged: dict[str, LexiconEntry],
    kept: dict[str, LexiconEntry],
    dropped: frozenset[str],
) -> dict[str, LexiconEntry]:
    """Rik's review is authoritative: dropped forms leave the list whatever their source; for kept forms his
    lemma, frame and flags win, older sources are kept (so the guideline gate still sees them)."""
    for norm in dropped:
        merged.pop(norm, None)
    for norm, entry in kept.items():
        existing = merged.get(norm)
        if existing is None:
            merged[norm] = entry
            continue
        merged[norm] = LexiconEntry(
            frame=entry.frame if entry.frame != TrifectaFrame.NONE else existing.frame,
            sources=existing.sources | entry.sources,
            technique=existing.technique,
            canonical_lemma=entry.canonical_lemma or existing.canonical_lemma,
            flags=entry.flags,
        )
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
    include_reviewed: bool = True,
    reviewed_path: str | Path | None = None,
) -> dict[str, LexiconEntry]:
    """Merge manual, cort-voc technique, and optional corpus-grown triggers; then apply the reviewed list.

    With the reviewed list present, the mined corpus list (whose `keep=yes` was written automatically) is
    not loaded unless `corpus_lexicon_path` is given explicitly: its real verbs went through Rik's review
    as generator f (VERB_LEXICON.md: "auto-keep disappears")."""
    reviewed, dropped = load_reviewed_lexicon(reviewed_path) if include_reviewed else ({}, frozenset())
    if reviewed and corpus_lexicon_path is None:
        include_corpus = False
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
    return _apply_reviewed(merged, reviewed, dropped) if include_reviewed else merged


def _compile_pattern(terms: list[str]) -> re.Pattern[str]:
    ordered = sorted(terms, key=len, reverse=True)
    return re.compile(
        r"\b(" + "|".join(re.escape(term) for term in ordered) + r")\b",
        re.IGNORECASE,
    )


# Matching is a dictionary lookup per word, not one regex alternation: with ~2,000 reviewed forms the
# alternation was 4x slower (16 Nov), and lookup cost does not grow with the list.
_WORD = re.compile(r"[^\W\d_]+")
_ENCLITIC_SET = frozenset(ENCLITICS)


def _is_enclitic_host(term: str) -> bool:
    return len(term) >= 3 and term.endswith(("t", "en"))


# Separable verbs (16 Nov): the particle goes to the end of the clause, "legt'er de Peeren in" = inleggen.
# A particle *closes* the clause (punctuation or a conjunction follows); a preposition heads a noun phrase
# ("in kout water", "aan 't Spit") and is not taken. Measured on 4 works: 576 readings, 18/20 correct.
SEPARABLE_PARTICLES: dict[str, str] = {
    "in": "in", "op": "op", "af": "af", "uit": "uit", "uyt": "uit", "toe": "toe", "aan": "aan", "aen": "aan",
    "door": "door", "deur": "door", "over": "over", "mede": "mede", "mee": "mede", "weg": "weg", "om": "om",
}
_CLAUSE_CLOSERS = frozenset({
    "en", "ende", "of", "maar", "maer", "om", "als", "tot", "dat", "datmen", "zo", "soo", "zoo", "dan",
    "totdat", "wanneer", "want",
})   # not "te": "om'er goud op te leggen" -> op belongs to the infinitive (opleggen), not the finite verb
_CLAUSE_TOKEN = re.compile(r"[^\W\d_]+|[.,;:!?]")
_SEPARABLE_LOOKAHEAD = 7          # words after the verb


def _separable_particle(text: str, end: int) -> tuple[str, str] | None:
    """(particle as written, normalised particle) closing the clause after position `end`, or None."""
    tokens = _CLAUSE_TOKEN.findall(text, end, min(len(text), end + 90))
    for i, tok in enumerate(tokens[:_SEPARABLE_LOOKAHEAD]):
        low = tok.lower()
        if low in ".,;:!?":
            return None
        if low in SEPARABLE_PARTICLES:
            nxt = tokens[i + 1].lower() if i + 1 < len(tokens) else "."
            if nxt in ".,;:!?" or nxt in _CLAUSE_CLOSERS:
                return tok, SEPARABLE_PARTICLES[low]
    return None


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
        include_reviewed: bool = True,
        reviewed_path: str | Path | None = None,
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
            include_reviewed=include_reviewed,
            reviewed_path=reviewed_path,
        )
        # Single words by lookup; the few multi-word entries keep a (small) regex.
        multi = [t for t in self._entries if not _WORD.fullmatch(t)]
        self._multi = _compile_pattern(multi) if multi else None
        self._pattern = _compile_pattern(list(self._entries)) if self._entries else None   # snippet_has_trigger
        # lemma -> its entry (the infinitive's own entry when there is one), for separable compounds
        self._by_lemma: dict[str, LexiconEntry] = {}
        for norm, entry in self._entries.items():
            if entry.canonical_lemma and (entry.canonical_lemma not in self._by_lemma or norm == entry.canonical_lemma):
                self._by_lemma[entry.canonical_lemma] = entry

    @property
    def entries(self) -> dict[str, LexiconEntry]:
        return dict(self._entries)

    def frame_for(self, verb: str) -> TrifectaFrame | None:
        entry = self._entries.get(normalize_hist_dutch(verb))
        return entry.frame if entry else None

    def entry_for(self, verb: str) -> LexiconEntry | None:
        return self._entries.get(normalize_hist_dutch(verb))

    def find_in_text(self, text: str) -> list[VerbHit]:
        if not self._entries:
            return []
        entries = self._entries
        hits: list[VerbHit] = []
        for match in _WORD.finditer(text):
            surface = match.group(0)
            key = surface.lower()
            entry = entries.get(key)
            if entry is None and not key.isascii():
                key = normalize_hist_dutch(surface)          # long s, ligatures
                entry = entries.get(key)
            start, end = match.start(), match.end()
            if entry is not None:
                # doet'er: the host is a word on its own, the enclitic follows an apostrophe
                tail = _WORD.match(text, end + 1) if text[end:end + 1] == "'" else None
                if tail and tail.group(0).lower() in _ENCLITIC_SET and _is_enclitic_host(key):
                    hits.append(self._hit(surface, entry, start, tail.end(), extra=("enclitic",)))
                else:
                    hits.append(self._hit(surface, entry, start, end))
                continue
            if key in ENCLITIC_STOP:
                continue
            for clitic in ENCLITICS:                          # kooktse, doetmen: one written word
                host = key[: -len(clitic)]
                if key.endswith(clitic) and _is_enclitic_host(host) and host in entries:
                    hits.append(self._hit(surface[: len(host)], entries[host], start, end, extra=("enclitic",)))
                    break
        if self._multi is not None:
            for match in self._multi.finditer(text):
                entry = self.entry_for(match.group(1))
                if entry is not None:
                    hits.append(self._hit(match.group(1), entry, match.start(), match.end()))
            hits.sort(key=lambda hit: (hit.start, hit.end))
        return [self._separable(text, hit) for hit in hits]

    def _separable(self, text: str, hit: VerbHit) -> VerbHit:
        """legt ... in -> lemma inleggen, with its frame; the hit keeps the verb's span and surface."""
        if not hit.lemma:
            return hit
        found = _separable_particle(text, hit.end)
        if found is None:
            return hit
        written, particle = found
        compound = self._by_lemma.get(particle + hit.lemma) or self._by_lemma.get(written.lower() + hit.lemma)
        if compound is None:
            return hit
        return VerbHit(
            hit.verb,
            compound.frame if compound.frame != TrifectaFrame.NONE else hit.frame,
            hit.start,
            hit.end,
            lexicon_sources=tuple(sorted(set(hit.lexicon_sources) | compound.sources)),
            technique=hit.technique,
            lemma=compound.canonical_lemma,
            flags=tuple(sorted(set(hit.flags) - {"ambiguous"} | compound.flags | {f"separable:{hit.lemma}"})),
        )

    @staticmethod
    def _hit(surface: str, entry: LexiconEntry, start: int, end: int, extra: tuple[str, ...] = ()) -> VerbHit:
        return VerbHit(
            surface,
            entry.frame,
            start,
            end,
            lexicon_sources=tuple(sorted(entry.sources)),
            technique=entry.technique,
            lemma=entry.canonical_lemma,
            flags=tuple(sorted(entry.flags)) + extra,
        )

    def snippet_has_trigger(self, text: str) -> bool:
        return bool(self.find_in_text(text))

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"guideline": 0, "manual": 0, "technique": 0, "corpus": 0, "reviewed": 0,
                                  "total": 0}
        for entry in self._entries.values():
            if "reviewed" in entry.sources:
                counts["reviewed"] += 1
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


# Therapeutic *indication* constructions (historic + modern). Not FrameNet cure
# verbs — phrases like "X is goed voor …" / "krachtig tegen …". Matched as
# multi-word spans so discovery is not limited to genezen/verzachten.
CURE_INDICATION_PATTERNS: tuple[tuple[str, str], ...] = (
    # regex (case-insensitive), canonical discovery id
    (r"\bgoed(?:e|t)?\s+voor\b", "goed_voor"),
    (r"\bgoet\s+vo(?:o|e)r\b", "goed_voor"),
    (r"\bbehoort\s+voor\b", "behoort_voor"),
    (r"\bkrachtig(?:e)?\s+tegen\b", "krachtig_tegen"),
    (r"\bgoed(?:e|t)?\s+tegen\b", "goed_tegen"),
    (r"\bgoet\s+tegen\b", "goed_tegen"),
    (r"\bbaat\s+(?:tegen|voor)\b", "baat_tegen"),
    (r"\bdienstig(?:e)?\s+(?:voor|tegen)\b", "dienstig_voor"),
    (r"\bnuttig(?:e)?\s+(?:voor|tegen)\b", "nuttig_voor"),
    (r"\bheilzaam(?:e)?\s+(?:voor|tegen)\b", "heilzaam_voor"),
    (r"\bhelpt\s+(?:tegen|voor)\b", "helpt_tegen"),
    (r"\bhelpen\s+(?:tegen|voor)\b", "helpt_tegen"),
    (r"\bprobaat\s+(?:voor|tegen)\b", "probaat_voor"),
    (r"\bremedie\s+(?:voor|tegen)\b", "remedie_voor"),
    # "gebruik X voor/tegen …" — gated by therapeutic context (see below)
    (
        r"\b(?:gebruik(?:t|en|e)?|gebruickt|gebruyckt|gebruicken|gebruycken)\s+"
        r"(?:\w+\s+){0,4}(?:voor|tegen)\b",
        "gebruik_voor",
    ),
)

# Indication ids that need local therapeutic cues (too common otherwise).
_CONTEXT_GATED_INDICATIONS: frozenset[str] = frozenset({"gebruik_voor"})

_THERAPEUTIC_CONTEXT = re.compile(
    r"\b(?:"
    r"hoest|koorts|pijn|ziekte|tering|jicht|podagra|worm(?:en)?|zweren?|"
    r"steen|koliek|verkoud(?:heid)?|waterzucht|kwaal|qualen?|qualen|"
    r"maag(?:ziekte|pijn)?|borst(?:ziekte|pijn)?|long(?:en)?|"
    r"genees|heel(?:en|kunde)|medicyn|remedie|heelen|verlichten|verzachten|"
    r"behandelen|cureren"
    r")\b",
    re.IGNORECASE,
)

_COOKING_CONTEXT = re.compile(
    r"\b(?:"
    r"koken|sieden|bakken|braden|bereiden|mengen|stoven|smoren|"
    r"stampen|kloppen|deeg|oven|braadpan|kookpot"
    r")\b",
    re.IGNORECASE,
)


def _indication_context_ok(text: str, start: int, end: int, *, canonical: str) -> bool:
    """For gated constructions (gebruik … voor/tegen), require remedy context."""
    if canonical not in _CONTEXT_GATED_INDICATIONS:
        return True
    window = 100
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    span = text[lo:hi]
    therapeutic = bool(_THERAPEUTIC_CONTEXT.search(span))
    cooking = bool(_COOKING_CONTEXT.search(span))
    if therapeutic and not cooking:
        return True
    if therapeutic and cooking:
        # Prefer cure when affliction cues are present even near prep wording
        return True
    return False


# "bewaren" is the single most common PRESERVING trigger in historic Dutch but
# also the most polysemous: apothecary stock-listing ("Medicamenten die men in
# de Winkels bewaren moet") and abstract/moral "protect, keep safe"
# ("levensgeesten bewaren") both use the bare verb with no preservation sense.
# Gate it on a nearby storage/duration cue, same mechanism as CURE's
# indication-construction context gate above.
_PRESERVING_STORAGE_CUE = re.compile(
    r"\b(?:"
    r"lang(?:e)?\s+(?:te\s+)?bewa(?:a)?r\w*|"
    r"om\s+(?:\w+\s+){0,3}te\s+bewa(?:a)?r\w*|"
    r"voor\s+(?:de\s+)?(?:verrotting|bederf|bederving)\s+(?:te\s+)?bewa(?:a)?r\w*|"
    r"van\s+(?:een|twee|drie|vier|vijf|zes|zeven|acht|negen|tien|\d+)\s+"
    r"(?:jaren?|maanden?|weken?|dagen?)|"
    r"jaren?\s+lang|"
    r"(?:goed|lang)\s+(?:blijven|houden|blijft|houdt)|"
    r"\bwinters?\b|"
    r"\bpot(?:je)?\b|\bton(?:ne)?\b|\bvat(?:je)?\b|\bkelder\b|\bflesch(?:en)?\b"
    r")\b",
    re.IGNORECASE,
)
_PRESERVING_NEGATIVE_CUE = re.compile(
    r"\b(?:winkel(?:s)?|medicament(?:en)?|apoth?eek|levensgeest(?:en)?)\b",
    re.IGNORECASE,
)


def bewaren_context_ok(text: str, start: int, end: int, *, window: int = 100) -> bool:
    """Require a storage/duration cue near a bare ``bewaren`` hit, and reject
    the apothecary-stock / abstract-protection senses outright."""
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    span = text[lo:hi]
    if _PRESERVING_NEGATIVE_CUE.search(span):
        return False
    return bool(_PRESERVING_STORAGE_CUE.search(span))


def find_cure_indication_hits(text: str) -> list[VerbHit]:
    """Multi-word CURE indication spans (goed voor, gebruik … tegen, …)."""
    if not text or not text.strip():
        return []
    hits: list[VerbHit] = []
    for pattern, canonical in CURE_INDICATION_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if not _indication_context_ok(
                text, match.start(), match.end(), canonical=canonical,
            ):
                continue
            hits.append(
                VerbHit(
                    verb=canonical,
                    frame=TrifectaFrame.CURE,
                    start=match.start(),
                    end=match.end(),
                    lexicon_sources=("indication",),
                    technique=None,
                ),
            )
    hits.sort(key=lambda hit: (hit.start, hit.end))
    return hits


def find_frame_verbs_in_text(text: str) -> list[VerbHit]:
    """Return frame-trigger hits in left-to-right order (verbs + CURE indications)."""
    hits = list(_DEFAULT_LEXICON.find_in_text(text))
    # Drop verb hits fully covered by an indication span (e.g. lone "dienstig").
    indications = find_cure_indication_hits(text)
    if not indications:
        return hits
    kept: list[VerbHit] = []
    for hit in hits:
        covered = any(ind.start <= hit.start and hit.end <= ind.end for ind in indications)
        if covered:
            continue
        kept.append(hit)
    merged = kept + indications
    merged.sort(key=lambda hit: (hit.start, hit.end))
    return merged


def snippet_has_frame_verb(text: str) -> bool:
    return bool(find_frame_verbs_in_text(text))


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
