"""Candidate inflected forms for (historical) Dutch verbs: a *generator*, not a lexicon.

`forms_for(infinitive)` proposes finite, past and participle forms plus historical spelling variants.
Over-generation is expected: forms only matter if they occur in the texts, and every form goes through
the verb check (V0) and Rik's review (plans/steps/VERB_LEXICON.md) before it can trigger anything.

Weak verbs follow the rules: stem, stem+t, 't kofschip for -te/-de, ge-…-t/-d. Strong and irregular verbs
come from `IRREGULAR`, which is hand-written and covers the strong verbs in the frame lexicon.
"""

from __future__ import annotations

import re

_VOWELS = "aeiouy"
_PREFIX_NO_GE = ("be", "ge", "ver", "ont", "her", "er")
_SEPARABLE = ("in", "op", "af", "uit", "uyt", "aan", "aen", "toe", "door", "doer", "over", "mede", "mit", "weg")
_KOFSCHIP = set("tkfsp") | {"ch", "x"}

# lemma (modern-ish infinitive) -> forms (present 3sg, past sg/pl, participle). Historical spellings are
# added by `_variants`, so only one spelling is needed here.
IRREGULAR: dict[str, tuple[str, ...]] = {
    "eten": ("eet", "at", "aten", "gegeten", "geeten"),
    "drinken": ("drinkt", "dronk", "dronken", "gedronken"),
    "nemen": ("neemt", "nam", "namen", "genomen"),
    "innemen": ("neemt in", "ingenomen", "inneemt"),
    "geven": ("geeft", "gaf", "gaven", "gegeven"),
    "doen": ("doet", "deed", "deden", "gedaan"),
    "braden": ("braadt", "briet", "brieden", "gebraden"),
    "bakken": ("bakt", "bakte", "gebakken"),
    "sieden": ("siedt", "sood", "soden", "gesoden"),
    "zieden": ("ziedt", "zood", "zoden", "gezoden"),
    "schenken": ("schenkt", "schonk", "schonken", "geschonken"),
    "smelten": ("smelt", "smolt", "smolten", "gesmolten"),
    "gieten": ("giet", "goot", "goten", "gegoten"),
    "genezen": ("geneest", "genas", "genazen", "genezen"),
    "genieten": ("geniet", "genoot", "genoten"),
    "snijden": ("snijdt", "sneed", "sneden", "gesneden"),
    "wassen": ("wast", "wiesch", "gewassen"),
    "breken": ("breekt", "brak", "braken", "gebroken"),
    "wegen": ("weegt", "woog", "wogen", "gewogen"),
    "verslinden": ("verslindt", "verslond", "verslonden"),
    "zuigen": ("zuigt", "zoog", "zogen", "gezogen"),
    "kauwen": ("kauwt", "kauwde", "gekauwd"),
    "brouwen": ("brouwt", "brouwde", "gebrouwen"),
    "malen": ("maalt", "maalde", "gemalen"),
    "zouten": ("zoutte", "gezouten"),
    "bewaren": ("bewaart", "bewaarde", "bewaard"),
    "drogen": ("droogt", "droogde", "gedroogd"),
    "smaken": ("smaakt", "smaakte", "gesmaakt"),
    "proeven": ("proeft", "proefde", "geproefd"),
    "voeden": ("voedt", "voedde", "gevoed"),
    "slikken": ("slikt", "slikte", "geslikt"),
    "trekken": ("trekt", "trok", "trokken", "getrokken"),
    "steken": ("steekt", "stak", "staken", "gestoken"),
    "laten": ("laat", "liet", "lieten", "gelaten"),
    "houden": ("houdt", "hield", "hielden", "gehouden"),
    "helpen": ("helpt", "hielp", "hielpen", "geholpen"),
}


def _stem(inf: str) -> str:
    """Infinitive -> written stem: bakken -> bak, koken -> kook, leven -> leef, lezen -> lees."""
    if not inf.endswith("en") or len(inf) < 4:
        return inf
    s = inf[:-2]
    if len(s) >= 2 and s[-1] == s[-2] and s[-1] not in _VOWELS:
        return s[:-1]                                    # bakken -> bak
    if s.endswith(("ij", "ui", "uy", "ou", "au", "ei", "oe", "ie", "eu", "ae", "aa", "ee", "oo", "uu")):
        stem = s
    elif len(s) > 4 and s.endswith(("er", "el", "em")):
        stem = s                                         # unstressed schwa syllable: roosteren -> rooster
    elif len(s) >= 2 and s[-2] in _VOWELS and s[-1] not in _VOWELS and (len(s) < 3 or s[-3] not in _VOWELS):
        stem = s[:-1] + s[-2] + s[-1]                     # open syllable: koken -> kook
    else:
        stem = s
    if stem.endswith("v"):
        stem = stem[:-1] + "f"
    elif stem.endswith("z"):
        stem = stem[:-1] + "s"
    return stem


