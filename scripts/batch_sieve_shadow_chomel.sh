#!/usr/bin/env bash
# Unattended: (1) Step A sieve shadow run on held-out rows, (2) Chomel entry-scope uncapped.
#   tmux new-session -d -s batch2 "caffeinate -is bash scripts/batch_sieve_shadow_chomel.sh"
set -u
cd "$(dirname "$0")/.."
export TOKENIZERS_PARALLELISM=false
EXP="/Volumes/Extreme SSD/scratch/trifecta/experiments"
LOG="$EXP/batch_sieve_shadow_chomel.log"; STATUS="$EXP/batch_sieve_shadow_chomel.status"
: > "$STATUS"
stage() {
  local name="$1"; shift
  echo "=== $(date '+%F %T') start $name" | tee -a "$LOG"
  "$@" >> "$LOG" 2>&1
  local rc=$?
  echo "$(date '+%F %T') $name exit=$rc" | tee -a "$STATUS" "$LOG"
}
stage sieve_shadow uv run python scripts/shadow_step_a_sieve.py
stage chomel_full uv run python scripts/run_entry_scope_harvest.py all \
  --only chom003huis01_01.xml --cap 0 --inputs entry_scope_kwic_inputs_chomel_full
mkdir -p docs/evidence/sieve_shadow docs/evidence/entry_scope
cp "$EXP/sieve_shadow/report.md" docs/evidence/sieve_shadow/ 2>/dev/null
cp "/Volumes/Extreme SSD/scratch/trifecta/entry_scope_report_chomel_full.md" docs/evidence/entry_scope/report_chomel_full.md 2>/dev/null
echo "$(date '+%F %T') done" | tee -a "$STATUS" "$LOG"
