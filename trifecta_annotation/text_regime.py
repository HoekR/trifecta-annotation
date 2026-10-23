"""Text-regime (genre) inference for stratified TRIFECTA annotation."""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field


class TextRegime(str, Enum):
    """Discourse type of the source document (Layer 0)."""

    RECIPE_PRACTICE = "RECIPE_PRACTICE"
    MEDICAL = "MEDICAL"
    TRAVEL = "TRAVEL"
    LITERARY = "LITERARY"
    ADMIN_TRADE = "ADMIN_TRADE"
    SCIENTIFIC = "SCIENTIFIC"
    UNKNOWN = "UNKNOWN"


_CORPUS_REGIME: dict[str, TextRegime] = {
    "voc_recipes": TextRegime.RECIPE_PRACTICE,
    "recipe_web": TextRegime.RECIPE_PRACTICE,
}

# Per-work overrides, keyed by DBNL text id (our `source_path` filenames minus
# ".xml" and any " (1)" duplicate marker). Title-keyword inference is fragile on
# historical Dutch in ways that are silent and consequential: it missed
# "Het secreet-boek vol heerlijke konsten" because the pattern lacked the
# inflectional -e, and "Koock-boeck ofte familieren kevken-boeck" because of u/v
# spelling — the two most recipe-structured works in the corpus. It also tagged
# a travel account as MEDICAL because "chirurgijn" appeared in its title.
#
# These are explicit, auditable calls over the 61 works in
# `food_snippets_long_kwic`. Entries marked REVIEW are genuinely debatable and
# three of them move published measurements, so they are worth a second opinion:
# see PLAN.md §9e.
_WORK_REGIME: dict[str, TextRegime] = {
    # --- recipe / household practice ---
    "_vol002volm01_01": TextRegime.RECIPE_PRACTICE,  # De volmaakte Hollandsche keuken-meid
    "chom003huis01_01": TextRegime.RECIPE_PRACTICE,  # Huishoudelyk woordboek
    "magi007kooc02_01": TextRegime.RECIPE_PRACTICE,  # Koock-boeck ofte familieren kevken-boeck
    "bate002secr02_01": TextRegime.RECIPE_PRACTICE,  # Het secreet-boek vol heerlijke konsten
    # REVIEW: book of Dutch ceremonial customs, food-adjacent rather than a
    # recipe book; kept as the pre-existing regex call.
    "alke003nede01_01": TextRegime.RECIPE_PRACTICE,  # Nederlands displegtigheden
    # --- medical ---
    "_pha001phar05_01": TextRegime.MEDICAL,  # Pharmacopoea Amstelredamensis
    "_pha001phar02_01": TextRegime.MEDICAL,  # Pharmacopaea Amstelredamensis
    "_lee024leeu02_01": TextRegime.MEDICAL,  # Leeuwarder Apotheek
    # REVIEW: dietetic treatise on tea; could equally be SCIENTIFIC.
    "bont009gebr01_01": TextRegime.MEDICAL,  # Gebruik en Mis-bruik van de Thee
    # --- travel / colonial accounts ---
    "wits008noor02_01": TextRegime.TRAVEL,  # Noord en Oost Tartarye
    "breu012dagv01_01": TextRegime.TRAVEL,  # Dagverhaal ... Paramaribo
    "fric007drie01_01": TextRegime.TRAVEL,  # Drie seer aenmercklijcke reysen (was MEDICAL: "chirurgijn")
    "teen002nege01_01": TextRegime.TRAVEL,  # De negerslaven in de kolonie Suriname
    "kapp006zesj01_01": TextRegime.TRAVEL,  # Zes jaren in Suriname
    "eman001lang01_01": TextRegime.TRAVEL,  # Langs den Nijl
    "teen002vruc02_01": TextRegime.TRAVEL,  # De vruchten mijner werkzaamheden (Teenstra, Suriname)
    # REVIEW: Indies sketches — arguably LITERARY.
    "hove006insa01_01": TextRegime.TRAVEL,  # In sarong en kabaai
    # REVIEW: natural & moral history of the Antilles — arguably SCIENTIFIC.
    "roch007natu01_01": TextRegime.TRAVEL,  # Natuurlyke en Zedelyke Historie d'Eylanden
    # --- trade / administrative ---
    "vivr001dial02_01": TextRegime.ADMIN_TRADE,  # Dialogves Flamen-Françoys ... Marchandise
    "wicq003jour01_01": TextRegime.ADMIN_TRADE,  # Journael ... handel der Franschen
    # --- scholarly / reference ---
    # REVIEW: a word-list. No REFERENCE regime exists; SCIENTIFIC is the closest.
    # This one matters: it is the highest unit-density work in the corpus
    # (24.2 cues/10k) and so a structural false positive.
    "hofm005nede02_01": TextRegime.SCIENTIFIC,  # Nederlandtsche woorden-schat
    "pica002naau05_01": TextRegime.SCIENTIFIC,  # Naaukeurige beschryving ... godtsdienst-plichten
    "_jaa002187401_01": TextRegime.SCIENTIFIC,  # Jaarboek Mij. der Nederlandse Letterkunde
    "_jaa033187301_01": TextRegime.SCIENTIFIC,  # Publications ... duché de Limbourg
    "_ber002185001_01": TextRegime.SCIENTIFIC,  # Berigten Historisch Genootschap Utrecht
    # --- literary: periodicals, novels, poetry, miscellanies ---
    "_vad003180901_01": TextRegime.LITERARY,
    "_vad003182101_01": TextRegime.LITERARY,
    "_vad003182701_01": TextRegime.LITERARY,
    "_vad003182901_01": TextRegime.LITERARY,
    "_vad003183301_01": TextRegime.LITERARY,
    "_vad003183401_01": TextRegime.LITERARY,
    "_vad003183901_01": TextRegime.LITERARY,
    "_vad003184101_01": TextRegime.LITERARY,
    "_vad003185501_01": TextRegime.LITERARY,
    "_vad003185901_01": TextRegime.LITERARY,
    "_hui002189201_01": TextRegime.LITERARY,
    "_hui002189901_01": TextRegime.LITERARY,
    "_hui002190001_01": TextRegime.LITERARY,
    "_tij008186501_01": TextRegime.LITERARY,
    "_nie148nieu01_01": TextRegime.LITERARY,
    "sche471verm01_01": TextRegime.LITERARY,
    "gram004madj01_01": TextRegime.LITERARY,
    "wolf016hist01_01": TextRegime.LITERARY,  # Sara Burgerhart
    "wolf016corn07_01": TextRegime.LITERARY,  # Cornelia Wildschut
    "meer017tone02_01": TextRegime.LITERARY,
    "_kod003kodd02_01": TextRegime.LITERARY,
    "weye002amst02_01": TextRegime.LITERARY,  # Den Amsterdamschen Hermes (spectatorial)
    "weye002ontl01_01": TextRegime.LITERARY,  # Den ontleeder der gebreeken (spectatorial)
    "_den001denk09_01": TextRegime.LITERARY,  # De Denker (spectatorial)
    "cats001houw01_01": TextRegime.LITERARY,  # Cats, Houwelick (didactic verse)
    "hond001dape02_01": TextRegime.LITERARY,  # Hondius, Dapes inemptae (georgic)
    "poir001dens01_01": TextRegime.LITERARY,
    "hein008denv01_01": TextRegime.LITERARY,  # Heinsius, picaresque
    "bure003magd01_01": TextRegime.LITERARY,
    "neuf002elis01_01": TextRegime.LITERARY,
    "_won001wond01_01": TextRegime.LITERARY,
    "_won002wond01_01": TextRegime.LITERARY,
    "joos025kley01_01": TextRegime.LITERARY,
    "koer001bloe01_01": TextRegime.LITERARY,
    "daum001hoeh01_01": TextRegime.LITERARY,  # Daum (ps. Maurits), Indies novel
    "bosb002medi02_01": TextRegime.LITERARY,  # Bosboom-Toussaint (was ADMIN_TRADE: "vredehandel")
}

