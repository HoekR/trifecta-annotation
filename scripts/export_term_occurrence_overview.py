"""Uncapped lexical occurrence census: how often/where each foodstuff appears.

Per `plans/steps/SENTENCE_HARVEST.md` H0. This is deliberately **not** the
Step A/B/C cascade — no LLM calls, no per-work cap, no genre gate. It scans
every source `scan_text` can already read (all DBNL PD TEI works via
`dbnl_xml`, the `colonial_books` PDFs/txt, the hand-downloaded editions) and
produces **two separate views**, not one:

1. **Noun view** (`foodstuff_occurrence_overview.csv`) — every food-term
   match, period. Answers "how often is X mentioned at all." Cheap but noisy:
   generic words that happen to be registered food terms (`blad`/`bloem`/
   `voet`) dominate the counts in botanical/narrative text — see the Caveat
   below.
2. **Verb-collocation view** (`foodstuff_frame_collocation_overview.csv`) —
   anchored on `trifecta_annotation.frame_verbs.find_frame_verbs_in_text`
   (the §9a verb-first POC's lexicon: frame verbs + CURE indication phrases
   like "goed voor"/"krachtig tegen"), with the nearest food term in a ±180
   char window picked via `pick_food_near_verb`. Answers "how often is X
   mentioned in a frame-relevant action/indication context" — structurally
   much less ambiguous than the noun view, at the cost of only counting
   mentions near a known frame verb.

Both are pure regex, no LLM calls, no per-work cap — cheap enough to run
exhaustively where the LLM cascade (H1/H2, capped at ~10 hits/work) cannot.
Neither replaces the other: the noun view is the total-mentions census, the
verb view is the frame-relevant one.

**Both are lexical censuses, not validated food-mention counts.** There is
no Step A here — a raw match does not mean the word was used in its food
sense, and a verb hit does not confirm the frame holds (that's what the
cascade is for). The noun view's common terms inflate counts the same way
`AMBIGUOUS_FUNCTION_WORDS` already had to exclude "mede" from the cascade's
own scan. Inspect `--top-terms` output before trusting either aggregate; the
`ambiguous_term` column flags only the already-known collisions, not every
possible one — there is no model here to catch what inspection misses.

    uv run python scripts/export_term_occurrence_overview.py --summary
    uv run python scripts/export_term_occurrence_overview.py --top-terms 30  # inspect before trusting
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

from data_io import resolve
from data_io.manifest import get_manager
from data_io.provenance import ProvenanceRecord, git_commit_hash, write_sidecar

from scripts.build_colonial_kwic import (
    AMBIGUOUS_FUNCTION_WORDS,
    COLONIAL_BOOKS,
    build_term_pattern,
    strip_tei,
)
from trifecta_annotation.adapters.food_snippets import DEFAULT_KWIC_CONTEXT_RADIUS
from trifecta_annotation.corpus_genre_join import build_genre_index, lookup_for_filename
from trifecta_annotation.dbnl_genre import work_stem
from trifecta_annotation.frame_verbs import find_frame_verbs_in_text, pick_food_near_verb
from trifecta_annotation.vocabulary import alt_label_index, load_food_terms

_FCH = re.compile(r"\bfch")

# The 3 colonial books with ready OCR .txt that build_colonial_kwic.py never
# wired in (confirmed present via `ls`, docs/CORPUS_ACQUISITION.md already
# calls them out as "already ship OCR .txt beside the PDF") — filename ->
# (title, year). Years from the Leiden OAI-DC records / CORPUS_ACQUISITION.md.
EXTRA_COLONIAL_TXT: dict[str, tuple[str, int | None]] = {
    "Nuttige Indische planten_953710.txt": ("Nuttige Indische planten", 1894),
    "insulinde_983061.txt": ("Insulinde", None),
    "Beelden_uit_Nederlandsch_Indie_961013.txt": ("Beelden uit Nederlandsch Indie", None),
}

# Used for the §9f structural-density check (447k chars), never food-scanned
# since. The folder holds the diplomatic edition as .docx/.epub, not .txt —
# pick the file whose own name matches the folder's "diplomatische editie
# compleet" label, not the sibling vlennep+hogendorp.docx (a different work).
VAN_LENNEP_DIARY_DIR = "Jacob van Lennep Dagboek 1823 diplomatische editie compleet (1347)"
VAN_LENNEP_DIARY_FILE = "Jacob van Lennep Dagboek 1823 diplomatisch - Marita Mathijsen.docx"
VAN_LENNEP_TITLE = "Jacob van Lennep Dagboek 1823"
VAN_LENNEP_YEAR = 1823


def _extract_docx_text(docx_path: Path) -> str:
    """word/document.xml stripped the same way TEI is — no python-docx
    dependency needed for a lexical scan that doesn't care about structure."""
    with zipfile.ZipFile(docx_path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
    return strip_tei(xml)


def _canonical_counts(
    text: str,
    *,
    pattern: re.Pattern[str],
    canonical: dict[str, str],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    for match in pattern.finditer(text):
        surface = match.group(1)
        counts[canonical.get(surface.lower(), surface.lower())] += 1
    return counts


def _verb_collocation_counts(
    text: str,
    *,
    pattern: re.Pattern[str],
    canonical: dict[str, str],
    radius: int = DEFAULT_KWIC_CONTEXT_RADIUS,
) -> Counter[tuple[str | None, str, str]]:
    """(canonical_food_or_None, verb, frame) -> count, for one document.

    Reuses the §9a verb-first POC's own picks (`find_frame_verbs_in_text`,
    `pick_food_near_verb`) rather than reimplementing verb-anchoring —
    exhaustive over the whole document (no cap), since this is still pure
    regex, no LLM call. Uses the same single compiled alternation `pattern`
    as the noun view to find food positions in each window — `term_positions`
    does a per-term regex search over thousands of terms per verb hit, which
    does not scale to a 3,655-document sweep; one `pattern.finditer` per
    window does the same job in one pass.
    """
    counts: Counter[tuple[str | None, str, str]] = Counter()
    for hit in find_frame_verbs_in_text(text):
        start = max(0, hit.start - radius)
        end = min(len(text), hit.end + radius)
        window = text[start:end]
        food_positions = [(m.start(1), m.group(1)) for m in pattern.finditer(window)]
        food = pick_food_near_verb(hit.start - start, food_positions)
        label = canonical.get(food.lower(), food.lower()) if food else None
        counts[(label, hit.verb, hit.frame.value)] += 1
    return counts


def scan_dbnl_xml(
    pattern: re.Pattern[str],
    canonical: dict[str, str],
    genre_index: dict,
) -> tuple[list[dict], list[dict]]:
    """Every DBNL PD TEI file in the zip, no cap, no genre gate. Returns
    (noun_rows, verb_collocation_rows)."""
    noun_rows: list[dict] = []
    verb_rows: list[dict] = []
    zip_path = resolve("dbnl_xml")
    with zipfile.ZipFile(zip_path) as archive:
        names = [n for n in archive.namelist() if n.endswith(".xml")]
        for i, name in enumerate(names):
            xml = archive.read(name).decode("utf-8", errors="replace")
            text = strip_tei(xml)
            lookup = lookup_for_filename(genre_index, name)
            stem = work_stem(Path(name).stem)
            base = {
                "work_id": stem,
                "source_path": name,
                "year": lookup.year,
                "year_source": lookup.year_source,
                "category": lookup.category,
                "category_scheme": lookup.category_scheme,
                "corpus": "dbnl_xml_full_sweep",
            }
            counts = _canonical_counts(text, pattern=pattern, canonical=canonical)
            for label, n in counts.items():
                noun_rows.append({**base, "canonical_pref_label": label, "match_count": n})
            vcounts = _verb_collocation_counts(text, pattern=pattern, canonical=canonical)
            for (label, verb, frame), n in vcounts.items():
                verb_rows.append(
                    {**base, "canonical_pref_label": label, "trigger_verb": verb, "frame_hint": frame, "match_count": n}
                )
            if (i + 1) % 200 == 0:
                print(f"  ...{i + 1}/{len(names)} DBNL TEI files scanned")
    return noun_rows, verb_rows


def _extract_pdf_text(pdf_path: Path) -> str:
    out = subprocess.run(["pdftotext", str(pdf_path), "-"], capture_output=True, text=True)
    return out.stdout


def scan_colonial_books(
    pattern: re.Pattern[str], canonical: dict[str, str]
) -> tuple[list[dict], list[dict]]:
    """All colonial_books entries, including the 3 never wired into the
    cascade's own ingestion and the Van Lennep diary (free text, never
    food-scanned before). Returns (noun_rows, verb_collocation_rows)."""
    noun_rows: list[dict] = []
    verb_rows: list[dict] = []
    book_dir = Path(resolve("colonial_books"))

    def _add(title: str, source_path: str, year: int | None, text: str) -> None:
        base = {
            "work_id": title,
            "source_path": source_path,
            "year": year,
            "year_source": "docs/CORPUS_ACQUISITION.md" if year else "",
            "category": None,
            "category_scheme": None,
            "corpus": "colonial_books_2026",
        }
        counts = _canonical_counts(text, pattern=pattern, canonical=canonical)
        for label, n in counts.items():
            noun_rows.append({**base, "canonical_pref_label": label, "match_count": n})
        vcounts = _verb_collocation_counts(text, pattern=pattern, canonical=canonical)
        for (label, verb, frame), n in vcounts.items():
            verb_rows.append(
                {**base, "canonical_pref_label": label, "trigger_verb": verb, "frame_hint": frame, "match_count": n}
            )

    for filename, (title, year, needs_fch_fix) in COLONIAL_BOOKS.items():
        pdf_path = book_dir / filename
        if not pdf_path.exists():
            continue
        text = _extract_pdf_text(pdf_path)
        if needs_fch_fix:
            text = _FCH.sub("sch", text)
        _add(title, filename, year, text)

    for filename, (title, year) in EXTRA_COLONIAL_TXT.items():
        txt_path = book_dir / filename
        if not txt_path.exists():
            print(f"  missing (skipped): {txt_path}")
            continue
        _add(title, filename, year, txt_path.read_text(encoding="utf-8", errors="replace"))

    dodoens_path = Path(resolve("colonial_books_ocr")) / "dodoens_frk.txt"
    if dodoens_path.exists():
        _add(
            "Cruydeboeck (Dodoens)",
            "Crŭÿde boeck_Dodoens_mobot31753000817624.pdf",
            1608,
            dodoens_path.read_text(encoding="utf-8", errors="replace"),
        )

    diary_path = book_dir / VAN_LENNEP_DIARY_DIR / VAN_LENNEP_DIARY_FILE
    if diary_path.exists():
        text = _extract_docx_text(diary_path)
        _add(VAN_LENNEP_TITLE, f"{VAN_LENNEP_DIARY_DIR}/{VAN_LENNEP_DIARY_FILE}", VAN_LENNEP_YEAR, text)
    else:
        print(f"  missing (skipped): {diary_path}")

    return noun_rows, verb_rows


def flag_ambiguous(rows: list[dict]) -> None:
    """Mark rows whose label is a known function-word collision, in place."""
    for row in rows:
        row["ambiguous_term"] = row["canonical_pref_label"] in AMBIGUOUS_FUNCTION_WORDS


def aggregate(rows: list[dict], *, extra_keys: tuple[str, ...] = ()) -> list[dict]:
    """Collapse to one row per (label, work, year, category, *extra_keys)."""
    agg: dict[tuple, dict] = {}
    for row in rows:
        key = (
            row["canonical_pref_label"],
            row["work_id"],
            row["year"],
            row["category"],
            *(row[k] for k in extra_keys),
        )
        if key not in agg:
            agg[key] = dict(row)
        else:
            agg[key]["match_count"] += row["match_count"]
    return sorted(
        agg.values(),
        key=lambda r: (-r["match_count"], str(r["canonical_pref_label"])),
    )


NOUN_CSV_FIELDS = [
    "canonical_pref_label",
    "work_id",
    "source_path",
    "year",
    "year_source",
    "category",
    "category_scheme",
    "corpus",
    "match_count",
    "ambiguous_term",
]

VERB_CSV_FIELDS = [
    "canonical_pref_label",
    "trigger_verb",
    "frame_hint",
    "work_id",
    "source_path",
    "year",
    "year_source",
    "category",
    "category_scheme",
    "corpus",
    "match_count",
    "ambiguous_term",
]


def save_overview_csv(
    rows: list[dict], *, logical_name: str, description: str, script: str, fields: list[str]
) -> Path:
    """CSV (not JSONL) output — this export is for scanning/pivoting, no
    programmatic reuse, so a flat CSV is the right format. Mirrors
    `save_jsonl`'s provenance sidecar so it stays consistent with the rest of
    the project's lineage tracking.
    """
    path = resolve(logical_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})

    manager = get_manager()
    dataset = manager.dataset(logical_name)
    record = ProvenanceRecord(
        logical_name=logical_name,
        phase=dataset.phase or "semi",
        parent_sources=[dataset.parent] if dataset.parent else [],
        description=description or dataset.description,
        created_by_script=script,
        record_count=len(rows),
        git_commit=git_commit_hash(path.parent),
    )
    write_sidecar(path, record)
    return path


def _report(
    rows: list[dict],
    raw_total: int,
    works_scanned: int,
    works_with_hits: int,
    *,
    title: str,
    caveat: str,
    is_verb_view: bool = False,
) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"- Raw lexical matches (pre-aggregation): {raw_total}")
    extra_key = " x trigger_verb x frame_hint" if is_verb_view else ""
    lines.append(f"- Aggregated rows (canonical_label x work x year x category{extra_key}): {len(rows)}")
    lines.append(f"- Works scanned: {works_scanned}")
    lines.append(f"- Works with >=1 match: {works_with_hits} ({100 * works_with_hits / max(works_scanned, 1):.1f}%)")
    lines.append("")
    lines.append("## Caveat")
    lines.append(caveat)
    lines.append("")
    lines.append("## Top 30 canonical labels by total match count")
    by_label: Counter[str] = Counter()
    for row in rows:
        by_label[str(row["canonical_pref_label"])] += row["match_count"]
    for label, n in by_label.most_common(30):
        flag = " [AMBIGUOUS]" if label in AMBIGUOUS_FUNCTION_WORDS else ""
        lines.append(f"- {label}: {n}{flag}")
    if is_verb_view:
        lines.append("")
        lines.append("## By frame_hint")
        by_frame: Counter[str] = Counter()
        for row in rows:
            by_frame[row["frame_hint"]] += row["match_count"]
        for frame, n in by_frame.most_common():
            lines.append(f"- {frame}: {n}")
        lines.append("")
        lines.append("## Top 20 trigger verbs")
        by_verb: Counter[str] = Counter()
        for row in rows:
            by_verb[row["trigger_verb"]] += row["match_count"]
        for verb, n in by_verb.most_common(20):
            lines.append(f"- {verb}: {n}")
        lines.append("")
        no_food = sum(r["match_count"] for r in rows if r["canonical_pref_label"] in (None, "None", ""))
        lines.append(f"## Verb hits with no food term in the +-{DEFAULT_KWIC_CONTEXT_RADIUS}-char window: {no_food}")
    lines.append("")
    years = [r["year"] for r in rows if r["year"]]
    if years:
        lines.append(f"## Year range: {min(years)}-{max(years)}")
        by_century = Counter((y // 100) * 100 for y in years)
        for century, n in sorted(by_century.items()):
            lines.append(f"- {century}s: {n} aggregated rows")
    return "\n".join(lines) + "\n"


_NOUN_CAVEAT = (
    "This is a lexical census, not a validated food-mention count — no Step A "
    "entity validation ran here. Common/ambiguous terms inflate counts. The "
    "`ambiguous_term` column flags known collisions "
    f"({sorted(AMBIGUOUS_FUNCTION_WORDS)}); inspect `--top-terms` before "
    "trusting any aggregate built on this file."
)

_VERB_CAVEAT = (
    "A verb/indication hit does not confirm the frame holds — that judgment is "
    "what the Step A/B/C cascade is for. This view only says a frame-relevant "
    f"trigger occurred within +-{DEFAULT_KWIC_CONTEXT_RADIUS} chars of a food "
    "term (or, per 'no food term' below, with no food term found nearby at "
    "all). Treat `frame_hint` as a prior, not a label."
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--top-terms", type=int, default=0, help="Print top-N noun-view terms and exit (no write)")
    parser.add_argument("--skip-dbnl", action="store_true", help="Smoke-test: skip the 3,655-file DBNL sweep")
    args = parser.parse_args()

    terms = load_food_terms()
    canonical = alt_label_index(terms)
    all_terms = set(canonical) | {str(p).strip().lower() for p in terms["Pref_label"].dropna()}
    all_terms -= AMBIGUOUS_FUNCTION_WORDS
    pattern = build_term_pattern({t: t for t in all_terms})
    genre_index = build_genre_index()

    noun_raw: list[dict] = []
    verb_raw: list[dict] = []
    if not args.skip_dbnl:
        print("Scanning DBNL PD TEI dump (3,655 files, no cap)...")
        n, v = scan_dbnl_xml(pattern, canonical, genre_index)
        noun_raw.extend(n)
        verb_raw.extend(v)
    print("Scanning colonial_books (incl. 3 previously-unwired + Van Lennep diary)...")
    n, v = scan_colonial_books(pattern, canonical)
    noun_raw.extend(n)
    verb_raw.extend(v)

    flag_ambiguous(noun_raw)
    flag_ambiguous(verb_raw)

    if args.top_terms:
        by_label: Counter[str] = Counter()
        for row in noun_raw:
            by_label[row["canonical_pref_label"]] += row["match_count"]
        for label, n in by_label.most_common(args.top_terms):
            flag = " [AMBIGUOUS]" if label in AMBIGUOUS_FUNCTION_WORDS else ""
            print(f"{n:8d}  {label}{flag}")
        return

    noun_total = sum(r["match_count"] for r in noun_raw)
    verb_total = sum(r["match_count"] for r in verb_raw)
    noun_rows = aggregate(noun_raw)
    verb_rows = aggregate(verb_raw, extra_keys=("trigger_verb", "frame_hint"))

    works_scanned = len({r["work_id"] for r in noun_raw}) if noun_raw else 0
    # Recompute total distinct works attempted (including zero-hit ones) for
    # an honest coverage denominator, not just works that produced a match.
    total_works_attempted = 0
    if not args.skip_dbnl:
        with zipfile.ZipFile(resolve("dbnl_xml")) as archive:
            total_works_attempted += len([n for n in archive.namelist() if n.endswith(".xml")])
    total_works_attempted += len(COLONIAL_BOOKS) + len(EXTRA_COLONIAL_TXT) + 2  # +Dodoens +diary

    noun_out = save_overview_csv(
        noun_rows,
        logical_name="foodstuff_occurrence_overview",
        description="Uncapped lexical occurrence census: foodstuff x work x year x category",
        script="scripts/export_term_occurrence_overview.py",
        fields=NOUN_CSV_FIELDS,
    )
    noun_report = _report(
        noun_rows, noun_total, total_works_attempted, works_scanned,
        title="foodstuff_occurrence_overview report (noun view)", caveat=_NOUN_CAVEAT,
    )
    noun_report_path = noun_out.parent / "foodstuff_occurrence_overview_report.md"
    noun_report_path.write_text(noun_report, encoding="utf-8")

    verb_works_scanned = len({r["work_id"] for r in verb_raw}) if verb_raw else 0
    verb_out = save_overview_csv(
        verb_rows,
        logical_name="foodstuff_frame_collocation_overview",
        description="Verb/indication-anchored frame-relevant occurrence census (§9a verb-first lexicon)",
        script="scripts/export_term_occurrence_overview.py",
        fields=VERB_CSV_FIELDS,
    )
    verb_report = _report(
        verb_rows, verb_total, total_works_attempted, verb_works_scanned,
        title="foodstuff_frame_collocation_overview report (verb view)", caveat=_VERB_CAVEAT,
        is_verb_view=True,
    )
    verb_report_path = verb_out.parent / "foodstuff_frame_collocation_overview_report.md"
    verb_report_path.write_text(verb_report, encoding="utf-8")

    print(f"wrote {len(noun_rows)} noun-view rows -> {noun_out}")
    print(f"wrote {len(verb_rows)} verb-view rows -> {verb_out}")
    print(f"reports -> {noun_report_path}, {verb_report_path}")
    if args.summary:
        print()
        print(noun_report)
        print()
        print(verb_report)


if __name__ == "__main__":
    main()
