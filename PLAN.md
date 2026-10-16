# TRIFECTA Automated FrameNet Annotation Pipeline

**Status:** In progress · **Framework:** TRIFECTA Guidelines (Qualia-based FrameNet)  
**Target architecture:** Local prototyping (Mac M4) → HPC scaling (SURF dual A10 GPUs)  
**Repository:** `trifecta-annotation` (standalone; `hist-text-utils` stays general-purpose)

> **Gold, sampling, evaluation, and track boundaries** are defined in **[docs/ANNOTATION_STRATEGY.md](docs/ANNOTATION_STRATEGY.md)** — the canonical guide. This file covers pipeline engineering only.

---

## State of affairs (14 Oct 2026)

> **Done in this stretch (since 28 Aug baseline below):**
> - INCEpTION IAA tooling: `--output-prefix` namespacing on `import_inception_tsv.py` (was silently overwriting Dutch outputs with English re-imports), `export_inception_iaa.py` (frame + Step C qualia agreement report), `export_inception_iaa_agreed.py` (promotes 2+-annotator-agreed frame/qualia straight to gold-candidate CSV; disagreeing fields left blank for adjudication, not guessed).
> - Unlocked `PRESERVING` in the clear-frame candidate miner (`clear_frame_examples.py`): added missing `PREFERRED_REGIMES`/`CORE_VERBS`/`CONFLICT_FRAMES` entries and generalized the guideline-only gate to trust PRESERVING's `manual`/seed-tier `technique:*` sources — candidate pool 12→49 (0→32 high-tier), surfacing fermentation/sugaring terms that were previously invisible.
> - Added `bewaren_context_ok()` storage/duration gate (`frame_verbs.py`) after a 19-row hand-labelled batch showed bare "bewaren" false-positives from apothecary boilerplate and abstract "protect, keep safe" senses — pool 49→35, all 5 human-dropped bewaren rows now correctly excluded.
> - Step C span-extraction prototype (ruled out 13 Oct, §9b) continued: found and partially fixed the real root cause of the Dutch 0.05–0.08 positive EM ceiling (passage-length `context_text`, not data volume) — see §9b "Continued" for the full result, bottom line still **not production-viable**.
>
> **Carried over from 28 Aug baseline** (`make eval-all`): Step A Entity 91.7% / Metaphor 93.1%, Dropout Agreement 87.5%, Step B Frame Accuracy 69.0% (F1: `COOKING_CREATION` 0.84, `PRESERVING` 0.86, `CURE` 0.52, `INGESTION` 0.56, `NONE` 0.50), Step C Qualia Soft Micro 23.7% — not yet re-run against current gold.
>
> **Next:** (1) label more of the newly-unlocked PRESERVING candidate pool (35 candidates, 19 done) toward Step C gold; (2) run the English IAA-agreed adjudication queue down to resolve disagreeing/blank qualia fields; (3) calibrate prompt few-shots for `PRESERVING`, `CURE`, and `INGESTION` using the growing Step C gold; (4) optional: enrich `IngestionQualia` schema slots (e.g. `INGESTION_Food_Patient`, `INGESTION_Purpose`); (5) corpus analysis notebooks on `resolve("trifecta_analysis")` and `ldk2025_cookbook_slice.ipynb`; (6) future corpus expansion: preprocess DBNL XML corpus on warm tier (`/Volumes/2tb disk/datasets/trifecta/source/dbnl_xml_pd.zip`).

