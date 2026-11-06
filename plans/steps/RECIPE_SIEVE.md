# Stratified harvest-and-sieve sampling for the Step A→B→C cascade

**Status:** done (implemented in `scripts/build_colonial_kwic.py`:
`stratify_by_position`, raised `max_scored`, position bins). Follow-on mode
sieve (verb-food default, optional `--regimes`) landed with PLAN.md §9i —
same file, not a re-open of this track.

**Depends on:** `plans/steps/SENTENCE_HARVEST.md` (H1/H2) — this refines those two
steps' per-work candidate *selection* method. It does not change their scope,
budget, or cap size.

---

## Problem, measured

The current per-work candidate selection (`verb_first_hits` +
`capped_candidates` in `scripts/build_colonial_kwic.py`) picks the
top-N-by-`confidence_score` candidates out of the first `max_scored=200` verb
hits found scanning forward from the start of the document. Checked against
two long, confirmed recipe-dense legacy/newly-wired acquisitions by directly
locating each selected `context_text` in the full extracted text (not via the
`target_char_offset` field, which only exists when a structural unit happens
to be found):

- **Oost-Indisch kookboek** (advertises 800+ recipes in its own title,
  433,224 chars extracted): all 10 selected hits land in the first **5.6%**
  of the document (char offsets 7,277–24,342).
- **Vervolg op M. Noël Chomel, Algemeen huishoudelyk-woordenboek**
  (4,647,522 chars, 767 pages): the 10 hits span 4.2%–56.9% — better, but
  still miss the back half of the book entirely.

So the ~10-row sample actually fed to the LLM cascade is an early-pages
sample, not a whole-book sample — for a work acquired specifically because
it's recipe-dense, this under-covers the thing we acquired it for.

**Root cause:** two independent sources of early-document bias stack: (1)
`find_frame_verbs_in_text` scans forward and `verb_first_hits` stops
collecting once `max_scored=200` candidates are gathered, regardless of how
much of the document that covers; (2) the final cap then picks the top-N by
`confidence_score` out of that already front-loaded pool.

---

## Fix: stratify by position, weight by score within each stratum

1. **Harvest** — remove (or substantially raise) `max_scored` so the full
   document is scanned for verb-food collocations before any selection
   happens. No LLM involved; this is the cheap half of the pipeline.
2. **Sieve** — bucket the harvested candidates into `cap` equal-width
   character-offset bins spanning the full document. Within each bin, keep
   the highest-`confidence_score` candidate. A bin with zero candidates is
   skipped, not force-filled.
3. Where `structural_parse.py` finds real structural units for the document
   (currently rare — 16/29,784 rows in the H1 sweep), prefer one pick per
   unit over blind character bins, since recipe/chapter length varies and a
   fixed-width bin can split or swallow units unevenly. Falls back to
   character bins when no units are found (the common case today).
4. Feed the sieved sample into Step A→B→C unchanged — same ~10/work budget as
   today. This changes *which* 10 candidates get annotated, not *how many*,
   so it doesn't touch the compute-budget math already decided for H1/H2.

## Scope

Applies to `capped_candidates`/`verb_first_hits` in
`scripts/build_colonial_kwic.py`, used by both the curated
legacy/newly-wired book list (`NEW_DBNL_WORKS`, `COLONIAL_BOOKS`,
`EXTRA_COLONIAL_TXT`, `KB_COOKBOOKS_2026`, `GOOGLE_BOOKS_2026`) and H1's full
genre-agnostic DBNL sweep — the position-clustering problem is generic to the
function, not specific to the 28-work set it was discovered on.

**Out of scope:** re-sieving the ~1,655 `dbnl_sweep_annotations` rows already
run through H2 (forward-looking fix, same precedent as the `text_regime.py`
false-positive fix). The 280-row `colonial_kwic_inputs.jsonl` built from the
28-work legacy/newly-wired list on 27 Oct has *not* yet been through Step
A→B→C — regenerate it with the sieve before that cascade run, not after.
`export_term_occurrence_overview.py` (H0) is untouched — it has no cascade
and no per-work sampling decision to make.

## Verification

- Re-run the position check (locate each sieved `context_text` in the full
  extracted text, as % of document length) for `Oost-Indisch kookboek` and
  `Vervolg op M. Noël Chomel` post-fix; offsets should spread across close to
  the full 0–100% range, not cluster in one quintile.
- `uv run python scripts/build_colonial_kwic.py --skip-sweep --summary` row
  count stays at ~10/work — this is a selection-quality fix, not a budget
  change.
- Spot-check 2–3 sieved candidates per bin manually to confirm they're still
  genuine food+verb collocations, not sieve-induced noise (picking a bin's
  only candidate even when it's a poor match).
