# Corpus acquisition — genre sources and the wanted list

Working document for extending the Dutch corpus for `COOKING_CREATION`,
`PRESERVING` and `CURE` across the 16th–19th century. Written 22 Oct 2026.

## Why this exists

The annotated corpus holds **5,030 rows in those three frames** over 61 works
(COOKING_CREATION 3,765 / CURE 1,046 / PRESERVING 219), but it cannot yet be
ordered by year and is badly concentrated: `Huishoudelyk woordboek` alone is
**53%** of those rows, the top 10 works are 80%, and nothing predates ~1612.
See the `project-annotations-missing-date` note for the date problem.

## Where the sources are

All registered in `data_manifest.toml`; nothing here uses a bare path.

| Logical | What it is |
|---|---|
| `dbnl_titels` | DBNL **public-domain** title metadata, 9,087 works (`sep=\|` first line) |
| `dbnl_xml` | DBNL **public-domain** TEI, 3,655 files |
| `kb_titles_parsed` | Earlier KB catalogue parse, 7,545 rows — richest genre data we have |
| `colonial_books` | Leiden UB colonial books (OCR txt + PDF + OAI-DC records) |
| `gutenberg_catalog` | Project Gutenberg catalogue feed |
| `ggc_cache` | Cached KB GGC SRU responses — **never re-query a cached title** |
| `dbnl_work_genre` | The genre sidecar built from all of the above |

`dbnl_titels`/`dbnl_xml` are the **PD subset**, and that is not a random sample:
it excludes 20th-century critical editions, which are exactly the best
transcriptions of the oldest texts. `Tbouck van wondre` is the worked example —
the dump has only the facsimile-only original `_tbo001tbou01`, while DBNL serves
the Frencken (1934) edition as `fren007tbou01_01`, absent here because it is
still in copyright. **Clear reuse terms before ingesting any such edition**; the
rest of the corpus is PD.

Useful shortcut: a title's `text_url` field predicts whether DBNL has a
transcription — present → 98% have TEI, absent → 8%.

## Finding genre

- **DBNL `genre` must not be used as a filter.** Seven coarse values, and
  measured against our own corpus an exclusion filter on it would discard
  **64% of the three-frame rows**, starting with all 2,679 of
  `Huishoudelyk woordboek` (filed `sec - taalkunde`). `categorie` is only 1/3
  (primary/secondary literature).
