#!/bin/bash
# Usage: run.sh <run name> [instance id regex]
# mini-swe-agent on SWE-bench Verified Mini against $LLM_GATEWAY with $MODEL, one task at a
# time, then grading through podman's Docker-compatible socket. $CONFIG layers another
# mini-swe-agent config on top (sampling for a different model, for example).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/../config.sh"
cd "$HERE"
NAME=$1
OUT=$RESULTS/swebench/$NAME
mkdir -p "$OUT"
. "$HERE/../common.sh"
printf 'model:\n  model_name: openai/%s\n  model_kwargs:\n    api_base: %s/v1\n' "$MODEL" "$LLM_GATEWAY" > "$OUT/endpoint.yaml"

wait_idle "${IDLE_MINUTES:-10}"
log "starting agent"
.venv/bin/mini-extra swebench --subset MariusHobbhahn/swe-bench-verified-mini --split test \
  ${2:+--filter "$2"} -w 1 -o "$OUT" -c swebench.yaml -c local.yaml -c "$OUT/endpoint.yaml" ${CONFIG:+-c $CONFIG}

log "agent done, grading"
DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock .venv/bin/python -m swebench.harness.run_evaluation \
  --dataset_name SWE-bench/SWE-bench_Verified --split test \
  --predictions_path "$OUT/preds.json" --max_workers 2 --run_id "$NAME" --report_dir "$OUT"
log "DONE"
