# Decision Log

Record durable methodological and architectural decisions here. Keep entries short enough to scan.

## Template

### YYYY-MM-DD: Decision title

- **Context:** What changed or what result forced a choice?
- **Decision:** What did we decide?
- **Reason:** Why is this the right tradeoff now?

---

### 2026-09-16: Embedding hybrid candidates (not pure KWIC, not LU-free)

- **Context:** KWIC thesaurus matching feeds the batch pool but yields ~33% Step A dropout (homographs, travel/catalog, false hits). Dissatisfaction with lexical-only discovery.
- **Decision:** Pilot **embedding retrieval + thesaurus LU anchor** → still emit `KwicInput` with `target_word`. Keep A→B→C LLM path; do not replace Step C with embeddings; do not drop the lexical unit for FrameNet/qualia claims. Embedder for pilot: mean-pooled `emanjavacas/gysbert`. Gate on 500 vs 500 comparison before scaling index or rewiring batch.
- **Reason:** Research object remains lemma-in-frame; embeddings fix *candidate quality/recall*, not annotation schemas. Reuse GysBERT already in the stack before adding a dedicated retrieval model.
- **Guide:** [plans/steps/EMBEDDING_CANDIDATES.md](../plans/steps/EMBEDDING_CANDIDATES.md)

---

### 2026-09-16: Adopt E5a KWIC embedding re-ranker (defer hybrid discovery)

- **Context:** E4/E5 pilots: denylist noise down; Step A FOOD rate n=100 — hybrid 0.87, re-ranked 0.86, KWIC baseline 0.69. Hybrid discovery ≈ re-ranked on FOOD rate but LU anchors can hit function words (`heeft`, `leven`).
- **Decision:** **Adopt E5a** — re-rank existing `kwic_inputs` with GysBERT centroids + NONE margin 0.05 + frame quotas → `embedding_kwic_reranked`; preferred batch path `make batch-kwic-reranked`. **Defer** embedding hybrid discovery / full index until LU anchoring is hardened. Do not replace A→B→C or Step C.
- **Reason:** Same operational KWIC universe with ~17pp fewer Step A dropouts; avoids premature discovery rewrite while shipping the validated filter.
- **Ops:** [docs/COMMANDS.md](COMMANDS.md) § Preferred re-rank; Makefile `rerank-kwic`, `batch-kwic-reranked`.
- **Spot-check:** `e5_spotcheck.csv` reviewed 2026-09-16 — operator: all look good.

## 2026-09-16: More Step C gold before M10-AN

- **Context:** M10-FS done; fork was M10-AN vs more Step C gold; soft micro 30.3% with CURE weakest at 20.8%; analytic claims still blocked
- **Decision:** Prioritize another Step C hand-gold quota (CURE-first, ~20–30 rows) before corpus analysis notebooks
- **Reason:** Trust for counts/trends needs more hand gold; notebooks alone will not close the blocker

## 2026-09-17: Gold→candidate feedback loop (lemma priors)

- **Context:** Gold hours mostly add eval rows; exporters only exclude record_ids; DEFAULT_DENYLIST (e.g. mede) not applied in clear-frame mine; dropped/other_sense never suppress lemmas
- **Decision:** Open track G0–G5 in plans/steps/GOLD_CANDIDATE_FEEDBACK.md; pause new gold export cycles until G3 ships; finish in-flight useful Step C rows only
- **Reason:** Each labelling session must improve next candidates (precision>recall sampling), not just grow N

## 2026-09-17: Adopt gold lemma priors in exporters (G4)

- **Context:** G4 dry-run: filtered pool hard-skipped 871 (564 mede denylist + 307 prior blocks); unfiltered still had bloed; deeper mine filled CURE but corpus-verb allen was noise (6 rows dropped). Labelled 18/18 on g4_clear_frame_filtered (13 INGESTION + 5 CURE).
- **Decision:** Adopt lemma priors default ON for clear-frame / preservare / regime exporters. Keep --no-lemma-priors escape hatch. Never disable denylist hard-skip. Prefer guideline verbs over --allow-corpus-verbs for CURE refill.
- **Reason:** Filter removes known non-food families without wiping rare frames when quotas/min-score are adjusted; false corpus verbs are an export hygiene issue, not a reason to loosen priors.
