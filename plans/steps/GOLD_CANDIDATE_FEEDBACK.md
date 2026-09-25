# Gold → better next candidates (lemma priors feedback)

**Status:** G5 done · gold-feedback track complete · operator gate before next M10 work

**Workflow:** After each G-step, stop and ask the operator for decisions. **Do not start the next step until the operator says `go`.**

**SvZ:** mirrored in [`docs/state.json`](../../docs/state.json) / [`docs/STATE.md`](../../docs/STATE.md).

**Goal:** Close the sampling loop so each imported gold hour improves the **next** export — not only `+N` eval rows. Labelling sessions must teach exporters which lemmas / senses to suppress, deprioritize, or require disambiguation for.

**Out of scope for this track:** Step C prompt/few-shot calibration (already M10-FS); embedding hybrid discovery; rewriting A→B→C schemas; bulk re-labelling of old gold.

**Primary docs:** [ANNOTATION_STRATEGY.md](../../docs/ANNOTATION_STRATEGY.md) § sampling + precision>recall, [GOLD_LABELLING.md](../../docs/GOLD_LABELLING.md) § Step 5, [thesaurus.py](../../trifecta_annotation/thesaurus.py) `DEFAULT_DENYLIST`, this file.

---

## Problem (locked diagnosis)

| Signal from gold sessions | Used by next clear-frame / preservare / regime export? |
|---------------------------|--------------------------------------------------------|
| Already-seen `record_id` | Yes — id exclude only |
| In-batch `max_per_target` | Yes — within one CSV only |
| Few-shots / Step C review | Yes — **prompt** loop, not candidate pool |
| Static `DEFAULT_DENYLIST` (incl. `mede`) | Thesaurus build + embedding LU anchor only — **not** clear-frame mine |
| `dropped` / `is_food_entity=false` / `homonym_check∈{other_sense,metaphor}` | **No** |
| Lemma-level reject / food-pass rates across sessions | **No** |

Result: operators re-triage the same noisy families (`mede`, canal `water`, …) every batch. Prompt/eval iterates; **sampling stays open-loop**.

---

## Decision (locked)

| Choice | Value |
|--------|-------|
| Unit of learning | Normalized `target_word` (lemma), optionally × `text_regime` |
| Source of truth | `gold_labelling_all.csv` + imported `trifecta_gold` (labelled rows); optional dropout-review CSV later |
| Hard block | `DEFAULT_DENYLIST` ∪ lemmas with high non-food / other_sense rate (threshold gated in G2) |
| Soft deprioritize | Lemmas already at gold quota for a frame; saturated food-pass lemmas |
| Require disambiguation | Polysemous-but-sometimes-food lemmas → force `homonym-filter` / lower score |
| Exporters to wire | `export_clear_frame_examples`, `export_preservare_gold_candidates`, `export_regime_stratified` (shared helper) |
| Success bar (G4) | Dry-run on last batch: blocked denylist+prior rows > 0; food-pass density of proposed batch ↑ vs pre-filter baseline; no silent wipe of rare frames |
| Operator labelling | Finish in-flight useful rows; lemma priors on for new exports |

---

## Steps

### G0 — Scope & success criteria — **DONE** (2026-09-17)

This file. Diagnosis confirmed: denylist exists; clear-frame never hard-skips it; gold rejections do not suppress lemmas.

### G1 — Shared target filter helper — **DONE** (2026-09-17)

`trifecta_annotation/gold_target_filter.py`:

- `normalize_target` + membership in `DEFAULT_DENYLIST`
- Optional blocked set from priors file / in-memory dict (`GoldTargetFilter.from_priors`)
- Pure functions + unit tests (`mede` blocked; kept food lemma passes)

**Do not** yet change exporter CLI defaults beyond opt-in flag if safer — exporters unchanged until G3.

**Done when:** tests green; helper importable from clear-frame and preservare paths.

### G2 — Build lemma priors from gold — **DONE** (2026-09-17)

