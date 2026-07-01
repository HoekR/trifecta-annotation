"""Frame-verb lexicon from TRIFECTA Annotation Guidelines NL (v3.0, March 2026).

Source: ``docs/Annotation_Guidelines_final.pdf`` — only ``.v`` (werkwoord) LU forms.
The GEBRUIK/USING prototype frame is not annotated; its verb list is kept for reference only.
"""

from __future__ import annotations

from trifecta_annotation.normalize import normalize_hist_dutch
from trifecta_annotation.schemas import TrifectaFrame

# COOKING_CREATION — De Cooking Creation LU's (.v only)
GUIDELINE_VERB_LEXICON: dict[TrifectaFrame, tuple[str, ...]] = {
    TrifectaFrame.COOKING_CREATION: (
        "aanbraden",
        "bakken",
        "barbecueen",
        "blancheren",
        "braden",
        "bruinen",
        "bereiden",
        "dichtschroeien",
        "frituren",
        "grillen",
        "klaarmaken",
        "kloppen",
        "koken",
        "maken",
        "opbakken",
        "opzetten",
        "pocheren",
        "poeleren",
        "roosteren",
        "samenstellen",
        "sauteren",
        "schroeien",
        "smelten",
        "smoren",
        "stomen",
        "stoven",
        "sudderen",
        "trekken",
        "uitbakken",
        "verwarmen",
        "verschroeien",
    ),
    TrifectaFrame.PRESERVING: (
        "conserveren",
        "drogen",
        "inblikken",
        "inleggen",
        "inmaken",
        "roken",
        "wecken",
        "zouten",
    ),
    TrifectaFrame.CURE: (
        "behandelen",
        "genezen",
        "verbeteren",
        "verlichten",
        "verzachten",
        "verzorgen",
        "voorschrijven",
    ),
    TrifectaFrame.INGESTION: (
        "consumeren",
        "dineren",
        "drinken",
        "eten",
        "innemen",
        "inslikken",
        "kauwen",
        "knabbelen",
        "likken",
        "lunchen",
        "ontbijten",
        "sabbelen",
        "schrokken",
        "slikken",
        "slurpen",
        "snacken",
        "snoepen",
        "verslinden",
        "voeden",
        "wegwerken",
    ),
}

# GEBRUIK prototype (.v only) — not a TRIFECTA macro-frame; not used for KWIC discovery.
GUIDELINE_USING_VERBS: tuple[str, ...] = (
    "bedienen",
    "gebruiken",
    "toepassen",
    "uitoefenen",
)

# Optional historic spellings → fill ``canonical_lemma`` in review CSV (override anytime).
SUGGESTED_CANONICAL_LEMMA: dict[str, str] = {
    "sieden": "koken",
    "syeden": "koken",
    "siedende": "koken",
    "medesieden": "koken",
    "mitsieden": "koken",
    "ghesoden": "koken",
    "gesoden": "koken",
    "stooten": "stampen",
    "ghebroken": "kloppen",
    "prossen": "pruttelen",
    "spruwen": "sudderen",
    "wallen": "koken",
    "ghebraden": "braden",
    "broeyen": "koken",
    "souten": "zouten",
    "pekelen": "zouten",
    "droogen": "drogen",
    "eeten": "eten",
    "drincken": "drinken",
    "spyzen": "eten",
    "temperen": "bereiden",
    "opdissen": "bereiden",
    "doerghedaen": "bereiden",
    "doergedaen": "bereiden",
    "duereghedaen": "bereiden",
    "duerghedaen": "bereiden",
    "dueredoen": "bereiden",
    "houden": "bewaren",
    "heelen": "genezen",
    "verheelen": "genezen",
    "lenigen": "verzachten",
    "cureren": "behandelen",
    "medicineren": "behandelen",
}


def suggested_canonical_lemma(term: str) -> str:
    """Default normalized lemma for review CSV; user may override ``canonical_lemma`` column."""
    norm = normalize_hist_dutch(term)
    if not norm:
        return ""
    return SUGGESTED_CANONICAL_LEMMA.get(norm, norm)


def canonical_frame_verb(term: str) -> str:
    """Alias for historic variant lookup (same as suggested canonical)."""
    return suggested_canonical_lemma(term)


def guideline_verb_entries() -> dict[str, tuple[TrifectaFrame, str]]:
    """Guideline ``.v`` lemmas + historic surface aliases → (frame, canonical_lemma)."""
    base: dict[str, TrifectaFrame] = {}
    for frame, verbs in GUIDELINE_VERB_LEXICON.items():
        for verb in verbs:
            norm = normalize_hist_dutch(verb)
            if norm:
                base[norm] = frame

    out: dict[str, tuple[TrifectaFrame, str]] = {}
    for norm, frame in base.items():
        out[norm] = (frame, norm)

    for variant, lemma in SUGGESTED_CANONICAL_LEMMA.items():
        lemma_norm = normalize_hist_dutch(lemma)
        if variant in out:
            continue
        if lemma_norm in base:
            out[variant] = (base[lemma_norm], lemma_norm)
        elif lemma_norm in SUGGESTED_CANONICAL_LEMMA.values():
            # Historic extra (e.g. bewaren) merged via FRAME_VERB_LEXICON in frame_verbs.py
            pass
    return out
