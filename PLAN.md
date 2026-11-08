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

## 9f. Finding — the product-side header heuristic is a confirmed (if underpowered) negative on current gold (23 Oct 2026)

**CORRECTED same day — the first pass had a real anchoring bug, not a structural finding.** It defaulted rows to position 0 (or "first occurrence of `target_word`") whenever it couldn't otherwise locate the target, which collapses to the *chapter's own start* whenever `context_text` already is the wide window — i.e. it would confidently pick the wrong unit for a reason that had nothing to do with whether headers work. Caught because Rik pushed back on the result not matching the already-established "Hulpmiddelen voor den Hik"-style header finding. Fixed by gating the measurement on locatability (below) instead of silently resolving it. Numbers in this section are the corrected ones; the retracted first-pass numbers are not reproduced here.

**What this tests:** §9e called the product side ("supported," unlike the untested affliction side) the natural next step — either two-stage Step C or unit-based re-annotation. Before building either, measurement F (`scripts/measure_unit_feasibility.py --only F`) tests the specific mechanism directly: does `unit_segmentation.py`'s regex header detector recover gold `COOKING_CREATION_Food_Product` / `PR_Food_Patient` values, end to end, on the actual Step C gold pool? Scoped to `RECIPE_PRACTICE`/`UNKNOWN` per a scoping check first — the Van Lennep 1823 travel diary (447k chars, `colonial_books`, not yet in any corpus export) scores 0.31 unit-cues/10k chars with zero false positives from its dated entries, an order of magnitude below even the `LITERARY` control in §9e's measurement C. Confirms structural headings are a recipe-collection story, not a running-text one, as a real example rather than only the corpus-average numbers already in §9e.

**A second, independent problem surfaced while fixing the first: `target_word` is frequently not a locatable literal span at all.** Of the 26 `RECIPE_PRACTICE` gold rows, 13 (all `preservare`-corpus) have **zero** case-insensitive occurrences of `target_word` in their own `context_text`, even after historical-spelling normalization (target `paling`, context spells it `palinck`/`palinc`; target `postelein`, context never uses that word at all). Of the remainder, several `cort_voc_db` rows have the target repeated many times across one shared chapter (`olie` ×13, `vet` ×8) with no char-offset stored anywhere in the schema to say which occurrence a given gold row is about. Measurement F now gates on **exactly one unambiguous occurrence** and reports the rest as `target_unlocatable`/`target_ambiguous` rather than guessing — this is a limitation of `target_word`-based position-finding generally (it will affect any future structure-aware mechanism built the same way), not specific to header extraction.

**Unlike D, truncation is not the main constraint here.** `cort_voc_db` rows' `context_text` runs up to tens of thousands of chars (often the whole chapter already); only `inception_snippets` rows (99% of the `UNKNOWN` bucket) are short enough that a `food_snippets_long_kwic` rejoin was attempted, and that rejoin essentially never found a match. So — for the rows that survive the locatability gate — this measures the header-detection heuristic's own precision, not a data-availability gap.

| Regime | n | target locatable | narrow window has gold value | no units (of locatable) | goal extracted | exact | soft |
|---|---:|---:|---:|---:|---:|---:|---:|
| `RECIPE_PRACTICE` ⚠ | 26 | 8 (30.8%) | 30.8% | 50.0% | 37.5% | **0.0%** | **0.0%** |
| `UNKNOWN` ⚠ | 196 | 55 (28.1%) | 33.2% | 98.2% | 1.8% | 0.0% | 0.0% |

⚠ both buckets are now small on the metric that matters (locatable n = 8 and 55) — this is the honest-anchor result, but it is underpowered, not a confident negative the way the retracted first pass looked. Only ~30% of either pool is even scoreable at all; most of this table is really a finding about `target_word` locatability, not about headers.

**Where a goal was extracted (3/8 `RECIPE_PRACTICE` rows), it was wrong every time** — not absent, wrong:

- gold `soep` vs extracted `Snoek` (a numbered sub-entry naming a dish, not the chapter-level goal)
- gold `vis` vs extracted `Aal` (a numbered sub-entry naming a different fish than the gold value)
- gold `Kwik` vs extracted `de Sublimaat corrosief` (a `purpose_om` header for a neighboring passage)

**Why this differs from §9e's own numbers.** §9e's 71% "unreachable" measurement (B) ran on `voc_recipes`' *given* Title/Content CSV columns — a clean, pre-segmented signal, with no locatability problem at all (Title and Content are already paired per row). This heuristic instead has to regex-detect the boundary inside raw flowing KWIC/chapter text *and* locate the right occurrence *and* pick the right field out of competing cue types, which is a materially harder task on every axis B didn't have to solve. The corpus-level structural claim (§9e) and this extraction mechanism's precision are different questions; this measurement answers the second one, on a small honestly-scoreable n: not promising, not yet proven either way.

**Recommendation: do not build two-stage Step C or unit-based re-annotation on top of `unit_segmentation.py`'s current cue detector, and do not treat this measurement as the final word either — it's underpowered.** The underlying structural claim (§9e) stands. The rollout path, if pursued, needs (a) a real per-recipe title/header field sourced at ingestion from structured data like `voc_recipes` (given boundaries, not regex-detected ones) rather than raw KWIC/chapter text, which also sidesteps the locatability problem entirely, or (b) a smarter boundary+granularity model plus a stored char-offset for the target occurrence — not a tuning pass on the existing regex cues. No pipeline change made; this is a measurement only, same as §9d. See `project_frame_split_options` memory for the decision this bears on.

---

## 9g. Implemented — structural parse as a pre-Step-A stage, 2-way search, "detect but don't trust" (23 Oct 2026)