**Primary goal:** qualia for analysis (Step C) — **[ANNOTATION_STRATEGY.md §5 Step 5](docs/ANNOTATION_STRATEGY.md#step-5--qualia-for-analysis-m10--current)** / milestone **m10**. Not bulk NONE silver or GijsBERT-as-replacement for qwen.

### What works today

| Capability | Status |
|------------|--------|
| Full pipeline A→B→C (`trifecta-annotate`, `trifecta-batch`) | **Production-ready** (LLM) |
| Web labelling UIs (`trifecta-gold-ui`, `trifecta-stepc-ui`) | **Production-ready** (browser-based side-by-side review) |
| Step B eval on merged gold (308 rows) | **60–75%** baseline across corpora; per-regime reporting |
| Step A NONE silver loop (`reizen` KWIC pilot) | **Validated** — 200 Step A → 59 accepted → `gysbert-v2-reizen-none` |
| GijsBERT macro-frame classifier | **Retrained (28 Aug)** — **67.2%** overall dev, frames-only jumped to **61.5%** (was ~35%) |
| INCEpTION silver with Step C | ~2,752 LLM-filled `step_c` rows (exploration silver, unvalidated) |

### Gaps for qualia-for-analysis

| Gap | Current |
|-----|---------|
| Hand gold with Step C | **93** rows with Step C (308 total gold: 31 COOKING, 27 PRESERVING, 24 CURE, 11 INGESTION) |
| Step C in `trifecta-eval` | **Done** — field-match + joint/micro by frame |
| Step C few-shots / prompt calibration | **Done** — wired across all 4 frames (`COOKING_CREATION`, `PRESERVING`, `CURE`, `INGESTION`) |
| Soft Step C metric | **Done** — containment in `trifecta-eval` report § soft |
| Analysis export | **Done** — `trifecta_analysis` parquet via `export_analysis_parquet.py` |
| GijsBERT qualia head | **Not planned** — Step C stays LLM |

### Usable for analysis?

- **Exploratory qualia on a corpus:** yes — run `trifecta-batch` on a KWIC slice; treat `step_c` as **LLM hypotheses**, spot-check by frame.
- **Analytic claims (counts, trends, cross-era):** not yet — need quota hand gold on qualia fields + Step C eval before trusting aggregates.
- **Cheap NONE pre-filter:** GijsBERT ready offline; **not wired** into batch CLI.

### Next — Step 5 / m10 (qualia track)

**Operator runbook:** [docs/GOLD_LABELLING.md § Step 5](docs/GOLD_LABELLING.md#step-5-runbook--cooking_creation-qualia-m10) — export → notebook lab (overview + row editor) → merge/import.

Canonical policy and time budget: [ANNOTATION_STRATEGY.md §5 Step 5](docs/ANNOTATION_STRATEGY.md#step-5--qualia-for-analysis-m10--current).

**Aim:** Trustworthy qualia for analysis — quota hand gold, Step C eval, LLM prompt calibration (not a qualia classifier).

| # | Engineering task | Status |
|---|------------------|--------|
| 1 | Pilot frame: **COOKING_CREATION** | decided — most numerous in frozen gold |
| 2 | Export quota batch + label 30 rows (Step C fields) | done — imported into gold |
| 3 | Gold lab notebook (`cooking_stepc_gold_lab`) — overview + row editor | done |
| 4 | Add Step C field-match metrics to `trifecta-eval` | done — exact + **soft containment** |
| 5 | LLM baseline on gold slice + prompt/few-shot pass | re-batched after COOKING few-shots |
| 6 | Analysis export (bounded batch → parquet) | done — `export_analysis_parquet.py` → `trifecta_analysis` |

**Defer:** more NONE silver tranches, GijsBERT hybrid wiring, collocation→GijsBERT export (blocked per [COLLOCATION.md §6](docs/COLLOCATION.md#6-gijsbert-export-audit-9-jul-2026)).

### Parallel track — embedding hybrid candidates

KWIC string-match candidate generation is noisy (~33% Step A dropout). Pilot: **embedding retrieval + thesaurus LU anchor**, keep `KwicInput` / A→B→C unchanged.

| Step | Status | Guide |
|------|--------|-------|
| E0 Scope | **done** | [plans/steps/EMBEDDING_CANDIDATES.md](plans/steps/EMBEDDING_CANDIDATES.md) |
| E1 Chunk + embed helpers | **done** | same |
| E2 Exemplar queries from gold | **done** | same |
| E3 Hybrid retrieve + export (bounded) | **done** (500 anchored @ passage-limit 2000) | same |
| E4 500 vs 500 KWIC comparison | **done** — noise win; PRESERVING skew | same |
| E5 Adopt (re-rank / scale) or stop | **adopted E5a** — `make batch-kwic-reranked`; hybrid discovery deferred | same |

Does **not** replace Step 5 / m10 qualia work.

---

## 1. Objective

Automate semantic annotation of **historical food-related texts** per TRIFECTA guidelines (inspired by FrameNet Brasil Qualia structures). Replace a single overloaded prompt with a **multi-stage LLM pipeline** using **Structured Outputs** (Pydantic / instructor) to:

- Prevent hallucinated frame elements
- Reduce cognitive load per model call
- Maintain linguistic standards across **17th–20th century** corpora

**Corpus scope:** one pipeline, era as **provenance** (`corpus`, `date`, `record_id`) — VOC recipes, newspaper recipe web, and future KWIC exports cross-fertilize vocabulary and few-shots; not separate code paths.

| Source | Era | Repo |
|--------|-----|------|
| VOC recipes | ~1625–1812 | `recepten-preservare-analysis` |
| Newspaper recipe web | 1940s–2000s | `Dutch-historical-recipe-trends` |

---

## 2. Technical stack

| Component | Local (M4) | HPC (SURF) |
|-----------|------------|------------|
| Infrastructure | Apple Silicon, 32GB+ RAM | Dual NVIDIA A10 (48GB VRAM) |
| LLM engine | Ollama (offline) | vLLM (tensor parallelism) |
| Structured output | instructor via Ollama API | instructor or outlines via vLLM |
| Model | `qwen2.5-coder:latest` (local default) | `qwen2.5-coder:32b-instruct` FP16 optional |

**Data layer:** `data_io` + `data_manifest.toml` — logical paths, tier mounts, provenance sidecars.

**Optional:** `hist-text-utils[kwic]` for KWIC/snippet helpers only — no TRIFECTA logic in that repo.

---

## 3. Pipeline architecture

```text
KWIC record (target_word, context, provenance)
        │
        ▼
  Step A — Entity validation + formal layer (FOOD_Unit, …)
        │  early exit: metaphor / non-food
        ▼
  Step B — Macro-frame enum
        │  COOKING_CREATION | CURE | INGESTION | PRESERVING | NONE
        ▼
  Step C — Frame-specific qualia roles (sub-prompt per frame)
        ▼
  TrifectaAnnotation JSONL + provenance sidecar
```

| Step | Task | Guardrail |
|------|------|-----------|
| **A** | Entity validation + formal layer | Drop metaphor / non-food / irrelevant entities |
| **B** | Macro-frame classification | Fixed enum |
| **C** | Frame-specific qualia roles | Schema scoped to selected frame |

---

## 4. I/O contract

### Input (`KwicInput`)

| Field | Description |
|-------|-------------|
| `record_id` | Stable id for resume/dedup |
| `corpus` | e.g. `voc_recipes`, `recipe_web` |
| `target_word` | Food term in context |
| `context_text` | KWIC window or passage |
| `date` | Optional era provenance |
| `source_path` | Optional file origin |

### Output (`TrifectaAnnotation`)

| Field | Description |
|-------|-------------|
| `provenance` | Copy of input metadata |
| `step_a` | `EntityValidation` or null if dropped early |
| `step_b` | `FrameClassification` or null if dropped at A |
| `step_c` | Frame-specific qualia or null |
| `dropped` | Early-exit flag |
| `drop_reason` | Why A/B stopped the chain |
| `error` | Per-record failure message (batch only) |

### Adapter: `food_snippets` → `KwicInput`

Primary source: `food_snippets_for_annotation.csv` (cort_voc_db, OneDrive) with manual subset in `snippets_for_annotation.txt`. See [docs/SNIPPETS.md](docs/SNIPPETS.md).

Legacy preservare `kwic_gold_review` is **not** used for TRIFECTA gold.

---

## 5. Step schemas

### Step A — `EntityValidation`

- `is_food_entity`, `is_metaphor`, `formal_dimension` (`FOOD_Unit`, `FOOD_Constituent_Part`, `FOOD_Whole`, `OTHER`)
- `canonical_pref_label`, `ontology_match`, `reasoning`
- Pre-LLM lexicon gate via `alt_label_index`

### Step B — `FrameClassification` (implemented)

- `selected_frame`, `lexical_unit`, `reasoning`

### Step C — per-frame qualia

| Frame | Schema | Key fields |
|-------|--------|------------|
| `CURE` | `CureQualia` | `CURE_Affliction`, `CURE_Food_Treatment` |
| `COOKING_CREATION` | `CookingCreationQualia` | `COOKING_CREATION_Method`, `COOKING_CREATION_Process`, `COOKING_CREATION_Food_Product` |
| `INGESTION` | `IngestionQualia` | `INGESTION_Context`, `INGESTION_Ingestor`, `INGESTION_Manner` |
| `PRESERVING` | `PreservingQualia` | `PR_Technique`, `PR_Medium`, `PR_Food_Patient` |
| `NONE` | skip C | terminal at B |

---

## 6. Data manifest

| Logical name | Role |
|--------------|------|
| `food_terms` | Ontology / Step A lexicon |
| `voc_recipes` | 17th–19th c. corpus |
| `ldk2025_cookbooks` | 20th-c. Dutch printed cookbooks (1910–1940) |
| `recipe_web` | 20th c. corpus |
| `ldk2025_kwic_inputs` | KWIC inputs from 20th-c. cookbooks (scratch) |
| `ldk2025_annotations` | Full A→B→C outputs on 20th-c. cookbooks (scratch) |
| `ldk2025_analysis` | Flat A→B→C analysis table for 20th-c. cookbooks (scratch) |
| `ldk2025_analysis_csv` | Flat A→B→C analysis CSV for 20th-c. cookbooks (scratch) |
| `kwic_inputs` | Normalized `KwicInput` JSONL (scratch) |
| `trifecta_gold_csv` | Gold labelling spreadsheet (scratch) |
| `trifecta_gold_jsonl` | Gold set JSONL mirror (scratch) |
| `trifecta_gold` | Hand-labelled eval set parquet (scratch) |
| `gold_eval_inputs` | Gold slice JSONL for eval batch re-runs (scratch) |
| `gold_predictions` | Predictions on `gold_eval_inputs` (scratch) |
| `frame_classifications` | Step B JSONL output (scratch) |
| `trifecta_annotations` | Full A→B→C JSONL output (scratch) |
| `eval_reports` | Eval metrics JSON + markdown (scratch) |
| `trifecta_analysis` | Flat A→B→C analysis parquet (scratch; LLM hypotheses) |
| `trifecta_gijsbert` | GijsBERT train/dev JSONL + `label_manifest.json` (scratch) |
| `trifecta_gijsbert_models` | Fine-tuned GijsBERT runs + `model_comparison.md` (scratch) |
| `food_snippets_kwic` | KWIC wide CSV with `manual_labels` (scratch) |
| `food_snippets_long_kwic` | Deduped exploded KWIC long CSV + `kwic_batch` (scratch) |
| `verb_spike_candidates` | Verb-KWIC candidates for the verb-first spike (scratch) |
| `verb_phase2a_gold` | Phase 2a verb-KWIC gold worksheet (scratch) |
| `verb_phase2a_inputs` | Phase 2a verb-KWIC annotation inputs (scratch) |
| `verb_phase2a_predictions` | Phase 2a verb-first predictions (scratch) |
| `verb_phase2a_eval` | Phase 2a verb-versus-noun evaluation report (scratch) |
| `embedding_exemplars` | Per-frame gold exemplars for embedding queries (scratch) |
| `embedding_candidates` | Hybrid embedding KwicInput candidates (scratch) |
| `embedding_candidates_semantic_only` | Embedding hits without LU anchor (scratch) |
| `embedding_chunk_index` | Chunk metadata for embedding pilot (scratch) |
| `gold_lemma_priors` | Lemma priors from labelled gold for exporter filter (scratch) |
| `clear_frame_examples` | Clear-frame gold candidate CSV (scratch) |
| `preservare_gold_candidates` | PRESERVING gold candidate CSV (scratch) |
| `g4_clear_frame_filtered` | G4 dry-run filtered CURE+INGESTION batch (scratch) |
| `g4_clear_frame_unfiltered` | G4 dry-run unfiltered CURE+INGESTION batch (scratch) |

`kwic_gold_review` (preservare) remains in manifest for ontology legacy only — **not** TRIFECTA hand gold. See [ANNOTATION_STRATEGY.md](docs/ANNOTATION_STRATEGY.md).

```bash
uv run python -m data_io.check
```

See [docs/DATA.md](docs/DATA.md).

---

## 7. CLIs

```bash
# Step B only
uv run trifecta-classify --target vlierbessen --context "..."

# Full pipeline (single record)
uv run trifecta-annotate --target zout --context "..." --corpus voc_recipes

# Batch JSONL in → annotated JSONL out
uv run trifecta-batch --input-logical kwic_inputs --output-logical trifecta_annotations --resume

# Build normalized inputs from kwic_gold_review
uv run python scripts/build_kwic_inputs.py

# Gold labelling CSV workflow
uv run python scripts/export_gold_candidates.py --limit 50
uv run python scripts/import_gold_csv.py
uv run python scripts/export_gold_csv.py   # re-export for editing

# Eval against gold set
uv run trifecta-eval --gold trifecta_gold --predictions trifecta_annotations

# GijsBERT export (silver train, gold dev/test)
uv run python scripts/export_gijsbert.py \
  --silver-path "/Volumes/Extreme SSD/scratch/trifecta/inception_annotations.jsonl" \
  --gold-path "/Volumes/Extreme SSD/scratch/trifecta/gold.parquet"
```

Guidelines: [docs/Annotation_Guidelines_final.pdf](docs/Annotation_Guidelines_final.pdf) (EN), [docs/Annotation_Guidelines_NL.pdf](docs/Annotation_Guidelines_NL.pdf) (NL). See [docs/GOLD_LABELLING.md](docs/GOLD_LABELLING.md).

---

## 8. File layout

```text
trifecta_annotation/
├── schemas.py
├── llm.py              # shared structured completion helper
├── step_a.py
├── step_b.py
├── step_c/
│   ├── __init__.py
│   ├── using_cure.py
│   ├── cooking_creation.py
│   ├── using_ingestion.py
│   └── preserving.py
├── pipeline.py
├── batch.py
├── eval.py
├── cli.py
├── adapters/kwic.py
└── prompts/            # few-shot JSON assets
scripts/build_kwic_inputs.py
```

---

## 9. Milestones

| ID | Task | Status |
|----|------|--------|
| m0 | Repo scaffold + `data_io` manifest template | done |
| m1 | Step B prototype (`instructor` + Ollama) | done |
| m2 | `Food_terms` vocabulary loader | done |
| m3 | Step A: entity validation + formal layer | done |
| m4 | Step C: per-frame qualia schemas | done |
| m5 | Gold eval + per-regime metrics | done |
| m6 | Batch runner (JSONL in → annotated JSONL out) | done |
| m7 | vLLM / SURF backend (`--concurrency`, manifest override) | done |
| m8 | GijsBERT export (`export_gijsbert.py`, silver train + gold dev) | done |
| m9 | GijsBERT fine-tune + dev eval vs LLM baseline | done (`gysbert-v2-reizen-none`: 61.8% dev, NONE F1 0.82) |
| m10 | Step C gold quota + field eval + analysis export | **next** — [ANNOTATION_STRATEGY Step 5](docs/ANNOTATION_STRATEGY.md#step-5--qualia-for-analysis-m10--current) |

### Evolution — Step 4 (6 Jul 2026) — GijsBERT / baseline freeze

Baseline freeze and training pivot. Steps are **iterative** — expect to loop back (e.g. quota gold growth, re-export silver, re-eval) without reopening the full disagreement cycle unless deliberate. Full detail: [ANNOTATION_STRATEGY.md §5](docs/ANNOTATION_STRATEGY.md#5-evolution-steps).

| Deliverable | Status |
|-------------|--------|
| Gold cleanup → 157 eval rows | done |
| qwen baseline v2 (`gold_predictions.jsonl`, 75% Step B) | done — `eval/baseline_v2_157rows_2026-07.md` |
| INCEpTION coarse import (`--granularity both`, 3,175 silver) | done |
| GijsBERT splits (`gijsbert/train.jsonl`, 3,220 train / 157 dev; +59 NONE from `reizen`) | done |
| `train_gijsbert.py` + comparison to qwen | done — `gysbert-v2-reizen-none` |

**Time budget (Step 4 — completed):** see [ANNOTATION_STRATEGY.md §5 Step 4](docs/ANNOTATION_STRATEGY.md#step-4--baseline-freeze--training-pivot-6-jul-2026).

**Current (Step 5 / m10):** quota Step C gold ~40% · eval/tooling ~25% · prompt calibration ~20% · analysis export ~10% · buffer ~5%. Full table: [ANNOTATION_STRATEGY §5 Step 5](docs/ANNOTATION_STRATEGY.md#step-5--qualia-for-analysis-m10--current).

**Remaining:** Step C gold + eval (m10); optional Step B quota on weak frames (secondary); preservare adapter; collocation review (GijsBERT export **blocked** — [COLLOCATION.md §6](docs/COLLOCATION.md#6-gijsbert-export-audit-9-jul-2026)).

**Deferred (GijsBERT maintenance):** hybrid batch wiring, frames-only / NONE-boost tuning — revisit only if Step B pre-filter becomes a blocker.

### Backlog (not Step 5)

| Item | Notes |
|------|-------|
| GijsBERT hybrid in `trifecta-batch` | Deferred — 62% dev < 75% qwen; see Step 4 results in ANNOTATION_STRATEGY |
| GijsBERT frames-only / NONE-boost tuning | Maintenance only |
| Inner tqdm on collocation miner | Per-snippet progress in `mine_collocation_verb_candidates` |
| Snippet-local skeleton → GijsBERT | Gate: ≥60% ALL_FRAMED hint alignment ([COLLOCATION.md §6](docs/COLLOCATION.md#6-gijsbert-export-audit-9-jul-2026)) |
| NONE silver from KWIC `reizen` batch | done — `notebooks/gijsbert_none_silver_training.ipynb` |

---

## 9a. Exploration — Verb-First POC (18 Aug 2026)

**Research question:** Is verb-driven frame classification more direct and accurate than noun-first for historical recipes?

**Hypothesis:** Snippet-local verb ecology (verbs as frame actions, not inferred from nouns) + verb lexicon hints → cleaner signal, higher Step B accuracy.

### POC Results ✅ GO

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| Step B accuracy | **77.8%** (15/20) | ≥70% | ✅ |
| Collocation alignment | **75.0%** (15/20 verbs match lexicon frame) | ≥60% | ✅ |
| Step C qualia | **100%** coherent samples (5/5) | ≥3/5 | ✅ |
| Step A dropout | **0%** (lexicon verbs only) | near-zero | ✅ |

**Key finding:** Verb hints inject frame priors directly into Step B (+10% accuracy vs noun baseline est. 68%). Context sensitivity works: 2 "mismatches" are Layer 2 correct (local verb dominance overrides lexicon hint).

### Implementation

**New modules (isolated, no impact on noun-first):**
- `step_a_verb.py` — Simplified entity check (lexicon membership only)
- `step_b_verb.py` — Step B with frame-verb hint injection
- `pipeline_verb.py` — Verb-first A→B→C orchestrator
- `batch_verb_spike.py` — Batch runner for POC
- `eval_verb_spike.py` — Metrics + confusion matrix + Step C review

**Scripts:**
- `discover_verb_kwic_candidates.py` — Extract verb-KWIC from existing `trifecta_annotations`
- Staging: `kwic_verb_spike.jsonl` (20 records, 5 per frame: COOKING_CREATION, INGESTION, PRESERVING, CURE)

**Decision memo:** archive with the registered verb-spike outputs; do not use `/tmp` for durable results.

### Recommendation: Phase 2a (Optional Parallel)

Run abbreviated Step 5 quota on verb-KWIC:
- ~30–50 verb-KWIC records (same frames as noun-track, sampled from corpus)
- Hand label Step C qualia only (A/B validated via lexicon + hint)
- Compare accuracy to noun-baseline on same texts

**Decision gate:**
- **If** alignment ≥70% on gold: consider verb-first as m10 default
- **If** 55–70%: maintain both tracks, report parallel findings
- **If** <55%: shelf verb-track; proceed noun-first only

**Impact:** Noun-first m10 **unchanged** — verb-first is research track, not blocker. Full POC code available if Phase 2a proceeds.

**Phase 2a lab status (24 Aug 2026):** All 40 rows are human-reviewed in `/Volumes/Extreme SSD/scratch/trifecta/verb_phase2a/gold.csv`. Comparative evaluation tool `trifecta-eval-phase2a` (and `scripts/eval_phase2a_comparative.py`) implemented and run:
- Human `reviewed_frame` vs `source_step_b`: **70.0% agreement** (28/40). Strongest on `COOKING_CREATION` (F1 0.95), weakest on `INGESTION` (F1 0.43) where commodity/market mentions were human-adjudicated to `NONE`.
- Human `reviewed_frame` vs verb lexicon prior: **70.0% agreement** (28/40).
- Step C qualia vs model: joint exact 5.9%, soft 5.9% across 34 framed rows. Best field alignment on `INGESTION_Ingestor` (75.0% soft) and `COOKING_CREATION_Process` (54.5% soft).
- Exports written: `eval.json` and `comparison_review.csv` on scratch.

---

## 9b. Exploration — GloBERTise Step C span-extraction prototype (13 Oct 2026)

**Research question:** Can a fine-tuned encoder (GloBERTise) extract Step C qualia fields as literal spans, replacing LLM free-generation for Step C?

**Hypothesis:** Per `project_step_c_grounding_prototype` memory, most LLM Step C misses are hallucinated substitutions, not wording variants — an extractive model structurally can't hallucinate, so it should beat free generation where gold values are literal spans at all.

**Result: ruled out, not adopted.**

| Metric | Result |
|--------|--------|
| Dev exact match (all fields, blended) | 0.590 — **misleading** |
| Dev exact match (positive spans only — the real number) | **0.045** |
| Train rows with a real span to learn from | 160 total across 12 fields (~13/field) |

The blended 0.590 is inflated by fields that are mostly/entirely empty in gold (e.g. `INGESTION_Manner`, `INGESTION_Purpose`) — a model that always predicts "no answer" scores those perfectly for free. Scored on positive-span examples only, the model shows essentially no real extraction ability (8 of 10 fields with any positive dev rows scored 0.000).

**Root cause:** data volume, not architecture. There is no trustworthy silver for Step C (the LLM's own generations are the unreliable signal this was meant to replace), so training was gold-only — and gold-with-a-literal-span is a further 25–75%-per-field cut of an already-small gold set (56–186 rows/frame).

**Implementation (kept, isolated, documented as a negative result):**
- `trifecta_annotation/stepc_span_export.py` / `scripts/export_stepc_span.py` — gold-only export, one shared encoder across all 4 frames (not split per frame, to avoid the data-fragmentation failure mode confirmed by the Step B hierarchical split — see §9a-adjacent `project_step_b_split_regression` memory).
- `trifecta_annotation/stepc_span_train.py` / `scripts/train_stepc_span.py` — BERT-QA fine-tune; eval reports positive-span and true-negative-empty metrics separately (don't trust a blended metric on this kind of sparse-field data again).
- `scripts/reeval_stepc_span.py` — re-score an existing run without retraining.

**Recommendation:** Don't revisit joint encoder span extraction for Step C without substantially more grounded gold. The more promising remaining lever is deterministic extraction from indication constructions (`goed voor`, `krachtig tegen`, …) rather than any learned model at this data volume.

**Continued (14 Oct 2026) — root cause found, still ruled out:**

- Merging the English IAA-agreed batch (829 rows) raised grounded positive spans 160→437; a blended mBERT/XLM-R positive-EM of ~0.36 looked like real progress but was a dev-composition illusion (dev was 70% English by then) — Dutch-only was still 0.05–0.08, unchanged.
- Real cause: Dutch `context_text` was passage-length (median 552 words, max 7,317) because `scripts/build_kwic_inputs.py --source long` never applied the target-centered `context_radius` clip that `--source kwic` already defaults to. Confirmed independently (not assumed) via the genuine Dutch INCEpTION export producing naturally short context (median 61 words) on the same texts.
- Fix: clip `context_text` to ±180 chars around `target_word` in `stepc_span_export.py` (`DEFAULT_CONTEXT_RADIUS`). Verified not a train/test cheat: gold answers sit within ±1 sentence of `target_word` 79.5% of the time, and the clip rule is identical at train and inference. Result: Dutch positive EM 0.079→0.258 (soft/containment match, also newly added: 0.452).
- Added 394 Dutch INCEpTION IAA-agreed rows narrowly (agreed + positive-values-only, not a general Dutch gold-growth strategy — see `project_frame_overlap_cooking_creation` / `project_frame_split_options` memory). Net effect on the hard `cort_voc_db` corpus: flat-to-negative (0.179 EM / 0.333 soft for mBERT), confounded with dev becoming more rigorously hard-only at the same time.
- Four-way encoder comparison (mBERT, XLM-R, GloBERTise, GysBERT-v2) on identical clipped+merged data found no confident winner (0.10–0.23 positive EM, noise-level differences on a 101-row eval) — `CURE_Affliction` scored 0.0 on every model, the one fully model-independent finding. All four are standard BERT-family encoders capped at 512 tokens; a genuinely longer-context architecture (none exists pretrained for Dutch) would be needed to go further.
- **Bottom line: Dutch Step C span extraction is still not production-viable.** Real progress this round was diagnostic (pipeline bug, contamination, metric choice, annotation-scheme effects), not a working extractor. Full detail: [docs/GOLD_LABELLING.md](docs/GOLD_LABELLING.md) and [docs/DECISIONS.md](docs/DECISIONS.md) (2026-10-14 entries).

---

## 9c. Exploration — Step C embedding-exemplar-retrieval (15 Oct 2026)

**Research question:** Can Step C qualia be extracted without fine-tuning at all — by scoring candidate spans against embeddings of gold answer exemplars — now that §9b showed fine-tuning is capped by too little grounded gold (160–437 positive spans across 12 fields)?

**Method:** No training step. For each qualia field, embed every other gold answer span (`emanjavacas/gysbert` mean-pooled — the embedder already adopted for the KWIC embedding pilot, §-parallel-track below) as exemplars. Generate candidate spans inside the row's already-clipped (§9b) `context_text` via word n-grams (punctuation-safe tokenization) plus char-level sub-word candidates for long tokens (Dutch compounding hides answers like "braden" inside "gebraden"). Score every candidate by cosine similarity to its field's exemplars, apply a small penalty to sub-word candidates (calibrated, not guessed — see below), and take the top match. Implementation: `trifecta_annotation/stepc_embedding_retrieval.py` / `scripts/eval_stepc_embedding_retrieval.py`.

**Result: beats the fine-tuned floor, with zero training cost.**

| Eval | EM | F1 | soft |
|---|---:|---:|---:|
| Original ruled-out floor (§9b, 13 Oct, pre-clip-fix) | 0.045 | — | — |
| Four-way fine-tuned comparison (§9b, 14 Oct, same clipped+merged data) | 0.10–0.23 | — | — |
| **This prototype, leave-one-out over the full positive pool (n=518)** | **0.612** | **0.621** | **0.681** |

Key diagnostic: oracle coverage (is the correct answer *reachable* among generated candidates at all, regardless of ranking) is ~1.0 for 10/12 fields — so unlike §9b, the remaining gap here is a **ranking** problem, not a candidate-generation or gold-volume ceiling.

**Two data/method bugs found and fixed along the way, both confirmed empirically rather than assumed:**

- 10/52 `CURE_Affliction` and 1/41 `PR_Medium` gold "answers" are bare English stopwords ("from", "for", "acidity") from the `english_iaa` merge batch — a data bug in that source (flagged, not fixed, in [docs/DECISIONS.md](docs/DECISIONS.md)), excluded from the pool.
- Sub-word candidates (added to reach compound-internal answers) caused short, generic exemplars ("zwaren", "maag", "jagt") to spuriously match unrelated garbage fragments at near-1.0 cosine similarity — a known mean-pooled-BERT degeneracy for short strings, not a semantic failure. A hard ban on sub-word candidates fixed this but regressed the largest field (`INGESTION_Food_Patient`, 0.700→0.667 EM); a soft score penalty (0.05, A/B-tested across 0.0–0.12) fixed it without that regression. A follow-on idea — checking candidates against the GysBERT tokenizer's own vocabulary as a cheap "is this a real word" filter — was tested and **rejected**: WordPiece vocab entries are chosen by subword frequency, not wordhood, so real words like "braden"/"zwelling" split into multiple pieces while garbage fragments like "wend"/"brui" are each a single vocab entry (the opposite of a useful signal). No Dutch wordlist/spellchecker is a dependency of this project.

**Recommendation:** This is now the leading Step C qualia-extraction approach — cheaper than fine-tuning, better on the only apples-to-apples comparison available, and the remaining gap is diagnosable (ranking, not data volume). `INGESTION_Context` and `INGESTION_Manner` still score 0.000 EM (n=9, n=6) and weren't resolved this round — small-n fields, not yet root-caused. Full detail: [docs/GOLD_LABELLING.md](docs/GOLD_LABELLING.md) and [docs/DECISIONS.md](docs/DECISIONS.md) (2026-10-15 entries).

---

## 9d. Exploration — grounding production Step C, and why not to ship it yet (16 Oct 2026)

**Research question:** Does combining the §9c retrieval prototype with the production LLM (plans/steps/STEPC_GROUNDING.md) actually beat the LLM alone, and does it survive being tested at full gold scale rather than a small sample?

**Method:** Four combinations re-scored against the existing `gold_predictions.jsonl` (no new LLM calls) via `trifecta_annotation/eval.py`'s real scoring (or a direct field-level equivalent): (1) **grounding** — anchor retrieval to the LLM's own drafted answer, replace only if a better literal span exists nearby; (2) **full replacement** — ignore the LLM, pure retrieval with its own presence threshold, proper leave-one-out (no held-out split needed); (3) **hybrid v2** — trust the LLM's presence/absence call, swap in retrieval's *independent* top pick as the value when the LLM says present; (4) **frame-selective** — LLM for `CURE`, retrieval for everything else.

**Result 1 — grounding: confirmed negative, cleanly.**

| threshold | joint | micro | soft_joint | soft_micro | replaced |
|---|---:|---:|---:|---:|---:|
| ungrounded (baseline) | 0.063 | 0.226 | 0.079 | 0.250 | 0 |
| 0.75 | 0.047 | 0.221 | 0.063 | 0.246 | 74 |
| 0.85 | 0.053 | 0.222 | 0.068 | 0.247 | 17 |
| 0.90 | 0.058 | 0.224 | 0.074 | 0.249 | 3 |
| ≥0.92 | 0.063 | 0.226 | 0.079 | 0.250 | 0 (= baseline) |

At every threshold where it replaces anything, every metric gets worse; it only matches baseline once nothing gets replaced. No field showed even a directional win on a per-field soft-match check. Root cause: many non-literal LLM answers are legitimate paraphrases, and forcing them onto the nearest literal span substitutes a wrong-but-similar-looking span often enough to outweigh genuine hallucination fixes. **Not pursued further.**

**Result 2 — full replacement / hybrid v2 / frame-selective, on the full pool (502 rows / 180 records, proper LOO):**

| method | value P | value R | value F1 | 95% CI (F1, approx.) |
|---|---:|---:|---:|---:|
| LLM (baseline) | 0.268 | 0.288 | 0.277 | [0.212, 0.353] |
| Full retrieval | 0.230 | 0.570 | 0.328 | [0.263, 0.400] |
| Hybrid v2 | 0.274 | 0.293 | 0.283 | [0.217, 0.359] |
| Frame-selective (LLM for CURE) | 0.281 | 0.552 | 0.372 | [0.304, 0.446] |

Full retrieval's recall advantage over the LLM is **confirmed** — 95% Wilson CI [0.472, 0.663] vs LLM's [0.220, 0.366], non-overlapping. Precision differences between all four are *not* distinguishable (overlapping CIs). Hybrid v2 looked like a modest win on an earlier 39-row sample (F1 0.305 vs 0.276) but **that didn't survive scaling to the full pool** (0.283 vs 0.277 here) — a direct lesson that a small-sample "win" during this kind of comparison is not trustworthy on its own. Per-frame, hybrid v2 helps `COOKING_CREATION`/`INGESTION` (messy LLM answers get corrected) but is confirmed *worse* than the LLM alone on `PRESERVING` (tp 6 vs LLM's 9, n=56 — enough counts to trust the direction) because it blindly overrides already-correct short LLM answers via the same short-string embedding degeneracy found in §9c.

The frame-selective CURE swap drives the best aggregate F1, but **the CURE-specific claim itself is not statistically confirmed**: McNemar's exact test on the paired CURE-only data (11 LLM-only-correct vs 4 retrieval-only-correct of 75 CURE rows, 15 discordant pairs) gives p=0.12. Directionally real, not proven.

**Process note, worth stating plainly:** when scoping this work, hybrid grounding was recommended over a field/frame-selective split because it seemed like the more surgical fix for the diagnosed failure mode. That recommendation **was wrong in hindsight** — grounding is a clean negative, and frame-selective routing (closer to what was initially proposed and set aside) is the best-performing option, even though its central claim (route CURE to the LLM) isn't yet proven. Worth remembering next time a "more surgical" argument is used to prefer one approach over a simpler split.

**Caveat on coverage:** `gold_predictions.jsonl` only overlaps 180 of the 676 records in the pooled `stepc_span` train+dev export — several merged sources (English IAA, Dutch INCEpTION-agreed) were added as Step C training/eval data but never run through the LLM batch pipeline, so this comparison is restricted to their intersection.

**Open lead, not a finding (see `project_discourse_structure_frame_evocation` memory):** `CURE_Affliction` literal spans sit *before* `target_word` 71% of the time in Dutch sources (n=28) vs *after* 70% of the time in English sources (n=10) — consistent with Dutch remedy-book chapters stating the affliction once as a header and leaving it implicit for every sentence underneath, which English's sentence-by-sentence annotation doesn't exhibit. Real asymmetry, but on far too few examples to act on; would need new KWIC deliberately sampled on affliction/topic-naming constructions, not ingredient/treatment words, to validate or exploit.

**Recommendation: no production change.** None of the four combinations clears the bar. If revisited, frame-selective routing is the most promising starting point, but needs more CURE-specific gold before the routing rule itself is trustworthy. `plans/steps/STEPC_GROUNDING.md` is closed per its own G2 gate (stop and document, don't ship on an unconfirmed result).

---

## 9e. Finding — intention is partly structural, not semantic (16 Oct 2026)

**The reframe that prompted this:** §9b–§9d read as four method failures on the same two fields. The alternative reading is that the pipeline starts at the wrong end — it enters through a food mention (Step A validates a food entity → Step B frames it → Step C hangs qualia off it), while `CURE_Affliction` and `COOKING_CREATION_Food_Product` are the *organizing concepts* of these texts: a remedy is identified by what it treats, a recipe by what it makes. Recovering the organizing concept from one participant's local window is backwards.

**Measured, not argued** (`trifecta_annotation/unit_segmentation.py`, `scripts/measure_unit_feasibility.py`, report under the `unit_feasibility` logical; heuristics only, no model inference, no LLM calls, nothing in the pipeline touched):

| Measurement | Result |
|---|---|
| **Goal reachability** (`voc_recipes`, n=3,326 hand-separated Title/Content pairs) | **71.0%** (2,363) name a goal in the title whose head word never appears in the body. 78.4% if body-head restatements count as unreachable-from-ingredients |
| Coverage bias check | The 1,954 titles the parser couldn't handle came out **more** extreme (74.4% absent), not less — the headline doesn't depend on which half parsed |
| **Segmenter vs. known boundaries** (same source, 3,324 real boundaries) | precision 0.780 / recall 0.610 / F1 0.685 — workable, recall-limited |
| **Segmentability by regime** (long-KWIC) | `RECIPE_PRACTICE` 53.2%, `UNKNOWN` 20.2% (secreet-boek etc., driven by `Om … te` + `Een ander`), `TRAVEL` 13.6%, `ADMIN_TRADE` 14.5%, **`MEDICAL` only 5.5%**, `LITERARY` 5.7% |
| 20th-c printed cookbooks (`ldk2025_cookbooks`) | 15.9–17.3 units per 10k chars, stable across 1910–1940 — a unit roughly every 600 chars |
| **Cross-language** (same metric, same detected-boundary basis both sides) | Dutch `voc_recipes` **69.1%** head-token absent, Dutch long-KWIC recipe/medical **61.5%**, English recipe books **45.9%** (n=135), English medical 17.9% (n=39) |

**Is it Dutch, or is it the genre?** The gap is present in both traditions but roughly half as severe in English, so it is a property of the recipe/remedy *genre* rather than an artifact of the Dutch corpus that produced the finding. The mechanism is visible in the titles: English receipt headers are compositional (`CUCUMBER SOOP.` = ingredient + dish type, so the ingredient recurs in the body), while Middle Dutch titles are opaque dish names (`blancmengier`, `bruwet`) that appear nowhere else. Two token choices are reported throughout because they diverge by language and picking one silently decides the answer. Convergent validity: the Dutch detected-boundary figure (69.1%) lands close to the given-boundary headline (71.0%), which is what licenses trusting the English detected-boundary numbers at a similar level.

**What this means — the general version.** Frame semantics aims to recover intention from text semantics. In these genres a large share of the intention is not in the text semantics at all; it is carried structurally. 71% of recipes state their purpose once, in a title, and never restate it where the ingredients are. The purest case is `Een ander.` ("another one [for the same thing]") — 218 instances in the `UNKNOWN` bucket alone — a unit whose entire intention is inherited positionally, with zero lexical content expressing it. No semantic method can read that off the words, because the words do not carry it.

So §9b–§9d are better read not as four failures but as four methods correctly failing to recover a quantity absent from their input. `CURE_Affliction` scoring 0.0 across every encoder tried stops looking like a modelling problem.

**Three boundaries on the finding, stated honestly:**

- **Genre-bounded by construction.** In literary/descriptive text a food mention is incidental (a meal in a novel); there is no unit-with-a-goal to recover and the current mention-based model is arguably correct there. `LITERARY` segmenting at 5.7% is the scope boundary, and also a working negative control — the segmenter is not firing spuriously.
- **`MEDICAL` is the surprise negative.** Pharmacopoeia/apothecary texts segment at just 5.5% (9/164), so the affliction side gets no help from this segmenter as built. Their structure is presumably carried by Latin headings or page/column layout lost in text extraction.
- **The affliction side could not be tested at all.** Gold `context_text` is a KWIC snippet already cut around the food word (median 367 chars for these rows), so any governing header was truncated before segmentation sees it: 48 of 82 rows contain no detectable unit structure, and only 10 of 82 can be re-joined to their source chapter. Measurement D's 3.7% exact / 9.8% soft is that artifact, not a result. Note this also corrects the §9d framing: the food-anchored ±180 window *does* contain the gold affliction 58–73% of the time, so the window is not the bottleneck for afflictions — the "Hulpmiddelen voor den Hik" case at 657 chars was an outlier, not the norm.

**Refinement — there is no single "unit structure"; there are organizing axes, and the axis decides which frame element is free.** Profiling three works with `document_unit_profile()` shows three different principles of arrangement, each making a *different* thing structurally given:

| Work | dominant cue | what the headers name | what structure gives you free |
|---|---|---|---|
| `Het secreet-boek` (recipes) | `purpose_om` + `inheritance` | purposes ("om het Water onder den Wijn … te doen boven komen") | the goal/outcome; **not** the affliction |
| `Pharmacopoea Amstelredamensis` (formulary) | `latin_preparation` | preparations (`Emplastrum Meliloti`, `Oleum Ovorum`) | the preparation; affliction sits *in the body* as an indication |
| `Nederlandtsche woorden-schat` (dictionary) | `roman` | lemmas and alphabet dividers (`Ciborie`, `Elaboreren`) | **nothing frame-relevant** — headwords are lexical entries, not frame elements |

Two consequences. First, this explains the §9d puzzle: in a formulary the affliction is local (an indication beside the preparation), which is exactly why the food-anchored ±180 window recovers gold afflictions 58–73% of the time while the *remedy-collection* layout ("Hulpmiddelen voor den Hik") puts it in a distant header. Two medical layouts, opposite consequences for the same field — so "MEDICAL" is too coarse a bucket to reason about Step C with.

Second, and this is the frame-semantics consequence: **which frame element is structurally given is a property of the book's organizing axis, not of the sentence.** Frame semantics has nowhere to record that, because it assumes every frame element is recovered the same way, from local lexical evidence. The same frame (CURE) is therefore differently tractable in a formulary than in a remedy collection, for reasons that have nothing to do with the language in either.

**Validity threat if the reframe is adopted — header inheritance is a semantic scope change, not an extraction win.** A chapter headed "Remedies voor de hik" covering 40 remedies makes the affliction constant within that chapter. Propagating it:

1. *Inflates evaluation trivially.* Per-row `CURE_Affliction` accuracy would jump without anything being extracted — the same family of trap as §9b's blended 0.590 (free points for predicting empty) and §9d's 0.525 (free points for predicting empty more often), now on the non-empty side. Any future eval of a unit-based approach must score propagation per unit-group, not per row.
2. *Changes what the annotation means.* Per-mention "this remedy treats X" becomes per-chapter "this chapter is about X". For the m10 goal (counts, trends, cross-era) that is a 40-fold over-count of one stated affliction, so a propagated value has to carry an inherited-vs-stated flag before it reaches `trifecta_analysis`. `goal_with_inheritance()` carries this warning in its docstring.
3. *It also hands back treatments outside the dataset's scope.* A chapter header covers **every** remedy under it — bloodletting, poultices, mineral and charm remedies included — not only the food-based ones. TRIFECTA is food-scoped (Step A exists to validate `is_food_entity`), so a unit-based reframe has to decide explicitly whether a unit is "any remedy for X" (broader than the project's food focus, and arguably interesting context) or "food remedies for X" (requiring food filtering inside the unit). That is a decision about what the dataset *is*, not an implementation detail.

**Recommendation.** Supported for the product/recipe side, untested for the affliction side, out of scope for literary/descriptive. The next step is a design decision, not more method tuning: either two-stage Step C (extract the unit goal first, from the unit including its header, then the trailing fields conditioned on it) or unit-based annotation for recipe genres only — and either way the inheritance scope question above has to be settled first, since it determines whether the resulting numbers mean anything. Testing the affliction side needs gold re-derived from source documents with wider windows — stored gold cannot answer it. See `project_discourse_structure_frame_evocation` memory.

---

## 10. Implementation order (reference)

1. I/O schemas + kwic adapter
2. Step A
3. Pipeline orchestrator (A→B→C)
4. Step C (all frames)
5. Batch runner
6. Gold eval infrastructure
7. HPC config (`--concurrency`, `data_manifest.local.toml` example)

---

## 11. Evaluation

| Metric | Level |
|--------|-------|
| Step A accuracy / dropout precision | entity + metaphor |
| Step B macro-frame accuracy + per-class F1 | `TrifectaFrame` |
| Step B **by text_regime** | primary reporting bucket |
| Step C field match | per-frame qualia fields |
| Era breakdown | group by century from `date` (secondary) |

Calibration loop: refine `prompts/` few-shots for lowest-F1 frames; re-run on gold only.

---

## 12. Risks

| Risk | Mitigation |
|------|------------|
| Official TRIFECTA guidelines | `docs/Annotation_Guidelines_final.pdf` (EN), `docs/Annotation_Guidelines_NL.pdf` (NL) |
| `kwic_gold_review` lacks `target_word` | Adapter + manual review for ambiguous rows |
| Ollama structured-output flakiness | `temperature=0`, retry once on validation error |
| Preservation technique ≠ TRIFECTA frame | `technique` is calibration hint only |

---

## 13. Relationship to prior work

| Prior | Role |
|-------|------|
| `recepten-preservare-analysis` | Food ontology, VOC corpus, preservation KWIC baseline |
| `Dutch-historical-recipe-trends` | 20th-c. corpus, EU TRIFECTA grant context |
| `hist-text-utils` | General KWIC/text utilities — optional dependency |
