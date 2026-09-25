# Embedding hybrid candidate generation (pilot)

**Status:** E0–E5a **adopted** · hybrid discovery deferred · harden LU later

**Workflow:** After each E-step, stop and ask the operator for decisions. **Do not start the next step until the operator says `go`.**

**SvZ:** mirrored in [`docs/state.json`](../../docs/state.json) / [`docs/STATE.md`](../../docs/STATE.md).

**Workflow:** After each E-step, stop and ask the operator for decisions. **Do not start the next step until the operator says `go`.**

**Goal:** Replace *pure KWIC hit-finding* with **embedding retrieval + thesaurus LU anchor**, without changing Steps A→B→C or dropping `target_word`.

**Out of scope for this track:** GijsBERT as Step B replacement; Step C embedding head; full-corpus FAISS on HPC; abandoning KWIC entirely.

**Primary docs:** [ANNOTATION_STRATEGY.md](../../docs/ANNOTATION_STRATEGY.md) (gold stays eval benchmark), [SNIPPETS.md](../../docs/SNIPPETS.md) (KWIC baseline), this file.

---

## Decision (locked)

| Choice | Value |
|--------|-------|
| Annotation unit | Keep `KwicInput` (`target_word` + `context_text`) |
| Embedder (pilot) | `emanjavacas/gysbert` mean-pooled last hidden state (already in stack) |
| Corpus pool | `food_snippets_long_kwic` (full passage) + optional cort_voc long |
| Queries | Hand-gold exemplars per frame + NONE (from `trifecta_gold`) |
| Hybrid rule | Retrieved span must contain a thesaurus alias → `target_word`; else side pool `semantic_only` |
| Success bar (E4) | On 500 vs 500: higher FOOD / lower NONE-homograph rate than KWIC; frame diversity not collapsed |
| E2 cap | `per_frame_cap=30` |
| NONE exemplars | Dropped gold → NONE (as implemented) |
| E3 passage-limit | **500** |
| E3 none-margin | **0.05** (food score > NONE + margin) |
| After E3 export | Proceed to **E4** |

---

## Steps

### E0 — Scope & success criteria — **DONE**

### E1 — Chunk + embed helpers — **DONE**

### E2 — Exemplar query builder — **DONE**

- Export: **150** exemplars (30 × 5 frames) → `embedding_exemplars`
- Command: `uv run python scripts/build_embedding_exemplars.py --summary`

### E3 — Hybrid retrieve + LU anchor + export — **DONE**

- Stratified `kwic_batch` sampling (avoid CSV-head pharmacopoeia bias)
- Working export: `--passage-limit 2000 --none-margin 0.05` → **500** anchored, LU rate **0.72**, semantic_only 197

```bash
uv run python scripts/export_embedding_candidates.py \
  --passage-limit 2000 --candidate-limit 500 --none-margin 0.05 \
  --top-k-per-frame 800 --seed 0 --summary
```

### E4 — Compare embedding vs KWIC (500 vs 500) — **DONE**

Report: `scratch/trifecta/embedding/e4_compare_report.json`

| Metric | Embedding | KWIC |
|--------|----------:|-----:|
| n | 500 | 500 |
| denylist target rate | **0.0** | 0.134 |
| LU present rate | **1.0** | 0.916 |
| frame_hint | PRESERVING 376 / CURE 107 / COOKING 17 / INGESTION **0** | (none) |
| gold overlap | ~0 | ~0 |

**Read:** clear **noise win** (denylist / LU). Frame diversity **skewed to PRESERVING**; INGESTION missing — watch before adopting as sole discovery path.

### E5 — Adopt or stop — **ADOPTED E5a** (2026-09-16)

**Decision:** Prefer KWIC **re-ranker** before batch; defer hybrid discovery.

**Ops**

```bash
make rerank-kwic
make batch-kwic-reranked
# docs: COMMANDS.md § Preferred embedding re-rank
```

**Done (evidence)**

- Per-frame quotas + NONE-margin fallback (INGESTION present)
- Step A n=100: hybrid **0.87**, re-ranked **0.86**, KWIC baseline **0.69**
- Spot-check CSV reviewed — **all look good** (operator, 2026-09-16)

**Follow-ups (not blocking adopt):** harden LU anchor (reject function words); optional larger `--sample-limit` / `--keep` for production batches.

---

## Parallel track (do not block)

Step 5 / m10 qualia gold + few-shots continues independently. This track only changes **who enters** the pipeline.

---

## Operator notes

- Prefer advising commands; user runs heavy embed / Step A.
- Extra: `uv sync --extra gijsbert` for model encode.
- Clear chat between E-steps if context is large.