Per-session follow-up to §9f, superseding (a) above: rather than sourcing a real title field from structured ingestion, implemented the structural parse directly against the new colonial/hand-download ingestion (`scripts/build_colonial_kwic.py`, `scripts/build_handdownload_kwic.py`), which already hold full document text before windowing — see `project_frame_split_options` memory for the design (2-way search: forward mention scan unchanged, backward lookup of the governing unit, "further parse" = widen `context_text` to the unit's span when trusted).

**Shipped:** `trifecta_annotation/structural_parse.py` (new — `document_structural_units`, `unit_for_offset`, `DocumentUnit`), new optional fields on `KwicInput`/`AnnotationProvenance` (`unit_id`, `unit_start`/`unit_end`, `target_char_offset`, `structural_header`, `structural_goal`, `structural_goal_inherited`, `structural_signal`), wired through `pipeline.py`/`pipeline_verb.py`'s `_provenance_from_input`, and into both ingestion scripts behind a genre gate (`RECIPE_PRACTICE` only for now — `MEDICAL` deliberately deferred, see below) and a `trust_goals` flag that **defaults to False**: diagnostic fields always populate when a unit is detected, but `structural_goal` and the `context_text` widening stay off until a real precision check passes. No existing field changed type/name; the two live `trifecta-batch` jobs are unaffected.

**Finding that shaped the trust gate, from inspecting real documents (not synthetic `voc_recipes`):** per-cue-type trust alone is insufficient. `_ams007amst01` ("De Amsterdamsze gaare-keuken", the one document currently gated into `RECIPE_PRACTICE`) produced exactly 2 "trusted" units by cue type — both wrong: lines of verse ("Voor de geen die ik bemin...", "Om daer te Trouwen zo 't behoort...") that happen to start with a trusted cue phrase, not recipe headers. Its unit density was 0.36/10k chars — statistically indistinguishable from the Van Lennep 1823 diary's 0.31/10k (§9f's confirmed pure-narrative negative control). By contrast, three formulary-style `MEDICAL` documents inspected cleanly at much higher density: `_pha002phar01` 6.8/10k (92/92 trusted, all genuine Latin preparation names), `krie024bata02` 15.7/10k, `verb122chir01` 11.0/10k. **Added a document-level density gate** (`_MIN_TRUSTED_DENSITY_PER_10K = 2.0` in `structural_parse.py`) on top of the per-cue-type check: a document can carry a correct genre tag and still be mostly non-recipe prose with only incidental cue matches, and density is what tells the two cases apart. After the gate, `_ams007amst01`'s false positives correctly drop to 0 trusted; the formularies are unaffected.

**Consequence:** with the density gate, the currently-enabled scope (`RECIPE_PRACTICE` only, one document) produces zero trusted `structural_goal` values right now — fully inert in production, by design. The `MEDICAL` formularies look like the most promising near-term candidate for cautious extension (high density, clean inspection), but remain deferred pending their own validation pass (§4f of the implementation plan) and the still-open scheme-decision gate (§3 of the plan / `docs/DECISIONS.md`) before any Step C wiring happens.

**Not yet done:** the formal 4f precision/recall measurement (hand-reviewed boundaries on real text, per cue type) — today's check was inspection-based, not a scored measurement; the scheme-decision sign-off; and the Step C wiring itself (held behind that sign-off). See `/Users/rikhoekstra/.claude/plans/snappy-squishing-bear.md` for the full plan.

---

## 9h. Finding — Chomel's TEI declares the unit boundaries §9f asked for, in four levels, two of them hiding as typography (29 Oct 2026)

**This is §9f's recommendation (a) — "a real per-recipe title/header field sourced at ingestion from structured data (given boundaries, not regex-detected ones)" — available as declared markup for the largest single source in `frame_sentences`.** §9g superseded (a) by implementing cue-regex detection against full document text instead; that path is currently inert in production (density gate, `trust_goals=False`, zero trusted goals). It also only covers the colonial/hand-download ingestion. The DBNL sweep — which contributes the rows discussed here — never received a structural parse at all.

**Source.** `chom003huis01_01.xml` (Noël Chomel, *Huishoudelyk woordboek*, 1743), inside `dbnl_xml_pd.zip` on the 2tb disk. It is **2,679 of 7,447 pre-1850 `frame_sentences` rows (36%)**, and 2,679 of the 2,681 rows dated 1743. Parsing needs `recover=True`: the file uses undefined HTML entities (`&nbsp;`), which also leak into `frame_sentences.csv` as literal text.

**The ingestion never parses the XML at all.** DBNL text reaches the pipeline through `strip_tei()` in `scripts/build_colonial_kwic.py`, which is `_WS.sub(" ", _TAG.sub(" ", xml))` — a regex that deletes every tag. All four levels below are destroyed in that one line before anything downstream sees the text, which is also why §9g had only cue detection to work with. The `record_id`s key on chapter — `chom003huis01_01.xml__ch10__abrikozen`, `__ch10__ajuin`, `__ch10__amandel` — so 100+ distinct entries collapse into one unit id. The file has `<div type="chapter">` × 40, which are **alphabet dividers** (`'B.'`, `'K.'`, `'H.'`), and `<div type="section">` × 4,795, of which 4,794 carry a `<head>`.

**Four levels, two of them typographic.** `div` nesting is flat (all 4,795 sections at depth 1), but the hierarchy is not:

| # | Carrier | Count | What it is |
|---|---|---:|---|
| 1 | `div[@type="chapter"]` | 40 | alphabet dividers |
| 2 | `div[@type="section"]` + `<head>` | 4,795 | headed blocks (4,794 headed) — **not reliably one entry each** |
| 3 | `<hi rend="b">` at element start | 2,341 | `trefwoorden`/`subtrefwoorden` lemma anchors |
| 4 | `<hi rend="i">` rubric labels | 386 units | materia-medica template |

**CORRECTION (30 Oct 2026): level 2 is not the entry, and the first version of this section said it was.** Chomel's sectioning is uneven. 3,597 sections are a single lemma (`'Bye-Korf.'`, `'Bye-Zalf.'`, `'Bye-kruid. Zie Melisse.'`), but 799 run on past their head into further lemmas marked **only** in bold — in those, the first anchor sits at mean position 0.39 of the section body, and anchors coincide with a section head just 28 times in 2,341. The worst case is a section headed `'De Akeley-Queekerey.'` (columbine cultivation), 8,739 chars long, containing 22 bold lemmas running `aranea, arbor Judae, arcanum duplicatum, argemone, aristolochia, arsenicum, artemisia, artischok` — a straight alphabetical run of unrelated headwords. The entry boundary is therefore the **union of section heads and bold anchors**: 7,136 units for this work (4,795 + 2,341), which is what `tei_segmentation.parse_entries` emits, tagged `unit_kind`.

