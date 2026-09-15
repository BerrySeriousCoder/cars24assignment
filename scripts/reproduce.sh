#!/usr/bin/env bash
set -euo pipefail
solution_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$solution_root"
python_command="${PYTHON:-python3}"
mode="${1:-test}"
if [[ $# -gt 0 ]]; then shift; fi
case "$mode" in
  test)
    exec "$python_command" -m op02.verify "$@"
    ;;
  run)
    exec "$python_command" -m op02.runner "$@"
    ;;
  eval)
    exec "$python_command" -m op02.eval_report "$@"
    ;;
  compare)
    exec "$python_command" -m op02.compare "$@"
    ;;
  smoke|ablation)
    run_stamp="$(date -u +%Y%m%dT%H%M%S)-$$"
    run_mode=offline
    configs=(old new degraded)
    if [[ "$mode" == ablation ]]; then
      run_mode=live
      configs=(old swap new no_prompt no_guard degraded)
    fi
    for configuration in "${configs[@]}"; do
      "$python_command" -m op02.runner --mode "$run_mode" --config "$configuration" \
        --output "results/$run_mode/$run_stamp-$configuration" "$@"
    done
    "$python_command" -m op02.compare \
      --old "results/$run_mode/$run_stamp-old/cases.jsonl" \
      --new "results/$run_mode/$run_stamp-new/cases.jsonl" \
      --output "results/$run_mode/$run_stamp-comparison.json"
    ;;
  *)
    echo 'Usage: bash scripts/reproduce.sh test|run|eval|compare|smoke|ablation [arguments]' >&2
    exit 2
    ;;
esac
