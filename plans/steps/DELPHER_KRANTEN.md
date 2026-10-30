# Delpher newspapers as a corpus slice — assessment before acquisition

**Status:** draft, **not approved**, deferred by operator (30 Oct 2026). Nothing
here is started. K0 is blocked on hardware (see below).

**Blocked on:** the operator's `External Disk` was not mounted when this was
written — only `2tb disk`, `Extreme SSD` and `Macintosh HD` were available, and
no newspaper-shaped directory exists on any of them. K0 cannot begin until it is
mounted, and until then we do not know which subset of Delpher is actually held
locally versus what would have to be downloaded.

**Workflow:** cheap-first, with a stop-and-report gate after every step, same
posture as `SENTENCE_HARVEST.md`. **Do not run any LLM cascade (K4) before K3 has
an explicit operator decision** — at 111 GB and ~2 million newspapers this is the
first corpus in the project where an unscoped cascade would be genuinely
expensive. The census path (K1) has no such cost and needs no LLM.

**Flat OCR is sufficient for this corpus** (operator, 30 Oct 2026) — an earlier
draft of this plan wrongly made article-level structure the go/no-go. It is not.
§9e established that a food mention in running prose is *locally* interpretable,
which is why `LITERARY` segments at only 5.7% and why that is the correct result
rather than a failure. Structure was load-bearing for Chomel because recipe-book
intention is carried structurally; news prose does not have that property. What
newspapers uniquely supply is **exact edition dates**, which come from the
edition metadata whatever the article markup does. Article-type filtering is
therefore an *optimisation* for cascade precision and cost (K2), not a
precondition for value.

**Goal:** decide whether Delpher newspapers are worth adding as a corpus slice
for COOKING_CREATION / PRESERVING / CURE, and if so define a *filtered* slice
rather than a whole-corpus sweep. A negative, documented answer is an acceptable
outcome — `STEPC_GROUNDING.md` closed that way.

**Out of scope for this track:** any change to `tei_segmentation.py` or
`structural_parse.py` (newspapers want their own reader, see K2); re-deriving
existing DBNL rows at entry granularity (PLAN.md §9h, its own sign-off);
resolving the COOKING_CREATION/PRESERVING/CURE frame split; post-1879 material
needing the SRU/OAI-PMH APIs or a custom KB arrangement (K0 scopes the open
archive only).

---

## Background

Source: <https://www.kb.nl/onderzoeken-vinden/datasets/delpher-kranten>, read
30 Oct 2026. What it states:

| Level | Formats |
|---|---|
| per edition | descriptive metadata (Dublin Core in XML), **structural metadata (MPEG21-DIDL)**, PDF |
| per scanned page | JPEG 2000, the OCR text as XML, **ALTO** with the coordinates of every word |

- Coverage: "bijna 2 miljoen kranten uit de jaren 1618 tot 1995" — *De Telegraaf*,
  *De Volkskrant*, *Het Parool*, plus regional and colonial titles.
- **`Het Delpher open krantenarchief`: 111 GB in 23 zip files, OCR + ALTO + XML,
  1618–1879.** This is the part that needs no special arrangement.
- Two APIs for the rest: OAI-PMH metadata harvest and an SRU search API.
  Custom arrangements on request.
- Licence: public domain at 140+ years; newer editions may carry copyright or
  privacy restrictions but are sometimes usable for "niet-commercieel
  wetenschappelijk onderzoek".

**Why this is structurally interesting.** The DIDL is a *declared* unit boundary
— the newspaper equivalent of what PLAN.md §9h recovered for Chomel — and ALTO
supplies a typographic layer beneath it (position and word geometry, the
inferred-structure signal of `feedback_typography_hides_structure`). That places
newspapers closer to the TEI case than to the re-OCR'd KB cookbook PDFs, which
declare nothing at all. Per §9h's lesson, declared boundaries need no
trust-gating, while anything derived from ALTO geometry does and must carry a
provenance flag distinguishing the two.

**Why it may be worth real effort: dates.** Per the `project_annotations_missing_date`
memory, `provenance.date` is null on all 10,537 existing annotation rows and
never existed upstream, which blocks every by-year deliverable. Newspaper
editions are dated **to the day**. If a newspaper slice lands, it is the first
corpus in this project that can support a genuine time series rather than a
work-level year estimate — and it would also dilute the concentration problem
(one work is 53% of the existing three-frame rows; Chomel alone is 36% of
pre-1850 `frame_sentences` rows).

**Why flat OCR is enough.** §9e measured `LITERARY` passages as segmenting at
only 5.7% and judged that *correct*: a food mention in running prose is
incidental and locally readable, so the mention-based model needs no governing
scope. News prose behaves the same way. This means a term census over flat OCR,
joined to edition dates, is a complete deliverable on its own — it is the
by-year series `project_annotations_missing_date` records as blocked, and it
needs no DIDL, no ALTO and no LLM. The structural work that dominated PLAN.md
§9h simply does not apply to this genre, and treating its absence as a defect
would be importing a recipe-book problem into a corpus that does not have it.

