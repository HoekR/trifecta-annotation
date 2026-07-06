#!/usr/bin/env bash
# Full model comparison: local 8B sweep → local 14B quality ceiling → optional remote.
# Machine-friendly: one model at a time, nice priority, unload between Ollama runs.
set -euo pipefail

ROOT="/Users/rikhoekstra/develop/trifecta-annotation"
SCRATCH="/Volumes/Extreme SSD/scratch/trifecta"
LOG="${SCRATCH}/eval/model_compare.log"
ENV_FILE="${ROOT}/model_compare.env"
MIN_ROWS=123

LOCAL_8B_MODELS=(llama3.1:8b mistral:latest cogito:8b)
# Swiss AI Apertus 8B (GGUF Q4_K_M via bartowski on HuggingFace)
APERTUS_MODEL="${APERTUS_MODEL:-hf.co/bartowski/swiss-ai_Apertus-8B-Instruct-2509-GGUF:Q4_K_M}"
LOCAL_QUALITY_MODEL="${LOCAL_QUALITY_MODEL:-qwen2.5:14b-instruct}"

cd "$ROOT"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$LOG"
}

run_local_ollama() {
  local model="$1"
  local label="${2:-}"
  log "Local Ollama batch: $model${label:+ (label=$label)}"
  local extra=()
  if [[ -n "$label" ]]; then
    extra+=(--run-label "$label")
  fi
  nice -n 15 env OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
    uv run python scripts/compare_llm_models.py --run-batch --skip-existing --min-rows "$MIN_ROWS" \
    --models "$model" "${extra[@]}" >> "$LOG" 2>&1
  ollama stop "$model" >/dev/null 2>&1 || true
  sleep 10
}

run_remote() {
  if [[ -z "${TRIFECTA_REMOTE_BASE_URL:-}" || -z "${TRIFECTA_REMOTE_MODEL:-}" ]]; then
    log "Remote skipped — set TRIFECTA_REMOTE_BASE_URL and TRIFECTA_REMOTE_MODEL in model_compare.env"
    return 0
  fi
  local label="${TRIFECTA_REMOTE_LABEL:-remote}"
  local out="${SCRATCH}/gold_predictions_${label}.jsonl"
  if [[ -n "${TRIFECTA_REMOTE_API_KEY:-}" ]]; then
    export TRIFECTA_API_KEY="${TRIFECTA_REMOTE_API_KEY}"
  fi
  log "Remote batch: label=$label model=$TRIFECTA_REMOTE_MODEL url=$TRIFECTA_REMOTE_BASE_URL"
  uv run python scripts/compare_llm_models.py --run-batch --skip-existing --min-rows "$MIN_ROWS" \
    --models "$TRIFECTA_REMOTE_MODEL" \
    --base-url "$TRIFECTA_REMOTE_BASE_URL" \
    --run-label "$label" \
    --output-path "$out" >> "$LOG" 2>&1
}

write_final_report() {
  uv run python scripts/compare_llm_models.py --allow-missing --predictions \
    "qwen=${SCRATCH}/gold_predictions.jsonl" \
    "llama3.1=${SCRATCH}/gold_predictions_llama3.1_8b.jsonl" \
    "mistral=${SCRATCH}/gold_predictions_mistral_latest.jsonl" \
    "cogito=${SCRATCH}/gold_predictions_cogito_8b.jsonl" \
    "qwen14b=${SCRATCH}/gold_predictions_qwen2.5_14b-instruct.jsonl" \
    "apertus_8b=${SCRATCH}/gold_predictions_apertus_8b.jsonl" \
    "${TRIFECTA_REMOTE_LABEL:-remote}=${SCRATCH}/gold_predictions_${TRIFECTA_REMOTE_LABEL:-remote}.jsonl" \
    --report-json "${SCRATCH}/eval/model_comparison.json" \
    --report-md "${SCRATCH}/eval/model_comparison.md" >> "$LOG" 2>&1
}

log "=== Model compare start ==="

log "Phase 1: local 8B models"
for model in "${LOCAL_8B_MODELS[@]}"; do
  run_local_ollama "$model"
done

if ollama show "$APERTUS_MODEL" >/dev/null 2>&1; then
  log "Phase 1b: Apertus 8B ($APERTUS_MODEL)"
  run_local_ollama "$APERTUS_MODEL" "apertus_8b"
else
  log "Phase 1b skipped — Apertus not installed (ollama pull $APERTUS_MODEL)"
fi

log "Phase 2: local quality ceiling ($LOCAL_QUALITY_MODEL)"
if ! ollama show "$LOCAL_QUALITY_MODEL" >/dev/null 2>&1; then
  log "Pulling $LOCAL_QUALITY_MODEL (one-time download)"
  ollama pull "$LOCAL_QUALITY_MODEL" >> "$LOG" 2>&1
fi
run_local_ollama "$LOCAL_QUALITY_MODEL"

log "Phase 3: optional remote"
run_remote

log "Final comparison report"
write_final_report

log "=== Model compare complete ==="