Levels 3–4 are recorded as **presentation, not semantics** — DBNL used no TEI dictionary elements (`<entryFree>`, `<term>`, `<label>`), so the structure survives only as bold and italic. Level 3's keywords read `'aal'`, `'aalbeziën'`, `'aamborstigheit'`, and `'aambyen'`/`'haemorrhoides'` (a cross-reference pair); position is load-bearing, since of 3,827 bold spans in paragraphs only the 2,341 that *open* their element are lemma anchors — the rest are emphasis. Offsets must be taken from the element walk rather than by searching the rendered text, since a term can recur in one section (`argemone` twice in the worst case) and `str.find` would collapse distinct lemmas onto one position.

**Level 4 is a grammar, established by order rather than by matching.** Frequency counts over italic strings (`Eigenschappen` 337, `Plaats` 302, `Beschryving` 151) show candidate markers only. The structural claim holds because the sequence is directional and recursive: `Beschryving > Plaats > Eigenschappen` in that exact order 71×, `Plaats` before `Eigenschappen` **188 vs 8**, `Beschryving` before `Plaats` **114 vs 13**, and the whole template cycles per described item — `(Beschryving Plaats Eigenschappen)+`. The rubrics are frame-determining: `Eigenschappen`/`Krachten`/`Dosis` carry medicinal action (CURE), while `Plaats` is habitat and `Beschryving` botanical description, which evoke no food frame.

**RETRACTED (30 Oct 2026) — the demonstration that this section was originally built on was wrong.** The first version resolved each audited sentence to the `<head>` of its nearest enclosing `div` and presented three rows as proof that local reading fails. Two of the three were misattributed, because nearest-enclosing-`div` is *itself* a local heuristic: it takes the closest available markup without checking that the markup level corresponds to the semantic unit. Re-resolved against merged section+anchor boundaries:

| sentence | originally claimed | true governing unit | verdict |
|---|---|---|---|
| "In vyf pinten goeden Wyns doet… Honing, Snuiftabak, gekwetste Boomvaren, Alantwortel" | `'Andere manier om Aal te vangen.'` → eel bait | anchor `aamborstigheit` (asthma), 8,127 chars into the section | **an asthma remedy — the plain semantic reading was right, the structural "correction" was wrong** |
| "Zy zuiveren het Bloed, verzagten den Buik, openen de Lever en Milt" | `'Bezigheid in de Bloem-tuinen.'` → garden calendar | anchor `hop` | **hops as blood-purifier, i.e. CURE — again the semantic reading was right** |
| "men steekt welriekende Kruiden in brand… Thym, Lavendel, Rosmaryn" | `'Geheim, om te beletten, dat de Duiven haar Hok niet verlaten.'` | section head governs (no preceding anchor) | **stands** |

**What survives and what does not.** The structural claims stand on their own evidence: `strip_tei` destroys all markup at ingestion; the four levels exist and are counted above; levels 3–4 are recorded typographically; level 4 is an ordered template. What does *not* survive is the rhetorical case that local semantic reading is reliably wrong here — on two of three probes it was right and the structural attribution was wrong. The honest lesson is narrower and more useful: **structure helps only at the level that matches the unit, and a wrong level is worse than none**, because it overrides a correct reading with false confidence. `tests/test_tei_segmentation.py::test_bold_lemma_opens_a_new_unit_inside_a_run_on_section` pins this case as a regression. The genuine instance of §9e's semantic-scope mismatch in this source is the bare `'Een ander.'` head, which carries no lexical content at all — see `Het secreet-boek`'s 112 below.

**Against §9g's mechanism, this source needs none of the machinery that made §9g inert.** Boundaries are declared, so there are no cue regexes to tune, no per-cue trust classification, and no document-level density gate to separate real headers from incidental verse matches (§9g's `_ams007amst01` failure). Char offsets come free from the parse, which also sidesteps §9f's separate `target_word`-locatability problem (13/26 `RECIPE_PRACTICE` gold rows had zero literal occurrences of their target).

**What still has to be built, and is not regex-shaped.** Hand-written head patterns reach ~10% of entries: `Middel` 363, `te vangen` 75, `Kweken|Planten|Zaaien` 44, `Voedzel` 5 — 487 of 4,794. The rest are heads like `'Andere Gekonfyte Abrikozen.'`, `'Andere Marmelade van Abrikozen.'`, `'Bezigheid in de Bloem-tuinen.'` So scope *classification* is a real task — but over ~7,100 short, formulaic, self-contained strings (section heads plus lemma anchors) rather than 2,679 sentences in context. **This is where an LLM is appropriate and currently is not applied:** a head or lemma is self-describing by construction, unlike a sentence mid-procedure, and the whole inventory is human-auditable in an afternoon. It also supplies the PRESERVING signal that `project_frame_split_options` deferred to a structure-aware Step C — `'Gekonfyte Abrikozen'` and `'Marmelade van Abrikozen'` name the *technique*, which the sentence bodies never do.

**Chomel is internally heterogeneous, which pushes §9e's organizing-axis finding down a level.** Level 4 covers only 347 of 4,795 sections because one household encyclopedia mixes herbal entries (rubric template), `Middel tegens X` remedies, fishing entries, month-marked garden calendars, and confectionery recipes. The axis is per *entry type*, not per work, so scope resolution must identify the entry type before applying a template. §9e's three-work table recorded `Nederlandtsche woorden-schat` (dictionary) as having "nothing frame-relevant" in its headwords; Chomel is the opposite case, an *encyclopedic* dictionary whose entry heads are richly frame-relevant. "Lemma-oriented source" is therefore not one category.

**Two levels is twice what conventional frame parsing admits.** Standard frame semantics is one-level — the lexical unit evokes the frame within its own sentence. Chomel needs at least two (head governs, sentence instantiates) and offers four. A frame inventory has nowhere to record the governing level, which is the same underspecification §9e flagged; it is not an engineering shortcut to be described as "a join".

