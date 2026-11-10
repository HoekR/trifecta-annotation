"""N1 of plans/steps/INDIES_NAMES.md: Dutch vs Malay food names in DBNL, 1750-1889.

(The public-domain DBNL TEI set ends in 1889; the --to default of 1920 just covers it.)

Bridges the gap before the first Indies cookbook (Samarang 1870): did the
Malay names (ketoembar, lombok, santen ...) already circulate in Dutch texts,
and in which genres? Counts only, no annotation: the question is which word,
where and when.

Same concepts as `NAME_PAIRS` in `scripts/export_food_harvest.py`, but with
**stricter Malay patterns**, because general prose has homonyms the cookbooks
do not: *Lombok* the island (1894 expedition), *Santen* the town (Xanten),
*klapper* = index / to clatter, *santen* = saints, *Santander*, German
*taugen*, the river Toelang Bawang (all found in the first run's samples). So:
lombok lowercase only, klapper only in compounds, santan / tauge whole words,
santen not counted. Every Malay hit keeps a context sample, to be read before the
numbers are trusted.

Reads the DBNL TEI zip (`dbnl_xml`) and the per-work year from
`dbnl_work_genre`; writes `indies_names_dbnl` (one row per work x concept with
a hit) and `indies_names_dbnl_samples`. Read-only on everything else.

    uv run python scripts/indies_names_dbnl.py [--from 1750 --to 1920]
"""

from __future__ import annotations

import argparse
import html
import re
import time
import zipfile
from collections import defaultdict

from data_io import resolve
from data_io.jsonl_io import save_semi_structured

from trifecta_annotation.catalogue_genre import reporting_genre
from trifecta_annotation.corpus_genre_join import load_genre_records
from trifecta_annotation.dbnl_genre import work_stem, xml_filenames_by_stem

SCRIPT = "scripts/indies_names_dbnl.py"
OUT, SAMPLES = "indies_names_dbnl", "indies_names_dbnl_samples"

# (concept, Dutch pattern, Malay pattern); (?-i:...) = case-sensitive part
PAIRS = [
    ("coriander", r"koriander|coriander", r"ketoembar|ketumbar"),
    ("chili", r"spaansche peper|spaanse peper", r"(?-i:lombok)|tjabe|tjabé"),
    ("coconut", r"kokos|cocos", r"klapper(?:boom|boomen|bomen|noot|noten|olie|melk|water|vleesch|vlees|dop|bast|tuin)|kelapa"),
    # "santen" dropped: in DBNL prose it is the archaic plural of "sant" (saints), all 63 samples
    ("coconut milk", r"kokosmelk|klappermelk", r"santan\b"),
    ("onion/shallot", r"sjalot|chalot|ajuin|uien|uijen|uyen|knoflook", r"(?<!toelang )(?<!toelang-)(?:bawang|brambang)"),
    ("bean sprouts", r"bonenkiemen", r"(?:taug[eé]|taoge)\b"),  # bare prefix hit German taugen
    ("ginger", r"gember", r"djahe"),
    ("cloves", r"kruidnagel", r"tjengkeh|tjengke"),
    ("cinnamon", r"kaneel|caneel", r"kajoe.?manis"),
]
COMP = [(c, re.compile(r"\b(?:" + d + r")", re.I), re.compile(r"\b(?:" + m + r")", re.I)) for c, d, m in PAIRS]
TAG = re.compile(r"<[^>]+>")
SAMPLES_PER_TERM_WORK = 3


def plain(xml: str) -> str:
    body = xml.split("<body", 1)[-1]  # skip the TEI header (catalogue text, not the work)
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", body))).replace("ſ", "s")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="y0", type=int, default=1750)
    ap.add_argument("--to", dest="y1", type=int, default=1920)
    a = ap.parse_args()

    zip_path = resolve("dbnl_xml")
    files = xml_filenames_by_stem(zip_path)
    works, seen = [], set()
    for r in load_genre_records():
        if r.get("id_scheme") != "dbnl_ti_id" or not r.get("year") or not (a.y0 <= r["year"] <= a.y1):
            continue
        stem = work_stem(r["ti_id"])
        if stem in files and stem not in seen:
            seen.add(stem)
            works.append((stem, files[stem], r.get("titel") or stem, r["year"]))
    print(f"{len(works)} DBNL works with TEI, {a.y0}-{a.y1}", flush=True)

    rows, samples, t0 = [], [], time.monotonic()
    with zipfile.ZipFile(zip_path) as archive:
        for i, (stem, fn, title, year) in enumerate(works, 1):
            text = plain(archive.read(fn).decode("utf-8", errors="replace"))
            words = len(text.split())
            genre, genre_source = reporting_genre(corpus=None, title=title, source_path=fn)
            for concept, d, m in COMP:
                nd, mh = len(d.findall(text)), list(m.finditer(text))
                if not nd and not mh:
                    continue
                rows.append({"source": "dbnl", "unit": title, "work_id": stem, "year": year,
                             "decade": year // 10 * 10, "genre": genre, "genre_source": genre_source,
                             "denominator": words, "denominator_unit": "words", "concept": concept,
                             "dutch": nd, "malay": len(mh)})
                per_term = defaultdict(int)
                for h in mh:
                    t = h.group(0).lower()
                    if per_term[t] < SAMPLES_PER_TERM_WORK:
                        per_term[t] += 1
                        samples.append({"work_id": stem, "title": title, "year": year, "genre": genre,
                                        "concept": concept, "term": h.group(0),
                                        "context": text[max(0, h.start() - 120):h.end() + 120]})
            if i % 500 == 0 or i == len(works):
                print(f"  {i}/{len(works)} works ({(time.monotonic() - t0) / 60:.1f} min)", flush=True)

    save_semi_structured(rows, logical_name=OUT, parent_sources=["dbnl_xml", "dbnl_work_genre"],
                         description=f"Dutch vs Malay food-name counts per DBNL work x concept, {a.y0}-{a.y1}",
                         script=SCRIPT)
    save_semi_structured(samples, logical_name=SAMPLES, parent_sources=[OUT],
                         description="Context samples of every Malay-name hit (max 3 per term per work)", script=SCRIPT)
    print(f"wrote {len(rows)} work x concept rows, {len(samples)} Malay samples")


if __name__ == "__main__":
    main()
