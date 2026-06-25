# TRIFECTA Automated FrameNet Annotation Pipeline

**Status:** In progress · **Framework:** TRIFECTA Guidelines (Qualia-based FrameNet)  
**Target architecture:** Local prototyping (Mac M4) → HPC scaling (SURF dual A10 GPUs)  
**Repository:** `trifecta-annotation` (standalone; `hist-text-utils` stays general-purpose)

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
| Model | `qwen2.5-coder:32b-instruct` (quantized) | same, FP16 |

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
        │  COOKING_CREATION | USING_CURE | USING_INGESTION | PRESERVING | NONE
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
| `USING_CURE` | `UsingCureQualia` | `cure_affliction`, `cure_food_treatment` |
| `COOKING_CREATION` | `CookingCreationQualia` | `preparation_method`, `heat_or_mechanical_process`, `result_state` |
| `USING_INGESTION` | `UsingIngestionQualia` | `consumption_context`, `consumer`, `manner` |
| `PRESERVING` | `PreservingQualia` | `preservation_technique`, `preserving_agent`, `target_food` |
| `NONE` | skip C | terminal at B |

---

## 6. Data manifest

| Logical name | Role |
|--------------|------|
| `food_terms` | Ontology / Step A lexicon |
| `voc_recipes` | 17th–19th c. corpus |
| `recipe_web` | 20th c. corpus |
| `kwic_gold_review` | Calibration pool (~249 KWIC rows) |
| `kwic_inputs` | Normalized `KwicInput` JSONL (scratch) |
| `trifecta_gold_csv` | Gold labelling spreadsheet (scratch) |
| `trifecta_gold_jsonl` | Gold set JSONL mirror (scratch) |
| `trifecta_gold` | Hand-labelled eval set parquet (scratch) |
| `frame_classifications` | Step B JSONL output (scratch) |
| `trifecta_annotations` | Full A→B→C JSONL output (scratch) |
| `eval_reports` | Eval metrics JSON + markdown (scratch) |

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
| m5 | Gold eval + era-stratified metrics | done |
| m6 | Batch runner (JSONL in → annotated JSONL out) | done |
| m7 | vLLM / SURF backend (`--concurrency`, manifest override) | done |

**Remaining human work:** curate ~50 hand-labelled gold records in `trifecta_gold`; refine few-shots after first eval.

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
| Step C field match | per-frame qualia fields |
| Era breakdown | group by century from `date` |

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
