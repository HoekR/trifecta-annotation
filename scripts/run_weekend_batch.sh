#!/usr/bin/env bash
# Automated weekend chains (no manual gold labelling).
# Usage:
#   ./scripts/run_weekend_batch.sh refresh          # parquet + eval exports only
#   ./scripts/run_weekend_batch.sh tranche          # expand kwic → rerank → batch → parquet
#   ./scripts/run_weekend_batch.sh tranche-medicijn # kwic medicijn tag → rerank → batch (run after tranche)
#   ./scripts/run_weekend_batch.sh gijsbert-export  # silver+gold → train/dev JSONL (after LLM tranches)
#   ./scripts/run_weekend_batch.sh gijsbert-train   # fine-tune Step B classifier (uv --extra gijsbert)
#   ./scripts/run_weekend_batch.sh gijsbert         # export + train + compare report
#   ./scripts/run_weekend_batch.sh step-a           # Step A only on current kwic_inputs
#
# Do not run two trifecta-batch jobs in parallel on one Mac/Ollama — queue sequentially.
set -euo pipefail
set -o pipefail
cd "$(dirname "$0")/.."

CHECK=(uv run python scripts/weekend_batch_checks.py)

run_checked() {
  echo "+ $*" >&2
  "$@"
}

manifest_check() {
  if ! uv run python -m data_io.check; then
    echo "Note: manifest check reported MISSING datasets (often optional); continuing." >&2
  fi
}

wait_for_trifecta_batch_idle() {
  while pgrep -f "[/]trifecta-batch" >/dev/null 2>&1; do
    echo "Waiting for trifecta-batch to finish..." >&2
    sleep 15
  done
}

count_rerank_new() {
  "${CHECK[@]}" rerank-new
}

run_rerank_batch_parquet() {
  local seed="${1:-1}"
  wait_for_trifecta_batch_idle
  run_checked uv run python scripts/build_embedding_exemplars.py --summary
  run_checked caffeinate -dims uv run python scripts/rerank_kwic_embeddings.py \
    --sample-limit 2000 --keep 500 --none-margin 0.05 --seed "${seed}" --summary
  read -r _rer _new <<< "$(count_rerank_new)"
  if [[ "${_new:-0}" -eq 0 ]]; then
    echo "Abort: 0 reranked rows are new vs trifecta_annotations (${_rer} reranked)." >&2
    return 1
  fi
  echo "Rerank: ${_new} new ids to annotate (of ${_rer})"
  local ann_before
  ann_before="$("${CHECK[@]}" annotation-rows)"
  local batch_log
  batch_log="$(mktemp -t trifecta-batch-log.XXXXXX)"
  caffeinate -dims uv run trifecta-batch \
    --input-logical embedding_kwic_reranked \
    --output-logical trifecta_annotations \
    --concurrency 4 --resume 2>&1 | tee "${batch_log}"
  batch_ec=${PIPESTATUS[0]}
  rm -f "${batch_log}"
  if [[ "${batch_ec}" -ne 0 ]]; then
    echo "trifecta-batch failed (exit ${batch_ec})." >&2
    return 1
  fi
  run_checked "${CHECK[@]}" assert-annotation-growth --before "${ann_before}" --min-delta "${_new}"
  run_checked uv run python scripts/export_analysis_parquet.py \
    --input-logical trifecta_annotations \
    --require-step-c --exclude-dropped
  analysis_path="$(uv run python -c "from data_io import resolve; print(resolve('trifecta_analysis'))")"
  run_checked "${CHECK[@]}" assert-file "${analysis_path}" --min-bytes 1000
}

MODE="${1:-refresh}"

case "$MODE" in
  refresh)
    manifest_check
    run_checked uv run python scripts/export_analysis_parquet.py \
      --input-logical trifecta_annotations \
      --require-step-c --exclude-dropped
    analysis_path="$(uv run python -c "from data_io import resolve; print(resolve('trifecta_analysis'))")"
    run_checked "${CHECK[@]}" assert-file "${analysis_path}" --min-bytes 1000
    run_checked uv run trifecta-eval --gold trifecta_gold --predictions gold_predictions
    eval_reports="$(uv run python -c "from data_io import resolve; print(resolve('eval_reports'))")"
    run_checked "${CHECK[@]}" assert-file "${eval_reports}/report.md" --min-bytes 200
    run_checked uv run python scripts/export_step_c_review.py
    run_checked "${CHECK[@]}" assert-file "${eval_reports}/step_c_review.csv" --min-bytes 100
    echo "Done: refresh (parquet + eval + step_c_review)"
    ;;

  tranche)
    manifest_check
    run_checked uv run python scripts/build_kwic_inputs.py --source long --limit 25000
    run_rerank_batch_parquet 1
    echo "Done: tranche"
    ;;

  tranche-medicijn)
    manifest_check
    run_checked uv run python scripts/build_kwic_inputs.py --source kwic --kwic-batch medicijn --limit 8000
    run_rerank_batch_parquet 2
    echo "Done: tranche-medicijn"
    ;;

  tranche-inmaken)
    manifest_check
    run_checked uv run python scripts/build_kwic_inputs.py --source kwic --kwic-batch inmaken --limit 8000
    run_rerank_batch_parquet 3
    echo "Done: tranche-inmaken"
    ;;

  step-a)
    manifest_check
    wait_for_trifecta_batch_idle
    OUT="$(uv run python -c "from data_io import resolve; print(resolve('trifecta_gold').replace('gold.parquet', 'step_a_kwic.jsonl'))")"
    run_checked caffeinate -dims uv run python scripts/batch_step_a.py \
      --input-logical kwic_inputs \
      --output-path "$OUT" \
      --concurrency 4 --resume
    run_checked "${CHECK[@]}" assert-file "$OUT" --min-bytes 50
    echo "Done: step-a → $OUT"
    ;;

  gijsbert-export)
    manifest_check
    run_checked uv run python scripts/export_gijsbert.py --silver-logical trifecta_annotations
    run_checked "${CHECK[@]}" assert-gijsbert-export
    echo "Done: gijsbert-export (train.jsonl + dev.jsonl under trifecta_gijsbert)"
    ;;

  gijsbert-train)
    manifest_check
    run_checked "${CHECK[@]}" assert-gijsbert-export
    RUN_DIR="$(uv run python -c "
from pathlib import Path
from data_io import resolve
root = Path(resolve('trifecta_gijsbert_models'))
root.mkdir(parents=True, exist_ok=True)
print(root / 'gysbert-v2-balanced-none-weekend')
")"
    run_checked caffeinate -dims uv run --extra gijsbert python scripts/train_gijsbert.py \
      --output-dir "${RUN_DIR}" \
      --oversample-none 2 \
      --class-weight-balance \
      --none-weight-boost 2.0
    run_checked "${CHECK[@]}" assert-train-run "${RUN_DIR}"
    run_checked uv run python scripts/compare_gijsbert_runs.py
    echo "Done: gijsbert-train → ${RUN_DIR}"
    ;;

  gijsbert)
    manifest_check
    run_checked bash "$0" gijsbert-export
    run_checked bash "$0" gijsbert-train
    echo "Done: gijsbert (export + train + compare)"
    ;;

  *)
    echo "Usage: $0 refresh|tranche|tranche-medicijn|tranche-inmaken|gijsbert|gijsbert-export|gijsbert-train|step-a" >&2
    exit 1
    ;;
esac