- **Basisclassificatie is the preferred scheme** (Rik, 22 Oct 2026 — "I like
  `49.00 huishoudkunde` best"). It is a real genre taxonomy with stable codes,
  unlike free-text subject headings. Prefer `kb_basisclassificatie`, then the
  GGC `basisclassificatie`, and treat the rest as corroboration.
- **KB `Trefwoord GOO` + `Basisclassificatie` are the best signal** — subjects on
  100% of `kb_titles_parsed`, codes on 95%. Note it is a *culinary* bibliography
  (`49.25 eetwaren naar bereiding` carries 6,781 rows), so strong for cookery and
  thin for CURE.
- **KB GGC via SRU** (`jsru.kb.nl`, no auth) fills gaps and is the confirmation
  step that makes title screening safe: it correctly rejected
  `Cornelia Burgerhart` (*Deugdverhalen; Kinderboeken*) and `De schat der
  kinderen` (*Leermiddelen*). Query the **short** title or it returns 0 records.
  **Do not hammer the catalogue** — `scripts/fetch_ggc_subjects.py` caches every
  response and rate-limits; it is the only script that touches the network.
- **Title keywords work only after filtering** and with word boundaries. Unfiltered
  they matched `kok` inside *Grandisson* and `recept` inside *Bijbelsch magazijn*.
- **Gutenberg is one vote, not an authority** — LoCC on 100% of records, but 1,114
  Dutch records of which 4 are classed `TX`. Its value is supplying free text for
  a few works the KB parse identifies.
- **Crossref is a dead end** here: `subject` null throughout, hits are digitisation
  datasets or modern writing *about* the work.

## Wanted list — hand lookup

Filtered to works dated 1500–1899 with **no text in any source we hold** that fill
a measured gap. Rejected as screen misfires: `Singende klucht van Pekelharing in
de kist` (1699, stock comic character) and `De schat der kinderen` (1860,
preserving *health*, not food).

### Facsimile-only in the PD dump — search for a text edition instead

| Year | Work | PD id | Note |
|---|---|---|---|
| 1513 | `Tbouck van wondre` | `_tbo001tbou01` | Frencken 1934 text edition at `fren007tbou01_01` — in copyright |
| ca. 1514 | `Een notabel boecxken van cokeryen` | `_not001nota02` | Earliest printed Dutch cookbook; look for a modern edition too |

Both are 16th-century blackletter. Taken as PD page images they need a
**Fraktur/gothic OCR model** — a default Tesseract pass reproduces the same
garbage already in the Dodoens scan.

### Not in DBNL at all — Delpher or Google Books

| Year | Work | Gap it fills |
|---|---|---|
| 1680 | `Nieuwe beproefde en wel ondersochte genees-middelen` (Digby) | CURE, 17th c. — KB records a Google Books route: `books.google.com/books?vid=KBNL: UBA000020037` |
| 1772 | `Volkoomen Neerlandsch kookkundig woordenboek` (Friesche keukenmeid) | PRESERVING (`pekelen`) |
| 1803 | `Aaltje, de volmaakte en zuinige keukenmeid` | PRESERVING (`confyten`); GOO also `Huismiddelen`, so CURE |
| 1831 | `Het echte Aaltje` | as above, revised |
| 1836 | `Nieuw volledig handboek der kookkunst` | PRESERVING (`inmaken`) |
| 1841 | `De volmaakte Geldersche keukenmeid` | PRESERVING (`inmaken`) |
| 1850 | `Daatje's woordenboek voor de keuken` | PRESERVING (`bewaren`) |
| 1881 | `De Fransche banketbakker` | PRESERVING-adjacent, sugar work |

These eight are 18th–19th-century roman type, so Delpher OCR should come out
usable. Expect the long-s problem on the 1772 and 1803 entries — and note
`normalize_hist_dutch` will **not** fix it, because its `_long_s_map` maps the
real `ſ` character while OCR of these books emits `f` (`befchouwcn`,
`fchetfen`). An `fch`→`sch` pass is the cheap repair.

**Not needed by hand:** the nine medical works found in the DBNL dump
(`Pharmacopoea Roterodamensis` 1709, `Bataviasche apotheek` 1746,
`Den Neder-landschen herbarius` 1698, `De Kartesiaanse academie` 1683,
`List en bedrog der medicynen` 1705, `Chirurgyns scheeps-Kist` 1723,
`Alle de ontleed- genees- en heelkundige werken` 1744,
`De Amsterdamsze gaare-keuken` 1796,
`Aanwijzingen tot het gebruik der medicynen voor zeevarenden` 1839) **already
have TEI**.

## Colonial books — OCR status

All seven PDFs already carry a text layer, so six need extraction, not
recognition. Measured on a page sample:

| Work | 4+ consonant runs | `fch` for `sch` | Verdict |
|---|---|---|---|
| `Crŭÿde boeck` (Dodoens) | 14.9% | — | **Unusable as shipped** — blackletter; re-OCR with Tesseract `frk`, see below |
| `specerijen` 1882 | 4.0% | 0 | Clean — extract as-is |
| `thee` | 3.9% | 0 | Clean; errors confined to Javanese place names |
| `Reize naar Surinamen` dl1 | 5.3% | 285 | Usable after an `fch`→`sch` pass |

`Nuttige Indische planten`, `Insulinde` and `Beelden uit Nederlandsch Indië`
already ship OCR `.txt` beside the PDF.

## Dodoens re-OCR — measured, not assumed

Tested with the engines in `~/develop/form_templates` (kraken, calamari,
pytesseract, TrOCR all installed). Its own `poc1_ocr_consensus_report.md` is
about handwritten form-field crops, so its numbers do **not** transfer; this is
a fresh measurement on Dodoens pages rendered at 300 dpi with `pdftoppm`.

Ground truth hand-transcribed from two pages, CER by Levenshtein, also scored
after `normalize_hist_dutch` because that is what the pipeline actually sees:

| Engine (`--psm 3`) | p120 raw / normalized | p300 raw / normalized |
|---|---|---|
| Embedded PDF layer | 48.1% / 45.7% | 45.4% / 41.6% |
| Tesseract `nld` | 22.2% / 13.3% | 17.0% / 15.3% |
| Tesseract `deu` | 23.1% / 16.2% | — |
| Tesseract `lat` | 38.0% / 32.4% | — |
| **Tesseract `frk`** | **11.1% / 5.7%** | **8.5% / 6.6%** |
| Tesseract `script/Fraktur` | 13.9% / 11.4% | — |
| Kraken + McCATMuS | 20.4% / 18.1% | 21.3% / 20.4% |
| Kraken + CATMuS-Print (tiny) | 27.8% / 25.7% | 25.5% / 22.6% |
| Calamari + `fraktur_historical` | not runnable — see below | |

**Use `frk` at `--psm 3`.** It cuts CER roughly fivefold against the embedded
layer and lands near 6% after normalisation, which is usable for frame and
keyword work.

**Ground truth caveat.** Two lines (~250 characters), hand-transcribed from the
300-dpi render by the same party that scored the engines — not independent, and
not a publishable measurement. Contested readings: the r-rotunda (shaped like
`2`) read as `r`, the `ij` ligature in `onghelijck`, and `wordē` as the nasal
abbreviation for `worden`. The *ranking* is safe because the gaps far exceed
that uncertainty; the absolute numbers carry a couple of points either way. A
defensible figure needs ~20 lines transcribed by someone other than the scorer.

**The purpose-built HTR engines lost.** Kraken 7.1.1 with both CATMuS models
(`10.5281/zenodo.10602357` print-diachronic, `10.5281/zenodo.13788177` McCATMuS
16th–21st c.) ran cleanly but scored 18–20% normalised against `frk`'s 6%. They
confuse `d`↔`b` (`enbe` for `ende`, `blaberen` for `bladeren`) and `w`↔`m`, and
they do not emit `ſ`. Kraken is also ~12× slower (24 s/page vs ~2 s). Calamari
1.0.5 could not be run at all: its `fraktur_historical` ensemble is the most
on-target model of the three, but calamari 1.0.5 builds TF1-style graphs and
fails on TensorFlow 2.21 / Keras 3 with `A KerasTensor cannot be used as input
to a TensorFlow function`. Running it needs `tf-keras` added to
`form_templates` — worth doing only if 6% turns out to be insufficient.

Two things that matter beyond the headline:

- **`frk` emits the real long s `ſ`**, which `normalize_hist_dutch`'s
  `_long_s_map` already handles (69 occurrences on one page, 1 `f`-substitution).
  Every non-Fraktur model, and the embedded layer, mangle it to `f` instead —
  18–22 substitutions per page — which the normaliser cannot repair. That alone
  decides the choice.
- **`--psm 11` is not a safe default** even though it scored best on one page
  (5.0% / 3.6% on p300 against psm 3's 8.5% / 6.6%). On p120 it collapsed to
  47.2%. The pages carry woodcuts and marginalia, so segmentation is the
  remaining error source, not character recognition. Per-page mode selection
  would need a plausibility score to pick between runs; `--psm 3` is the robust
  single choice.

## corpus_overview year/category coverage — decided, not pursued further

`trifecta_annotation/corpus_genre_join.py` joins `food_snippets` filenames to a
`year`/`year_source`/`category` from the `dbnl_work_genre` sidecar (verified
22 Oct 2026 against live data: 56/63 works, 89%, got both). **Decision: leave
the remaining 11% (7 works) unresolved rather than chase them further.**

The 7 — `hui002189201`, `hui002189901`, `hui002190001`, `weye002amst02`,
`daum001hoeh01`, `hove006insa01`, `won001wond01` — are not a year-parsing gap.
Checked directly: none of these ti_id stems appear in `dbnl_titels_pd.csv` at
all, under any form. They are simply absent from the PD dump, the same "dump
isn't a random sample" issue as `Tbouck van wondre` (see above). One of them
(`won001wond01`, "Wonderlicke avontuer van twee goelieven") is archaic-spelling
and likely 17th-century, not the 1890s-periodical pattern the other six show —
worth knowing if anyone assumes the whole group is late and skips it.

**Known, deliberately unimplemented fallback:** an earlier ad hoc pass in this
corpus-dating work parsed a year straight out of a DBNL id when present
(`_vad003182101_01` → 1821, `_hui002189201_01` → 1892) — this is **not** wired
into `corpus_genre_join.py`. It would not help the 7 above (they have no dump
entry to extract an id from), but would recover year for a handful of
periodical jaargangen elsewhere that do have a dump row without a populated
`_jaar`/`jaar` cell. Left out because 89% coverage was judged good enough;
revisit only if a later pass specifically needs the periodical jaargangen
dated.

## Known limits

- **20th century is a bibliography, not a corpus.** `kb_titles_parsed` has 4,248
  rows dated 1900–1999 with full genre codes, but **only 14 carry an access URL**.
  Existing 20th-c. *text*: `ldk2025_cookbooks` (1910–1940) and `recipe_web`.
- **Delpher is not reachable programmatically** from this setup. During the Oct
  2026 PHP-vulnerability outages `dbnl.org`, `delpher.nl` and `kb.nl` all returned
  503 while `jsru.kb.nl`, `data.bibliotheken.nl` and `resolver.kb.nl` stayed up.
  Independently of the outage, KB resolver links lead to the OCLC catalogue, not
  to Delpher text; getting Delpher text needs a browser, a KB API key, or a bulk
  dataset request.
- **PRESERVING cannot be grown much by work selection.** DBNL's short titles name
  it twice; KB's full subtitles give 195 rows / 26 works, which is the lead above,
  but the frame stays structurally hard to find by title.
- **Work-level genre is the wrong grain for periodicals.** Treating them as a
  blanket genre is still informative: across the 20 periodical works already
  annotated, three-frame yield is **22% against 58%** elsewhere and half the food
  mentions drop at Step A — but `INGESTION` runs **14% against 6%**. If
  literature, travel and periodicals are kept as a category, INGESTION is the
  frame they actually support.
