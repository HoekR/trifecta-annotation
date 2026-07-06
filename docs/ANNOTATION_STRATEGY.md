# Annotation strategy — canonical guide

**This document is the single source of truth** for gold design, sampling policy, evaluation reporting, and track boundaries (Dutch hand gold, INCEpTION silver, preservare). Operational column/UI detail: [GOLD_LABELLING.md](GOLD_LABELLING.md). Snippet ingest: [SNIPPETS.md](SNIPPETS.md). Pipeline engineering: [PLAN.md](../PLAN.md).

---

## 1. Problem statement

TRIFECTA annotation asks three things at once:

1. Is the target a **food entity** in context (Step A)?
2. Which **macro-frame** applies (Step B: COOKING, CURE, INGESTION, PRESERVING, NONE)?
3. Which **qualia roles** fill the frame (Step C)?

Early gold work showed a **design signal**, not a labelling failure:

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
         PRESERVING/COOKING mainly in RECIPE_PRACTICE; CURE in MEDICAL; NONE common in LITERARY/TRAVEL

Layer 3 — Step C / qualia
         PR_Technique, CURE_Affliction, etc. — thin in gold until core Step B is stratified
```

**Evaluation:** report Step B (and later Step C) **per `text_regime`**, with pooled metrics secondary. Implemented in `trifecta-eval` → `by_text_regime` in `eval/report.md`.

### Sampling rules

| Rule | Rationale |
|------|-----------|
| **Cap per lemma** (max 2 `target_word` per batch unless deliberate) | Stops *water*-style spirals |
| **Sample by regime × phenomenon** | Grow PRESERVING, medical cure on purpose |
| **No new core gold with `UNKNOWN` regime** | Layer 0 must be set before merge |
| **Disagreement CSV for adjudication only** | `keep_gold` / `adopt_pred` / `custom` — not auto-relabel |

---

## 3. Three annotation tracks

| Track | Files | Role |
|-------|-------|------|
| **A — Dutch hand gold** | `gold_labelling_all.csv`, `gold.parquet` | Eval reference; regime-stratified growth |
| **B — INCEpTION silver** | `inception_silver_labelling.csv`, `inception_annotations.jsonl` | Snippet-line view over cort_voc; **not** merged into hand gold by default |
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

## 5. Gold history (reference)

| Phase | What |
|-------|------|
| Batch 1–2 | ~100 food/verb-seeded rows → baseline ~66% Step B |
| Fixes | 49 adjudicated rows → ~76% on 100-row slice |
| July 2026 | 123 rows after fixes; pooled **~74%**; regime backfill in progress |
| Next | Regime-stratified +50 → target ~175 core rows with known regimes |

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

## 7. Future work (not blocking current gold)

| Item | Notes |
|------|-------|
| **Coarse frames** | FOOD_TRANSFORM / MEDICAL_CURE / CONSUMPTION / OUT_OF_SCOPE — adopt if COOKING/PRESERVING fatigue persists after regime stratification |
| **Preservare adapter** | `import_preservare_kwic.py` — separate eval slice |
| **Step C in gold** | After Step B stable per regime |
| **Per-regime GijsBERT** | After silver + gold aligned |

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

Scratch root: `/Volumes/Extreme SSD/scratch/trifecta/`.

---

## 9. Scratch file map

| Path | Track |
|------|-------|
| `gold_labelling_all.csv` / `gold.parquet` | Hand gold (A) |
| `gold_labelling_regime_batch.csv` | Next label queue |
| `gold_eval_inputs.jsonl` / `gold_predictions.jsonl` | Eval batch |
| `eval/report.md` / `eval/metrics.json` | Metrics (**per-regime primary**) |
| `eval/gold_fixes.csv` | Adjudication queue |
| `inception_silver_labelling.csv` | INCEpTION silver (B) |
| `eval/regime_review_unknown.csv` | Layer-0 review export |
| `eval/corpus_texts_overview.csv` | Source works catalogue (titles, regimes, counts) |

---

## 10. Related docs

| Doc | Use for |
|-----|---------|
| [GOLD_LABELLING.md](GOLD_LABELLING.md) | CSV columns, UI fields |
| [SNIPPETS.md](SNIPPETS.md) | cort_voc ingest, kwic build |
| [RESEARCH_STRATEGY_SUMMARY.md](RESEARCH_STRATEGY_SUMMARY.md) | English track coordination only |
| [PLAN.md](../PLAN.md) | Pipeline code, schemas, HPC — not gold policy |
| [LABEL_MAPPING_EN_NL.md](LABEL_MAPPING_EN_NL.md) | WebAnno ↔ JSON |

---

*Last updated: July 2026 — canonical guide; regime-first gold, per-regime eval, three-track model.*
