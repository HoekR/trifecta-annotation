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

---

## 2026-10-14: Clip Step C `context_text` to a target-word-centered window

- **Context:** Dutch Step C span-extraction stuck at ~0.05–0.08 positive EM even after merging more grounded gold. Root cause: `scripts/build_kwic_inputs.py --source long` (the path that built the Dutch gold pipeline) never applied the `context_radius` clip `--source kwic` already defaults to, so Dutch `context_text` was passage-length (median 552 words, max 7,317) — a needle-in-haystack problem no amount of training data fixes. Verified clipping isn't a train/test cheat first: gold answers sit within ±1 sentence of `target_word` 79.5% of the time, and the clip rule (center on `target_word`, which Step A/B always know before Step C runs) applies identically at train and inference time.
- **Decision:** Clip `context_text` to ±180 chars around `target_word` inside `stepc_span_export.py` (`DEFAULT_CONTEXT_RADIUS`, reusing the existing `local_context_window` helper), applied uniformly to every record regardless of source. Accept the ~9% of Dutch positive examples lost where the answer falls outside the radius as an honest, disclosed recall ceiling — do not chase it with a larger radius without re-checking the wrong-entry-match risk that uncovered (see below).
- **Reason:** Dutch positive EM rose 0.079→0.258 (soft match 0.452) on the same eval; the clip also incidentally excludes some pre-existing wrong-span contamination from `find_span()`'s naive first-match behavior over long concatenated documents, which was never real signal.

## 2026-10-14: Add soft/containment match to the Step C span-extraction eval

- **Context:** Raw exact-match on BERT-QA span predictions was always going to be unfair for archaic Dutch — span boundaries are debatable and there's no single canonical wording. The LLM-based Step C eval already has a precedent for this exact problem (`soft_qualia_match`, bidirectional substring containment, used for the `soft` Step C scores elsewhere in this doc) that the span-extraction eval (`stepc_span_train.py`) didn't carry over.
- **Decision:** Added a `soft_match` metric (same containment logic) to `_evaluate_predictions`, reported alongside EM and token F1 — not replacing either. Soft match alone would let an oversized prediction "contain" the gold answer for free; token F1 penalizes that through precision, so all three stay in every report.
- **Reason:** Consistency with the project's existing eval philosophy (`eval_strictness` in `plans/iteration.toml`: exact for strict reporting, soft for judgment); the gap between EM and soft match on Dutch (0.258 vs 0.452) is itself informative about how much of the miss is wording vs. real extraction failure.

## 2026-10-14: Dutch INCEpTION data — narrow use only, not a general Step C gold-growth strategy

- **Context:** 802 overlapping Dutch INCEpTION targets available (394 frame-agreed, 74 literal-span-groundable Step C values at 100%), far more than the 14 rows previously in gold from this source. Tempting as a general fix for thin Dutch Step C data, but four reasons argue against leaning on it broadly: (1) curated/hand-picked document pool, not the hard `cort_voc_db` material; (2) short windows trivialize true-negative rejection; (3) "empty" fields are empty by omission (positive-seeking annotation), not deliberate negative judgment like the main gold workflow; (4) annotators can skip confusing cases, the production cascade cannot. The separate Dutch INCEpTION annotation *effort* was also discontinued over low inter-annotator agreement — task difficulty, not just annotator skill, per the diagnosis in `docs/GOLD_LABELLING.md`.
- **Decision:** Merged only the inter-annotator-**agreed** subset, and only treated its **positive, literal-span-groundable values** as training signal — not its empty fields as negatives, and not as a template for growing Dutch gold generally. Built durable source-composition tracking (`source_tag` per example, `EASY_SOURCE_TAGS` excluded from the dev split by construction, counts recorded in `field_manifest.json`) so this and English-sourced data can never again silently dominate an eval set the way the first English merge did.
- **Reason:** Retraining on the merged data showed flat-to-negative results on the hard corpus (0.179 EM / 0.333 soft, down from 0.258/0.452 pre-merge) — confirms this data helps least exactly where help is needed, and justifies treating it as a narrow, bounded addition rather than the fix.

## 2026-10-15: Adopt embedding-exemplar-retrieval as the leading Step C qualia approach

- **Context:** The fine-tuned BERT-QA span extractor (2026-10-13/14 entries above) was capped by gold volume, not fixable without substantially more grounded gold. A zero-training alternative — score candidate spans against embeddings of every other gold answer span for the field (`emanjavacas/gysbert` mean-pooled) — doesn't need per-field training volume, only exemplars to compare against.
- **Decision:** Adopt `trifecta_annotation/stepc_embedding_retrieval.py` / `scripts/eval_stepc_embedding_retrieval.py` as the leading Step C extraction approach. Leave-one-out eval over the full positive pool (n=518): EM 0.612, F1 0.621, soft 0.681 — beats the four-way fine-tuned comparison's 0.10–0.23 EM range on the same clipped+merged data. Candidate generation uses punctuation-safe word n-grams plus char-level sub-word candidates (for Dutch compounds), with sub-word candidates scored at a flat −0.05 penalty (A/B-tested 0.0–0.12 on the full LOO pool) rather than excluded outright — exclusion fixed the degeneracy but regressed `INGESTION_Food_Patient` (0.700→0.667 EM), the penalty did not.
- **Reason:** Oracle-coverage diagnostic (is the correct answer reachable among generated candidates at all) is ~1.0 for 10/12 fields, confirming the remaining gap is a ranking problem, not a data-volume ceiling like the fine-tuned approach — meaning further gains are tractable without more gold labelling.

## 2026-10-15: `english_iaa` batch contains junk Step C values — flagged, not fixed

- **Context:** Diagnosing embedding-retrieval misses on `CURE_Affliction` found its top wrong predictions were all driven by a handful of exemplars that turned out to be bare English stopwords ("from", "for", "acidity") rather than real affliction names. Traced to source: 10/52 `CURE_Affliction` and 1/41 `PR_Medium` positive-span rows from the `english_iaa` merge batch (`inception_en_iaa_agreed_gold.csv`, via `scripts/export_inception_iaa_agreed.py`).
- **Decision:** Excluded these specific values from the embedding-retrieval exemplar pool (`JUNK_EXEMPLARS` in `stepc_embedding_retrieval.py`) and from LOO eval. Did **not** fix the upstream export/import — the likely cause is a token-alignment or span-boundary bug in the WebAnno→gold-row conversion (`scripts/export_inception_iaa_agreed.py` / `trifecta_annotation/adapters/inception_tsv.py`), which also means these same bad rows are still present as positive training signal for the fine-tuned BERT-QA extractor's train split.
- **Reason:** Scope — this round was about proving the retrieval method's potential, not auditing the INCEpTION pipeline. Flagging here so the export bug doesn't get silently relied on or rediscovered from scratch; fixing it is a separate follow-up.
