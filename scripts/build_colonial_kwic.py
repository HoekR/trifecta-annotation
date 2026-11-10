"""Build KWIC inputs from the colonial/new-DBNL texts secured this session.

These texts have never been through the project's `food_snippets` pipeline
(the `historic-matcher` package that built it lives in a sibling repo, out of
scope to pull in here). This is a compact, local re-implementation of the same
job: word-boundary match against `food_terms` (Food_terms.csv, Pref_label +
Alt_label), cut a `DEFAULT_KWIC_CONTEXT_RADIUS`-char window around each hit,
emit one KwicInput-shaped record per hit — same shape
`adapters/food_snippets.py` produces, so the existing Step A/B/C pipeline and
`trifecta-batch` can run over it unmodified.

Two input kinds:
- **TEI XML** (the 9 new DBNL works found this session) — tags stripped with a
  regex, not a full TEI parser; good enough to find food-term windows, not
  good enough for anything that needs structure (headings, page breaks).
- **Plain OCR text** (Dodoens `frk`, and the colonial books with an already
  usable text layer) — read as-is. Reize gets the `fch`->`sch` repair for its
  long-s OCR artifact (see docs/CORPUS_ACQUISITION.md) before matching.

    uv run python scripts/build_colonial_kwic.py --summary
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from data_io import resolve
from data_io.jsonl_io import save_semi_structured

from trifecta_annotation.adapters.food_snippets import DEFAULT_KWIC_CONTEXT_RADIUS
from trifecta_annotation.clear_frame_examples import score_snippet_for_frame
from trifecta_annotation.corpus_genre_join import load_genre_records
from trifecta_annotation.dbnl_genre import sweep_candidates, work_stem, xml_filenames_by_stem
from trifecta_annotation.frame_verbs import find_frame_verbs_in_text
from trifecta_annotation.structural_parse import DocumentUnit, document_structural_units, unit_for_offset
from trifecta_annotation.tei_segmentation import attach_tei_scope_to_rows, entry_for_offset, render_tei
from trifecta_annotation.text_regime import TextRegime, infer_text_regime
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

# Uniform cap for brand-new sources only (the full genre-agnostic DBNL sweep,
# the 3 previously-unwired colonial_books .txt files, the Van Lennep diary).
# Decided with Rik: measured full-corpus scan density (~3.1M raw hits) vs.
# measured cascade throughput (~4-12 sec/row) puts a few-days LLM budget at
# ~30-50k rows; 3,655 works x 10 ~= 36,550 worst case. Does NOT apply
# retroactively to the already-annotated NEW_DBNL_WORKS/COLONIAL_BOOKS/Dodoens
# sources below — those already ran uncapped and recapping them now would only
# shrink already-paid-for coverage for no benefit.
DEFAULT_SWEEP_CAP = 10
# Separate budget for entry-scope rows in structured RECIPE/MEDICAL works —
# see `capped_candidates`.
DEFAULT_ENTRY_SCOPE_CAP = 500

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

# work_id -> (title, year) for the 9 new-DBNL works (TEI available, see
# docs/CORPUS_ACQUISITION.md "Not needed by hand" list).
NEW_DBNL_WORKS: dict[str, tuple[str, int]] = {
    "blan012kart01": ("De Kartesiaanse academie ofte, institutie der medicyne", 1683),
    "blan012nede01": ("Den Neder-landschen herbarius ofte kruid-boek", 1698),
    "pitt003list01": ("List en bedrog der medicynen", 1705),
    "_pha002phar01": ("Pharmacopoea Roterodamensis Galeno-Chymica", 1709),
    "verb122chir01": ("Chirurgyns scheeps-Kist", 1723),
    "ruys009alle01": ("Alle de ontleed- genees- en heelkundige werken", 1744),
    "krie024bata02": ("Bataviasche apotheek", 1746),
    "_ams007amst01": ("De Amsterdamsze gaare-keuken", 1796),
    "_aan004aanw01": ("Aanwijzingen tot het gebruik der medicynen voor zeevarenden", 1839),
}

# filename (under colonial_books) -> (title, year, needs_fch_repair)
COLONIAL_BOOKS: dict[str, tuple[str, int | None, bool]] = {
    "specerijen_1882.pdf": ("Specerijen", 1882, False),
    "thee.pdf": ("Thee", None, False),
    "Reize naar Surinamen_dl1.pdf": ("Reize naar Surinamen, Deel 1", 1800, True),
    "Reize naar Surinamen_dl4.pdf": ("Reize naar Surinamen, Deel 4", 1800, True),
}

# 3 colonial_books entries with ready OCR .txt, never wired in before
# (docs/CORPUS_ACQUISITION.md already calls these out as "already ship OCR
# .txt beside the PDF" — confirmed present via `ls`, no new acquisition
# needed). filename -> (title, year).
EXTRA_COLONIAL_TXT: dict[str, tuple[str, int | None]] = {
    "Nuttige Indische planten_953710.txt": ("Nuttige Indische planten", 1894),
    # Dated 6 Nov 2026 (previously None). Full title "Insulinde: Schetsen van
    # land en volk van Nederlandsch O.-Indië" (Wouters, Van Hulzen & Koning,
    # Noordhoff). Its own preface is signed "J. Koning. Wijk-aan-Zee, Voorjaar
    # 1924."; matches both a bibliographic record for this exact anthology and
    # Delpher's own catalog entry ("Insulinde » 1924").
    "insulinde_983061.txt": ("Insulinde", 1924),
    # Dated 6 Nov 2026 (previously None). By Frederica Johanna van Uildriks
    # (Haarlem: H.D. Tjeenk Willink). The text's own latest cited year is 1893;
    # confirmed via web search as this exact title/author/publisher, 1893.
    "Beelden_uit_Nederlandsch_Indie_961013.txt": ("Beelden uit Nederlandsch Indie", 1893),
}

# KB/Delpher-digitized cookbooks acquired 2026 (real recipe-practice content —
# the H1 full DBNL sweep confirmed it finds none of this: every RECIPE_PRACTICE
# title-keyword hit there turned out to be verse/drama, not a cookbook; see
# `trifecta_annotation/text_regime.py`'s H1-false-positive overrides). Already
# have a usable OCR text layer (CCS docWorks / iTextSharp producers), no
# re-OCR needed. filename (under colonial_books_ocr/acquisitions) -> (title, year).
KB_COOKBOOKS_2026: dict[str, tuple[str, int | None]] = {
    "mmkb18_002953000_pdf.pdf": ("Visser's Nederlandsch-Indisch vegetarisch kookboek", 1911),
    "mmkb18a_013242000_pdf.pdf": ("Kwatta's groot kookboek", 1910),
    "mmkb18a_013925000_pdf.pdf": ("Het nieuwste kookboek", 1907),
    "mmkb18a_022522000_pdf.pdf": ("Geïllustreerd kookboek", 1909),
    "mmkb31_043972000_pdf.pdf": ("Oost-Indisch kookboek", 1913),
    # Dated 6 Nov 2026 (previously None). Full title "Kookboek voor de fijnere
    # keuken, Nieuw Haagsch Kookboek" by Mevr. C. M. Wilderink-Jansen (Van
    # Holkema & Warendorf). Preface in the scanned text itself is signed "DEN
    # HAAG, October 1900", corroborated by three independent antiquarian
    # listings (AbeBooks, antiqbook.nl, egidiusamsterdam.com) describing a
    # "1900 First Edition". Delpher's own catalog record for this exact scan
    # (MMSFKB02:000035287) gives "[1890]" — square brackets mean an *estimated*
    # date, and it is a year before the book's own signed preface, so treated
    # here as a probable cataloging error rather than used.
    "mmsfkb02_000035287_pdf.pdf": ("Kookboek voor de fijnere keuken", 1900),
    # Dated 6 Nov 2026 (previously None). A distinct work from the 1907
    # "Het nieuwste kookboek" above despite the identical generic title — a
    # different, shorter booklet with different regional advertisers (Delft vs.
    # Rotterdam/Den Haag), by a different author. Its own cover states "Premie
    # op Warendorfs Geïll. familie-Kalender voor 1906" (a premium given away
    # with the 1906 illustrated family calendar); web search independently
    # identifies this edition as by M.M. Gunst-van Houten, Van Holkema &
    # Warendorf, 1906, confirming the cover date rather than the calendar's
    # usual autumn-before-cover-year print convention.
    "mmsfkb02_000036589_pdf.pdf": ("Het nieuwste kookboek (kort)", 1906),
}

# 5 of the 7 above have a scrambled embedded text layer (words correct,
# reading order nonsense, throughout the whole document — found during
# SENTENCE_HARVEST.md's RECIPE_SIEVE position-check verification; `mmsfkb02*`
# is unaffected). Re-OCR'd with `ocr_colonial_pdf.py` (-l nld --psm 3, which a
# single-page proof-of-concept confirmed fixes the reading order). Maps
# KB_COOKBOOKS_2026's filename to the re-OCR text's book slug.
KB_COOKBOOKS_REOCR: dict[str, str] = {
    "mmkb18_002953000_pdf.pdf": "visser",
    "mmkb18a_013242000_pdf.pdf": "kwatta",
    "mmkb18a_013925000_pdf.pdf": "nieuwste",
    "mmkb18a_022522000_pdf.pdf": "geillustreerd",
    "mmkb31_043972000_pdf.pdf": "oost_indisch",
}

# Google Books acquisitions 2026 (same acquisitions folder, different source/
# producer than the KB/Delpher scans above). "Vervolg op M. Noël Chomel" is a
# direct sequel to chom003huis01 (Huishoudelyk woordboek) — already the single
# largest source in trifecta_annotations, so this is a high-value addition.
GOOGLE_BOOKS_2026: dict[str, tuple[str, int | None]] = {
    "De_volmaakte_Geldersche_keuken_meid_onde.pdf": ("De volmaakte Geldersche keuken-meid", 1756),
    "Nieuwe_beproefde_en_wel_ondersochte_gene.pdf": ("Nieuwe beproefde en wel ondersochte genees-middelen (Digby)", 1680),
    # Dated 6 Nov 2026 (previously None). This scan is specifically Volume XIV
    # of de Chalmot's 9+-volume continuation (1786-93), not a single-dated
    # work -- "Zynde het XIV. DEEL van het WOORDENBOEK", imprint "TE CAMPEN by
    # J.A. DE CHALMOT, AMSTELDAM by J. YNTEMA, MDCCXCIL" (OCR-mangled
    # MDCCXCII). Independently confirmed: DBNL's own Vaderlandsche
    # Letteroefeningen, Jaargang 1792, lists "Veertiende Stuk. Te Campen by
    # J.A. de Chalmot, en te Amsterdam by J. Yntema" published 1792 -- same
    # publishers, same place, same volume number.
    "Vervolg_op_M_Noël_Chomel_Algemeen_huish.pdf": ("Vervolg op M. Noël Chomel, Algemeen huishoudelyk-woordenboek (XIV. Deel)", 1792),
}

# Google Books batch of 9 Nov 2026 (Rik, ~/Downloads/kookboeken; 10 works), staged under
# colonial_books_ocr/acquisitions/google_books_2026_11/ as PDF + text. The text
# was extracted with pdftotext from page 2: page 1 is Google's "Over dit boek"
# disclaimer, the rest carries no Google text. The OCR is good enough for
# harvesting (no re-OCR; lower scores of the medical and pastry books reflect
# vocabulary, not OCR). Years: from the title pages (1870, 1872, 1893), the
# prefaces (Betje: 8th printing, prefaces Aug 1887 and May 1890, so >= 1890,
# recorded as 1890) and Rik for the rest. filename -> (title, year).
GOOGLE_BOOKS_2026_11_DIR = "acquisitions/google_books_2026_11"
# Wannée, Kookboek van de Amsterdamsche Huishoudschool: editions missing from LDK2025/corpus.
# Raw PDF text (see the folder README); used for name counts, not annotated.
WANNEE_2026_11_DIR = "acquisitions/wannee_2026_11"
WANNEE_2026_11: dict[str, tuple[str, int]] = {
    "cookbook_1911.txt": ("Kookboek Amsterdamsche Huishoudschool 1911 (PDF text)", 1911),
    "cookbook_1920.txt": ("Kookboek Amsterdamsche Huishoudschool 1920 (PDF text)", 1920),
}
GOOGLE_BOOKS_2026_11: dict[str, tuple[str, int | None]] = {
    "Oost_Indisch_kookboek.pdf": ("Oost-Indisch kookboek (tweede druk)", 1870),
    "Oost_Indisch_kookboek_bevattende_meer_da.pdf": ("Oost-Indisch kookboek, bevattende meer dan ... recepten", 1893),
    "Indisch_kookboek.pdf": ("Indisch kookboek (Gallas Haak-Bastiaanse)", 1872),
    "Betje_de_goedkoope_keukenmeid.pdf": ("Betje, de goedkoope keukenmeid (8e druk)", 1890),
    "Het_boek_der_banketbakkerij.pdf": ("Het boek der banketbakkerij (Gouffé)", 1878),
    "Kookboek_voor_gezonden_en_zieken.pdf": ("Kookboek voor gezonden en zieken (Wiel)", 1875),
    "De_nieuwe_geneeskunde_zonder_medicijnen.pdf": ("De nieuwe geneeskunde zonder medicijnen (Kuhne)", 1893),
    "Medische_verhandelingen.pdf": ("Medische verhandelingen (Allinson)", 1892),
    # Nijmegen, A. van Goor, "I. Deel"; year 1790 per Rik (Google Books KW2sHpXGCNAC).
    # 18th-century print: long s (ſ) replaced by s in the staged text, the PDF is
    # untouched; some ſ is OCR'd as f ("Citroen-foep"), which this cannot repair.
    "De_nieuwe_in_en_buitenlandsche_kock_of_v.pdf": ("De nieuwe in- en buitenlandsche kock (I. Deel)", 1790),
    # KNIL regulations; Rik: 1874 or 1879, recorded as the earlier. Mostly tables.
    "Algemeene_orders_reglementen_en_instruct.pdf": ("Algemeene orders, reglementen en instructiën", 1874),
}

# Place of printing for cookbooks where it is a variable of interest: an Indies
# cookbook printed in the Netherlands (Nijmegen 1872) writes 'Spaansche peper'
# where the Samarang editions write 'lombok'. Keyed by title.
PLACE_OF_PRINT: dict[str, str] = {
    "Oost-Indisch kookboek (tweede druk)": "Samarang",
    "Oost-Indisch kookboek, bevattende meer dan ... recepten": "Samarang",
    "Oost-Indisch kookboek": "Samarang",                       # KB copy, 1913
    "Indisch kookboek (Gallas Haak-Bastiaanse)": "Nijmegen",
    "De nieuwe in- en buitenlandsche kock (I. Deel)": "Nijmegen",
    "Betje, de goedkoope keukenmeid (8e druk)": "Gouda",
    "Het boek der banketbakkerij (Gouffé)": "Rotterdam",
}

# Extracted for the §9f structural-density check (447k chars), never
# food-scanned since. The folder holds the diplomatic edition as .docx/.epub,
# not .txt — this is the file whose own name matches the folder's
# "diplomatische editie compleet" label (not the sibling vlennep+hogendorp.docx,
# a different work).
VAN_LENNEP_DIARY_DIR = "Jacob van Lennep Dagboek 1823 diplomatische editie compleet (1347)"
VAN_LENNEP_DIARY_FILE = "Jacob van Lennep Dagboek 1823 diplomatisch - Marita Mathijsen.docx"
VAN_LENNEP_TITLE = "Jacob van Lennep Dagboek 1823"
VAN_LENNEP_YEAR = 1823

# The 2 hand-downloaded scholarly editions (build_handdownload_kwic.py) use
# different work_ids than the PD dump's facsimile-only originals (see
# docs/CORPUS_ACQUISITION.md "Facsimile-only in the PD dump"), so they would
# not collide with the dynamic sweep's `has_xml` candidates anyway — excluded
# here defensively, not because of a measured collision.
_HANDDOWNLOAD_STEMS = {work_stem("fren007tbou01"), work_stem("_not001nota01")}


def _extract_docx_text(docx_path: Path) -> str:
    """word/document.xml stripped the same way TEI is — no python-docx
    dependency needed for a scan that doesn't care about structure."""
    with zipfile.ZipFile(docx_path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    return strip_tei(xml)


def ingested_dbnl_stems() -> set[str]:
    """Work stems already in the corpus: the original 61 (via
    `trifecta_annotations`' own provenance) + the 9 hand-picked NEW_DBNL_WORKS
    + the 2 handdownload editions. Read fresh each run rather than hardcoded,
    so this doesn't drift as the corpus grows."""
    stems = set(NEW_DBNL_WORKS) | _HANDDOWNLOAD_STEMS
    stems = {work_stem(s) for s in stems}
    try:
        path = Path(resolve("trifecta_annotations"))
    except Exception:
        return stems
    if not path.exists():
        return stems
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("---"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            source_path = (record.get("provenance") or {}).get("source_path") or ""
            if source_path:
                stems.add(work_stem(Path(source_path).stem))
    return stems

_FCH = re.compile(r"\bfch")


def strip_tei(xml: str) -> str:
    return _WS.sub(" ", _TAG.sub(" ", xml)).strip()


def extract_pdf_text(pdf_path: Path) -> str:
    out = subprocess.run(["pdftotext", str(pdf_path), "-"], capture_output=True, text=True)
    return out.stdout


# Confirmed real Food_terms entries that collide with extremely common Dutch
# function/grammar words, so they would be near-100% false positives in running
# text rather than the usual ambiguous-noun case Step A is built to filter.
# "mede" = mead, but overwhelmingly hits the conjunction "mede" (also/likewise)
# — measured: 2,702 of this batch's hits, dwarfing every genuine food term.
AMBIGUOUS_FUNCTION_WORDS = frozenset({"mede"})


def build_term_pattern(terms: dict[str, str]) -> re.Pattern[str]:
    """One alternation, longest terms first so a longer match wins ties."""
    escaped = sorted(
        (re.escape(t) for t in terms if len(t) >= 3 and t not in AMBIGUOUS_FUNCTION_WORDS),
        key=len, reverse=True,
    )
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


# Genre gate for the structural-parse stage (PLAN.md "Document-level
# structural parse as a pre-Step-A stage" §2). RECIPE_PRACTICE only for now —
# MEDICAL is explicitly deferred: these new works mix formulary-style texts
# (where the cue set is known-good, e.g. _pha002phar01) with general medical
# treatises/surgical-manual layouts that have never been precision-checked,
# and §2 says MEDICAL needs its own per-work validation before inclusion.
_STRUCTURAL_PARSE_REGIMES = frozenset({TextRegime.RECIPE_PRACTICE})


def structural_units_for_document(
    text: str, *, title: str, source_path: str, corpus: str
) -> list[DocumentUnit] | None:
    """Genre-gated entry point for the structural pre-pass. None = out of scope.

    Caller (not `document_structural_units` itself) is responsible for the
    genre gate — see the warning in `structural_parse.py`'s module docstring
    about false "trusted" headers on ungated running text.
    """
    regime = infer_text_regime(corpus=corpus, title=title, source_path=source_path)
    if regime not in _STRUCTURAL_PARSE_REGIMES:
        return None
    return document_structural_units(text)


def scan_text(
    text: str,
    *,
    pattern: re.Pattern[str],
    canonical: dict[str, str],
    source_path: str,
    title: str,
    corpus: str,
    date: str | None,
    regime: TextRegime | None = None,
    radius: int = DEFAULT_KWIC_CONTEXT_RADIUS,
    units: list[DocumentUnit] | None = None,
    trust_goals: bool = False,
) -> list[dict]:
    """Forward scan for food-term mentions (unchanged), plus an optional
    backward lookup of each mention's governing structural unit.

    `trust_goals` gates whether a trusted unit's goal/wider context actually
    get used — default False ("detect but don't trust", PLAN.md §4f) until a
    precision check against real source documents of this kind has run.
    Diagnostic fields (unit id/offsets/header) are always populated when a
    unit is found, regardless of `trust_goals`, since those are safe either
    way; only `structural_goal` and the `context_text` widening are held back.
    """
    rows: list[dict] = []
    seen_spans: set[tuple[int, int]] = set()
    for match in pattern.finditer(text):
        span = match.span()
        if any(a <= span[0] < b for a, b in seen_spans):
            continue  # a longer alternation already covered this position
        seen_spans.add(span)
        surface = match.group(1)
        pref_label = canonical.get(surface.lower(), surface.lower())
        start = max(0, span[0] - radius)
        end = min(len(text), span[1] + radius)

        unit = unit_for_offset(units, span[0]) if units else None
        if unit is not None and unit.goal_trusted and trust_goals:
            context = text[unit.start : unit.end].strip()
        else:
            context = text[start:end].strip()
        if not context:
            continue

        record_id = f"{source_path}__{len(rows)}__{pref_label}"
        row: dict = {
            "record_id": record_id,
            "corpus": corpus,
            "target_word": surface,
            "context_text": context,
            "date": date,
            "source_path": source_path,
            "title": title,
            "candidate_terms": [pref_label],
            # Always set (not just when a structural unit is found) — the
            # position-stratified sieve in `capped_candidates` needs this for
            # every candidate, verb-scored or noun-fallback. See
            # plans/steps/RECIPE_SIEVE.md.
            "target_char_offset": span[0],
            # `verb_first_hits` has always written this; `scan_text` never did,
            # so every noun-fallback row shipped with no regime. That made
            # `text_regime == absent` read as "genre inference failed" when it
            # actually meant "noun-fallback row" — the two were perfectly
            # confounded in dbnl_sweep (PLAN.md §9i).
            "text_regime": regime.value if regime is not None else None,
            # Same confounding for mode: without this tag, "exclude
            # noun-fallback" could only be inferred from a missing field.
            "kwic_mode": "noun_fallback",
        }
        if unit is not None:
            row["unit_id"] = unit.unit_id
            row["unit_start"] = unit.start
            row["unit_end"] = unit.end
            row["structural_header"] = unit.header_text
            row["structural_signal"] = unit.signal
            if unit.goal_trusted and trust_goals:
                row["structural_goal"] = unit.goal_text
                row["structural_goal_inherited"] = unit.goal_inherited
        rows.append(row)
    return rows


def verb_first_hits(
    text: str,
    *,
    pattern: re.Pattern[str],
    food_terms_list: list[str],
    canonical: dict[str, str],
    source_path: str,
    title: str,
    corpus: str,
    date: str | None,
    regime: TextRegime,
    radius: int = DEFAULT_KWIC_CONTEXT_RADIUS,
    units: list[DocumentUnit] | None = None,
    trust_goals: bool = False,
    max_scored: int = 3000,
) -> list[tuple[int, dict]]:
    """Verb/indication-anchored candidates ("collocation with the verbs
    first", per Rik) — reuses `clear_frame_examples.score_snippet_for_frame`
    as-is rather than reimplementing its scoring (regime fit, core-verb bonus,
    homonym-risk penalty, conflict-frame penalty, confidence tiers), since
    that machinery is already built and validated for exactly this judgment:
    which verb+food collocation is actually a clear frame example.

    Returns (confidence_score, row) pairs. Deliberately NOT truncated to the
    caller's cap here — `capped_candidates` needs the full harvested pool to
    sieve by document position (plans/steps/RECIPE_SIEVE.md): an earlier
    version stopped after the first 200 scored candidates, which clustered
    every selected example in the first few percent of long documents
    (measured: 10/10 hits in the first 5.6% of "Oost-Indisch kookboek").

    `pattern.search(window)` is a cheap pre-check, not a correctness
    requirement: `score_snippet_for_frame` already returns `None` when a
    window has no food term, but it discovers that via `term_positions`'s
    per-term regex scan over the full food-terms list (thousands of terms) —
    the same O(hits x terms) cost already fixed once in the H0 occurrence
    scan. H0's own verb view measured 67% of verb hits have no food term
    nearby at all, so skipping the slow path for those (one single compiled
    `pattern.search`, not thousands of per-term searches) matters at
    full-corpus scale, not just stylistically.

    `max_scored` is now just a pathological-input safety ceiling, not the
    normal operating limit — measured full-document harvests over the 28
    legacy/newly-wired works topped out around 8,000 raw noun hits and well
    under 3,000 verb-qualifying candidates in under a minute each (worst
    case: "Vervolg op M. Noël Chomel", 57s). H0 found one outlier DBNL file
    with 52,368 noun hits; 3,000 keeps a dictionary-like outlier bounded
    without reintroducing the early-document cutoff for any real document
    seen so far.
    """
    scored: list[tuple[int, dict]] = []
    seen_spans: set[tuple[int, int]] = set()
    for hit in find_frame_verbs_in_text(text):
        if len(scored) >= max_scored:
            break
        start = max(0, hit.start - radius)
        end = min(len(text), hit.end + radius)
        if any(a <= hit.start < b for a, b in seen_spans):
            continue  # already covered by an earlier, wider/overlapping window
        window = text[start:end]
        if not pattern.search(window):
            continue
        candidate = score_snippet_for_frame(window, food_terms_list, hit.frame, regime=regime)
        if candidate is None:
            continue
        seen_spans.add((start, end))
        rec = candidate.record

        # score_snippet_for_frame scores against the snippet alone and
        # returns no document position — easy to recover: the verb it picked
        # is in our own already-known window, so locate it there.
        verb_match = re.search(rf"\b{re.escape(candidate.discovery_verb)}\b", window, re.IGNORECASE)
        target_offset = start + (verb_match.start() if verb_match else 0)
        unit = unit_for_offset(units, target_offset) if units else None

        row: dict = {
            "record_id": f"{source_path}__{len(scored)}__verbfirst__{rec.target_word}",
            "corpus": corpus,
            "target_word": rec.target_word,
            "context_text": window.strip(),
            "date": date,
            "source_path": source_path,
            "title": title,
            "candidate_terms": [canonical.get(rec.target_word.lower(), rec.target_word.lower())],
            "discovery_verb": rec.discovery_verb,
            "frame_hint": rec.frame_hint,
            "text_regime": regime.value,
            "kwic_mode": "verb_food",
            # Always set — see the matching note in `scan_text`.
            "target_char_offset": target_offset,
        }
        if unit is not None:
            row["unit_id"] = unit.unit_id
            row["unit_start"] = unit.start
            row["unit_end"] = unit.end
            row["structural_header"] = unit.header_text
            row["structural_signal"] = unit.signal
            if unit.goal_trusted and trust_goals:
                row["structural_goal"] = unit.goal_text
                row["structural_goal_inherited"] = unit.goal_inherited
        scored.append((candidate.confidence_score, row))

    return scored


# Baseline score for noun-fallback candidates in the position sieve below —
# lower than any real `score_snippet_for_frame` confidence score, so a
# verb-scored candidate always wins its bin over a noun-only one.
_NOUN_FALLBACK_SCORE = -1.0


def stratify_by_position(
    candidates: list[tuple[float, dict]], *, cap: int, doc_length: int
) -> list[dict]:
    """Bucket candidates into `cap` equal-width character-offset bins
    spanning the whole document; keep only the highest-scoring candidate per
    bin. A bin with no candidate is skipped, not force-filled.

    Fixes the measured early-document clustering from picking top-`cap` by
    score alone out of a forward-scanned, early-stopped pool — see
    plans/steps/RECIPE_SIEVE.md. Every candidate must carry
    `target_char_offset` (both `scan_text` and `verb_first_hits` always set
    it now).
    """
    if not candidates or doc_length <= 0:
        return []
    best_per_bin: dict[int, tuple[float, dict]] = {}
    for score, row in candidates:
        offset = row["target_char_offset"]
        bin_index = min(cap - 1, offset * cap // doc_length)
        current = best_per_bin.get(bin_index)
        if current is None or score > current[0]:
            best_per_bin[bin_index] = (score, row)
    return [row for _, (_, row) in sorted(best_per_bin.items())]


# Work regimes where TEI entry scope adds candidates (selection-mode v2,
# PLAN.md §9i): in structured recipe/medical works most real frames found by
# entry scope have no qualifying verb, so verb_food alone leaves them unseen.
# In LITERARY/UNKNOWN works entry scope yielded ~10% and is not used.
ENTRY_SCOPE_REGIMES = frozenset({TextRegime.RECIPE_PRACTICE, TextRegime.MEDICAL})


def entry_scope_hits(
    noun_hits: list[dict],
    *,
    located: tuple | list,
    exclude_offsets: set[int],
) -> list[dict]:
    """Mentions inside a TEI entry whose (scope) head carries a recipe/medical
    cue, minus those the verb route already reaches. Tagged `entry_scope`."""
    from trifecta_annotation.regime_routing import regime_from_tei_scope_head

    out: list[dict] = []
    for hit in noun_hits:
        offset = hit["target_char_offset"]
        if offset in exclude_offsets:
            continue
        entry = entry_for_offset(located, offset)
        if entry is None:
            continue
        if regime_from_tei_scope_head(entry.scope_head or entry.head) is None:
            continue
        row = dict(hit)
        row["kwic_mode"] = "entry_scope"
        row["record_id"] = f"{hit['source_path']}__scope__{offset}__{hit['candidate_terms'][0]}"
        out.append(row)
    return out


def capped_candidates(
    text: str,
    *,
    pattern: re.Pattern[str],
    canonical: dict[str, str],
    food_terms_list: list[str],
    source_path: str,
    title: str,
    corpus: str,
    date: str | None,
    units: list[DocumentUnit] | None = None,
    trust_goals: bool = False,
    cap: int,
    include_noun_fallback: bool = False,
    allowed_regimes: frozenset[TextRegime] | None = None,
    located: tuple | list | None = None,
    entry_scope: bool = True,
    entry_scope_cap: int | None = DEFAULT_ENTRY_SCOPE_CAP,
) -> list[dict]:
    """Harvest the whole document, then sieve down to `cap` by document
    position rather than by score alone. See plans/steps/RECIPE_SIEVE.md.

    Default pool is verb-food only (PLAN.md §9i): noun-fallback survived Step A
    at ~31% vs much higher for verb_food in every regime stratum, so topping up
    with unscored noun hits burned ~30% of LLM spend for ~15% of usable output.
    Pass ``include_noun_fallback=True`` to restore the old top-up for ablation.

    ``allowed_regimes`` is an optional document-level gate (off by default) so
    UNKNOWN TEI sweep material is not silently dropped until entry-scope exists.

    Routing (PLAN.md §9i, selection v2): when ``located`` (from ``render_tei``)
    is given and the work regime is in ``ENTRY_SCOPE_REGIMES``, entry-scope
    mentions the verb route cannot reach are added on top of the ``cap``
    verb_food rows, with their own position-stratified budget
    (``DEFAULT_ENTRY_SCOPE_CAP`` = 500, ``None`` = uncapped). The 10/work sweep
    cap exists to spread budget over weak material; these rows are ~88% real
    frames, so a 10 cap would discard the reach v2 found, while 500 spread
    across the work avoids paying for many near-identical entries.
    Everything else stays verb_food only. Pass ``entry_scope=False`` to disable.
    """
    regime = infer_text_regime(corpus=corpus, title=title, source_path=source_path)
    if allowed_regimes is not None and regime not in allowed_regimes:
        return []
    verb_scored = verb_first_hits(
        text, pattern=pattern, food_terms_list=food_terms_list, canonical=canonical,
        source_path=source_path, title=title, corpus=corpus, date=date,
        regime=regime, units=units, trust_goals=trust_goals,
    )
    pool: list[tuple[float, dict]] = list(verb_scored)
    if include_noun_fallback:
        covered_offsets = {row["target_char_offset"] for _, row in verb_scored}
        noun_hits = scan_text(
            text, pattern=pattern, canonical=canonical,
            source_path=source_path, title=title, corpus=corpus, date=date,
            regime=regime, units=units, trust_goals=trust_goals,
        )
        pool.extend(
            (_NOUN_FALLBACK_SCORE, hit)
            for hit in noun_hits
            if hit["target_char_offset"] not in covered_offsets
        )
    selected = stratify_by_position(pool, cap=cap, doc_length=len(text))
    if entry_scope and located and regime in ENTRY_SCOPE_REGIMES:
        verb_offsets = {row["target_char_offset"] for _, row in verb_scored}
        nouns = scan_text(
            text, pattern=pattern, canonical=canonical,
            source_path=source_path, title=title, corpus=corpus, date=date,
            regime=regime, units=units, trust_goals=trust_goals,
        )
        scoped = entry_scope_hits(nouns, located=located, exclude_offsets=verb_offsets)
        # Over budget: keep evenly spaced rows in document order. Not
        # `stratify_by_position` — its bins are document-wide, so entries
        # clustered in one stretch collapse to one row per bin (528 eligible
        # rows in the secreet-boek came out as 90).
        if entry_scope_cap and len(scoped) > entry_scope_cap:
            scoped.sort(key=lambda row: row["target_char_offset"])
            scoped = [scoped[k * len(scoped) // entry_scope_cap] for k in range(entry_scope_cap)]
        selected += scoped
    return selected


def _parse_allowed_regimes(raw: str | None) -> frozenset[TextRegime] | None:
    """Comma-separated TextRegime names → frozenset, or None when unset."""
    if not raw:
        return None
    values: set[TextRegime] = set()
    for part in raw.split(","):
        name = part.strip()
        if not name:
            continue
        try:
            values.add(TextRegime[name] if name in TextRegime.__members__ else TextRegime(name))
        except (KeyError, ValueError) as exc:
            known = ", ".join(r.value for r in TextRegime)
            raise SystemExit(f"unknown regime {name!r}; expected one of: {known}") from exc
    return frozenset(values) if values else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--limit-per-work", type=int, default=None,
                        help="Override cap for ALL sources incl. already-run ones (smoke-testing only)")
    parser.add_argument("--skip-sweep", action="store_true",
                        help="Smoke-test: skip the full genre-agnostic DBNL sweep (H1)")
    parser.add_argument(
        "--include-noun-fallback",
        action="store_true",
        help="Top up verb-food bins with unscored noun hits (ablation; default off per PLAN §9i)",
    )
    parser.add_argument(
        "--regimes",
        default=None,
        metavar="LIST",
        help="Optional comma-separated TextRegime allow-list (e.g. RECIPE_PRACTICE,MEDICAL); "
             "default keeps all regimes",
    )
    parser.add_argument(
        "--entry-scope-cap", type=int, default=DEFAULT_ENTRY_SCOPE_CAP, metavar="N",
        help=f"Per-work cap on entry-scope rows in RECIPE/MEDICAL TEI works "
             f"(default {DEFAULT_ENTRY_SCOPE_CAP}; 0 = uncapped)",
    )
    parser.add_argument("--no-entry-scope", action="store_true",
                        help="Disable the entry-scope route (verb_food only, pre-v2 behaviour)")
    args = parser.parse_args()
    allowed_regimes = _parse_allowed_regimes(args.regimes)

    terms = load_food_terms()
    canonical = alt_label_index(terms)
    all_terms = set(canonical) | {str(p).strip().lower() for p in terms["Pref_label"].dropna()}
    pattern = build_term_pattern({t: t for t in all_terms})
    food_terms_list = sorted(all_terms)

    rows: list[dict] = []
    per_work: dict[str, int] = {}

    # Uniform cap everywhere, including the legacy NEW_DBNL_WORKS/COLONIAL_BOOKS/
    # Dodoens sources below. Reading those from the real `dbnl_xml` zip (fixed
    # here — they previously read a stale prior-session scratchpad extraction
    # that turned out to hold only a partial excerpt per work, not the full
    # text) multiplies their row counts ~40x over the original ~840-row
    # `colonial_annotations` run. The fuller text is real and worth having
    # scanned, but feeding all of it to the LLM cascade uncapped would roughly
    # double the planned few-days budget — so it gets the same cap as every
    # other source here, not special-cased as "already done, leave uncapped."
    sweep_cap = args.limit_per_work or DEFAULT_SWEEP_CAP
    sieve_kwargs = {
        "include_noun_fallback": args.include_noun_fallback,
        "allowed_regimes": allowed_regimes,
        "entry_scope": not args.no_entry_scope,
        "entry_scope_cap": args.entry_scope_cap or None,
    }

    dbnl_zip_path = resolve("dbnl_xml")
    filenames_by_stem = xml_filenames_by_stem(dbnl_zip_path)

    print(f"legacy phase: {len(NEW_DBNL_WORKS)} new-DBNL works, "
          f"{len(COLONIAL_BOOKS)} colonial PDFs, Dodoens, "
          f"{len(EXTRA_COLONIAL_TXT)} extra colonial .txt, 1 diary", flush=True)
    with zipfile.ZipFile(dbnl_zip_path) as archive:
        for work_id, (title, year) in NEW_DBNL_WORKS.items():
            t0 = time.monotonic()
            filename = filenames_by_stem.get(work_stem(work_id))
            if not filename:
                print(f"  missing from dbnl_xml zip (skipped): {work_id}", flush=True)
                continue
            xml = archive.read(filename).decode("utf-8", errors="replace")
            rendered = render_tei(xml, work_id=filename)
            text = rendered.text
            units = structural_units_for_document(
                text, title=title, source_path=filename, corpus="dbnl_new_2026"
            )
            hits = capped_candidates(
                text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
                source_path=filename, title=title,
                corpus="dbnl_new_2026", date=str(year), units=units, cap=sweep_cap,
                located=rendered.located, **sieve_kwargs,
            )
            hits = attach_tei_scope_to_rows(hits, located=rendered.located)
            rows.extend(hits)
            per_work[title] = len(hits)
            print(f"  [new-dbnl] {title!r}: {len(hits)} hits ({time.monotonic() - t0:.1f}s)", flush=True)

    book_dir = Path(resolve("colonial_books"))
    for filename, (title, year, needs_fch_fix) in COLONIAL_BOOKS.items():
        t0 = time.monotonic()
        pdf_path = book_dir / filename
        if not pdf_path.exists():
            continue
        text = extract_pdf_text(pdf_path)
        if needs_fch_fix:
            text = _FCH.sub("sch", text)
        units = structural_units_for_document(
            text, title=title, source_path=filename, corpus="colonial_books_2026"
        )
        hits = capped_candidates(
            text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
            source_path=filename, title=title,
            corpus="colonial_books_2026", date=str(year) if year else None, units=units, cap=sweep_cap,
            **sieve_kwargs,
        )
        rows.extend(hits)
        per_work[title] = len(hits)
        print(f"  [colonial-pdf] {title!r}: {len(hits)} hits ({time.monotonic() - t0:.1f}s)", flush=True)

    dodoens_t0 = time.monotonic()
    dodoens_path = Path(resolve("colonial_books_ocr")) / "dodoens_frk.txt"
    if dodoens_path.exists():
        text = dodoens_path.read_text(encoding="utf-8", errors="replace")
        units = structural_units_for_document(
            text, title="Cruydeboeck (Dodoens)",
            source_path="Crŭÿde boeck_Dodoens_mobot31753000817624.pdf",
            corpus="colonial_books_2026",
        )
        hits = capped_candidates(
            text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
            source_path="Crŭÿde boeck_Dodoens_mobot31753000817624.pdf",
            title="Cruydeboeck (Dodoens)", corpus="colonial_books_2026", date="1608", units=units,
            cap=sweep_cap, **sieve_kwargs,
        )
        rows.extend(hits)
        per_work["Cruydeboeck (Dodoens)"] = len(hits)
        print(f"  [dodoens] {len(hits)} hits ({time.monotonic() - dodoens_t0:.1f}s)", flush=True)

    # --- Newly wired (H1): 3 colonial_books .txt files with ready OCR, never
    # ingested before — same uniform cap, since these never ran through the
    # cascade either.
    for filename, (title, year) in EXTRA_COLONIAL_TXT.items():
        t0 = time.monotonic()
        txt_path = book_dir / filename
        if not txt_path.exists():
            print(f"  missing (skipped): {txt_path}", flush=True)
            continue
        text = txt_path.read_text(encoding="utf-8", errors="replace")
        units = structural_units_for_document(
            text, title=title, source_path=filename, corpus="colonial_books_2026"
        )
        hits = capped_candidates(
            text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
            source_path=filename, title=title,
            corpus="colonial_books_2026", date=str(year) if year else None, units=units, cap=sweep_cap,
            **sieve_kwargs,
        )
        rows.extend(hits)
        per_work[title] = len(hits)
        print(f"  [colonial-txt] {title!r}: {len(hits)} hits ({time.monotonic() - t0:.1f}s)", flush=True)

    kb_cookbook_dir = Path(resolve("colonial_books_ocr")) / "acquisitions"
    for filename, (title, year) in KB_COOKBOOKS_2026.items():
        t0 = time.monotonic()
        ocr_slug = KB_COOKBOOKS_REOCR.get(filename)
        if ocr_slug:
            text_path = Path(resolve("colonial_books_ocr")) / f"{ocr_slug}_nld.txt"
            if not text_path.exists():
                print(f"  missing re-OCR text (skipped): {text_path}", flush=True)
                continue
            text = text_path.read_text(encoding="utf-8", errors="replace")
        else:
            pdf_path = kb_cookbook_dir / filename
            if not pdf_path.exists():
                print(f"  missing (skipped): {pdf_path}", flush=True)
                continue
            text = extract_pdf_text(pdf_path)
        units = structural_units_for_document(
            text, title=title, source_path=filename, corpus="kb_cookbooks_2026"
        )
        hits = capped_candidates(
            text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
            source_path=filename, title=title,
            corpus="kb_cookbooks_2026", date=str(year) if year else None, units=units, cap=sweep_cap,
            **sieve_kwargs,
        )
        rows.extend(hits)
        per_work[title] = len(hits)
        print(f"  [kb-cookbook] {title!r}: {len(hits)} hits ({time.monotonic() - t0:.1f}s)", flush=True)

    for filename, (title, year) in GOOGLE_BOOKS_2026.items():
        t0 = time.monotonic()
        pdf_path = kb_cookbook_dir / filename
        if not pdf_path.exists():
            print(f"  missing (skipped): {pdf_path}", flush=True)
            continue
        text = extract_pdf_text(pdf_path)
        units = structural_units_for_document(
            text, title=title, source_path=filename, corpus="google_books_2026"
        )
        hits = capped_candidates(
            text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
            source_path=filename, title=title,
            corpus="google_books_2026", date=str(year) if year else None, units=units, cap=sweep_cap,
            **sieve_kwargs,
        )
        rows.extend(hits)
        per_work[title] = len(hits)
        print(f"  [google-books] {title!r}: {len(hits)} hits ({time.monotonic() - t0:.1f}s)", flush=True)

    diary_t0 = time.monotonic()
    diary_path = book_dir / VAN_LENNEP_DIARY_DIR / VAN_LENNEP_DIARY_FILE
    if diary_path.exists():
        text = _extract_docx_text(diary_path)
        diary_source = f"{VAN_LENNEP_DIARY_DIR}/{VAN_LENNEP_DIARY_FILE}"
        units = structural_units_for_document(
            text, title=VAN_LENNEP_TITLE, source_path=diary_source, corpus="colonial_books_2026"
        )
        hits = capped_candidates(
            text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
            source_path=diary_source, title=VAN_LENNEP_TITLE,
            corpus="colonial_books_2026", date=str(VAN_LENNEP_YEAR), units=units, cap=sweep_cap,
            **sieve_kwargs,
        )
        rows.extend(hits)
        per_work[VAN_LENNEP_TITLE] = len(hits)
        print(f"  [diary] {len(hits)} hits ({time.monotonic() - diary_t0:.1f}s)", flush=True)
    else:
        print(f"  missing (skipped): {diary_path}", flush=True)

    out = save_semi_structured(
        rows,
        logical_name="colonial_kwic_inputs",
        parent_sources=["colonial_books", "colonial_books_ocr"],
        description="KwicInput records from the 9 new-DBNL works + colonial books (+3 newly-wired + Van Lennep diary)",
        script="scripts/build_colonial_kwic.py",
    )
    print(f"wrote {len(rows)} rows -> {out}", flush=True)
    if args.summary:
        for title, n in sorted(per_work.items(), key=lambda t: -t[1]):
            print(f"  {n:5d}  {title}")

    # --- H1: genre-agnostic, capped sweep over every other DBNL PD work with
    # TEI text. No genre filter — see dbnl_genre.sweep_candidates docstring.
    if args.skip_sweep:
        return

    exclude = ingested_dbnl_stems()
    genre_records = load_genre_records()
    candidates = sweep_candidates(genre_records, filenames_by_stem=filenames_by_stem, exclude_stems=exclude)
    print(f"H1 sweep: {len(candidates)} DBNL works with TEI text, not already ingested", flush=True)

    sweep_rows: list[dict] = []
    sweep_per_work: dict[str, int] = {}
    sweep_t0 = time.monotonic()
    with zipfile.ZipFile(dbnl_zip_path) as archive:
        for i, cand in enumerate(candidates):
            xml = archive.read(cand["filename"]).decode("utf-8", errors="replace")
            rendered = render_tei(xml, work_id=cand["filename"])
            text = rendered.text
            title = cand["titel"] or cand["ti_id"]
            units = structural_units_for_document(
                text, title=title, source_path=cand["filename"], corpus="dbnl_full_sweep_2026"
            )
            hits = capped_candidates(
                text, pattern=pattern, canonical=canonical, food_terms_list=food_terms_list,
                source_path=cand["filename"], title=title,
                corpus="dbnl_full_sweep_2026",
                date=str(cand["year"]) if cand["year"] else None,
                units=units, cap=sweep_cap, located=rendered.located, **sieve_kwargs,
            )
            hits = attach_tei_scope_to_rows(hits, located=rendered.located)
            sweep_rows.extend(hits)
            sweep_per_work[title] = len(hits)
            if (i + 1) % 50 == 0:
                elapsed = time.monotonic() - sweep_t0
                rate = (i + 1) / elapsed
                remaining = (len(candidates) - (i + 1)) / rate
                print(
                    f"  ...{i + 1}/{len(candidates)} sweep works scanned, {len(sweep_rows)} rows so far "
                    f"({rate:.2f} works/s, ~{remaining / 60:.0f} min remaining)",
                    flush=True,
                )

    sweep_out = save_semi_structured(
        sweep_rows,
        logical_name="dbnl_sweep_kwic_inputs",
        parent_sources=["dbnl_xml", "dbnl_work_genre"],
        description="Genre-agnostic, capped (~10/work) KwicInput sweep over every other DBNL PD work with TEI text",
        script="scripts/build_colonial_kwic.py",
    )
    print(f"wrote {len(sweep_rows)} sweep rows -> {sweep_out}")
    if args.summary:
        top = sorted(sweep_per_work.items(), key=lambda t: -t[1])[:20]
        for title, n in top:
            print(f"  {n:5d}  {title}")


if __name__ == "__main__":
    main()
