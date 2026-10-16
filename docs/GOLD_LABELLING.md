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
| Step 5 gold lab notebook | **`notebooks/cooking_stepc_gold_lab.ipynb`** — overview table + row editor |
| Web UI for Step C batches | **`trifecta-stepc-ui`** (`gold_labeller/app.py`) — side-by-side browser UI on port 5051 (recommended) |
| Gold UI Step A/B | `trifecta-gold-ui` on port 5050 for general gold spreadsheet |
| `export_clear_frame_examples.py` default `--frames` | `COOKING_CREATION,INGESTION` — use `--frames` to filter by target frame |
| `trifecta-eval` Step C metrics | **Implemented** — see `eval/report.md` § Step C after `trifecta-eval` |

### Step 0 — Export candidate batch

Lemma priors are **on by default** (stderr filter report). Escape only with `--no-lemma-priors` (denylist still applies). While labelling: finish clear food + Step C rows; set `homonym_check` / `dropped` on noise so the next prior rebuild learns. After merge/import, rebuild before the next export:

```bash
uv run python scripts/build_gold_lemma_priors.py --summary
```

**Paths:** use manifest logical names (`--output-logical` / `--csv-logical` / `--batch-logical`). **Never** `$SCRATCH/…` — if `SCRATCH` is unset that becomes `/eval/…` and is refused.

For `PRESERVING`:
```bash
uv run python scripts/export_preservare_gold_candidates.py --summary --pool-summary --limit 20
# → resolve("preservare_gold_candidates")
```

For `CURE` / `INGESTION` (writes `clear_frame_examples` by default):
```bash
uv run python scripts/export_clear_frame_examples.py --frames CURE --limit 30 --summary
# or: --frames CURE,INGESTION
```

CURE discovery uses guideline cure verbs **and** indication constructions
(`goed voor`, `behoort voor`, `krachtig tegen`, …). `gebruik … voor/tegen` is
included only when a nearby therapeutic cue is present (e.g. hoest, koorts);
prep-only “gebruik boter voor het bakken” is excluded.

### Step 1 — Open the web UI (recommended) or notebook

**Web UI (Fastest):**
```bash
uv run trifecta-stepc-ui
# defaults to --csv-logical clear_frame_examples
# PRESERVING: uv run trifecta-stepc-ui --csv-logical preservare_gold_candidates
# Open http://127.0.0.1:5051 in browser
```

**Notebook Lab:**
```bash
uv run python scripts/generate_notebooks.py --name cooking_stepc_gold_lab
# Open notebooks/cooking_stepc_gold_lab.ipynb in Jupyter / VS Code
```

### Step 2 — Save, merge, import

```bash
uv run python scripts/merge_gold_batch.py \
  --batch-logical clear_frame_examples \
  --import-after
# PRESERVING: --batch-logical preservare_gold_candidates
```

Only rows with `labelled=true` import. Step C columns are read from CSV if present.

### Step 3 — What comes after (engineering / not manual)

1. Rebuild eval inputs, re-batch gold, eval (manifest logical names — no `$SCRATCH`):
```bash
make eval-gold
# same as:
# uv run python scripts/rebuild_gold_eval_inputs.py
# caffeinate -dims uv run trifecta-batch --model qwen2.5-coder:latest \
#   --input-logical gold_eval_inputs --output-logical gold_predictions --resume
# uv run trifecta-eval --gold trifecta_gold --predictions gold_predictions
```

2. Step C metrics also via review export (exact + soft in `eval/report.md`):
```bash
make eval-stepc
# or: uv run python scripts/export_step_c_review.py
```

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

PRESERVING few-shots (2026-09-25): reviewed against soft Step C (micro 0.31, n=27). Asset `step_c_preserving_fewshots.json` — droogen plus rooken, zouten, inleggen; patient is the preserved food, not an added spice. Re-batch once with `make eval-gold` before judging whether the soft score is worth keeping. Fourteen of 27 misses are Step B (COOKING/NONE), which these few-shots do not change.

**Step C span-extraction prototype (2026-10-13, ruled out):** Tried fine-tuning GloBERTise as a joint BERT-QA span extractor for all 12 Step C qualia fields across all 4 frames (one shared encoder, not split per frame — `trifecta_annotation/stepc_span_export.py` / `stepc_span_train.py`, `scripts/export_stepc_span.py` / `train_stepc_span.py`). Gold-only training (no trustworthy silver exists for Step C). Dev "all fields" exact match looked good (0.590) but that's inflated by trivial no-answer predictions on fields that are mostly/entirely empty in gold; rescored on positive-span examples only, exact match was **0.045** — essentially no real extraction. Root cause: only 160 real-span training examples total across all 12 fields (~13/field). **Do not revisit this approach without substantially more grounded gold** (or switch to deterministic extraction from indication constructions, per `project_step_c_grounding_prototype` memory). Always score positive-span and true-negative-empty subsets separately for any future Step C model eval — the training/eval code already does this (`stepc_span_train.py::_evaluate_predictions`); a blended metric alone is misleading here.