_WORK_KEY_RE = re.compile(r"\s*\(\d+\)")


def work_key(source_path: str | None) -> str:
    """DBNL text id from a source path, for `_WORK_REGIME` lookup."""
    if not source_path:
        return ""
    name = str(source_path).strip().rsplit("/", 1)[-1]
    name = _WORK_KEY_RE.sub("", name)
    return name.removesuffix(".xml")

# First match wins; recipe before literary (overlap in titles).
_TITLE_PATTERNS: list[tuple[TextRegime, re.Pattern[str]]] = [
    (
        TextRegime.RECIPE_PRACTICE,
        re.compile(
            # koock/kevken: historical o-doubling and u/v interchange.
            # heerl...konst: needs the inflectional -e ("heerlijke konsten").
            r"recept|koek|ko[oc]+k|keuken|kevken|huishoud|displegt|culin|bakker|"
            r"spys|toespys|heerl(?:ijk|yke)e?\s+konst|smaak",
            re.IGNORECASE,
        ),
    ),
    (
        TextRegime.MEDICAL,
        re.compile(
            r"pharm|medic|chirurg|apotheek|heelk|genees|ziekte|chir\b",
            re.IGNORECASE,
        ),
    ),
    (
        TextRegime.TRAVEL,
        re.compile(
            r"reis|reisiger|geograph|tartarye|amerika|oost[\s-]?ind|west[\s-]?ind|"
            r"zeevaart|scheep|voyage|landen\s+van",
            re.IGNORECASE,
        ),
    ),
    (
        TextRegime.ADMIN_TRADE,
        re.compile(
            r"marchand|handel|koopman|comptoir|compagnie|staten|ordonnant|"
            r"dialog.*marchand",
            re.IGNORECASE,
        ),
    ),
    (
        TextRegime.SCIENTIFIC,
        re.compile(
            r"natuurk|natuurlyke\s+historie|encyclop|botan|historie\s+van\s+d",
            re.IGNORECASE,
        ),
    ),
    (
        TextRegime.LITERARY,
        re.compile(
            r"letteroefen|vermaak|verhaal|roman|dicht|blijspel|tijdspiegel|"
            r"huisvriend|juffertje|tooneel|boeck\s+van",
            re.IGNORECASE,
        ),
    ),
]


