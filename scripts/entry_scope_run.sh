#!/usr/bin/env bash
# Unattended entry-scope production run: harvest -> annotate -> report.
#   tmux new-session -d -s entryscope "caffeinate -is bash scripts/entry_scope_run.sh"
set -u
cd "$(dirname "$0")/.."
export TOKENIZERS_PARALLELISM=false
EXP="/Volumes/Extreme SSD/scratch/trifecta/experiments"
mkdir -p "$EXP"
LOG="$EXP/entry_scope_run.log"; STATUS="$EXP/entry_scope_run.status"
: > "$STATUS"
for phase in harvest annotate report; do
  echo "=== $(date '+%F %T') start $phase" | tee -a "$LOG"
  uv run python scripts/run_entry_scope_harvest.py "$phase" >> "$LOG" 2>&1
  rc=$?
  echo "$(date '+%F %T') $phase exit=$rc" | tee -a "$STATUS" "$LOG"
  [ $rc -ne 0 ] && break
done
mkdir -p docs/evidence/entry_scope
cp "/Volumes/Extreme SSD/scratch/trifecta/entry_scope_report.md" docs/evidence/entry_scope/report.md 2>/dev/null
echo "$(date '+%F %T') done" | tee -a "$STATUS" "$LOG"
