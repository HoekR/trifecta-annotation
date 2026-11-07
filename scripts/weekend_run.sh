#!/usr/bin/env bash
# Unattended weekend run: selection-mode experiment v2 (five modes, ten works).
# Each stage runs even if the previous one failed; exit codes go to STATUS.
# Start detached so it survives closing the terminal / Claude session:
#   tmux new-session -d -s weekend "caffeinate -is bash scripts/weekend_run.sh"
set -u
cd "$(dirname "$0")/.."
export TOKENIZERS_PARALLELISM=false

EXP="/Volumes/Extreme SSD/scratch/trifecta/experiments"
mkdir -p "$EXP"
LOG="$EXP/weekend_run.log"
STATUS="$EXP/weekend_run.status"
: > "$STATUS"

stage() {
  local name="$1"; shift
  echo "=== $(date '+%F %T') start $name" | tee -a "$LOG"
  "$@" >> "$LOG" 2>&1
  local rc=$?
  echo "$(date '+%F %T') $name exit=$rc" | tee -a "$STATUS" "$LOG"
}

stage selection_modes_v2 uv run python scripts/experiment_selection_modes.py all

# Small evidence summaries go into the repo (uncommitted) so conclusions don't
# depend on the external drive being mounted.
mkdir -p docs/evidence/selection_modes_v1 docs/evidence/selection_modes_v2 docs/evidence/step_a_keepdrop_threshold
cp "$EXP/selection_modes/report.md" docs/evidence/selection_modes_v1/ 2>/dev/null
cp "$EXP/selection_modes_v2/report.md" docs/evidence/selection_modes_v2/ 2>/dev/null
cp "/Volumes/Extreme SSD/scratch/trifecta/step_a_keepdrop/models/globertise-keepdrop/threshold_sweep.json" \
   docs/evidence/step_a_keepdrop_threshold/ 2>/dev/null
echo "$(date '+%F %T') done" | tee -a "$STATUS" "$LOG"
