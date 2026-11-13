"""Spelling keys for historical Dutch: two forms match when their keys are equal.

Ported, with permission of the project group, from `Data-Scopes/archival-language`,
`archival_language/corpus/spelling_variants.py` at commit c11f64c (2026-11-10), LotA step P1.6. Kept:

- the word rules (`RULES`) in their order. The `n_*` rules replay `normalise_spelling` from
  `formula_detection.normalisation.rewrite_historic_dutch` (formula-detection, MIT, Marijn Koolen),
  which is a dependency here. The others come from REPUBLIC phases 2.8 and 2.9 (see each rule's `source`);
- the guards: letters only and at least `MIN_LEN` letters (or a named short token), and the frequency-ratio
  guard against chance merges, stricter for short keys (`guard_merges`).

Left out: the colon abbreviations and `abbr_mogende`, which are specific to the States General resolutions.

Spelling only. Inflection is `verb_forms.forms_for`'s job; the two are complementary (VERB_LEXICON.md).
Known false merges from LotA's review: hart/hard (`t_d`), ont/ond, licht/ligt, lachen/lagen (`ch_gh`).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from formula_detection.normalisation import rewrite_historic_dutch as rh

MIN_LEN = 3
RATIO = 0.005
RATIO_SHORT = 0.04
SHORT_KEY = 4
SHORT_NAMED = frozenset({"hy", "wy", "my", "zy", "gy", "sy"})

SRC_N = "formula_detection.normalisation.rewrite_historic_dutch.normalise_spelling"
SRC_28 = "republic-classification scripts/phase2_8/step03b_lib.py (RULES, FOLD_ORDER)"
SRC_29 = "republic-classification scripts/phase2_9/step01_alternations.py (NEW, FAMILIES)"


@dataclass(frozen=True)
class Rule:
    name: str
    source: str
    description: str
    func: Callable[[str], str]


def _sub(pat: str, rep: str) -> Callable[[str], str]:
    rx = re.compile(pat)
    return lambda w: rx.sub(rep, w)


def _chain(trigger: Callable[[str], bool], fn: Callable[[str], str]) -> Callable[[str], str]:
    return lambda w: fn(w) if trigger(w) else w


RULES: list[Rule] = [
    Rule("sch_s", SRC_29, "adjective-final -sch -> -s after n, l, d", _sub(r"(?<=[nld]s)ch$", "")),
    Rule("n_ck", SRC_N, "ck -> k / kk by context", _chain(lambda w: "ck" in w, rh.replace_ck)),
    Rule("n_ae", SRC_N, "ae -> aa by context", _chain(lambda w: "ae" in w.lower(), rh.replace_ae)),
    Rule("n_gh", SRC_N, "gh -> g / ch by context", _chain(lambda w: "gh" in w, rh.replace_gh)),
    Rule("n_uy", SRC_N, "uy -> ui / uu by context", _chain(lambda w: "uy" in w.lower(), rh.replace_uy)),
    Rule("n_ey", SRC_N, "ey -> ei by context", _chain(lambda w: "ey" in w.lower(), rh.replace_ey)),
    Rule("n_y", SRC_N, "y -> ij / i by context", _chain(lambda w: "y" in w.lower(), rh.replace_y)),
    Rule("n_t", SRC_N, "final -dt, -heit, -lant(dt) -> -d, -heid, -land",
         _chain(lambda w: w.lower().endswith("t"), rh.replace_t)),
    Rule("ij_y", SRC_28, "ij = y", _sub(r"ij", "y")),
    Rule("ch_gh", SRC_28, "ch -> gh (with gh_g gives cht -> gt)", _sub(r"ch", "gh")),
    Rule("gh_g", SRC_28, "gh -> g", _sub(r"gh", "g")),
    Rule("ck_k", SRC_28, "ck -> k", _sub(r"ck", "k")),
    Rule("ae_aa", SRC_28, "ae -> aa", _sub(r"ae", "aa")),
    Rule("ey_ei", SRC_28, "ey -> ei at the ij = y level", _sub(r"ey", "ei")),
    Rule("uy_ui", SRC_28, "uy -> ui", _sub(r"uy", "ui")),
    Rule("u_v", SRC_29, "medial u -> v before a, e, o", _sub(r"(?<=[bcdefhklmnprstwz])u(?=[aeo])", "v")),
    Rule("z_s_medial", SRC_29, "medial s -> z between vowels", _sub(r"(?<=[aeiouy])s(?=[aeiouy])", "z")),
    Rule("vowel_double", SRC_28, "open-syllable doubling a, e, o -> aa, ee, oo",
         _sub(r"(?<![aeo])([aeo])(?=[^aeiouy][aeiouy])(?!ren)", r"\1\1")),
    Rule("eren_eeren", SRC_28, "eren -> eeren", _sub(r"(?<!e)eren", "eeren")),
    Rule("dt_d", SRC_28, "final dt -> d (also covers dt_t)", _sub(r"dt$", "d")),
    Rule("t_d", SRC_28, "final t -> d after n, r, y", _sub(r"(?<=[nry])t$", "d")),
    Rule("ff_f", SRC_28, "final ff -> f", _sub(r"ff$", "f")),
    Rule("s_z", SRC_28, "initial s -> z", _sub(r"^s", "z")),
]
RULE_NAMES = [r.name for r in RULES]


def eligible(term: str) -> bool:
    return term in SHORT_NAMED or (term.isalpha() and len(term) >= MIN_LEN)


def key_word(term: str, skip: frozenset[str] = frozenset()) -> tuple[str, tuple[str, ...]]:
    """Normalised key of one lower-cased term, and the rules that changed it (in order).

    `skip` leaves rules out, for the per-rule leave-one-out check."""
    if not eligible(term):
        return term, ()
    w, fired = term, []
    for r in RULES:
        if r.name in skip:
            continue
        w2 = r.func(w)
        if w2 != w:
            fired.append(r.name)
            w = w2
    return w, tuple(fired)


def key(term: str) -> str:
    return key_word(term.lower())[0]


def guard_merges(counts: Mapping[str, int], ratio: float = RATIO) -> dict[str, str]:
    """term -> group key, with LotA's ratio guard: a member whose count is below `ratio` (`RATIO_SHORT` for
    keys of `SHORT_KEY` letters or fewer) of its group's largest member keeps its own key (prefixed `~`)."""
    keys = {t: key(t) for t in counts}
    gmax: dict[str, int] = defaultdict(int)
    for t, k in keys.items():
        gmax[k] = max(gmax[k], counts[t])
    out = {}
    for t, k in keys.items():
        thr = max(ratio, RATIO_SHORT) if len(k) <= SHORT_KEY else ratio
        out[t] = ("~" + t) if counts[t] < thr * gmax[k] and counts[t] < gmax[k] else k
    return out


_DOUBLE_CONS = re.compile(r"([^aeiouy])\1+")


def loose_key(term: str) -> str:
    """Our addition (not LotA's): the key with doubled *consonants* squeezed and the prefix doubling undone.

    LotA's key keeps two doublings apart that matter for verb forms: `vowel_double` also hits the ge-
    prefix (gekookt -> geekookt) and `n_ck` writes kk (gheckoockt -> gekkookt). Vowel length is left alone:
    squeezing vowels merged naam/nam (13 Nov check), and the LotA key already normalises vowel length in
    open syllables."""
    k = key(term)
    k = re.sub(r"^(ver|be|ont|toe|in|op|af|uit|door|over)?gee(?=[^aeiouy])", lambda m: (m.group(1) or "") + "ge", k)
    return _DOUBLE_CONS.sub(r"\1", k)