**Step C span-extraction, continued (2026-10-14):** Root cause found and partially fixed. Merging the English IAA-agreed batch (829 rows) raised grounded positive spans 160→437, but a blended mBERT/XLM-R positive-EM of ~0.36 was a dev-composition illusion — dev was 70% English by then; Dutch-only was still 0.05–0.08, unchanged. Real cause (tested, not assumed): Dutch `context_text` was passage-length (median 552 words, max 7,317) because `scripts/build_kwic_inputs.py --source long` (the path that built the Dutch gold pipeline) never applied the target-centered `context_radius` clip that `--source kwic` already defaults to — confirmed independently by the genuine Dutch INCEpTION export (same texts, different pipeline) producing naturally short context (median 61 words). Fixed by clipping `context_text` to ±180 chars around `target_word` inside `stepc_span_export.py` (`DEFAULT_CONTEXT_RADIUS`, reusing `local_context_window`) — verified this isn't cheating: gold answers sit within ±1 sentence of the target word 79.5% of the time, and the clip rule is identical at train and inference time. Result: Dutch positive EM 0.079→0.258 (soft/containment match, also added this session mirroring `soft_qualia_match`: 0.452). Clipping also incidentally dropped some pre-existing wrong-span contamination (naive `find_span()` first-match grabbing unrelated dictionary entries in long concatenated documents).

Also added 394 Dutch INCEpTION inter-annotator-agreed rows (`inception_nl_v2_iaa_agreed_gold.csv`, 100% literal-span-groundable) — used narrowly (agreed + positive-values-only, not as a general Dutch gold-growth strategy; see `project_frame_overlap_cooking_creation` / `project_frame_split_options` memory for why INCEpTION-sourced Dutch data is a curated, easier, positive-biased slice). Net effect on the hard `cort_voc_db` corpus after retraining: flat-to-negative (0.179 EM / 0.333 soft for mBERT), confounded with dev becoming more rigorously hard-only at the same time (legacy INCEpTION rows correctly excluded from dev for the first time). Four-way encoder comparison (mBERT, XLM-R, GloBERTise, GysBERT-v2) on identical clipped+merged data found no confident winner (0.10–0.23 positive EM, noise-level differences on a 101-row eval) — **`CURE_Affliction` scored 0.0 on every single model**, the one fully model-independent finding. All four are standard BERT-family encoders capped at 512 tokens; this ceiling, not model choice, is why the clip was necessary, and a genuinely longer-context architecture (none exists pretrained for Dutch) would be needed to go further. **Bottom line: Dutch Step C span extraction is still not production-viable** — real progress was diagnostic (pipeline bug, contamination, metric choice, annotation-scheme effects), not a working extractor.

