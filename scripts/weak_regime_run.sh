#!/usr/bin/env bash
# Unattended weak-regime verb_food annotation (harvest already done): annotate -> report -> overview.
# Resumable: rerunning skips rows already in weak_regime_verb_annotations.
#   tmux new-session -d -s weakregime "caffeinate -is bash scripts/weak_regime_run.sh"
set -u
cd "$(dirname "$0")/.."
export TOKENIZERS_PARALLELISM=false
EXP="/Volumes/Extreme SSD/scratch/trifecta/experiments"
mkdir -p "$EXP"
LOG="$EXP/weak_regime_run.log"; STATUS="$EXP/weak_regime_run.status"
: > "$STATUS"
for phase in annotate report; do
  echo "=== $(date '+%F %T') start $phase" | tee -a "$LOG"
  uv run python scripts/run_weak_regime_harvest.py "$phase" >> "$LOG" 2>&1
  rc=$?
  echo "$(date '+%F %T') $phase exit=$rc" | tee -a "$STATUS" "$LOG"
  [ $rc -ne 0 ] && break
done
uv run python scripts/build_results_overview.py >> "$LOG" 2>&1
mkdir -p docs/evidence/weak_regime
cp "/Volumes/Extreme SSD/scratch/trifecta/weak_regime_verb_report.md" docs/evidence/weak_regime/report.md 2>/dev/null
cp "/Volumes/Extreme SSD/scratch/trifecta/weak_regime_verb_counts.md" docs/evidence/weak_regime/counts.md 2>/dev/null
echo "$(date '+%F %T') done" | tee -a "$STATUS" "$LOG"