**Where structure would still help, as an optimisation.** Two sub-genres are
formulaic and dense in food terms — **household/cookery columns and
advertisements** — so if article types can be told apart cheaply, they give a
much higher-yield slice for any LLM cascade, cutting cost and noise. The KB page
documents **no article-type field** (no advertisement / news / family-notice
classification, no article titles, no font information). KB newspaper DIDL is
generally understood to carry per-article subject labels, but that was *not
verified* and must not be assumed. K2 checks it; a negative answer costs the
track nothing, it just means the cascade runs on a date/title-bounded slice
instead of a type-bounded one.

---

## Steps

### K0 — Inventory what is actually held locally — **blocked on mounting `External Disk`**

Establish ground truth before any design. Report: which Delpher products are
present (open-archive zips? loose ALTO/DIDL? PDFs only?), year span, which
titles, total size, and whether it is a KB-shaped directory tree or a
hand-assembled selection. Then register whatever is kept as a `data_io` logical
name in `data_manifest.toml` with a DVC-tracked mirror, per
`project_data_lineage_dvc` — no ad-hoc paths, given how `kwic_inputs.jsonl` was
lost. Stop and report.

### K1 — By-year occurrence census over flat OCR — the primary deliverable

Needs no DIDL, no ALTO and no LLM. Extend the existing uncapped census
(`export_term_occurrence_overview.py`-style) to read newspaper OCR text, joined
to **edition date** from the per-edition metadata, and report foodstuff
occurrence by term × year × title. This is the by-year series that
`project_annotations_missing_date` records as blocked for every existing corpus,
and newspapers are the first source that can supply it.

Two things to get right, both already project lessons:
- Edition dates are exact, so they must **not** be routed through the
  work-level year-estimate path `corpus_genre_join` applies to DBNL works; tag
  the row's `year_source` as an edition date.
- Per `feedback_progress_reporting_heavy_scripts`, add periodic flushed
  plain-text progress — tqdm alone goes silent under log capture, and this is a
  long I/O-bound run.

Stop and report term × year counts before anything else is built.

### K2 — Optional: verify the DIDL article layer, for cascade precision

Not a gate. Only worth doing if K3 is heading toward an LLM cascade and the cost
needs cutting. On a handful of editions spanning at least two titles and two
decades, answer:
1. Does DIDL give per-article boundaries that resolve to article-level OCR text?
2. **Do articles carry a type/subject label** (advertentie / artikel /
   familiebericht / illustratie met onderschrift), populated consistently across
   titles and decades?
3. Is there an article title/heading field, and is it filled?
4. Can a word's ALTO coordinates be recovered from an article unit?

Apply §9h's own lesson: confirm the DIDL unit *is* the article before trusting
it, rather than assuming the nearest available boundary is the right one. A
negative answer costs the track nothing — it means the cascade is bounded by
date and title rather than by article type.

If it passes and a cascade is wanted, build a read-only article segmenter as a
newspaper counterpart to `tei_segmentation.py`, kept separate from it (different
format, different unit, no shared parsing): article units carrying
`newspaper_title`, `edition_date`, `page`, `article_id`, `article_type`, `title`,
`text`. Same posture — writes nothing without an explicit output directory,
makes no frame judgements, changes no `record_id`s.

### K3 — Operator decision: is a cascade wanted at all?

K1 may well be the whole deliverable. Decide explicitly whether the three-frame
sentence-level cascade adds enough over the census to justify its cost, and if
so on what slice (dates × titles, optionally × article types from K2). Closing
here with the census shipped and no cascade is a perfectly good outcome.

### K4 — Cascade batch on the approved slice only

Only on an approved K3 scope. Site the compute on Lyceum per
`reference_remote_compute` (~€10 unused credit, preferred over SURF). Merge into
`frame_sentences` as a new `source_corpus` value, which the H3 contract already
supports — and which `tests/test_export_frame_sentences.py` now actually covers.

---

## Verification

- Date handling: edition dates are exact, so they must *not* be routed through
  the work-level year-estimate path that `corpus_genre_join` applies to DBNL
  works; a newspaper row's `year_source` should say it came from an edition date.
- K1's counts are reported per title as well as per year, so a single
  high-volume title cannot masquerade as a trend — the concentration trap that
  `project_annotations_missing_date` and §9h both ran into (one work = 53% of
  three-frame rows; Chomel = 36% of pre-1850 `frame_sentences` rows).
- OCR quality is reported alongside the counts, not assumed: 17th–18th c.
  newspaper OCR is poor, and a term's absence may be an OCR artefact rather
  than a real absence. Spot-check the low-yield years before reading any trend.
- K2, if run, is reported as *observed fields from real files*, quoted, not as
  expected DIDL semantics.
- Any structure derived from ALTO geometry is flagged inferred, never mixed with
  declared DIDL boundaries (§9h).
- Nothing is added to `frame_sentences` before K3 sign-off.
