# Annotation strategy — rationale and tooling

This document records **why** the gold/eval workflow evolved the way it did (researcher discussion, March–July 2026) and **how** the repo supports it. It complements operational guides: [GOLD_LABELLING.md](GOLD_LABELLING.md), [SNIPPETS.md](SNIPPETS.md), [TRIFECTA.md](TRIFECTA.md).

---

## 1. Problem statement

TRIFECTA annotation asks three things at once:

1. Is the target a **food entity** in context (Step A)?
2. Which **macro-frame** applies (Step B: COOKING, CURE, INGESTION, PRESERVING, NONE)?
3. Which **qualia roles** fill the frame (Step C)?

Early gold work (100 hand-labelled rows + LLM eval) showed:

| Metric (vs qwen2.5-coder:latest, after gold fixes) | Approx. |
|-----------------------------------------------------|---------|
| Step B frame accuracy | ~76% |
| PRESERVING per-frame F1 | 0.0 (1 gold row) |
| Disagreement rows (model ≠ gold) | ~49 unique `record_id`s |

The workflow also felt **circular**: effort clustered on polysemous lemmas (*water*, *boter*, *brood*) and annotator–model disputes, without clearly advancing coverage of food **practices** in historic text.

That is a **design signal**, not a labelling failure.

---

## 2. Why lemma-driven sampling loops

### What we did initially

- Sample gold candidates from **food terms** and **frame verbs** in cort_voc snippets.
- Export disagreements vs LLM into `gold_fixes.csv` for adjudication.
- Treat disputed lemmas as the priority queue for more labels.

### Why that loads work without much gain

| Mechanism | Effect |
|-----------|--------|
| KWIC keyed on **high-frequency or disputed lemmas** | Same words recur; annotators re-argue polysemy |
| Frame labels on **mixed text types** | Recipe practice vs travelogue vs literary mention get one rubric |
| **COOKING vs PRESERVING vs CURE** boundaries | Often semantic or genre-driven, not a crisp “frame” distinction |
| Thin frames in gold (e.g. 1× PRESERVING) | Per-frame F1 is meaningless for rare classes |

**Example — *water*:** In a recipe it may be a food constituent; in trade or travel text it is not; the frame may be NONE or context-dependent. More rows on “water” do not fix that without a **policy** and **text-type stratification**.

### Agreed direction

- Stop letting **disagreement exports** drive the only sampling strategy (use them for **error analysis**, not as the sole gold expansion plan).
- **Cap per lemma** in gold (e.g. max 2 rows per `target_word` unless deliberately studying that lemma).
- Sample by **phenomenon** (preservation scenes, medical recipes) and **text regime**, not by dispute count alone.
- Separate **core gold** (clear cases) from an **edge bank** (ambiguous; do not train headline F1 on it yet).

---

## 3. Layered annotation model

We adopted a **stack** instead of one flat TRIFECTA pass on every snippet:

```text
Layer 0 — text_regime (genre / discourse type)
         RECIPE_PRACTICE | MEDICAL | TRAVEL | LITERARY | ADMIN_TRADE | SCIENTIFIC | UNKNOWN

Layer 1 — Step A (entity + dropout)
         Is this snippet even in scope for food-practice annotation in this regime?

Layer 2 — Step B (macro-frame), regime-conditioned
         e.g. PRESERVING / COOKING mainly in RECIPE_PRACTICE; CURE in MEDICAL; NONE common in LITERARY/TRAVEL

Layer 3 — Step C / qualia (semantics)
         e.g. PR_Technique (salting, smoking) — preservation technique taxonomy
```

**Rationale:** Cooking-related texts produce different frame behaviour than literary or travel writing. Eval and gold should be **reported per regime**, not merged into one F1 that punishes the model for genre mismatch.

### Implemented: `text_regime`

| Piece | Location |
|-------|----------|
| Enum + title/corpus rules | `trifecta_annotation/text_regime.py` |
| Field on `KwicInput` / provenance | `trifecta_annotation/schemas.py` |
| Gold CSV column | `text_regime` in `GOLD_CSV_COLUMNS` |
| Backfill script | `scripts/tag_text_regime.py` |
| Gold UI dropdown | `gold_labeller/templates/label.html` |

```bash
uv run python scripts/tag_text_regime.py \
  --csv-path "/Volumes/Extreme SSD/scratch/trifecta/gold_labelling_all.csv"
```