**Retracted in the same session: the precision audit that led here.** A hand audit of random `frame_sentences` rows produced 60% frame-correct for Chomel, 30% for other pre-1850, ~25% for post-1850, 45% pre-1850 overall. **Do not cite these.** They were produced by judging each sentence from its own text alone, which reproduces exactly the local-window error the pipeline makes — one local guess scored against another. Probing 8 of the judged sentences against their real heads got at least 3 badly wrong in both directions (the three rows in the table above are all mine). This is the fourth instance of the trap family in §9b/§9d/§9f: a semantic scorer over an inadequate input keeps finding ways to look informative. The only durable number from that audit is the corpus-composition one: Chomel is 36% of pre-1850 rows, so any pre/post-1850 comparison is a statement about source mix, not about period.

**KB cookbook PDFs: latent, not absent.** The re-OCR'd PDFs (§ `scripts/ocr_colonial_pdf.py`) have no declared structure — broken text layer is why they needed re-OCR. But the pipeline already runs `tesseract --psm 3` (full automatic page segmentation), which computes blocks, paragraphs, lines and font sizes internally, and then writes plain `.txt`, discarding all of it (`ocr_page`, lines 113–118). Requesting `hocr`/`alto`/`tsv` output retains bounding boxes, font size and per-word confidence. That yields *inferred* scope (font-size clustering, indentation, running heads) rather than declared scope, so it needs a provenance flag distinguishing the two; it should not inherit TEI-level trust.

**Carried-over constraints for any rollout.** From §9e's trap list: tag every scope-derived element `inherited` vs `stated` before it reaches `trifecta_analysis` (a 40-remedy chapter otherwise 40-fold over-counts one stated affliction), and score per unit-group rather than per row. Anaphoric heads need a carry-forward rule, but the need is per-source: 401 of Chomel's heads (8.4%) open with `Ander/Andere/Nog`, yet nearly all restate their scope anyway (`'Andere manier om Aal te vangen.'`), unlike `voc_recipes`' 218 bare `'Een ander.'` instances — and unlike `Het secreet-boek`, which has **112 bare `'Een ander.'` heads of 1,493** (see the generality check below).

### Generality check across three more works (30 Oct 2026) — levels 1–2 are corpus-general, levels 3–4 are per-work

