#!/bin/zsh
# Keep checking; start the routed run once the disks holding the models and the output are back (Rik, 21 Nov 2026).
# Only watches the disk: never mounts or repairs it. Log: logs/routed_wait.log
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "${0:A:h}/.."
say_() { echo "$(date '+%a %H:%M') $1"; osascript -e "display notification \"$1\" with title \"Routed run\"" >/dev/null 2>&1; }
# ~/.ollama/models may be a link to an external disk; the catalog raises while the output's disk is missing.
disk_ok() {
  timeout 15 ls "$HOME/.ollama/models/manifests" >/dev/null 2>&1 || return 1
  OUT=$(timeout 30 .venv/bin/python -c "from data_io import resolve; print(resolve('triangulation_b_routed_annotations'))" 2>/dev/null) || return 1
  [[ -f "$OUT" ]] && pmset -g batt | grep -q "AC Power"
}
model_ok() { timeout 180 curl -sf localhost:11434/api/chat -d '{"model":"qwen2.5-coder:latest","stream":false,"options":{"num_predict":1},"messages":[{"role":"user","content":"hi"}]}' >/dev/null 2>&1; }
say_ "waiting for the model and output disks; checking every minute"
n=0
until disk_ok && { curl -sf -m3 localhost:11434/api/version >/dev/null || { open -a Ollama; sleep 20; }; model_ok; }; do
  sleep 60; (( ++n % 60 == 0 )) && say_ "still waiting for the model and output disks ($((n/60)) h)"
done
if pgrep -f "triangulation_sample[.]py annotate" >/dev/null; then say_ "disks back, run already going"; exit 0; fi
before=$(wc -l < "$OUT")
say_ "disks back and model answers: starting the run at $before rows"
nohup caffeinate -is uv run python scripts/triangulation_sample.py annotate --tag routed --skip-errors >> logs/routed_run.log 2>&1 &
sleep 5
nohup uv run python scripts/run_progress.py --inputs triangulation_b_routed_run_kwic_inputs --output triangulation_b_routed_annotations --process "triangulation_sample[.]py annotate" --every 60 --title "Routed run" >> logs/routed_progress.log 2>&1 &
sleep 300
after=$(wc -l < "$OUT")
if pgrep -f "triangulation_sample[.]py annotate" >/dev/null && (( after > before )); then say_ "run is writing: $after rows after 5 min"; else say_ "PROBLEM: run not writing after 5 min ($after rows), check logs/routed_run.log"; fi
