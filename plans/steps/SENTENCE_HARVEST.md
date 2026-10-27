# Exhaustive 16th–19th c. sentence harvest + aggregative occurrence overview

**Status:** approved, not started (25 Oct 2026).

**Workflow:** H0 (occurrence overview) and H2 (capped cascade batch) are both
multi-hour-to-multi-day unattended runs with real compute/time cost. **After
each H-step, stop and report results before starting the next.** Do not
start H2's batch run until the operator has reviewed H1's row counts.

**Goal:** Ship a sentence-level dataset of COOKING_CREATION/PRESERVING/CURE
sentences spanning the 16th–19th century, ordered by year, for aggregate
research on foodstuff occurrence by frame — plus a separate, uncapped
occurrence census that answers "how often and where is each foodstuff
mentioned" without needing the LLM cascade at all.

**Out of scope for this track:** resolving the COOKING_CREATION/PRESERVING/CURE
frame-split ambiguity (deliberately deferred elsewhere, see `PLAN.md`
frame-overlap finding; this track documents the caveat, doesn't fix it);
`docs/CORPUS_ACQUISITION.md`'s "wanted list" (8 works needing Delpher/Google
Books acquisition — no text available yet); any change to
`structural_parse.py` / Step C organizing-field wiring (held behind its own
sign-off, unrelated here); building a new aggregation/analysis notebook (the
exports themselves are the deliverable).

---

## Background

`scripts/export_frame_sentences.py` already states this exact deliverable in
its own docstring but only reads `trifecta_annotations` (the original
61-work corpus), which per `docs/CORPUS_ACQUISITION.md` is concentrated
(`Huishoudelyk woordboek` alone is 53% of annotated three-frame rows) and
doesn't predate ~1612. Two batches completed in a prior session
(`colonial_annotations`: 840 rows, 1608–1882; `handdownload_annotations`:
120 rows, 1513/1514 — both already through Step A→B→C) close part of that
gap but were never wired into the exporter.

**Why this isn't just "wire those two in" (the operator's two corrections):**

1. **Document selection must not be genre-gated.** An earlier draft scanned
   only DBNL works whose assigned genre looked food-relevant. Rejected:
   `docs/CORPUS_ACQUISITION.md` already shows an exclusion filter on DBNL's
   own `genre` field would have discarded `Huishoudelyk woordboek` — using
   genre to decide *which works get scanned* repeats that mistake. The
   Step A→B→C cascade exists precisely so a work's genre doesn't need to be
   known in advance; it should run over every available work, not a
   genre-filtered subset. Genre stays in its existing role — post-hoc
   category metadata via `corpus_genre_join`, never a scan gate.
2. **Frame scope is known-unresolved, not fixed by this track.** The
   COOKING_CREATION/PRESERVING/CURE boundary overlap is a documented,
   deliberately-deferred issue. This track carries that caveat into the
   report rather than pretending to resolve it.

**Measured cost of "no genre gate" (not assumed):** a 150-file random sample
of the 3,655-file DBNL PD TEI dump, scanned with the existing food-term
lexicon match, found avg 858 hits/file (only 2/150 zero-hit; one file alone
hit 52,368 — common words like *water*/*wijn*/*brood* appear in almost any
Dutch prose) → **~3.1M raw lexical matches extrapolated across the full
dump**. Cross-checked against actual batch throughput this session
(`colonial_annotations`: 840 rows/~55 min ≈ 4 sec/row; `handdownload_annotations`:
120 rows/~24 min ≈ 12 sec/row through the real cascade), a few-days budget of
local LLM throughput supports on the order of **30,000–50,000 cascade rows**,
not millions.

**Resolution — two separate outputs, not one shrunk to fit:** the 3.1M
figure is a *lexical match count*, not an LLM cost — only the cascade
(Step A/B/C) needs a budget cap. So:

- **H0** — an uncapped, full-corpus occurrence census (cheap, ~2 hours, no
  LLM) answering "how often/where is each foodstuff mentioned" — this is the
  aggregative-overview-of-use deliverable in its own right.
- **H1–H2** — a budgeted cascade sample (~10 KWIC hits/work uniform cap,
  reusing `build_colonial_kwic.py`'s existing `--limit-per-work`, not
  genre-weighted) producing validated, frame-labeled sentences — necessarily
  smaller than H0's census, answering a different question (which mentions
  are genuinely food, in which frame, with what qualia).

---

## Steps

### H0 — Uncapped lexical occurrence overview — **next**

New script `scripts/export_term_occurrence_overview.py`. Scans every source
`scan_text`/`build_term_pattern` can already read (all 3,655 DBNL PD TEI
works via `dbnl_xml`, `colonial_books`, `trifecta_annotations`'s own sources,
the handdownload editions) with **no per-work cap** and **no Step A/B/C
call**. Per match: `canonical_pref_label` (via `alt_label_index`, so
`palinck`/`paling` collapse together), work/year/category (via
`corpus_genre_join`/`dbnl_work_genre`). Aggregates to one row per
`(canonical_pref_label, work, year, category)`, not one row per raw match.