Ran the same four checks on `bate002secr02_01.xml` (`Het secreet-boek`, 1694), `_pha002phar01_01.xml` (`Pharmacopoea Roterodamensis` — the formulary §9g inspected at 6.8 units/10k) and `_pha001phar02_01.xml` (`Pharmacopaea Amstelredamensis` — the one §9e profiled, and the one carrying rows: 98 vs Rotterdam's 6). **Design consequence: one reader for levels 1–2, per-work adapters for levels 3–4.**

**Levels 1–2 generalize.** Every work has the identical skeleton — `div[@type="chapter"]` plus `div[@type="section"]` flat at depth 1 — with heads on essentially every div: 4,794/4,795 (Chomel), 1,493/1,494 (secreet-boek), 302/303 (Amsterdam), 260/261 (Rotterdam). The entry-head layer is therefore a corpus-wide property of the DBNL encoding, not a Chomel peculiarity, and it is where the value is.

**Levels 3–4 do not generalize at all:**

| work | content carrier | `rend="b"` | `rend="i"` function |
|---|---|---|---|
| Chomel | `<p>` | 3,354 keyword anchors | rubric template `(Beschryving Plaats Eigenschappen)+` |
| `Het secreet-boek` | `<p>` | absent (4 total) | authorities + ingredients, two functions |
| Pharmacopoeas | **`<item>`** (2,633) | absent | Latin quantity units (`unc`, `libr`, `sem`, `duas`) + `Dosis` ×42 |

**Position disambiguates one marker carrying two functions** — the clearest quantitative support for the [[feedback_typography_hides_structure]] rule. In `Het secreet-boek`, italics mark both Renaissance authorities (`Mizaldus` ×101, `Cardanus` ×66, `Alexius` ×55) and ingredients (`Azijn` ×96, `Wijn` ×89, `Suycker` ×57, `Caneel` ×50). Mean fractional position within the paragraph separates them cleanly: **authorities 0.96** (attribution trailing the recipe, n=251) vs **ingredients 0.39** (inside the procedure, n=364). The italicised ingredients amount to a declared ingredient list, frame-element-relevant for `COOKING_CREATION_Food_Product` / `PR_Food_Patient` independently of the head layer.

**Methodological bug in the checks themselves, worth not repeating:** the first pass was `<p>`-centric and would have reported the formularies as sparsely marked (713 and 559 italics in `<p>`), when they are the *most* densely marked of the three — 846 and 2,501 of their `hi` sit inside `<item>`, under 238 `<list>` elements. Any structural reader must enumerate content carriers rather than assume `<p>`.

**Two caveats against over-optimism.** (1) Head *presence* is ~100% but head *informativeness* is not: the formularies' chapter heads are bare alphabet letters (`'B.'`, `'C.'`, `'D.'`), carrying no scope. (2) The formularies are internally heterogeneous like Chomel — 182/267 Amsterdam sections contain `<item>`s, and one section under head `'B.'` is a Latin→Dutch synonym glossary (`"Bardanae, oft Lappae Mai. klissen."`, `"Bistortae, Herts-tong."`), not a preparation. Head text alone will not tell a glossary section from a recipe section; the content carrier will.

Heads also differ in kind exactly as §9e's three-work table predicted: Chomel's name topical lemmas, `Het secreet-boek`'s name purposes (`'Om te maken een Keersse die niet uyt te blasen en is.'`), the formularies' name preparations or bare letters.

### Shipped — read-only segmenter (30 Oct 2026)

`trifecta_annotation/tei_segmentation.py` (`TeiEntry`, `Anchor`, `parse_entries`, `head_inventory`, `read_work_xml`) plus `scripts/segment_tei_entries.py`, with `tests/test_tei_segmentation.py` (12 tests). Deliberately **not** part of `structural_parse.py`: that module detects boundaries with cue regexes and must then decide whether to trust them (per-cue checks plus the density gate); here the boundaries are declared, so there is nothing to trust-gate. Folding them together would let the declared path inherit machinery built for a far weaker signal.

**CORRECTED 7 Nov 2026 — now `lxml`, not stdlib `ElementTree`.** Switched when wiring entry-head scope surfaced that `tei_segmentation`'s own text rendering and `strip_tei`'s regex stripping disagree at every tag boundary with no inserted whitespace (e.g. `aamborstigheit</hi>, Kortademigheit` — zero whitespace in the raw XML), compounding to a 5% length drift over a full document and defeating substring-based offset recovery. The fix needs a structural, one-pass walk rather than two independently-built texts reconciled afterward; `lxml` was chosen for speed with an identical API (operator's call — "much faster, API is identical"). Declared in `pyproject.toml`. Undefined HTML entities are still resolved before parsing via `html.entities.name2codepoint`, which both fixes the hard parse failure and stops `&nbsp;` leaking into exports as literal text; `lxml.etree.fromstring` additionally needs the sanitized text encoded to bytes (it refuses a `str` with an `encoding`-declaring XML prolog) and `load_dtd=False`/`no_network=True` to stop it trying to fetch the DOCTYPE's PUBLIC identifier.

Read-only in both directions: reads one member of the `dbnl_xml` zip without extracting it, and writes nothing unless `--out-dir` is passed. It makes no frame judgements and changes no `record_id`s. Output per work: `*_entries.jsonl` (full units with text and offsets) and `*_heads.csv` (the flat inventory for human review).

Counts: Chomel 7,136 units (4,795 section heads + 2,341 lemma anchors), `Het secreet-boek` 1,386, Amstelredamensis 267, Roterodamensis 219. The segmenter reproduces the hand figures above — `Beschryving>Plaats>Eigenschappen` 72, `Dosis` 42, 112 bare secreet heads — and classifies the formularies' bare-letter heads as `divider`, a kind that supplies no scope and is not carried forward, so entries after a letter heading do not inherit `'B.'`.

**No pipeline change made — measurement, source inspection and a read-only tool, same posture as §9d/§9f.** Re-deriving Chomel at entry granularity changes record identity (`__ch10__` → per-unit ids) and would invalidate existing `record_id`s, which are referenced from `trifecta_annotation/fewshot_export.py` and `scripts/merge_verb_phase2a_gold.py` — so it needs sign-off. Still open: reading the head inventory by eye before any classification runs; whether the remaining DBNL works fall into these three adapter shapes or add more; and whether the `verwijswoorden` cross-references (`'Bye-kruid. Zie Melisse.'`, `'aambyen'`/`'haemorrhoides'`) are worth resolving into a synonym layer.

---

## 9i. Finding — pipeline economics: where the LLM budget actually goes, and the three cheap levers that move it (6 Nov 2026)

**Measurement only, no pipeline change.** All figures aggregate the four annotation sources (`annotations`, `dbnl_sweep_annotations`, `colonial_annotations`, `handdownload_annotations`), error rows excluded.

### Cost structure

Step A runs on every candidate; Step B only if A does not drop; Step C only on a non-`NONE` frame ([pipeline.py](../trifecta_annotation/pipeline.py) `annotate_record`).

| stage | calls | share |
|---|---:|---:|
| Step A | 40,715 | **54.7%** |
| Step B | 19,567 | 26.3% |
| Step C | 14,089 | 18.9% |
| **total** | **74,371** | |

**14,089 usable frame rows from 74,371 calls = 5.28 calls per output row**, and 34.6% of candidates entering the pipeline survive to a real frame. Over half the budget is Step A, and 51.9% of Step A calls end in a drop — i.e. roughly a quarter of all spend buys nothing but a "no." That is the inefficiency any tuning should target first.

### `text_regime` already predicts Step A's verdict — for free

The field is computed at harvest and stored on every candidate; nothing downstream routes on it.

| regime | n | Step A drop | survives |
|---|---:|---:|---:|
| `RECIPE_PRACTICE` | 4,126 | **12.6%** | 87% |
| `MEDICAL` | 697 | **19.7%** | 80% |
| `LITERARY` | 4,322 | 44.3% | 56% |
| `UNKNOWN` | 14,319 | 49.9% | 50% |
| absent | 15,572 | **68.5%** | 31% |

Routing tradeoffs, measured against the full run:

| routing | calls | yield | calls/row | spend | output kept |
|---|---:|---:|---:|---:|---:|
| everything (current) | 74,371 | 14,089 | 5.28 | 100% | 100% |
| `RECIPE_PRACTICE`+`MEDICAL` | 12,655 | 3,664 | 3.45 | 17% | 26% |
| + `LITERARY` | 21,353 | 5,634 | 3.79 | 29% | 40% |
| **exclude absent-regime** | 51,779 | 11,976 | 4.32 | **70%** | **85%** |

### Candidate-selection mode — and the `text_regime` bug that made the first two attempts wrong

**Bug first, because it invalidates any naive reading of `text_regime`.** `capped_candidates` computes `regime = infer_text_regime(...)` and passes it to `verb_first_hits`, which writes `text_regime` on every row — but it does **not** pass it to `scan_text`, and `scan_text` never writes the field ([build_colonial_kwic.py](../scripts/build_colonial_kwic.py), `scan_text` row construction vs `verb_first_hits`). Therefore:

> **`text_regime == absent` means "produced by the noun fallback", not "genre inference failed."**

In `dbnl_sweep` the two are perfectly confounded — all 12,206+ `verb_food` rows carry a regime, all 15,418 `noun_fallback` rows are `absent`, zero exceptions. Any table that treats `absent` as a genre stratum is really reporting a *mode* effect. **Fix: pass `regime` into `scan_text` and write it to the row.** One line; costs nothing; required before regime can be trusted as a routing key.

`infer_text_regime` is a pure function of `(corpus, title, source_path)`, all present in provenance, so the missing regimes are recoverable retrospectively. Recovered, the absent bucket is **92% `UNKNOWN`** (14,214 of 15,418), plus 851 `LITERARY`, 171 `TRAVEL`, 133 `ADMIN_TRADE`, 48 `SCIENTIFIC`, 1 `MEDICAL`, and **no `RECIPE_PRACTICE` at all** — so it is not hidden good material being wasted; it is genuinely weak material.

**The clean comparison.** Holding source file *and* regime fixed (`dbnl_sweep` only, regimes recovered for noun rows), `verb_food` beats `noun_fallback` in every stratum:

| regime | `verb_food` | `noun_fallback` | verb advantage (percentage points) |
|---|---:|---:|---:|
| `TRAVEL` | 30.3% (n=175) | 72.5% (n=171) | **+42.2** |
| `LITERARY` | 33.9% (n=1,783) | 69.9% (n=851) | **+36.0** |
| `UNKNOWN` | 52.6% (n=12,206) | 68.8% (n=14,214) | **+16.2** |
| `ADMIN_TRADE` | 52.5% (n=80) | 66.9% (n=133) | +14.4 |
| `SCIENTIFIC` | 43.6% (n=39) | 52.1% (n=48) | +8.5 |

**Two earlier readings of this data were wrong and are retracted.** (1) A first pass claimed `verb_food` *underperforms* the plain noun regex in recipe/medical genres — that compared the old hand-curated `annotations.jsonl` (all the noun and embedding rows) against the newer sweeps (all the verb rows), zero overlap, pure corpus-era artifact. (2) A second pass treated `absent` as a failed-inference genre bucket and proposed fixing genre inference to recover it — wrong premise, per the bug above. The corrected direction is the opposite of (1): **`verb_food` is the stronger selector, consistently.**

**Residual confound, not removable observationally.** `noun_fallback` only fills position bins where *no* verb-food collocation existed (verb candidates always outrank it, `_NOUN_FALLBACK_SCORE = -1.0`), so the two modes describe different material by construction. The 5-stratum consistency and large n make the direction credible, but a pure method test still requires a designed experiment: one fixed candidate pool from one work, selected by each mode, Step A survival compared on the same material.

**Status of the embedding claim.** `embedding_rerank` 4.3% vs `noun_fallback` 13.3% within `RECIPE_PRACTICE` is same-file and same-era (both `annotations.jsonl`), but its 533 rows are concentrated in Chomel (264) and De volmaakte Hollandsche keuken-meid (134), so work selection is uncontrolled — **suggestive, not established**. It covers 1.3% of candidates. Note the corrected baseline: embedding must now be benchmarked against `verb_food`, the stronger mode, not against `noun_fallback`.

### Sieve, don't discard — the acceptable false-drop rate depends on the counterfactual

The absent-regime bucket is **15,572 candidates, 22,592 calls (30% of spend), 2,113 usable rows (15% of output)**, 31.5% surviving Step A.

The GloBERTise (`globertise-balanced-none`) measured NOT_NONE recall of **0.752** (confusion matrix over the 432-row dev set) was correctly damning for a *universal* pre-filter: against "run everything," silently destroying 24.8% of real frame rows is unacceptable. Against "discard this bucket entirely," the same classifier retains ~1,585 of 2,113 rows while cutting most of 22,592 calls. Same number, opposite verdict, purely because the baseline moved from keep-all to keep-none. **Operating-point decisions must state their counterfactual.**

Caveat on reuse: GloBERTise was trained on the Step B 5-way frame task and only collapsed post-hoc into a NONE filter. The right target for a Step A sieve is Step A's own keep/drop verdict, for which **40,715 labelled rows exist at 51.9/48.1 balance** (15,572 of them inside the absent bucket) — in-domain, on-target, and `gijsbert_train.py` already provides the harness. Choose the threshold by recall, not accuracy.

### Why "absent regime" is a bug to fix — but not the bug first assumed

Absent regime is 38% of all candidates, and it *is* a bug to fix, but the fix is the one-line `scan_text` omission above, not genre inference. An earlier draft invoked the `project_genre_predicate` memory (keyword genre inference fails silently on historical Dutch, needing per-work overrides) as the explanation. That memory is real but **does not apply here** — inference ran fine and its result was simply never written to noun-fallback rows.

Consequence for routing: "exclude absent-regime, save 30% of spend for 15% of output" is really **"exclude noun-fallback candidates."** The arithmetic stands, the mechanism was misattributed — and since the clean comparison above shows `noun_fallback` genuinely is the weaker mode in every stratum, the filter is defensible on its merits. It is a mode-quality decision, not a genre decision, and should be described as one.

**Shipped (6 Nov 2026, forward-looking harvest only):** `scan_text` now writes `kwic_mode="noun_fallback"` (with `text_regime`), and `capped_candidates` **defaults to verb-food only** — counterfactual = discard noun-fallback, not "run everything." Escape hatch `--include-noun-fallback` restores the old top-up for ablation; optional `--regimes RECIPE_PRACTICE,MEDICAL` is a document-level allow-list **off by default** so UNKNOWN TEI sweep material is not silently killed. Does not rewrite already-cascaded annotation JSONL.

**Genre-routed sieves (2026-11-06, wired):** route by `text_regime` after TEI entry-scope upgrade — see [docs/DECISIONS.md](docs/DECISIONS.md). Harvest stays verb-food; weak regimes may run a binary Step A KEEP/DROP encoder before LLM A (`trifecta-batch --step-a-sieve-model …`); RECIPE/MEDICAL go straight to LLM. Export/train: `scripts/export_step_a_keepdrop.py`, `scripts/train_step_a_keepdrop.py` (user-run GPU). TEI: `attach_tei_scope_to_rows` stamps `tei_scope_head` and may upgrade UNKNOWN → MEDICAL/RECIPE from entry heads.

**Step A keep/drop sieve trained and thresholded (7 Nov 2026).** GloBERTise (`globalise/GloBERTise`) fine-tuned on the 40,715 Step A labels, split by work; ~1h40m on MPS. Model: scratch `step_a_keepdrop/models/globertise-keepdrop/`. Dev accuracy 92.5% (n=7,103) — but accuracy is the wrong metric for a sieve, so `scripts/sweep_step_a_keepdrop.py` reports keep-recall (true KEEPs surviving) and calls saved per regime and threshold; full output in `threshold_sweep.json` beside the model.

| regime (sieved?) | n | keep-recall @0.5 (argmax) | keep-recall @0.98 | Step A calls saved @0.98 |
|---|---:|---:|---:|---:|
| UNKNOWN (yes) | 4,705 | 0.922 | **0.952** | 50.8% |
| TRAVEL (yes) | 1,120 | 0.959 | **0.980** | 44.4% |
| LITERARY (yes) | 727 | 0.924 | **0.964** | 46.2% |
| ADMIN_TRADE (yes) | 92 | 0.961 | 0.961 | 40.2% |
| MEDICAL (no — direct LLM) | 419 | 0.942 | 0.972 | 18.4% (drop-precision only 0.80–0.88) |

**Decision: `DEFAULT_DROP_THRESHOLD = 0.98`** in `step_a_keepdrop.py`, replacing argmax (=0.5), which lost 4–8% of real KEEPs in the sieved regimes. Overridable via `trifecta-batch --step-a-sieve-threshold`. The curve is flat from 0.5 to 0.95 and only bends at 0.98, so values above 0.98 were not swept and may buy more recall — worth one more sweep if the 5% UNKNOWN loss matters. MEDICAL stays unsieved, confirmed: low savings and weak drop-precision. Caveat: keep-recall here is agreement with LLM Step A, not with gold.

**TEI offset alignment fixed (7 Nov 2026).** `attach_tei_scope_to_rows` originally placed entries by substring-anchoring `tei_segmentation`'s text into `strip_tei`'s, and only placed ~63% of Chomel's entries: the two renderings disagree at every tag boundary with no whitespace in the source (`aamborstigheit</hi>, Kortademigheit`), drifting ~5% over the document — enough to mis-attribute the §9h asthma-remedy passage to the eel-catching head. Replaced by `render_tei`: one lxml walk produces the harvester's text *and* every entry's offset, so they agree by construction. Measured: **7,120/7,120** Chomel entries placed (1,386/1,386 secreet-boek, 268/268 Amstelredamensis), 0.6s for Chomel, no `&nbsp;` leaks. TEI harvests (`build_colonial_kwic.py` new-DBNL + H1 sweep, `build_handdownload_kwic.py`) now read `render_tei` text instead of `strip_tei`, which also drops the `teiHeader` and DBNL's digitisation apparatus from what gets harvested. Consequence: `target_char_offset` and index-based `record_id`s of *future* TEI harvests differ from rows harvested earlier, so re-harvesting an already-annotated work will not `--resume`-match its old rows. `export_term_occurrence_overview.py` still uses `strip_tei` (counts only, no offsets).

**Selection modes, controlled experiment (7 Nov 2026) — settles the confounded comparisons above.** `scripts/experiment_selection_modes.py`: per work, one fixed random pool of 1,500 mention windows; each mode ranks the same pool; top 40 per mode; union (355 rows) annotated once by the normal cascade on local Ollama (default model), 0 errors. Exemplars from the test works (29 of 150) excluded from the embedding centroids. Works: Chomel (RECIPE_PRACTICE), *De Tijdspiegel* 33 (LITERARY), a States Bible (UNKNOWN). Output: scratch `experiments/selection_modes/`.

| real-frame yield | `verb_food` | embedding | noun (random) |
|---|---:|---:|---:|
| all (n=120 each) | **76%** | 62% | 33% |
| RECIPE_PRACTICE | 75% | **82%** | 65% |
| LITERARY | **75%** | 62% | 15% |
| UNKNOWN | **78%** | 40% | 20% |

Conclusions: (1) **`verb_food` is the best general selector**, consistent across regimes — the corrected observational direction above is now confirmed causally, and the shipped verb-food harvest default is right. (2) **The embedding route is not 3× better**: competitive only on recipe material (33 vs 30, within noise), clearly worse elsewhere. The earlier 4.3%-drop figure was plausibly inflated by exemplar leakage (the old `embedding_rerank` rows were mostly Chomel, and Chomel is among the exemplar sources) — consistent, not proven. Do not widen `embedding_rerank`. (3) Random noun hits are poor (15% in LITERARY), supporting the noun-fallback removal. Caveat that matters for volume: `verb_food` can only select mentions with a qualifying verb nearby — 494/1,500 in Chomel but ~90/1,500 in the LITERARY and UNKNOWN works — so it is precise but narrow; embedding is the only scorer that ranks the whole pool. Limits: n=40 per cell, one work per regime.

**Selection modes v2 (7 Nov 2026, unattended run, `scripts/weekend_run.sh`).** The same design across 10 works: 3 RECIPE (Chomel, secreet-boek, volmaakte keuken-meid), 1 MEDICAL (Pharmacopoea Amstelredamensis), the 3 largest LITERARY sweep works and the 3 largest UNKNOWN works (Bible editions collapsed). Top 60 per mode, plus two structural modes: `entry_scope` (the mention lies inside a TEI entry whose head matches a `regime_from_tei_scope_head` cue) and `entry_scope_head` (the same, with `[Kopje: …]` prefixed). The union of 1,990 rows was annotated on local Ollama with 0 errors. Full table: [docs/evidence/selection_modes_v2/report.md](docs/evidence/selection_modes_v2/report.md).

| real-frame yield | `verb_food` | embedding | noun | entry_scope | +head |
|---|---:|---:|---:|---:|---:|
| RECIPE_PRACTICE | 90% | **91%** | 80% | 86% | 88% |
| MEDICAL | 85% | **90%** | 72% | 89% | 83% |
| LITERARY | **55%** | 35% | 10% | 9% (n=11) | 0% (n=11) |
| UNKNOWN | **41%** | 19% | 11% | 11% (n=9) | 33% (n=9) |

Conclusions:
1. **Within recipe and medical works, precision no longer separates the modes; reach does.** Most of the real frames that the non-verb modes find are *unreachable by verb*: RECIPE entry_scope 93/136, RECIPE embedding 110/163, MEDICAL embedding 42/54. In structured works, verb_food therefore leaves most findings unselected. This confirms structurally-evoked frames need a non-verb route (§9e).
2. **In weak regimes verb_food stays clearly best.** Entry scope barely applies there: there are few TEI entries, and the scope cues are recipe and medical heads.
3. **The head prefix gives no measurable gain** (80% vs 78% overall, n=197).
4. **Do not compare the ALL rows across modes.** 159 of entry_scope's 197 rows come from RECIPE works (composition effect).

Routing **implemented** in `capped_candidates`: in RECIPE/MEDICAL TEI works, entry-scope mentions the verb route cannot reach are added with their own position-stratified cap (`DEFAULT_ENTRY_SCOPE_CAP` = 500/work, `--entry-scope-cap`, `--no-entry-scope`). Everything else stays verb_food only. Embedding is not added (a harvest-time embedder is heavier, and entry scope already supplies the reach).

**Entry-scope production run (7 Nov 2026).** All 24 RECIPE/MEDICAL DBNL TEI works, entry-scope rows only, cap 500/work: 2,590 rows, 0 errors. Real-frame yield was RECIPE 81%, MEDICAL 51%, giving 1,684 new frames the verb harvest cannot reach, at ~1.5 candidates per frame vs ~2.9 in production. Practical remedy books reach 85–93%; medical treatises 25–56%, because the head matches while the food mention is incidental. 7 works with entries yielded 0 rows (cue regexes probably miss Latin heads). Not merged into canonical yet (record_id mismatch, so dedupe is needed first). Report: [docs/evidence/entry_scope/REPORT.md](docs/evidence/entry_scope/REPORT.md). **Chomel uncapped: stopped (8 Nov).** 6,819 eligible rows fall under only 583 distinct entry heads (~12 mentions per entry), so rows beyond the evenly spaced 500 mostly add depth within entries already covered, not new ones. Cap 500 stays. Count frames per entry (`tei_scope_head`), not per row, in dictionary-structured works. Caveat: "real frame" is the pipeline's own verdict, not gold.

**Sieve shadow run (8 Nov 2026), held out from training.** The sieve was run against the real LLM verdicts on 4,638 rows annotated after training: the entry-scope run plus selection v1/v2, minus 35 texts in the training split and 262 duplicates. Report: [docs/evidence/sieve_shadow/report.md](docs/evidence/sieve_shadow/report.md).

| at P(DROP) ≥ 0.98 | n | Step A calls saved | real frames lost |
|---|---:|---:|---:|
| **as routed in production** (weak regimes) | 1,160 | **43%** | **1.5%** (5 of 329) |
| RECIPE_PRACTICE, if sieved | 1,921 | 9% | 1.1% |
| MEDICAL, if sieved | 1,548 | 27% | 4.8% |
| works unseen in training | 1,115 | 16% | 2.2% |

Conclusions:
1. **0.98 holds up on held-out data.** In production the sieve saves ~43% of weak-regime Step A calls and loses ~1.5% of their real frames.
2. **The routing is right.** Sieving RECIPE would save little (9%), and sieving MEDICAL would cost the most findings (4.8%). Both stay direct-to-LLM.
3. **No sign of over-fitting by work.** Loss is 2.2% on unseen works vs 2.3% on seen ones.

Limits: the routed rows come from the selection experiments, i.e. a few works per regime, chosen by selection mode rather than by the production sweep's distribution. 0.99 would halve the frame loss again (1.2%) for 1 point fewer calls saved; that is not worth changing on n=329 real frames.

**Still deferred:** (1) Step B NONE encoder gate on weak-regime A-survivors only; (2) domain-mismatch scoring beyond lexical `assess_homonym_context`; (3) sweeping thresholds above 0.98.

**Two distinct problems were being conflated, and both are real:**

| symptom | cause | fix |
|---|---|---|
| `text_regime` **absent** (15,418 rows) | `scan_text` never writes the field | one line: pass `regime` in, write it — **done** |
| `text_regime` **`UNKNOWN`** (12,206 rows, **2,039 distinct works**, median 6 rows each) | genuine genre-inference failure — the `project_genre_predicate` problem, since per-work overrides exist only for the original 61 works, not the ~2,800 sweep works | TEI entry-scope upgrade at harvest — **wired**; no cheap work-level fix |

The second is the one that matters strategically. Work-level regime inference **cannot** classify 2,039 of the sweep works, and hand-writing overrides for ~2,800 works is not realistic. §9h's entry-head scope supplies a *per-entry* signal precisely where *per-work* inference returns `UNKNOWN` — now stamped on harvest rows via `attach_tei_scope_to_rows`.

### Context: the cap=50 headroom test that prompted this (6 Nov 2026)

Raising the per-work candidate cap from 10 to 50 on the five works measured richest (Chomel 22,168 verb+food collocations uncapped vs a cap of 10, etc.) harvested 248 candidates; a stratified sample across all five works returned **0 of 21 surviving Step A**. Offsets were verified to span 0.5–98% of each document, so this is not an early-pages sampling artifact. Nearly all the weak candidates came through the scored `verb_food` path, not the unscored fallback — meaning `score_snippet_for_frame`'s homonym penalty passed them: `assess_homonym_context` catches *lexical* homonyms (`mede` = conjunction vs mead) but has no mechanism for *domain* mismatch (`huid`/`maag`/`oogen` genuinely mean skin/stomach/eyes, just about animals or anatomy rather than human food practice).

Honest limits: n=21 with 0 survivors is consistent with a true keep rate up to roughly 10–14%, so "worse than cap=10" is supported, "yields nothing" is not. Also, the 20% drop rate initially used as the comparison baseline was **not** like-for-like — it came from the original hand-curated 61-work corpus, which predates `stratify_by_position`. The correct same-mechanism cap=10 baseline is the 29,784-row H2 sweep at **59.7% drop** (dominated by `metaphor`, 15,760 of 17,785 — genre dilution, consistent with §9e).

**Infrastructure note.** This run used a rented Lyceum L40S serving Qwen2.5-32B-Instruct-AWQ, then Qwen2.5-Coder-32B-Instruct-AWQ, via vLLM in Docker (`$2.22/h`, ~$1 spent). Both models produced the same ~100% drop rate, ruling out model choice as the cause. A persistent ~50% HTTP 401 rate affected only *new* TCP connections while reused connections always succeeded — a Lyceum edge/networking flake, not an auth problem; `run_batch(resume=True)` absorbs it via `_strip_retry_errors`. Pointing the pipeline at a remote endpoint needs no code change (`OLLAMA_BASE_URL`/`TRIFECTA_MODEL`/`TRIFECTA_API_KEY`); `scripts/check_remote_endpoint.py` verifies one through the real `structured_completion` path. The `TRIFECTA_REMOTE_*` names in `model_compare.env` are reference profiles that **no code reads**.

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