**Step C embedding-exemplar-retrieval (2026-10-15, adopted as leading approach):** Replaced fine-tuning with zero-training retrieval — score candidate spans inside the already-clipped `context_text` against embeddings of every other gold answer span for that field (`emanjavacas/gysbert` mean-pooled, reusing the KWIC embedding pilot's embedder), take the nearest match. `trifecta_annotation/stepc_embedding_retrieval.py` / `scripts/eval_stepc_embedding_retrieval.py`. Leave-one-out over the full positive pool (n=518, junk-filtered — see below): **EM 0.612, F1 0.621, soft 0.681** — beats the four-way fine-tuned comparison's 0.10–0.23 EM range on the same clipped+merged data, with no training step. Diagnostic: oracle coverage (is the right answer *reachable* among candidates at all) is ~1.0 for 10/12 fields after two fixes — punctuation-safe tokenization (a naive `\S+` split previously attached trailing periods, e.g. "Stoven." never matched gold "Stoven") and char-level sub-word candidates for Dutch compounds ("braden" inside "gebraden"). So the remaining gap is a **ranking** problem, not a candidate-generation or gold-volume ceiling, unlike the fine-tuned prototype above.

Diagnosing the worst misses (same method that found the §9b contamination issues — print gold vs. top prediction and where the gold candidate actually ranked) surfaced two more issues, both confirmed empirically before fixing: (1) 10/52 `CURE_Affliction` and 1/41 `PR_Medium` gold "answers" are bare English stopwords ("from", "for", "acidity") from the `english_iaa` merge batch — a data bug in that source (see `docs/DECISIONS.md`), excluded from the pool, not fixed at the source this round; (2) the sub-word candidates let short, generic exemplars ("zwaren", "maag", "jagt") spuriously match unrelated garbage fragments at near-1.0 cosine similarity — a known mean-pooled-BERT degeneracy for short strings. A hard ban on sub-word candidates fixed this but regressed the largest field (`INGESTION_Food_Patient`, 0.700→0.667 EM); a flat 0.05 score penalty on sub-word candidates (A/B-tested 0.0–0.12) fixed it without that regression. Tried and **rejected**: checking candidates against the GysBERT tokenizer's own vocabulary as a free "is this a real word" filter — WordPiece vocab entries are chosen by subword frequency, not wordhood, so real words like "braden"/"zwelling" split into multiple pieces while garbage fragments like "wend"/"brui" are each a single vocab entry (the opposite of a useful signal); no Dutch wordlist is a dependency of this project. `INGESTION_Context` (n=9) and `INGESTION_Manner` (n=6) still score 0.000 EM — too few examples to root-cause confidently this round.

**Step C grounding / production integration (2026-10-16, no production change):** Tried combining §9c retrieval with the production LLM four ways, re-scoring the existing `gold_predictions.jsonl` (no new LLM calls). **Grounding** (anchor retrieval to the LLM's own drafted answer, replace only if a better literal span exists nearby) was a clean, confirmed negative at every threshold tested (0.75–0.95) on the full gold set — every metric got worse wherever it replaced anything, no field showed even a directional win; it only matched baseline once the threshold was strict enough that nothing got replaced. On the much larger pooled comparison (502 rows / 180 records, proper leave-one-out — not a small held-out split), **full replacement** (pure retrieval, own presence threshold) showed a confirmed recall advantage over the LLM (95% CI [0.472, 0.663] vs [0.220, 0.366], non-overlapping) and the best precision-unconfirmed-but-not-worse F1 (0.328 vs 0.277). **Hybrid v2** (trust the LLM's presence call, swap in retrieval's independent value pick) looked like a real win on an earlier 39-row sample (F1 0.305 vs 0.276) but washed out to statistically identical to the LLM alone at full scale (0.283 vs 0.277) — a direct demonstration that small-sample comparisons during this kind of work are not trustworthy on their own, and per-frame it's confirmed *worse* than the LLM on `PRESERVING` specifically (blind override breaks already-correct short answers via the same degeneracy as above). **Frame-selective** (LLM for CURE, retrieval elsewhere) scored best overall (F1 0.372) but the CURE-specific claim behind it isn't statistically confirmed — McNemar's exact test on the paired CURE-only data gives p=0.12 (11 LLM-only-correct vs 4 retrieval-only-correct of 75 rows). Process note: hybrid grounding was recommended over a frame/field-selective split when scoping this work, on the theory that it was the more surgical fix — that call was wrong in hindsight, since grounding is the clean negative and frame-selective is the best (if unproven) performer. **No production change**; `plans/steps/STEPC_GROUNDING.md` closed per its own stop-and-document gate. Side finding, not yet actionable (see `project_discourse_structure_frame_evocation` memory): Dutch `CURE_Affliction` literal spans sit before `target_word` 71% of the time (n=28) vs after 70% of the time for English sources (n=10) — consistent with Dutch remedy chapters stating the affliction once as a header rather than re-evoking it per sentence, but on far too few examples to act on without new, deliberately-sampled KWIC.

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

## Verb Phase 2a review

The verb Phase 2a worksheet is managed by the `verb_phase2a_gold` dataset and currently resolves to:

```text
/Volumes/Extreme SSD/scratch/trifecta/verb_phase2a/gold.csv
```

Open the browser editor from the repository root:

```bash
uv sync --extra gold-ui
uv run trifecta-verb-phase2a-ui --port 5051
```

Then open http://127.0.0.1:5051. The `source_step_b` and `frame_verb` columns are prior model/lexicon evidence, not gold. For each row, review the frame and verb, fill only the Step C roles supported by the snippet, add an `uncertainty_note` when needed, and mark the row reviewed. Human decisions are stored separately in `reviewed_frame`, `reviewed_lexical_unit`, and `reviewed`.

The worksheet is a 40-row research-track batch. In particular, check generic or ambiguous verb hits such as measurement words (`pinten`, `ponden`) and broad instructions (`nemen`) rather than accepting the source hint automatically.

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
make eval-gold
# or logical names:
# uv run python scripts/rebuild_gold_eval_inputs.py
# uv run trifecta-batch --input-logical gold_eval_inputs --output-logical gold_predictions --resume
# uv run trifecta-eval --gold trifecta_gold --predictions gold_predictions
```

Report: read **By text_regime** in `eval/report.md` first; pooled Step B is secondary.

## Review disagreements (CSV — edit this, not Excel)

See [ANNOTATION_STRATEGY.md](ANNOTATION_STRATEGY.md) §6 for rationale (why not to let disagreements alone drive all sampling).

**Notebook (pandas):** Step B boundary pairs + gold `notes` for paper quotes:

```bash
uv run python scripts/generate_notebooks.py --name frame_disagreement_review
# open notebooks/frame_disagreement_review.ipynb
```

Filters **COOKING↔CURE**, **CURE↔INGESTION**, service/use-verb heuristics; does not replace labelling unless §2.1 rules change.

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