`scripts/build_gold_lemma_priors.py` + `trifecta_annotation/gold_lemma_priors.py`:

- Reads `gold_labelling_all.csv` (labelled rows) via `data_io.resolve`
- Per normalized target: `n`, food-pass / drop / other_sense / metaphor rates, frame + regime mix
- Hard-block thresholds (CLI-gated defaults): `min_n=3`, `food_pass_rate≤0.2`, `drop_rate≥0.75`, or `other_sense_rate≥0.5`
- Soft lists: `require_disambiguation`, `soft_deprioritize` (for G3; not hard-skip yet)
- Writes `gold_lemma_priors` JSON (compatible with `GoldTargetFilter.from_priors`)

**First build:** labelled=308, lemmas=153, **blocked=6** (`bloed`, `bloem`, `huid`, `mede`, `munt`, `noot`); `water`/`appel` → disambiguation only.

```bash
uv run python scripts/build_gold_lemma_priors.py --summary
uv run python -m data_io.check
```

### G3 — Wire filter into exporters — **DONE** (2026-09-17)

In `mine_clear_frame_candidates` / preservare mine / regime export:

1. Hard-skip denylist targets (always)
2. Hard-skip prior-blocked lemmas; soft: `require_disambiguation` (homonym gate) + `soft_deprioritize` (sample after non-soft)
3. Pre-labelling **batch report** JSON on stderr (`format_filter_report`)

CLI: lemma priors **default on**; `--no-lemma-priors` escape hatch (denylist still applies). Thresholds documented in `--help`.

```bash
uv run python scripts/export_clear_frame_examples.py --frames CURE,INGESTION --summary --limit 20
uv run python scripts/export_preservare_gold_candidates.py --summary --limit 10
uv run python scripts/export_regime_stratified.py --summary
# escape: add --no-lemma-priors
```

**Done when:** exporters wired + unit tests green; operator dry-run comparison is **G4**.

### G4 — Operator dry-run & adopt — **DONE** (2026-09-17)

- Compared filtered vs `--no-lemma-priors`: denylist+priors cut noise (`mede`/`bloed`/…); CURE pool thin but not over-blocked
- Deeper mine (`--min-score 3`, frame quotas) filled CURE; dropped 6 false `allen` corpus-verb rows by hand
- Labelled batch: **18/18** on `g4_clear_frame_filtered` (13 INGESTION + 5 CURE)
- **Adopted:** lemma priors **default on**; `--no-lemma-priors` escape only; do **not** disable denylist

**Done when:** operator says adopt (or revise thresholds once). ✓

### G5 — Labelling hygiene (docs only) — **DONE** (2026-09-17)

[GOLD_LABELLING.md](../../docs/GOLD_LABELLING.md) Step 0 now states: priors default on + filter report; label clear food / mark drops; rebuild priors after import before next export.

**Done when:** runbook mentions the closed loop in ≤10 lines. ✓

---

## Operator guidance (labelling vs this track)

| Situation | Do |
|-----------|----|
| Mid-batch, row is clear food + useful Step C | Finish and save — still +N valuable gold |
| Mid-batch, another `mede` / obvious non-food | Drop fast (`dropped`/`other_sense`); do not agonize |
| Batch finished or mostly triage noise | **Stop new exports** until merge/import + priors rebuild |
| Disks disconnected | No labelling; code/tests only |

**Default recommendation:** lemma priors on for all new exports; rebuild priors (G2) after each import (see GOLD_LABELLING Step 0).

---

## Non-goals / defer

- Auto-editing `DEFAULT_DENYLIST` without operator review of promoted lemmas
- Using `labelled=false` rows as soft training signal for LLMs
- Replacing Step A with the lemma filter (filter is **pre**-labelling only)

---

## Handoff checklist

After each G-step:

1. Mark step status in this file + SvZ (`scripts/svz.py update …`)
2. Short 3-bullet handoff to operator
3. Name next step; remind to clear chat before the next major step