Rules are **heuristic** (Dutch title patterns). Review and override in the gold UI; re-run with `--overwrite` when rules improve.

---

## 4. Coarse frames first (discussion; not fully implemented)

**Observation:** Step B frames are partly **semantic** (what kind of practice) rather than classic FrameNet alternations. Annotators fatigue on COOKING vs PRESERVING vs CURE when the real issue is “is this a food-practice passage at all?”

**Proposed coarse phase (future schema work):**

```text
FOOD_TRANSFORM  — cook + preserve + generic prep (split later)
MEDICAL_CURE
CONSUMPTION     — ingestion
OUT_OF_SCOPE    — metaphor, trade, non-practice
```

**Rationale:** Match how silver labels and GijsBERT fine-tuning should work — stable coarse labels first, split only when accuracy justifies it. Preservare (below) is already a **FOOD_TRANSFORM / PRESERVING** sub-world.

---

## 5. Preservare piggyback track (planned)

Sibling repo: `recepten-preservare-analysis` — preservation techniques (salting, smoking, drying, pickling, …) on VOC recipes.

| Asset | Role for TRIFECTA |
|-------|-------------------|
| `technique_term_association.csv` | PRESERVING verb seeds (already in `frame_verbs.py`) |
| `Food_terms.csv` | Step A lexicon |
| `ollama_kwic_review.csv` (~248 rows) | Technique-anchored KWIC — **not** merged into TRIFECTA gold yet |
| `pres_features.csv` / `ollama_labels.csv` | Recipe-level weak supervision |

**Rationale:** Preservare is **scene-defined** (preservation practice), not lemma-defined. It avoids the *water* spiral and maps naturally to `RECIPE_PRACTICE` + `PRESERVING` + `PR_*` qualia.

**Status:** Discussed; adapter script (`import_preservare_kwic.py`) not yet built. `PLAN.md` notes legacy `kwic_gold_review` is not TRIFECTA gold — intentional; use a **separate preservation eval slice** first, then bridge.

---

## 6. Gold set evolution (what we actually ran)

### Batch 1–2 (100 rows)

- Food-seeded + verb-seeded candidates → `gold_labelling_all.csv` → `gold.parquet`.
- LLM batch on 100 eval inputs → `gold_predictions.jsonl`.
- Baseline Step B accuracy ~66% before fixes; ~76% after adjudication.

### Disagreement review (`gold_fixes.csv`)

Export:

```bash
uv run python scripts/eval_disagreements.py
```

| File | Edit? |
|------|-------|
| `eval/gold_fixes.csv` | **Yes** — verdict + optional overrides |
| `frame_disagreements.csv` | Skim only |
| `dropout_disagreements.csv` | Skim only |
| `step_a_disagreements.csv` | Skim only |

Apply:

```bash
uv run python scripts/import_gold_fixes.py --import-after
```

**Verdict shorthand** (normalized in `gold_io.normalize_gold_fix_verdict`):

| Type | Meaning |
|------|---------|
| `k` or `keep*` | Keep hand gold |
| `a`, `adopt*`, `pred*` | Adopt model prediction |
| `w`, `wij*`, `custom` | Manual override columns |

**Note:** `adopt_gold` is accepted as alias for `keep_gold` (common typo).

**Important:** Rows with `keep_gold` **remain** in disagreement exports if the model still disagrees — that is expected. Adjudication documents your stance; it does not force the model to agree.

### Batch 3 (verb / frame-stratified, ~25 candidates)

```bash
uv run python scripts/export_gold_candidates.py --source verb --limit 25 --summary
```

Target balance (from `--summary`): COOKING, CURE, INGESTION, PRESERVING (~6 each).

**Workflow:**

1. Export → `gold_labelling.csv` (unlabelled).
2. Label in UI or CSV (`labelled=true`).
3. Merge into master CSV (does **not** replace existing 100 rows):

```bash
uv run python scripts/merge_gold_batch.py
```

4. Import **labelled** rows only:

```bash
uv run python scripts/import_gold_csv.py \
  --input-path "/Volumes/Extreme SSD/scratch/trifecta/gold_labelling_all.csv"
```

`import_gold_csv` on an unlabelled batch alone fails with “No labelled rows” — **by design**.

---

## 7. LLM experiments

### Model comparison (local, machine-friendly)

Script: `scripts/run_model_compare.sh` — one Ollama model at a time, `nice`, `ollama stop` between runs.

