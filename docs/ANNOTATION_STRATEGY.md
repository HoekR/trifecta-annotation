# Annotation strategy — canonical guide

**This document is the single source of truth** for gold design, sampling policy, evaluation reporting, and track boundaries (Dutch hand gold, INCEpTION silver, preservare). Operational column/UI detail: [GOLD_LABELLING.md](GOLD_LABELLING.md). Snippet ingest: [SNIPPETS.md](SNIPPETS.md). Collocation / frame-verb growth: [COLLOCATION.md](COLLOCATION.md). Pipeline engineering: [PLAN.md](../PLAN.md).

---

## 1. Problem statement

TRIFECTA annotation asks three things at once:

1. Is the target a **food entity** in context (Step A)?
2. Which **macro-frame** applies (Step B: COOKING, CURE, INGESTION, PRESERVING, NONE)?
3. Which **qualia roles** fill the frame (Step C)?

Early gold work showed a **design signal**, not a labelling failure. **Current frozen benchmark:** 157 rows, **75% Step B** (qwen2.5-coder:latest, 6 Jul 2026) — see [§5 Evolution steps](#5-evolution-steps).

| Finding (123-row gold, qwen2.5-coder:latest, July 2026) | Implication |
|----------------------------------------------------------|-------------|
| Step B frame accuracy **~74%** (pooled) | LLM usable as silver labeler, not gold-quality |
| **64/123** rows `text_regime=UNKNOWN` | Genre mixing under one rubric — fix Layer 0 first |
| **1× PRESERVING** in gold | Per-frame F1 for rare frames is not meaningful yet |
| Effort on polysemous lemmas (*water*, *boter*) | Lemma-driven expansion **loops** without practice coverage |

**Do not** let disagreement exports alone drive gold growth. Use them for **error analysis** and selective adjudication.

---

## 2. Layered annotation model

```text
Layer 0 — text_regime (genre / discourse type)
         RECIPE_PRACTICE | MEDICAL | TRAVEL | LITERARY | ADMIN_TRADE | SCIENTIFIC | UNKNOWN

Layer 1 — Step A (entity + dropout)
         In scope for food-practice annotation in this regime?

Layer 2 — Step B (macro-frame), regime-conditioned
         Frame = linguistic scenario around target, NOT the same as text_regime
         (see §2.1 — especially COOKING_CREATION vs CURE in recipe contexts)

Layer 3 — Step C / qualia
         PR_Technique, CURE_Affliction, etc. — thin in gold until core Step B is stratified
```

**Evaluation:** report Step B (and later Step C) **per `text_regime`**, with pooled metrics secondary. `trifecta-eval` writes per-frame **precision, recall, and F1** in `eval/report.md` and `eval/metrics.json` — read precision first when tuning archetypical framing (§2.2).

**Regime × frame (correlations, not rules):** PRESERVING and COOKING_CREATION are *common* in `RECIPE_PRACTICE`; CURE is *common* in `MEDICAL`; NONE is *common* in `LITERARY` / `TRAVEL`. A recipe snippet can still be CURE; a medical book can still be COOKING_CREATION. Tag regime from source/title; choose frame from the **local KWIC scenario**.

### 2.1 COOKING_CREATION vs CURE (recipe ≠ cure frame)

A frequent source of disagreement — including in `RECIPE_PRACTICE` eval (weakest regime ~65% Step B) — is conflating **genre** with **macro-frame**:

| Dimension | What it asks | Example |
|-----------|--------------|---------|
| `text_regime` | What kind of text / work is this from? | `RECIPE_PRACTICE`, `MEDICAL` |
| Step B frame | What **scenario** surrounds the food target in **this snippet**? | `COOKING_CREATION`, `CURE`, … |

**Core rule:** A passage can be a **recipe** (or from a pharmacopoeia) and still activate **COOKING_CREATION** if the snippet is about **making** the product. Label **CURE** only when the snippet is about the food **functioning as treatment** for an affliction — not merely because the recipe is “for” a cure in a book-level sense.

| Choose | When the snippet … | Typical `lexical_unit` |
|--------|-------------------|------------------------|
| **COOKING_CREATION** | Describes preparation: ingredients, heat, time, tools, “neem … kook … tot …” | `koken`, `sieden`, `mengen`, `bakken` |
| **CURE** | Describes therapeutic use: symptom/affliction + food as remedy | `verzachten`, `genezen`, `tegen de hoest`, `behoort voor` |
| **INGESTION** | Describes eating/drinking without a medical framing | `eten`, `drinken`, `smaken` |

**Worked examples (same “cure recipe” book, different snippets):**

1. *“Neem viooltjes en honing, kook alles tot een dikke siroop.”* → **COOKING_CREATION** (`kook`) — preparation steps, even if the book title is “ tegen de hoest”.
2. *“Deze siroop verzacht de droge hoest.”* → **CURE** (`verzacht`) — affliction + food-as-treatment.
3. *“Geef des morgens een lepel van de siroop.”* → often **INGESTION** or **CURE** depending on whether intake is framed as diet or as dosing against illness; prefer **CURE** when affliction/dosage-for-treatment is explicit.

**Do not:** label CURE because `text_regime=MEDICAL` or because the source is a pharmacopoeia; **do not** label COOKING_CREATION only because `text_regime=RECIPE_PRACTICE`.

**Silver / LLM note:** INCEpTION coarse `MEDICAL_CURE` and LLM prompts both skew toward CURE in recipe-like medical text. Hand gold and adjudication should apply the rule above; expect systematic qwen/GijsBERT errors on prep-step lines in cure recipes until guidelines are reflected in prompts and few-shots.

**Adjudication log (Jul 2026):** `eval/recipe_practice_cure_cooking_adjudication.md` — 8 RECIPE_PRACTICE / pharmacopoeia rows in `gold_fixes.csv` with §2.1 notes; 2 verdicts corrected (gengber, olie) from adopt-CURE → keep COOKING.

**Step C carry-over:** Under COOKING_CREATION, medicinal purpose may appear in notes or `COOKING_CREATION_Food_Product` but does not flip the frame to CURE. Under CURE, fill `CURE_Affliction` and `CURE_Food_Treatment` when stated.

### Sampling rules

| Rule | Rationale |
|------|-----------|
| **Cap per lemma** (max 2 `target_word` per batch unless deliberate) | Stops *water*-style spirals |
| **Sample by regime × phenomenon** | Grow PRESERVING, **COOKING vs CURE in recipe/medical overlap** on purpose |
| **No new core gold with `UNKNOWN` regime** | Layer 0 must be set before merge |
| **Disagreement CSV for adjudication only** | `keep_gold` / `adopt_pred` / `custom` — not auto-relabel |

### 2.2 Archetypical framing and prior FE/LU work (smell / taste)

Related FrameNet-style work on historical Dutch smell and taste used mBERT, monolingual BERT, XLM-RoBERTa, and MacBERTh in **multiclass token classification** and **multitask** setups (FE + LU as separate heads). Best multitask models: monolingual BERT (smell) and XLM-RoBERTa (taste). Reported **per-label F1** (not pooled accuracy) shows a steep hierarchy:

| Label type | Example roles | monoBERT F1 | RoBERTa-XLM F1 |
|------------|---------------|-------------|----------------|
| 1 — frame anchor | Smell/Taste_Word | 0.871 | **0.932** |
| 2 — lexical trigger | Smell/Taste_Source | 0.571 | 0.587 |
| 3 — core qualia | Quality | 0.758 | **0.817** |
| 4 — participant | Odour/Taste_Carrier | 0.482 | **0.788** |
| 5–10 — peripheral | Evoked, Location, Perceiver, Time, Circumstances, Effect | 0.28–0.57 | 0.28–0.56 |

**Implication for TRIFECTA:** FrameNet roles are **archetypical** — the target word and governing LU are learnable; peripheral FEs collapse without dense gold. TRIFECTA mirrors this in layers:

| Prior work (smell/taste) | TRIFECTA layer | Current gold / eval |
|--------------------------|----------------|---------------------|
| Smell/Taste_Word (F1 ≈ 0.87–0.93) | Step A — food entity | ~82–85% entity accuracy |
| Source / LU (F1 ≈ 0.57–0.59) | Step B — `lexical_unit` + macro-frame | Step B ~60–75% accuracy across regimes |
| Quality, Carrier, … (F1 ≈ 0.28–0.79) | Step C — qualia roles | **93 / 308** hand gold; field-match + soft containment eval |

**Metric preference:** In archetypical framing, **precision outweighs recall** — a false positive frame (e.g. COOKING on a homograph or DROPPED row) pollutes silver and training more than a missed marginal instance. Gold should stay conservative; eval should report **per-frame precision and recall** (not F1 alone) and prioritise reducing false positives on COOKING_CREATION and INGESTION in LITERARY / homograph slices. Jul 2026 literary spot-check (36 disagreements) confirmed systematic **over-framing** by qwen, not systematic gold failure — no import to gold.

### 2.3 Layered Evaluation: Rough-to-Refinement vs. Strict Joint Accuracy

TRIFECTA follows a **coarse-to-fine (rough $\to$ refinement)** architecture:
```text
[Step A: Entity Gate]  ──►  [Step B: Macro-Frame]  ──►  [Step C: Qualia Roles]
   (Rough food filter)        (Coarse categorization)      (Granular, open-ended slots)
```

**Why strict joint accuracy clashes with refinement:**
1. **Granularity and Variation in Historical Dutch:** In Step C, human annotators and LLM prompts often extract the same semantic role at slightly different granularities (e.g. human writes `pekel`, model extracts `dekt ze met pekel en olie`). Requiring exact string matches across all 3–5 fields simultaneously treats a 90% correct granular extraction as a total failure ($0\%$).
2. **Refinement is Additive:** Discovering *that* cinnamon was used for `CURE` (Step B) and *that* the affliction was `de tering` (Step C: `Affliction`) is already a high-value extraction, even if an incidental `Manner` or `Dosage` slot is worded differently.

**Evaluation layers in TRIFECTA:**
- **Step A:** Entity & Metaphor Accuracy (~82–86%) — evaluates filtering of non-food items, livestock, and metaphors.
- **Step B:** Per-Frame Precision & Recall — evaluates semantic domain classification (`COOKING_CREATION`, `PRESERVING`, `CURE`, `INGESTION`, `NONE`).
- **Step C:** Per-Field Accuracy & Soft Containment — evaluates reliability of individual semantic slots (e.g. `PR_Food_Patient` or `CURE_Affliction`).
- **Composite Micro-Accuracy:** Field-level hit rate across all slot opportunities ($\frac{\sum \text{Correct Field Hits}}{\sum \text{Total Field Opportunities}}$), tracking overall extraction density without penalizing valid partial extractions.

**Grounding analytic claims:** Corpus analysis should not wait for perfect joint row accuracy. Instead, researchers can query specific fields whose individual field accuracy and soft precision meet domain reliability thresholds.

---

## 3. Three annotation tracks

| Track | Files | Role |
|-------|-------|------|
| **A — Dutch hand gold** | `gold_labelling_all.csv`, `gold.parquet` | Eval reference; regime-stratified growth |
| **B — INCEpTION silver** | `inception_silver_labelling.csv`, `inception_annotations.jsonl` | Snippet-line view over cort_voc; **not** merged into hand gold by default. Import: `--granularity both` (fine + coarse). |
| **C — Preservare (planned)** | sibling repo KWIC | Separate `RECIPE_PRACTICE` + PRESERVING slice; bridge later |

**INCEpTION:** annotations are **lines from food snippets**, not full INCEpTION doc batches. Import matches context text to `food_snippets_for_annotation.csv` for `title`, `source_path`, `text_regime`. Notes: `inception_import; snippet_view; silver/unreconciled`.

**English colleagues:** parallel schema and frames; no shared `record_id` with Dutch. See [RESEARCH_STRATEGY_SUMMARY.md](RESEARCH_STRATEGY_SUMMARY.md) for EN-only coordination points.

---

## 4. Gold workflow (current)

### 4.1 Fix Layer 0 on existing gold

```bash
# Re-infer UNKNOWN rows (title + snippet text lookup)
uv run python scripts/tag_text_regime.py --refresh-unknown --import-after

# Or hand-review UNKNOWN in UI
uv run python scripts/export_regime_review.py --to-gold-ui
uv run trifecta-gold-ui
uv run python scripts/export_regime_review.py --apply-gold-ui --import-after
```

### 4.2 Grow gold (regime-stratified batch)

```bash
uv run python scripts/export_regime_stratified.py --summary \
  --regime-quota "RECIPE_PRACTICE:25,MEDICAL:25"
# → gold_labelling_regime_batch.csv (50 unlabelled KWIC candidates)

uv run trifecta-gold-ui   # label; set text_regime if needed
uv run python scripts/merge_gold_batch.py \
  --batch-path "/Volumes/Extreme SSD/scratch/trifecta/gold_labelling_regime_batch.csv"
uv run python scripts/import_gold_csv.py \
  --input-path "/Volumes/Extreme SSD/scratch/trifecta/gold_labelling_all.csv"
```

Optional verb/frame export (secondary): `export_gold_candidates.py --source verb --limit 25`.

**Clear-frame gold batch** (heldere COOKING / INGESTION uit cort_voc verb-KWIC):

```bash
uv run python scripts/export_clear_frame_examples.py --summary --pool-summary \
  --frames COOKING_CREATION \
  --frame-quota "COOKING_CREATION:30" --limit 30 \
  --output-path "/Volumes/Extreme SSD/scratch/trifecta/eval/cooking_stepc_batch.csv"
# Full labelling workflow: docs/GOLD_LABELLING.md § Step 5 runbook
```

**PRESERVING batch** (preservare recipe dataset + technique seeds):

```bash
uv run python scripts/export_preservare_gold_candidates.py --summary --pool-summary --limit 10
# → scratch/eval/preservare_gold_candidates.csv
# Source: ~/develop/recepten-preservare-analysis (recipe_dataset_2 + technique_term_association)
```

### 4.3 Eval loop

```bash
uv run python scripts/rebuild_gold_eval_inputs.py
uv run trifecta-batch --model qwen2.5-coder:latest \
  --input-path "/Volumes/Extreme SSD/scratch/trifecta/gold_eval_inputs.jsonl" \
  --output-path "/Volumes/Extreme SSD/scratch/trifecta/gold_predictions.jsonl"
uv run trifecta-eval \
  --gold-path "/Volumes/Extreme SSD/scratch/trifecta/gold.parquet" \
  --predictions-path "/Volumes/Extreme SSD/scratch/trifecta/gold_predictions.jsonl"
```

Read **per-regime** section in `eval/report.md` before pooled Step B.

### 4.4 Selective disagreement review

```bash
uv run python scripts/eval_disagreements.py
# Edit eval/gold_fixes.csv — frame rows first; skim dropout/step_a
uv run python scripts/import_gold_fixes.py --import-after
```

---

## 5. Evolution steps

Steps are **iterative**, not a one-way gate. You may revisit eval (Track A), silver (Track C), or training (Track B) in any order; the table marks **decision points** and frozen artifacts, not a strict waterfall.

| Step | Date | What | Outcome |
|------|------|------|---------|
| 1 — Pilot gold | early 2026 | ~100 food/verb-seeded rows | Baseline ~66% Step B |
| 2 — Adjudication | early 2026 | 49 rows via `gold_fixes.csv` | ~76% on 100-row slice |
| 3 — Regime layer | Jul 2026 | `text_regime` backfill + per-regime eval | 123 rows; pooled ~74%; UNKNOWN regime mix diagnosed |
| 4 — **Baseline freeze + training pivot** | **6 Jul 2026** | **See below** | **157-row eval benchmark frozen; GijsBERT m9 done** |
| 5 — **Qualia for analysis (m10)** | **Jul 2026 →** | **See below** | **Quota Step C gold + field eval + prompt calibration** |

### Step 4 — Baseline freeze + training pivot (6 Jul 2026)

**Decision:** Stop the label → batch → eval → disagreement loop. Treat hand gold as a **stable eval benchmark**; shift effort to **producing a model** (GijsBERT).

**Gold cleanup (Track A):**

| Action | Effect |
|--------|--------|
| Remove 12× `pha001phar*` pharmacopoeia glossary rows | `labelled=false` |
| Remove 9× denylisted targets (`witte`, `wit`, `van`, `een`) | `labelled=false` |
| Apply 104 user-curated fixes from `gold_fixes.csv` | `--import-after` |
| **Do not** re-run `eval_disagreements.py` without intent | `gold_fixes.csv` is user-owned; auto re-export can drop rows |

**Result:** **157 labelled rows** → `gold.parquet`, `gold_eval_inputs.jsonl`.

**LLM baseline v2 (frozen):**

```bash
uv run trifecta-batch --model qwen2.5-coder:latest \
  --input-path "/Volumes/Extreme SSD/scratch/trifecta/gold_eval_inputs.jsonl" \
  --output-path "/Volumes/Extreme SSD/scratch/trifecta/gold_predictions.jsonl"
uv run trifecta-eval \
  --gold-path "/Volumes/Extreme SSD/scratch/trifecta/gold.parquet" \
  --predictions-path "/Volumes/Extreme SSD/scratch/trifecta/gold_predictions.jsonl"
```

| Metric | v2 (157 rows) | Prior (173 rows, stale) |
|--------|---------------|-------------------------|
| Step B accuracy | **75.0%** | ~59% |
| Step A entity | 82.2% | — |
| Dropout agreement | 77.7% | — |

**Per-frame F1:** INGESTION 0.83 · CURE 0.79 · PRESERVING 0.80 · NONE 0.71 · COOKING_CREATION 0.67

**Weakest regime:** RECIPE_PRACTICE 65.5% (n=29) — error analysis only, not disagreement-driven gold growth.

**Snapshots:** `eval/report.md`, `eval/baseline_v2_157rows_2026-07.md`

**INCEpTION silver (Track B):**

- Coarse import (`--granularity both`): **3,175 rows** in `inception_silver_labelling.csv`
- `fine_inception` 3,118 · `coarse_inception` 57
- Coarse frames: `FOOD_TRANSFORM` / `MEDICAL_CURE` / `CONSUMPTION` / `OUT_OF_SCOPE`
- **Not eval-grade** — feeds training, not hand gold merge

**Silver Step B for rows without INCEpTION frame LU (367 rows):**

INCEpTION fine import leaves `step_b` empty when no frame LU was drawn; import tags these as `coarse_frame=OUT_OF_SCOPE`. Two silver strategies (train only — not eval-grade):

| Strategy | Silver input | NONE in train | Notes |
|----------|--------------|---------------|-------|
| **Coarse NONE** (recommended for GijsBERT) | `inception_annotations.jsonl` | ~366 | `OUT_OF_SCOPE` → NONE in export; aligns better with hand gold NONE rate |
| **LLM backfill** (experiment) | `inception_annotations_llm.jsonl` | ~95 | qwen Step B on 367 rows; assigns frames more often than hand gold |

LLM backfill (optional):

```bash
uv run python scripts/backfill_silver_step_b.py --run-batch \
  --silver-path "/Volumes/Extreme SSD/scratch/trifecta/inception_annotations.jsonl" \
  --output-path "/Volumes/Extreme SSD/scratch/trifecta/inception_annotations_llm.jsonl"
```

Output: `inception_annotations_llm.jsonl` (+ `.llm_backfill.jsonl` raw LLM). Re-run with `--resume` if interrupted.

**GijsBERT export** (use coarse silver for current best recipe):

```bash
uv run python scripts/export_gijsbert.py \
  --silver-path "/Volumes/Extreme SSD/scratch/trifecta/inception_annotations.jsonl" \
  --gold-path "/Volumes/Extreme SSD/scratch/trifecta/gold.parquet" \
  --output-dir "/Volumes/Extreme SSD/scratch/trifecta/gijsbert"
```

| Split | Rows | Source |
|-------|------|--------|
| `train.jsonl` | 3,161 | INCEpTION silver (gold `record_id`s excluded) |
| `dev.jsonl` / `test.jsonl` | 157 each | hand gold |
| Train NONE (coarse) | ~366 | `OUT_OF_SCOPE` → NONE |
| Base model | `emanjavacas/GysBERT-v2` | mark mode: `[TGT]` + `[VRB]` |

**GijsBERT fine-tune** (`scripts/train_gijsbert.py`):

```bash
# Balanced NONE (best pooled dev so far — Jul 2026)
uv run python scripts/train_gijsbert.py \
  --model "emanjavacas/GysBERT-v2" \
  --data-dir "/Volumes/Extreme SSD/scratch/trifecta/gijsbert" \
  --output-dir "/Volumes/Extreme SSD/scratch/trifecta/gijsbert/models/gysbert-v2-balanced-none" \
  --oversample-none 2 --class-weight-balance --none-weight-boost 2.0

# Frames-only head (4 classes, dev n=69 frame rows)
uv run python scripts/train_gijsbert.py \
  --model "emanjavacas/GysBERT-v2" \
  --data-dir "/Volumes/Extreme SSD/scratch/trifecta/gijsbert" \
  --output-dir "/Volumes/Extreme SSD/scratch/trifecta/gijsbert/models/gysbert-v2-frames-only" \
  --frames-only
```

| Flag | Purpose |
|------|---------|
| `--oversample-none N` | Duplicate NONE train rows N times total (1 = off) |
| `--class-weight-balance` | Inverse-frequency weights in loss |
| `--none-weight-boost` | Extra multiplier on NONE class weight (default 2.0) |
| `--frames-only` | Train/eval on 4 frame classes only (excl. NONE) |

**Fine-tune results (157-row gold dev, Jul 2026):**

| Run | Dev acc (all) | Dev acc (frames, n=69) | NONE F1 | Notes |
|-----|---------------|------------------------|---------|-------|
| qwen baseline | **75.0%** | — | 0.71 | frozen eval reference |
| gysbert-v2 + LLM silver | 22.3% | 44.9% | 0.09 | train lacked NONE signal |
| **gysbert-v2-balanced-none** | **62.4%** | 34.8% | **0.82** | coarse NONE + 2× oversample + class weights |
| gysbert-v2-frames-only | **37.7%** (n=69) | 37.7% | n/a | 4-class head, no NONE |

Reports per run: `gijsbert/models/<run>/dev_metrics.json` + `report.md`. Compare: `scripts/compare_gijsbert_runs.py`.

**Time budget (Step 4 — completed Jul 2026):**

| Activity | ~share | Output / guardrail |
|----------|--------|-------------------|
| **Planning & strategy** | **10%** | Evolution steps, docs (`PLAN.md`, this file), architecture choices |
| **Pipeline & tooling** | **5%** | Import/export scripts, thesaurus, eval infra |
| **A — Eval** | **10%** | Baseline reports, spot-check; **not** open-ended disagreement review |
| **B — Training** | **55%** | GijsBERT export, fine-tune, dev vs qwen 75% baseline |
| **C — INCEpTION silver** | **20%** | Coarse/fine annotation for train corpus; not eval-grade |
| **Buffer** | **~5%** | Model compares, scratch hygiene, one-off fixes |

### Step 5 — Qualia for analysis (m10) — **current**

**Decision (10 Jul 2026, updated Aug 2026):** Primary effort focused on **Step C qualia** for corpus analysis. Step C stays **LLM** (no GijsBERT qualia head). “Finetuning qualia” means **prompt / few-shot calibration** against hand gold, not classifier training.

**Aim:** Trustworthy qualia annotations for analysis — quota hand gold on Step C fields, field-level eval, calibrated LLM prompts, bounded export to parquet.

| Gap | Status (Aug 2026) |
|-----|-------------------|
| Hand gold with Step C | **93 rows with Step C** in **308 total gold** (31 COOKING, 27 PRESERVING, 24 CURE, 11 INGESTION) |
| `trifecta-eval` | **Done** — per-field exact match + soft containment metrics |
| Gold labeller UI | **Done** — `trifecta-stepc-ui` dedicated browser UI on port 5051 |
| Prompt calibration | **COOKING wired**; few-shots for PRESERVING, CURE, INGESTION ready |
| Extended ontology | Added `tabak` (+ historical variants) with validated pilot tranche |

**Steps (see [PLAN.md § State of affairs](../PLAN.md) for engineering detail):**

| # | Task | Deliverable |
|---|------|-------------|
| 1 | Pick pilot frame | **COOKING_CREATION** (most numerous in frozen gold; qualia: Method, Process, Food_Product) — done |
| 2 | **Export quota batches** | COOKING, PRESERVING, CURE, INGESTION, Tabak pilot — done |
| 3 | **Gold labeller Step C** | Dedicated `trifecta-stepc-ui` web app on port 5051 — done |
| 4 | **Label quota batches** | 308 validated gold rows imported into `gold.parquet` — done |
| 5 | **Step C eval** | `trifecta-eval` field-match metrics + per-regime report — done |
| 6 | **LLM baseline** | `trifecta-batch` on gold slice → Step C baseline report — done |
| 7 | **Prompt / few-shot pass** | Few-shot injection for PRESERVING, CURE, INGESTION — **next** |
| 8 | **Analysis export** | Bounded A→B→C batch → parquet; document uncertainty for notebooks — done |

**Usable after Step 5 (partial):**

- Per-field Step C F1 on pilot frame (not yet corpus-wide claims)
- Exploratory qualia on full corpus still = LLM hypotheses until more frames get quota gold

**Defer (unchanged from Step 4 close-out):**

- More NONE silver tranches (`reizen` pilot done)
- GijsBERT hybrid wiring into `trifecta-batch` (62% dev < 75% qwen)
- GijsBERT frames-only / NONE-boost tuning (maintenance only if needed)
- Collocation → GijsBERT `[VRB]` export ([COLLOCATION.md §6](COLLOCATION.md#6-gijsbert-export-audit-9-jul-2026) blocked)
- Optional Step B quota gold (+5–10 PRESERVING / +10 RECIPE_PRACTICE for frame F1) — **secondary** to Step C pilot

**Time budget (Step 5 — rough guide):**

| Activity | ~share | Output |
|----------|--------|--------|
| **Quota Step C gold** | **40%** | Labeller UI + 30–50 labelled rows |
| **Eval + tooling** | **25%** | Step C metrics in `trifecta-eval`, baseline report |
| **Prompt calibration** | **20%** | Few-shots per frame, gold-only re-runs |
| **Analysis export** | **10%** | Parquet + notebook smoke test |
| **Planning / buffer** | **5%** | Docs, spot-checks |

**Milestone ID:** `m10` in [PLAN.md §9](../PLAN.md#9-milestones).

---

## 6. LLM and models

Default model: `qwen2.5-coder:latest` (`trifecta_annotation/config.py`).

| Model (123-row gold, July 2026) | Step B |
|---------------------------------|--------|
| qwen2.5:14b-instruct | 76.3% (100-row slice) |
| qwen2.5-coder:latest | **73.6%** (123 rows) |
| mistral 7B | 60.9% |
| **Apertus 8B** (`hf.co/bartowski/swiss-ai_Apertus-8B-Instruct-2509-GGUF:Q4_K_M`) | *pending* |

Run Apertus on the gold eval set:

```bash
uv run python scripts/compare_llm_models.py --run-batch --run-label apertus_8b \
  --models "hf.co/bartowski/swiss-ai_Apertus-8B-Instruct-2509-GGUF:Q4_K_M"
```

Or full sweep (includes Apertus if pulled): `./scripts/run_model_compare.sh`

Reports: `eval/model_comparison.md`. English glossary hint pilot: little gain on disagreement slice.

---

## 7. Future work (not blocking Step 5)

| Item | Notes |
|------|-------|
| **Step C in gold + eval** | **Active (Step 5 / m10)** — quota gold, `trifecta-eval` field metrics, prompt calibration |
| **GijsBERT Step B** | **Maintenance** — m9 done (`gysbert-v2-balanced-none` 62.4% dev vs 75% qwen); hybrid batch wiring deferred |
| **Coarse 4-class head** | Optional second head on INCEpTION coarse silver |
| **Preservare adapter** | `export_preservare_gold_candidates.py` — feeds Step C PRESERVING quota |
| **Per-regime GijsBERT** | After pooled model beats LLM baseline (not current priority) |
| **Step B quota gold** | +5–10 PRESERVING / +10 RECIPE_PRACTICE — secondary to Step C pilot |
| **Collocation skeleton** | Lexicon growth + review; GijsBERT export blocked — [COLLOCATION.md §6](COLLOCATION.md#6-gijsbert-export-audit-9-jul-2026) |

---

## 8. Command reference

| Task | Command |
|------|---------|
| Gold UI | `uv sync --extra gold-ui && uv run trifecta-gold-ui` |
| Tag / refresh regime | `uv run python scripts/tag_text_regime.py --refresh-unknown --import-after` |
| Corpus text overview | `uv run python scripts/export_corpus_overview.py --summary` |
| Regime review export | `uv run python scripts/export_regime_review.py --to-gold-ui` |
| Regime-stratified batch | `uv run python scripts/export_regime_stratified.py --summary` |
| Merge batch | `uv run python scripts/merge_gold_batch.py --batch-path …/gold_labelling_regime_batch.csv` |
| Import gold | `uv run python scripts/import_gold_csv.py --input-path …/gold_labelling_all.csv` |
| Rebuild eval inputs | `uv run python scripts/rebuild_gold_eval_inputs.py` |
| INCEpTION import | `uv run python scripts/import_inception_tsv.py --annotator rikh --annotator dekker` |
| Disagreements | `uv run python scripts/eval_disagreements.py` |
| Apply fixes | `uv run python scripts/import_gold_fixes.py --import-after` |
| Eval | `uv run trifecta-eval --gold-path …/gold.parquet --predictions-path …/gold_predictions.jsonl` |
| GijsBERT export | `uv run python scripts/export_gijsbert.py --silver-path …/inception_annotations.jsonl --gold-path …/gold.parquet` |
| LLM silver backfill | `uv run python scripts/backfill_silver_step_b.py --run-batch --silver-path …/inception_annotations.jsonl --output-path …/inception_annotations_llm.jsonl` |
| GijsBERT train | `uv run python scripts/train_gijsbert.py --model emanjavacas/GysBERT-v2 --data-dir …/gijsbert --output-dir …/models/<run>` |
| GijsBERT compare | `uv run python scripts/compare_gijsbert_runs.py --runs …` |
| Collocation skeleton | `uv run python scripts/export_collocation_skeleton.py --summary` |
| Frame-verb lexicon grow | `uv run python scripts/build_frame_verb_lexicon.py --collocation-miner --summary` |
| Verb lexicon stats | `uv run python scripts/verb_lexicon_summary.py` |

Scratch root: `/Volumes/Extreme SSD/scratch/trifecta/`.

---

## 9. Scratch file map

| Path | Track |
|------|-------|
| `gold_labelling_all.csv` / `gold.parquet` | Hand gold (A) |
| `gold_labelling_regime_batch.csv` | Next label queue |
| `gold_eval_inputs.jsonl` / `gold_predictions.jsonl` | Eval batch |
| `eval/report.md` / `eval/metrics.json` | Metrics (**per-regime primary**) |
| `eval/baseline_v2_157rows_2026-07.md` | Frozen qwen baseline (157 rows) |
| `eval/gold_fixes.csv` | User-curated adjudication (do not auto re-export) |
| `inception_silver_labelling.csv` | INCEpTION silver (B); `annotation_type`, `coarse_frame`, `annotator` |
| `inception_annotations.jsonl` | INCEpTION silver JSONL (coarse NONE export source) |
| `inception_annotations_llm.jsonl` | LLM-backfilled silver (experiment) |
| `gijsbert/train.jsonl`, `dev.jsonl`, `label_manifest.json` | GijsBERT export (train = silver, dev = gold) |
| `gijsbert/models/gysbert-v2-balanced-none/` | Best pooled run (62.4% dev, NONE F1 0.82) |
| `gijsbert/models/gysbert-v2-frames-only/` | 4-class frames-only run |
| `gijsbert/models/gysbert-v2-llm-silver/` | LLM silver experiment (22.3% dev) |
| `models/hub/` | HF pretrained weights (GysBERT, GysBERT-v2, historic-dutch BERT) |
| `gijsbert/models/` | Fine-tuned classifiers + `train_compare.log` |
| `eval/regime_review_unknown.csv` | Layer-0 review export |
| `eval/collocation_skeleton.csv` | Target↔collocate PMI skeleton ([COLLOCATION.md](COLLOCATION.md)) |
| `eval/corpus_texts_overview.csv` | Source works catalogue (titles, regimes, counts) |

---

## 10. Related docs

| Doc | Use for |
|-----|---------|
| [GOLD_LABELLING.md](GOLD_LABELLING.md) | CSV columns, UI fields |
| [SNIPPETS.md](SNIPPETS.md) | cort_voc ingest, kwic build |
| [COLLOCATION.md](COLLOCATION.md) | Collocation skeleton, frame-verb lexicon growth |
| [RESEARCH_STRATEGY_SUMMARY.md](RESEARCH_STRATEGY_SUMMARY.md) | English track coordination only |
| [PLAN.md](../PLAN.md) | Pipeline code, schemas, HPC — not gold policy |
| [LABEL_MAPPING_EN_NL.md](LABEL_MAPPING_EN_NL.md) | WebAnno ↔ JSON |

---

*Last updated: 13 July 2026 — Step 5 (m10) qualia track harmonized with PLAN.md; GijsBERT m9 complete, Step C active.*