def infer_text_regime(
    *,
    corpus: str | None = None,
    title: str | None = None,
    source_path: str | None = None,
    text_regime: str | TextRegime | None = None,
) -> TextRegime:
    """Infer document regime from corpus id and/or source metadata."""
    if text_regime is not None and str(text_regime).strip():
        try:
            return TextRegime(str(text_regime).strip())
        except ValueError:
            pass

    # Explicit per-work calls beat both corpus defaults and title keywords:
    # keyword inference fails silently on historical spelling and inflection.
    key = work_key(source_path)
    if key and key in _WORK_REGIME:
        return _WORK_REGIME[key]

    corpus_key = (corpus or "").strip().lower()
    if corpus_key in _CORPUS_REGIME:
        return _CORPUS_REGIME[corpus_key]

    haystack = " ".join(
        part for part in (title or "", source_path or "") if part
    ).strip()
    if not haystack:
        return TextRegime.UNKNOWN

    for regime, pattern in _TITLE_PATTERNS:
        if pattern.search(haystack):
            return regime
    return TextRegime.UNKNOWN


class TextRegimeContext(BaseModel):
    """Layer-0 metadata carried on KWIC / gold rows."""

    text_regime: TextRegime = Field(default=TextRegime.UNKNOWN)
    title: str | None = None
