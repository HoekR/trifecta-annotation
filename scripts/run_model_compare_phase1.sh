#!/usr/bin/env bash
# Phase 1: Dutch-only model comparison, one model at a time (machine-friendly).
set -euo pipefail

ROOT="/Users/rikhoekstra/develop/trifecta-annotation"
SCRATCH="/Volumes/Extreme SSD/scratch/trifecta"
LOG="${SCRATCH}/eval/model_compare_phase1.log"
MODELS=(llama3.1:8b mistral:latest cogito:8b)

cd "$ROOT"

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$LOG"
}

run_one_model() {
  local model="$1"
  local out="${SCRATCH}/gold_predictions_$(echo "$model" | sed 's/[^a-zA-Z0-9._-]/_/g').jsonl"
  if [[ -f "$out" ]] && [[ $(wc -l < "$out" | tr -d ' ') -ge 100 ]]; then
    log "Skip complete: $model ($out)"
    return 0
  fi
  log "Batch start: $model"
  nice -n 15 env OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
    uv run python scripts/compare_llm_models.py --run-batch --skip-existing \
    --models "$model" >> "$LOG" 2>&1
  log "Batch done: $model"
  ollama stop "$model" >/dev/null 2>&1 || true
  sleep 10
}

log "=== Phase 1 start (gentle) ==="
for model in "${MODELS[@]}"; do
  run_one_model "$model"
done

log "=== Final comparison report ==="
uv run python scripts/compare_llm_models.py \
  --predictions \
    qwen="${SCRATCH}/gold_predictions.jsonl" \
    llama3.1="${SCRATCH}/gold_predictions_llama3.1_8b.jsonl" \
    mistral="${SCRATCH}/gold_predictions_mistral_latest.jsonl" \
    cogito="${SCRATCH}/gold_predictions_cogito_8b.jsonl" \
  >> "$LOG" 2>&1

log "=== Phase 1 complete ==="
