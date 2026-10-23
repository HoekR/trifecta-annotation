#!/usr/bin/env bash
# Sequential GijsBERT fine-tunes + comparison report.
set -euo pipefail

ROOT="/Volumes/Extreme SSD/scratch/trifecta/gijsbert"
MODELS="$ROOT/models"
REPO="$HOME/develop/trifecta-annotation"
LOG="$MODELS/train_compare.log"

train_running() {
  pgrep -f "${REPO}/.venv/bin/python3.*train_gijsbert" >/dev/null 2>&1
}

download_running() {
  pgrep -f "${REPO}/.venv/bin/python3.*download_hf_models" >/dev/null 2>&1
}

wait_for_jobs() {
  while train_running || download_running; do
    sleep 30
  done
}

cd "$REPO"
mkdir -p "$MODELS"

run_one() {
  local label="$1"
  local model="$2"
  local out="$3"
  echo "=== $label $(date) ===" | tee -a "$LOG"
  uv run python scripts/train_gijsbert.py \
    --model "$model" \
    --output-dir "$out" \
    2>&1 | tee -a "$out.log"
}

wait_for_jobs
run_one "GysBERT-v2" "emanjavacas/GysBERT-v2" "$MODELS/gysbert-v2"
run_one "historic-dbmdz" "dbmdz/bert-base-historic-dutch-cased" "$MODELS/historic-dbmdz"
uv run python scripts/compare_gijsbert_runs.py
echo "=== ALL DONE $(date) ===" | tee -a "$LOG"
