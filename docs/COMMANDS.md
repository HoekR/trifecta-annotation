# TRIFECTA Annotation Pipeline Command Playbook & Operational Wisdom

Quick reference for common execution commands, overnight runs, evaluation tasks, and system optimization.

---

## 1. Overnight & Batch Execution (Preventing Throttling)

### Running Overnight Batches with `caffeinate`
To prevent macOS from throttling background processes to Efficiency cores, spinning down external SSDs, or sleeping the system:

```bash
# Flags:
# -d : prevent display idle sleep
# -i : prevent system idle sleep
# -m : prevent disk idle sleep
# -s : prevent system sleep on AC power
caffeinate -dims uv run trifecta-batch \
  --input-logical kwic_inputs \
  --output-logical trifecta_annotations \
  --concurrency 4 \
  --resume
```

### Turning off Display Immediately While Job Runs
```bash
# Sleep displays immediately without sleeping the Mac:
pmset displaysleepnow

# Keyboard shortcut: Control + Command + Q (lock), then Escape (screen off).
```

---

## 2. Corpus Preparation & KWIC Extraction

```bash
# Check dataset paths and external mount availability
uv run python -m data_io.check

# Ingest snippets from source into scratch
uv run python scripts/ingest_food_snippets.py

# Build KWIC inputs (10k balanced tranche)
uv run python scripts/build_kwic_inputs.py --source kwic --limit 10000

# Build full KWIC inputs without limits (~107k candidate rows)
uv run python scripts/build_kwic_inputs.py --source kwic

# Build KWIC inputs for specific sub-batches
uv run python scripts/build_kwic_inputs.py --source kwic --kwic-batch "recept,inmaken,medicijn"
```

### Preferred: embedding re-rank before batch (E5a, adopted 2026-09-16)

Keeps KWIC as the source pool; filters with GysBERT embeddings + NONE margin + frame quotas. Pilot evidence: Step A FOOD ~86% on re-ranked vs ~69% on raw KWIC (`n=100`). Hybrid *discovery* deferred until LU anchors are hardened.

Requires: `uv sync --extra gijsbert`, scratch HF hub, and `kwic_inputs` already built.

```bash
# Exemplars from gold (once / after gold changes)
uv run python scripts/build_embedding_exemplars.py --summary

# Re-rank KWIC → embedding_kwic_reranked
uv run python scripts/rerank_kwic_embeddings.py \
  --sample-limit 2000 --keep 500 --none-margin 0.05 --seed 0 --summary

# Or Makefile
make rerank-kwic
make batch-kwic-reranked   # re-rank then trifecta-batch on embedding_kwic_reranked
make step-a-reranked       # Step A only on re-ranked pool
```

Guide: [plans/steps/EMBEDDING_CANDIDATES.md](../plans/steps/EMBEDDING_CANDIDATES.md). Spot-check CSV (optional): `scratch/trifecta/embedding/e5_spotcheck.csv`.

---

## 3. Evaluation, Analysis & Parquet Export

Paths live in `data_manifest.toml` (`gold_eval_inputs`, `gold_predictions`, `trifecta_gold`) — no `$SCRATCH`.

```bash
# Gold-only re-batch after prompt/few-shot changes (rebuild → batch → eval)
make eval-gold

# Or step by step (logical names only):
uv run python scripts/rebuild_gold_eval_inputs.py
caffeinate -dims uv run trifecta-batch --model qwen2.5-coder:latest \
  --input-logical gold_eval_inputs \
  --output-logical gold_predictions \
  --resume
uv run trifecta-eval --gold trifecta_gold --predictions gold_predictions

# Export JSONL batch to DuckDB/parquet analysis table
uv run python scripts/export_analysis_parquet.py

# Eval only (expects gold_predictions already written)
make eval-all
# same as: uv run trifecta-eval --gold trifecta_gold --predictions gold_predictions

# Export Step C qualia review CSV
uv run python scripts/export_step_c_review.py
# or: make eval-stepc
```

---

## 4. Labelling UIs & Review

```bash
# Step C browser labelling UI (port 5051) — defaults to clear_frame_examples
uv run trifecta-stepc-ui
# PRESERVING batch: uv run trifecta-stepc-ui --csv-logical preservare_gold_candidates

# Primary gold review UI (port 5050)
uv run trifecta-gold-ui
```

Clear-frame / preservare exports write via `--output-logical` (defaults in manifest). Never `$SCRATCH/…`.
---

## 5. Documentatie \& PDF Generatie

Voor het converteren van Markdown rapporten of bevindingen naar nette PDF's met Pandoc en `pdflatex`:

```bash
# Markdown direct converteren naar PDF met marges
pandoc docs/uw_bestand.md -o docs/uw_bestand.pdf --pdf-engine=pdflatex -V geometry:margin=2.5cm

# Tussentijdse bevindingen PDF compileren
pandoc docs/tussentijdse_bevindingen_kwic_batch.md -o docs/tussentijdse_bevindingen_kwic_batch.pdf --pdf-engine=pdflatex -V geometry:margin=2.5cm

# Of via LaTeX bronbestand
pdflatex -output-directory docs docs/tussentijdse_bevindingen_kwic_batch.tex
```

---

## 6. Model Management & GijsBERT

```bash
# Check Ollama status and GPU offload
ollama ps

# Export data for GijsBERT training
uv run python scripts/export_gijsbert.py

# Train GijsBERT frame classifier
uv run python scripts/train_gijsbert.py
```

---

## Operational Wisdom & Lessons Learned

1. **macOS Energy Management on Apple Silicon:**
   - When screens go blank or system goes idle without power assertions, macOS lowers process QoS and moves threads from Performance cores to Efficiency cores.
   - Always run multi-hour batch runs wrapped in `caffeinate -dims ...`.
2. **Batching Strategy for Large Corpora:**
   - **E5a embedding re-rank (preferred KWIC path):** `make rerank-kwic` / `make batch-kwic-reranked` before heavy A→B→C — cuts Step A waste vs raw KWIC.
   - **Step A pre-filtering:** Run lightweight Step A across the corpus first to discard non-food/metaphors (~20–40% early exit) before triggering heavier Step B & C calls.
   - **GijsBERT pre-filter:** Use fine-tuned GijsBERT locally for high-throughput NONE filtering before calling Ollama (still deferred for Step B replacement).
3. **Data Integrity & Paths:**
   - Never use ad-hoc hardcoded paths; always use `data_io.resolve(...)` backed by `data_manifest.toml`.