def _split_prefix(inf: str) -> tuple[str, str]:
    for p in sorted(_SEPARABLE, key=len, reverse=True):
        if inf.startswith(p) and len(inf) - len(p) >= 4:
            return p, inf[len(p):]
    return "", inf


def _weak(inf: str) -> set[str]:
    prefix, base = _split_prefix(inf)
    raw = base[:-2] if base.endswith("en") else base
    stem = _stem(base)
    voiceless = raw[-1:] in _KOFSCHIP or raw[-2:] in _KOFSCHIP
    past = "te" if voiceless else "de"
    pp_end = "t" if voiceless else "d"
    ge = "" if base.startswith(_PREFIX_NO_GE) else "ge"
    pp_stem = stem if not stem.endswith(pp_end) else stem[:-1]
    finite = {stem, stem if stem.endswith("t") else stem + "t", stem + past, stem + past + "n"}
    if stem.endswith("d"):
        finite.add(stem + "t")                           # bereidt, braadt
    # Separable verbs: the bare finite forms ("maakt ... in") belong to the base verb's lemma, not this
    # one, so only the joined forms are proposed here.
    out = {prefix + f for f in finite} if prefix else finite
    out.add(prefix + ge + pp_stem + pp_end)
    # older texts write the participle with -t where modern spelling has -d, and the reverse (gemengt, bewaart)
    out.add(prefix + ge + pp_stem + ("d" if pp_end == "t" else "t"))
    return out


def _variants(form: str) -> set[str]:
    """Historical spellings: ck/k, y/ij, ae/aa, uy/ui, gh-, dt/t, oo/o and ee/e doubling."""
    out = {form}
    for a, b in (("ij", "y"), ("aa", "ae"), ("ui", "uy")):
        out |= {f.replace(a, b) for f in list(out) if a in f}
    out |= {("z" if f[0] == "s" else "s") + f[1:] for f in list(out)
            if f[:1] in ("s", "z") and f[1:2] in tuple(_VOWELS)}                                  # sieden/zieden
    out |= {f.replace("kk", "ck") for f in list(out) if "kk" in f}                            # bakken -> backen
    out |= {re.sub(r"(?<=[aeiou])k(?![kc])", "ck", f) for f in list(out)}                     # bakt -> backt
    out |= {re.sub(r"^ge", "ghe", f) for f in list(out) if f.startswith("ge")}
    # open syllable spelled with a double vowel in older texts, and the reverse: koken <-> kooken
    # (not in the prefixes ge-/ghe-/be-: "geegeeten")
    out |= {re.sub(r"(?<![aeiou])(?<!^g)(?<!^gh)(?<!^b)([aeo])(?=[^aeiou][aeiou])", r"\1\1", f) for f in list(out)}
    out |= {re.sub(r"(?<![aeiou])(aa|ee|oo)(?=[^aeiou][aeiou])", lambda m: m.group(1)[0], f) for f in list(out)}
    return {f for f in out if f}


def forms_for(infinitive: str) -> dict[str, str]:
    """form -> kind ('lemma', 'irregular' or 'rule'). Includes the infinitive's own variants."""
    inf = infinitive.strip().lower()
    out: dict[str, str] = {}
    for v in _variants(inf):
        out.setdefault(v, "lemma")
    modern = inf.replace("ae", "aa").replace("y", "ij").replace("ck", "k").replace("uy", "ui")
    irregular = IRREGULAR.get(inf) or IRREGULAR.get(modern)
    # irregular verbs still have a regular stem/imperative and 1sg (drink, neem): add it to the table's forms
    base_forms = (set(irregular) | {_stem(inf)}) if irregular else _weak(inf)
    kind = "irregular" if irregular else "rule"
    for f in base_forms:
        if " " in f:
            continue                                     # separable "neemt in": not a single token
        for v in _variants(f):
            out.setdefault(v, kind)
    return out