Phases: 8B models (llama3.1, mistral, cogito) → local 14B (`qwen2.5:14b-instruct`) → optional remote (env in `model_compare.env.example`).

Reports: `eval/model_comparison.json`, `eval/model_comparison.md`.

Manual compare:

```bash
uv run python scripts/compare_llm_models.py --predictions \
  qwen=/Volumes/Extreme\ SSD/scratch/trifecta/gold_predictions.jsonl \
  ...
```

### English-hint pilot (scratch)

Hypothesis: English glossary terms in prompts help cross-lingual frame labelling.

```bash
uv run python scripts/batch_english_hint_pilot.py --run-batch
```

Uses `trifecta_thesaurus_glossary.csv` hints on disagreement slice only.

### Remote GPU (194.171.4.243)

Attempted via VPN; SSH blocked until GPU server `authorized_keys` contains `~/.ssh/id_gpu_server_ed25519.pub`. Remote batch uses `TRIFECTA_REMOTE_*` in `model_compare.env` (OpenAI-compatible API). **Do not** expose Ollama on public IP — use SSH tunnel.

---

## 8. Recommended priorities (consensus)

| Priority | Action | Why |
|----------|--------|-----|
| 1 | Label batch 3 (`trifecta-gold-ui`; needs `uv sync --extra gold-ui`) | Grows PRESERVING/COOKING gold |
| 2 | Review `text_regime` in UI; fix UNKNOWN rows | Stratify eval and sampling |
| 3 | Skim 11 **frame** disagreements; use `k` / `a` / `wij` in `gold_fixes.csv` | High-value adjudication |
| 4 | Preservare KWIC adapter + `RECIPE_PRACTICE` gold slice | Closed-world preservation |
| 5 | Per-regime eval in `trifecta-eval` (future) | Stop blending travelogue with recipes |
| 6 | Coarse frame schema (future) | Reduce COOKING/PRESERVING fatigue |

**De-prioritise:** Expanding gold only from disagreement queue without regime/lemma caps.

---

## 9. Command reference

| Task | Command |
|------|---------|
| Gold UI | `uv sync --extra gold-ui && uv run trifecta-gold-ui` |
| Export candidates | `uv run python scripts/export_gold_candidates.py --source verb --limit 25` |
| Merge batch into all | `uv run python scripts/merge_gold_batch.py` |
| Tag text regime | `uv run python scripts/tag_text_regime.py --csv-path …/gold_labelling_all.csv` |
| Import gold | `uv run python scripts/import_gold_csv.py --input-path …/gold_labelling_all.csv` |
| Export disagreements | `uv run python scripts/eval_disagreements.py` |
| Apply fixes | `uv run python scripts/import_gold_fixes.py --import-after` |
| Eval | `uv run trifecta-eval --gold-path …/gold.parquet --predictions-path …/gold_predictions.jsonl` |
| Model compare | `./scripts/run_model_compare.sh` (background) |
| English-hint pilot | `uv run python scripts/batch_english_hint_pilot.py --run-batch` |

Scratch tier default root: `/Volumes/Extreme SSD/scratch/trifecta/`.

---

## 10. File map (scratch)

| Path | Role |
|------|------|
| `gold_labelling.csv` | Current candidate batch (UI default) |
| `gold_labelling_all.csv` | Merged hand labels + pending candidates |
| `gold.parquet` / `gold.jsonl` | Imported labelled gold |
| `gold_eval_inputs.jsonl` | KWIC inputs for eval batch |
| `gold_predictions.jsonl` | LLM predictions on eval set |
| `eval/gold_fixes.csv` | Disagreement adjudication |
| `eval/model_comparison.md` | Model shootout report |
| `eval/model_compare.log` | Background compare log |

---

## 11. Related docs

- [GOLD_LABELLING.md](GOLD_LABELLING.md) — column definitions, CSV/UI workflow
- [SNIPPETS.md](SNIPPETS.md) — cort_voc ingest, verb-seeded export
- [PLAN.md](../PLAN.md) — milestones, preservare / DBNL path
- `model_compare.env.example` — remote LLM endpoint template
- `recepten-preservare-analysis/docs/analysis_summary.md` — preservation pipeline (sibling repo)

---

*Last updated: July 2026 — reflects conversation on sampling, regimes, preservare, model compare, and gold_fixes workflow.*