**Load-bearing caveat, must ship visibly, not silently:** this is a lexical
census — no model rejects metaphor/non-food senses. Common short terms will
inflate counts the way `AMBIGUOUS_FUNCTION_WORDS` already had to exclude
"mede" (2,702 near-100%-false-positive hits) from the cascade's own scan.
Before shipping: rank terms by hit count relative to length/commonness,
inspect top outliers by eye, exclude confirmed function-word collisions
(reusing `AMBIGUOUS_FUNCTION_WORDS`) or flag them with a visible
`ambiguous_term` column.

Output: `foodstuff_occurrence_overview` manifest logical (CSV + `_report.md`
sibling: total matches, matches after canonical collapse, exclusions
applied, coverage — expect ~3,653/3,655 works with ≥1 match).

**Checkpoint:** stop here, report results, before starting H1.

### H1 — Genre-agnostic, capped document sweep

Replace `build_colonial_kwic.py`'s hardcoded `NEW_DBNL_WORKS` dict with a
function reading every `dbnl_ti_id` record from `dbnl_work_genre.jsonl` with
`has_xml=True`, excluding stems already ingested (61 original + 9 known-new
+ 2 handdownload) — **no genre filtering**. Extract TEI from the `dbnl_xml`
zip (reuse `xml_stems` from `dbnl_genre.py`), run `strip_tei` + `scan_text`
with `--limit-per-work 10` uniform. Tag `corpus="dbnl_full_sweep_2026"`.

Also wire in 3 `colonial_books` `.txt` files with ready OCR
(`Nuttige Indische planten_953710.txt`, `insulinde_983061.txt`,
`Beelden_uit_Nederlandsch_Indie_961013.txt` — present on disk, never
ingested, no new OCR needed) and the Van Lennep 1823 diary (already
extracted for the §9f structural-density check, never food-scanned) — same
cap, `corpus="colonial_books_2026"`.

New manifest logicals: `dbnl_sweep_kwic_inputs` → `dbnl_sweep_annotations`
(mirrors `colonial_kwic_inputs`/`colonial_annotations`). The 3 books + diary
land inside the existing `colonial_kwic_inputs`/`colonial_annotations` pair.

**Checkpoint:** run the KWIC-extraction step alone first (no LLM calls),
report row counts (~36,550 worst case, likely lower — most works are short)
before H2's batch run.

**Candidate-selection fix, found during this track (27 Oct 2026):** the
per-work top-10 selection clusters in the first few percent of long documents
instead of spanning them — see `plans/steps/RECIPE_SIEVE.md`. Apply that fix
before (re-)running H1 for any work longer than a few pages.

### H2 — Run the capped cascade batch

`uv run trifecta-batch` over `dbnl_sweep_kwic_inputs` → `dbnl_sweep_annotations`,
and re-run `colonial_kwic_inputs` → `colonial_annotations` (now including the
3 books + diary) — same CLI as the two already-completed jobs, no pipeline
code changes. Monitor throughput against the ~4–12 sec/row measured rate;
reassess the ~1.5–5 day time estimate partway through. If tight: `--concurrency`
or a remote GPU tier (Lyceum preferred over SURF per standing preference) is
the lever, not lowering per-work coverage.

**Checkpoint:** stop, report actual row counts/frame distribution, before H3.

### H3 — Merge every annotation source into `frame_sentences`

`scripts/export_frame_sentences.py`:
- Concatenate `trifecta_annotations`, `colonial_annotations`,
  `handdownload_annotations`, `dbnl_sweep_annotations`.
- Year fallback: when `corpus_genre_join` resolves no year, try
  `int(provenance.date)`, tag `year_source="provenance.date"`.
- Category fallback: when no category, use `provenance.text_regime` with
  `category_scheme="text_regime"` (already a valid scheme name in
  `corpus_genre_join.py`'s `_CATEGORY_SCHEME_ORDER`).
- Explicit `year < 1900` guard, counted not silently dropped.
- New field `canonical_pref_label` (from `step_a.canonical_pref_label`,
  falling back to `target_word`) — the real join key for occurrence research;
  raw `target_word` keeps spelling variants separate and undercounts.
- Report: per-source-corpus breakdown, foodstuff×frame×century count table,
  and the frame-scope caveat (see Background §2) stated explicitly near the
  top, not buried.

### H4 — CSV sibling export

Flat CSV next to `frame_sentences.jsonl` (same fields, plain
`csv.DictWriter`). New `frame_sentences_csv` manifest logical, mirroring the
existing `ldk2025_analysis`/`ldk2025_analysis_csv` pair, `parent =
"frame_sentences"`.

---

## Verification

- H0: coverage ~3,653/3,655 works with ≥1 match; ambiguous-term handling
  visibly applied, not silently baked in.
- H1: row counts sane (~36,550 worst case) before any LLM spend.
- H2: throughput tracked against measured 4–12 sec/row; row/frame counts
  reported before merging.
- H3: `frame_sentences_report.md` year range ~1513–1882, non-zero
  1500s/1600s, all four source corpora represented, frame-scope caveat
  present.
- H4: JSONL/CSV row-count parity; `canonical_pref_label` normalizes at least
  one known spelling-variant case (e.g. `palinck`/`paling`).
- `uv run python -m data_io.check` passes with the new manifest entries.
