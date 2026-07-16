# Gold labelling CSV guide

> **Policy (sampling, regimes, eval, tracks):** [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md) — canonical guide. This file is operational reference only (columns, UI, commands).

> **Active work (Step 5 / m10):** follow **[§ Step 5 runbook — COOKING_CREATION qualia](#step-5-runbook--cooking_creation-qualia-m10)** below end-to-end. Do not infer the workflow from `PLAN.md` alone.

---

## Step 5 runbook — COOKING_CREATION qualia (m10)

**You are here if:** you exported a clear-frame batch and need to know what to do next.

**Aim:** hand-label ~30 `COOKING_CREATION` rows with Step A, B, **and** Step C qualia fields, then merge into `gold.parquet`.

### Known gaps (read once)

| What | Status |
|------|--------|
| Step 5 gold lab notebook | **`notebooks/cooking_stepc_gold_lab.ipynb`** — overview table + row editor (primary workflow) |
| Gold UI Step A/B | Optional — Flask UI still works for snippet highlighting |
| Gold UI Step C | **Deferred** — use notebook row editor |
| `export_clear_frame_examples.py` default `--frames` | `COOKING_CREATION,INGESTION` — use `--frames COOKING_CREATION` for a COOKING-only batch |
| `trifecta-eval` Step C metrics | **Implemented** — see `eval/report.md` § Step C after `trifecta-eval` |

### Step 0 — Export batch (done once per batch)

```bash
cd ~/develop/trifecta-annotation
SCRATCH="/Volumes/Extreme SSD/scratch/trifecta"

uv run python scripts/export_clear_frame_examples.py --summary --pool-summary \
  --frames COOKING_CREATION \
  --frame-quota "COOKING_CREATION:30" --limit 30 \
  --output-path "$SCRATCH/eval/cooking_stepc_batch.csv"
```

Output: **`$SCRATCH/eval/cooking_stepc_batch.csv`** — candidate rows with `labelled=false`, miner hints in `selected_frame` / `lexical_unit` / `step_b_reasoning`.

### Step 1 — Open the gold lab notebook (primary)

```bash
cd ~/develop/trifecta-annotation
uv sync
uv run python scripts/generate_notebooks.py --name cooking_stepc_gold_lab
# Open notebooks/cooking_stepc_gold_lab.ipynb in Jupyter / VS Code
```

**Two-pane workflow:**

1. **Overview table** (itables) — all rows; filter/sort to spot gaps.
2. **Row editor** — **pending queue only** by default; highlighted snippet + fields.
3. **Save & next** — marks row, auto-saves CSV, advances to next unlabelled row.

Jump within the pending queue via dropdown or Prev/Next. Set `pending_only=False` on `RowLabeller` to revisit finished rows.

### Step 2 — Save, merge, import

```bash
uv run python scripts/merge_gold_batch.py \
  --batch-path "$SCRATCH/eval/cooking_stepc_batch.csv"

uv run python scripts/import_gold_csv.py \
  --input-path "$SCRATCH/gold_labelling_all.csv"
```

Only rows with `labelled=true` import. Step C columns are read from CSV if present.

### Step 3 — What comes after (engineering / not manual)

1. Step C metrics in `trifecta-eval` — **done** (exact + soft containment; joint / micro; by frame).
2. Re-run `trifecta-eval` on `gold_predictions.jsonl` and read § Step C (exact + soft) in `eval/report.md`.
3. Export / browse good matches + misses for few-shot picking:

```bash
# CLI
uv run python scripts/export_step_c_review.py
uv run python scripts/export_step_c_review.py --fewshot-only --frames COOKING_CREATION

# Notebook — plain pandas + walk_details (no itables; works in Cursor)
uv run python scripts/generate_notebooks.py --name step_c_review
# open notebooks/step_c_review.ipynb
```

Writes `eval/step_c_review.csv` (joint / partial_strong first; `fewshot_candidate` column).
Use `walk_details(df, start=0, n=5)` to compare GOLD vs PRED line-by-line.

**Note:** exact-match Step C scores understate quality when predictions are longer but still correct (pred ⊃ gold). Use **§ Step C — soft match (containment)** in `eval/report.md` for that judgment.

COOKING few-shots (2026-07-16): review table indices `1,5–11,22,23,26` → `trifecta_annotation/prompts/step_c_cooking_fewshots.json` (pred fields). Skipped `0,2,3,4` (PRESERVING/INGESTION).

4. Prompt / few-shot tuning on weakest qualia fields.

5. Analysis export (LLM hypotheses → flat parquet):

```bash
uv run python scripts/export_analysis_parquet.py
# or: --require-step-c --exclude-dropped
# → resolve("trifecta_analysis") = scratch/trifecta/analysis/annotations.parquet
```

Every row carries `uncertainty_note`: treat `step_c` as hypotheses unless hand gold.

### Quick reference — which file am I editing?

| File | When |
|------|------|
| `eval/cooking_stepc_batch.csv` | Active batch (export → label → merge) |
| `gold_labelling_all.csv` | Merged master gold (after `merge_gold_batch.py`) |
| `gold.parquet` | Imported eval set (after `import_gold_csv.py`) |
| `eval/gold_fixes.csv` | **Frozen 157-row adjudication only** — not this workflow |

---

## Web UI (recommended)

Hand-label rows in the browser instead of editing the CSV in Excel:

```bash
cd ~/develop/trifecta-annotation
uv sync --extra gold-ui
uv run trifecta-gold-ui
```

Open http://127.0.0.1:5050 — you get one snippet at a time with the **target word highlighted**, Step A/B fields, prev/next navigation, and progress (`N / 50 labelled`).

- **Save** — writes directly to `trifecta/gold_labelling.csv` on scratch.
- **Save & next** — save and jump to the next row.
- **LLM suggest** — optional draft from the pipeline (you must review; do not accept blindly).

When all rows are done:

```bash
uv run python scripts/merge_gold_batch.py
uv run python scripts/import_gold_csv.py --input-path "/Volumes/Extreme SSD/scratch/trifecta/gold_labelling_all.csv"
```

`merge_gold_batch.py` appends new `gold_labelling.csv` rows into `gold_labelling_all.csv` (keeps existing 100 labels). Import only picks up rows with `labelled=true` — label batch 3 in the UI first.

Tag or refresh `text_regime` on existing rows:

```bash
uv run python scripts/tag_text_regime.py --csv-path "/Volumes/Extreme SSD/scratch/trifecta/gold_labelling_all.csv"
```

### Regime review and stratified batch

See [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md) §4.1–4.2. Commands:

```bash
uv run python scripts/tag_text_regime.py --refresh-unknown --import-after
uv run python scripts/export_regime_review.py --to-gold-ui   # optional hand review
uv run python scripts/export_regime_stratified.py --summary
```

## Export candidates

```bash
uv run python scripts/build_kwic_inputs.py
uv run python scripts/export_gold_candidates.py --limit 50
```

Writes `trifecta_gold_csv` (scratch tier: `trifecta/gold_labelling.csv`).

## CSV columns

| Column | Required when labelled | Values / notes |
|--------|------------------------|----------------|
| `record_id` | yes | Stable id; must match batch predictions |
| `corpus` | yes | e.g. `voc_recipes`, `recipe_web` |
| `text_regime` | recommended | `RECIPE_PRACTICE`, `MEDICAL`, `TRAVEL`, `LITERARY`, `ADMIN_TRADE`, `SCIENTIFIC`, `UNKNOWN` |
| `target_word` | yes | Food term in context |
| `context_text` | yes | KWIC window |
| `date` | no | Year or date string for era metrics |
| `source_path` | no | Origin file if known |
| `labelled` | yes | `true` when row is ready to import |
| `dropped` | if early exit | `true` / `false` |
| `drop_reason` | if dropped | `metaphor`, `not_food_entity`, … |
| `is_food_entity` | if not dropped at A | `true` / `false` |
| `is_metaphor` | if not dropped at A | `true` / `false` |
| `formal_dimension` | no | `FOOD_Unit`, `FOOD_Constituent_Part`, `FOOD_Whole`, `OTHER` |
| `canonical_pref_label` | no | From `Food_terms` when matched |
| `pref_label_en` / `gloss_en` | no | From `trifecta_thesaurus_glossary.csv` when available (English reviewer hint) |
| `ontology_match` | no | `true` / `false` |
| `step_a_reasoning` | recommended | Short justification |
| `selected_frame` | if passes A | `COOKING_CREATION`, `CURE`, `INGESTION`, `PRESERVING`, `NONE` — see [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md) §2.1 for **COOKING vs CURE** (recipe prep ≠ cure frame) |
| `lexical_unit` | if frame ≠ NONE | Frame trigger word |
| `step_b_reasoning` | recommended | Short justification |
| `COOKING_CREATION_Method` | Step C (COOKING) | See [Step 5 runbook](GOLD_LABELLING.md#step-5-runbook--cooking_creation-qualia-m10) |
| `COOKING_CREATION_Process` | Step C (COOKING) | |
| `COOKING_CREATION_Food_Product` | Step C (COOKING) | |
| `CURE_Affliction` / `CURE_Food_Treatment` | Step C (CURE) | |
| `INGESTION_Context` / `INGESTION_Ingestor` / `INGESTION_Manner` | Step C (INGESTION) | |
| `PR_Technique` / `PR_Medium` / `PR_Food_Patient` | Step C (PRESERVING) | |
| `notes` | no | Free-text reviewer notes |

**Dropout rows:** set `labelled=true`, fill Step A fields, set `dropped=true`, leave Step B empty.

**Pass-through rows:** set `labelled=true`, `dropped=false`, fill Step A and Step B.

If Step A marks metaphor or non-food, `dropped` is inferred as `true` unless you explicitly set `dropped=true` in the sheet.

## Import labelled CSV

```bash
uv run python scripts/import_gold_csv.py
```

Creates:

- `trifecta_gold` — parquet (`annotation_json` column)
- `trifecta_gold_jsonl` — JSONL mirror

## Re-export for editing

```bash
uv run python scripts/export_gold_csv.py
```

## Evaluate

See [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md) §4.3 for the full eval loop. Quick path:

```bash
uv run python scripts/rebuild_gold_eval_inputs.py
uv run trifecta-batch --model qwen2.5-coder:latest \
  --input-path "/Volumes/Extreme SSD/scratch/trifecta/gold_eval_inputs.jsonl" \
  --output-path "/Volumes/Extreme SSD/scratch/trifecta/gold_predictions.jsonl"
uv run trifecta-eval \
  --gold-path "/Volumes/Extreme SSD/scratch/trifecta/gold.parquet" \
  --predictions-path "/Volumes/Extreme SSD/scratch/trifecta/gold_predictions.jsonl"
```

Report: read **By text_regime** in `eval/report.md` first; pooled Step B is secondary.

## Review disagreements (CSV — edit this, not Excel)

See [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md) §6 for rationale (why not to let disagreements alone drive all sampling).

Export mismatches vs Qwen:

```bash
uv run python scripts/eval_disagreements.py
```

Writes under `trifecta/eval/`:

| File | Edit? |
|------|-------|
| **`gold_fixes.csv`** | **Yes** — fill `verdict` + optional overrides |
| `frame_disagreements.csv` | Skim only |
| `dropout_disagreements.csv` | Skim only |
| `step_a_disagreements.csv` | Skim only |

Optional skim workbook (never import from this):

```bash
uv run python scripts/eval_disagreements.py --workbook
```

Edit **`gold_fixes.csv`** in Cursor or any plain-text editor — same format as your gold CSV (`true`/`false` strings, UTF-8). Avoid Excel Save-As round-trips; they mangle booleans and encoding.

### `gold_fixes.csv` columns

| Column | You fill? | Meaning |
|--------|-----------|---------|
| `record_id` … `pred_dropped` | no | Context |
| **`verdict`** | **yes** | Shorthand: `k` or `keep*` → keep hand gold; `a` / `adopt*` / `pred*` → adopt model; `w` / `wij*` / `custom` → manual override |
| **`review_notes`** | no | Optional note appended to gold row on import |
| **`reviewed_at`** | no | When you adjudicated (ISO UTC); preserved on re-export — **not** auto-set to today |
| **`export_updated_at`** | no | When disagreement export last changed this row's issue text (system) |
| **`review_notes`** | optional | Appended to gold `notes` |
| `selected_frame`, `dropped`, … | if `custom` | Only columns you want to change |

Re-exporting disagreements **preserves** your `gold_fixes.csv` edits.

### Apply fixes → import gold

```bash
uv run python scripts/import_gold_fixes.py --import-after
```

Defaults: `gold_labelling_all.csv`, `eval/gold_fixes.csv`, `gold_predictions.jsonl`.

Then re-eval:

```bash
uv run trifecta-eval \
  --gold-path "/Volumes/Extreme SSD/scratch/trifecta/gold.parquet" \
  --predictions-path "/Volumes/Extreme SSD/scratch/trifecta/gold_predictions.jsonl"

uv run python scripts/eval_disagreements.py
```

## English-hint scratch experiment

Cross-lingual carry-over test: append glossary English terms to Step A/B prompts on the **disagreement slice** only (scratch tier).

```bash
export TRIFECTA_MODEL=qwen2.5-coder:latest

# Re-run LLM on disagreement rows with English reviewer hints
uv run python scripts/batch_english_hint_pilot.py --run-batch

# Or compare existing baseline vs en-hint predictions (no LLM call)
uv run python scripts/batch_english_hint_pilot.py
```

Outputs: `gold_predictions_en_hint.jsonl`, `eval/english_hint_pilot.json` (delta vs Dutch-only baseline on the same `record_id`s).

Batch flag for any JSONL input:

```bash
uv run trifecta-batch --input-path ... --output-path ... --english-hint
```

## LLM model comparison

Side-by-side metrics on the same gold slice (full eval set or disagreement rows).

**Full sweep** (local 8B → local 14B → optional remote), machine-friendly:

```bash
cp model_compare.env.example model_compare.env   # optional: remote API
nohup ./scripts/run_model_compare.sh >> "/Volumes/Extreme SSD/scratch/trifecta/eval/model_compare.log" 2>&1 &
tail -f "/Volumes/Extreme SSD/scratch/trifecta/eval/model_compare.log"
```

Remote options in `model_compare.env`: SURF vLLM, OpenRouter, or any OpenAI-compatible endpoint (`TRIFECTA_REMOTE_BASE_URL`, `TRIFECTA_REMOTE_MODEL`, `TRIFECTA_REMOTE_API_KEY`).

Manual runs:

```bash
# Run and compare two models on all 100 gold eval rows
uv run python scripts/compare_llm_models.py --run-batch --min-rows 100 \
  --models qwen2.5-coder:latest llama3.1:8b

# Remote single model (offloads GPU from your Mac)
export TRIFECTA_API_KEY=sk-or-...
uv run python scripts/compare_llm_models.py --run-batch --min-rows 100 \
  --models qwen/qwen2.5-coder-32b-instruct \
  --base-url https://openrouter.ai/api/v1 \
  --run-label qwen-32b-openrouter \
  --output-path "/Volumes/Extreme SSD/scratch/trifecta/gold_predictions_qwen-32b-openrouter.jsonl"

# Compare existing prediction files (no LLM calls)
uv run python scripts/compare_llm_models.py \
  --predictions qwen=/Volumes/Extreme\ SSD/scratch/trifecta/gold_predictions.jsonl \
              qwen-en=/Volumes/Extreme\ SSD/scratch/trifecta/gold_predictions_en_hint.jsonl

# Disagreement slice only
uv run python scripts/compare_llm_models.py --slice disagreements \
  --predictions qwen=.../gold_predictions.jsonl qwen-en=.../gold_predictions_en_hint.jsonl
```

Outputs: `eval/model_comparison.json` and `eval/model_comparison.md` (ranked by Step B accuracy).

Per-model batch outputs default to `gold_predictions_{model_slug}.jsonl` on the scratch tier.
