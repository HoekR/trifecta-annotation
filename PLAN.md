# TRIFECTA Automated FrameNet Annotation Pipeline

**Status:** In progress · **Framework:** TRIFECTA Guidelines (Qualia-based FrameNet)  
**Target architecture:** Local prototyping (Mac M4) → HPC scaling (SURF dual A10 GPUs)  
**Repository:** `trifecta-annotation` (standalone; `hist-text-utils` stays general-purpose)

> **Gold, sampling, evaluation, and track boundaries** are defined in **[docs/ANNOTATION_STRATEGY.md](docs/ANNOTATION_STRATEGY.md)** — the canonical guide. This file covers pipeline engineering only.

---

## State of affairs (17 Jul 2026)

> **Paused for holidays (17 Jul 2026).** Resume here.
>
> **Done in this stretch:** COOKING Step C pilot gold (~27 rows in ~187 gold) · soft Step C eval · COOKING few-shots + re-batch · `trifecta_analysis` parquet · EN brief (`docs/RESEARCH_STRATEGY_SUMMARY.md` + docx/rtf/html).
>
> **Next when back:** (1) more Step C hand gold beyond COOKING (PRESERVING / INGESTION / CURE quotas) via [GOLD_LABELLING.md § Step 5](docs/GOLD_LABELLING.md#step-5-runbook--cooking_creation-qualia-m10); (2) analysis notebooks on `resolve("trifecta_analysis")` (always show `uncertainty_note`). Optional: GijsBERT hybrid, more NONE silver, collocation export.

**Primary goal:** qualia for analysis (Step C) — **[ANNOTATION_STRATEGY.md §5 Step 5](docs/ANNOTATION_STRATEGY.md#step-5--qualia-for-analysis-m10--current)** / milestone **m10**. Not bulk NONE silver or GijsBERT-as-replacement for qwen.

### What works today

| Capability | Status |
|------------|--------|
| Full pipeline A→B→C (`trifecta-annotate`, `trifecta-batch`) | **Production-ready** (LLM) |
| Step B eval on frozen 157-row gold | **75%** qwen baseline; per-regime reporting |
| Step A NONE silver loop (`reizen` KWIC pilot) | **Validated** — 200 Step A → 59 accepted → `gysbert-v2-reizen-none` |
| GijsBERT macro-frame classifier | **Trained** — 61.8% pooled dev, NONE F1 0.82; frames-only weak (~35%) |
| INCEpTION silver with Step C | ~2,752 LLM-filled `step_c` rows (exploration silver, unvalidated) |

### Gaps for qualia-for-analysis

| Gap | Current |
|-----|---------|
| Hand gold with Step C | **~27** rows with Step C (187 total gold after COOKING pilot) |
| Step C in `trifecta-eval` | **Done** — field-match + joint/micro by frame |
| Step C few-shots / prompt calibration | **COOKING wired** — `prompts/step_c_cooking_fewshots.json` |
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
| `recipe_web` | 20th c. corpus |
| `kwic_inputs` | Normalized `KwicInput` JSONL (scratch) |
| `trifecta_gold_csv` | Gold labelling spreadsheet (scratch) |
| `trifecta_gold_jsonl` | Gold set JSONL mirror (scratch) |
| `trifecta_gold` | Hand-labelled eval set parquet (scratch) |
| `frame_classifications` | Step B JSONL output (scratch) |
| `trifecta_annotations` | Full A→B→C JSONL output (scratch) |
| `eval_reports` | Eval metrics JSON + markdown (scratch) |
| `trifecta_analysis` | Flat A→B→C analysis parquet (scratch; LLM hypotheses) |
| `trifecta_gijsbert` | GijsBERT train/dev JSONL + `label_manifest.json` (scratch) |
| `trifecta_gijsbert_models` | Fine-tuned GijsBERT runs + `model_comparison.md` (scratch) |
| `food_snippets_kwic` | KWIC wide CSV with `manual_labels` (scratch) |
| `food_snippets_long_kwic` | Deduped exploded KWIC long CSV + `kwic_batch` (scratch) |

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
