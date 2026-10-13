.PHONY: help check status screen-off batch-kwic batch-kwic-10k batch-kwic-reranked \
	rerank-kwic step-a-bulk step-a-reranked eval-all eval-gold eval-gold-fresh eval-stepc \
	weekend-refresh weekend-tranche weekend-tranche-medicijn weekend-tranche-inmaken \
	weekend-gijsbert weekend-gijsbert-export weekend-gijsbert-train weekend-step-a \
	ui-stepc ui-gold export-parquet

help:
	@echo "TRIFECTA Annotation Pipeline Commands"
	@echo "======================================="
	@echo "make status            - Check active LLM/Ollama processes and GPU offload"
	@echo "make check             - Validate data manifest and mount paths"
	@echo "make batch-kwic        - Run full KWIC batch with caffeinate (anti-throttle)"
	@echo "make batch-kwic-10k    - Generate 10k KWIC inputs and run caffeinated batch"
	@echo "make rerank-kwic       - E5a: embedding re-rank kwic_inputs → embedding_kwic_reranked"
	@echo "make batch-kwic-reranked - Preferred: re-rank then batch on embedding_kwic_reranked"
	@echo "make step-a-bulk       - Run lightweight Step A entity/metaphor filter in bulk"
	@echo "make step-a-reranked   - Step A on embedding_kwic_reranked pool"
	@echo "make eval-gold         - Rebuild gold_eval_inputs, batch → gold_predictions, trifecta-eval"
	@echo "make eval-gold-fresh   - Same but full re-batch (no --resume, concurrency 4) + eval-stepc"
	@echo "make weekend-refresh   - Parquet + trifecta-eval + step_c_review (no LLM batch)"
	@echo "make weekend-tranche   - Expand kwic (25k) → rerank 500 → batch new ids → parquet"
	@echo "make weekend-tranche-medicijn - kwic medicijn tag → rerank → batch (queue after tranche)"
	@echo "make weekend-tranche-inmaken  - kwic inmaken tag → rerank → batch (PRESERVING-heavy)"
	@echo "make weekend-gijsbert - Export GijsBERT splits from annotations + train (Step B)"
	@echo "make weekend-step-a    - Step A only on kwic_inputs → step_a_kwic.jsonl"
	@echo "make eval-all          - Export parquet analysis table and run trifecta-eval"
	@echo "make eval-stepc        - Export Step C qualia review CSV"
	@echo "make ui-stepc          - Launch Step C review web UI on port 5051"
	@echo "make ui-gold           - Launch Gold review web UI on port 5050"
	@echo "make screen-off        - Immediately blank/sleep displays"

check:
	uv run python -m data_io.check

status:
	@echo "--- Ollama Status ---"
	@ollama ps || true
	@echo "\n--- Batch Process Check ---"
	@ps aux | grep -E 'trifecta-batch|llama-server' | grep -v grep || echo "No active batch running."

screen-off:
	pmset displaysleepnow

# Full caffeinated batch run (prevents idle sleep, disk sleep, and E-core downclocking)
batch-kwic:
	caffeinate -dims uv run trifecta-batch \
		--input-logical kwic_inputs \
		--output-logical trifecta_annotations \
		--concurrency 4 \
		--resume

# Prepare 10k inputs then batch
batch-kwic-10k:
	uv run python scripts/build_kwic_inputs.py --source kwic --limit 10000
	caffeinate -dims uv run trifecta-batch \
		--input-logical kwic_inputs \
		--output-logical trifecta_annotations \
		--concurrency 4 \
		--resume

# E5a: embedding re-rank of KWIC inputs (needs embedding_exemplars + gijsbert extra)
rerank-kwic:
	uv run python scripts/build_embedding_exemplars.py --summary
	caffeinate -dims uv run python scripts/rerank_kwic_embeddings.py \
		--sample-limit 2000 --keep 500 --none-margin 0.05 --seed 0 --summary

# Preferred analysis batch path: re-ranked KWIC → A→B→C
batch-kwic-reranked: rerank-kwic
	caffeinate -dims uv run trifecta-batch \
		--input-logical embedding_kwic_reranked \
		--output-logical trifecta_annotations \
		--concurrency 4 \
		--resume

# Step A pre-filtering pass (fast entity dropout)
step-a-bulk:
	caffeinate -dims uv run python scripts/batch_step_a.py \
		--input-logical kwic_inputs \
		--concurrency 4 \
		--resume

step-a-reranked:
	caffeinate -dims uv run python scripts/batch_step_a.py \
		--input-logical embedding_kwic_reranked \
		--concurrency 4 \
		--resume

# Gold-only re-batch + eval (manifest: gold_eval_inputs → gold_predictions)
eval-gold:
	uv run python scripts/rebuild_gold_eval_inputs.py
	caffeinate -dims uv run trifecta-batch --model qwen2.5-coder:latest \
		--input-logical gold_eval_inputs \
		--output-logical gold_predictions \
		--resume
	uv run trifecta-eval --gold trifecta_gold --predictions gold_predictions

# Full gold re-inference after prompt/few-shot changes (replaces gold_predictions.jsonl)
eval-gold-fresh:
	uv run python scripts/rebuild_gold_eval_inputs.py
	caffeinate -dims uv run trifecta-batch --model qwen2.5-coder:latest \
		--input-logical gold_eval_inputs \
		--output-logical gold_predictions \
		--concurrency 4
	uv run trifecta-eval --gold trifecta_gold --predictions gold_predictions
	$(MAKE) eval-stepc

# Export to parquet and evaluate against gold
eval-all: export-parquet
	uv run trifecta-eval --gold trifecta_gold --predictions gold_predictions

export-parquet:
	uv run python scripts/export_analysis_parquet.py

eval-stepc:
	uv run python scripts/export_step_c_review.py

weekend-refresh:
	bash scripts/run_weekend_batch.sh refresh

weekend-tranche:
	bash scripts/run_weekend_batch.sh tranche

weekend-tranche-medicijn:
	bash scripts/run_weekend_batch.sh tranche-medicijn

weekend-tranche-inmaken:
	bash scripts/run_weekend_batch.sh tranche-inmaken

weekend-step-a:
	bash scripts/run_weekend_batch.sh step-a

weekend-gijsbert-export:
	bash scripts/run_weekend_batch.sh gijsbert-export

weekend-gijsbert-train:
	bash scripts/run_weekend_batch.sh gijsbert-train

weekend-gijsbert:
	bash scripts/run_weekend_batch.sh gijsbert

ui-stepc:
	uv run trifecta-stepc-ui

ui-gold:
	uv run trifecta-gold-ui
