#!/bin/bash
# Usage: MODEL_FILE=<gguf in $MODELS_DIR> prefilldepth.sh LABEL=IMAGE[,ENV=VALUE...]...
# llama-bench prompt processing at depth 0, 32k and 100k for each llama.cpp image (and optional
# environment switches), with llama-swap stopped so each run owns the GPU. Example:
#   prefilldepth.sh upstream=ghcr.io/ggml-org/llama.cpp:server-rocm-b11804 \
#                   patched=my-image,GGML_HIP_FA_BAND_FETCH_AHEAD=0
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/../config.sh"
. "$HERE/../common.sh"
: "${MODEL_FILE:?set MODEL_FILE}"
: "${SWAP_UNIT:?set SWAP_UNIT}"
: "${BENCH_ARGS:=-ngl 99 -fa 1 -ctk q8_0 -ctv q8_0 -b 2048 -ub 1024 -p 512 -n 0 -d 0,32768,100000 -r 1}"
OUT=$RESULTS/prefilldepth-$(date +%Y%m%d-%H%M)
mkdir -p "$OUT"
PAUSED=()
cleanup() {
  podman rm -f llm-diag >/dev/null 2>&1
  systemctl --user start "$SWAP_UNIT"
  load "$MODEL" && log "production restored" || log "WARNING: production did not come back"
  for p in "${PAUSED[@]}"; do kill -CONT "$p"; done; log "resumed: ${PAUSED[*]:-none}"
}
trap cleanup EXIT
trap 'exit 1' INT TERM HUP

wait_idle "${IDLE_MINUTES:-10}"
for name in ${PAUSE:-}; do for p in $(pgrep -x "$name"); do kill -STOP "$p" && PAUSED+=("$p"); done; done
log "paused: ${PAUSED[*]:-none}"
systemctl --user stop "$SWAP_UNIT"
gpu_env=(); for e in $GPU_ENV; do gpu_env+=(-e "$e"); done
for spec in "$@"; do
  label=${spec%%=*}; rest=${spec#*=}; img=${rest%%,*}
  extra=(); IFS=, read -ra kv <<< "${rest#"$img"}"; for e in "${kv[@]}"; do [ -n "$e" ] && extra+=(-e "$e"); done
  log "$label"
  podman run --rm --name llm-diag --device /dev/dri --device /dev/kfd "${gpu_env[@]}" "${extra[@]}" \
    --ulimit memlock=-1:-1 -v "$MODELS_DIR:/models:ro,z" --entrypoint /app/llama "$img" \
    bench -m "/models/$MODEL_FILE" $BENCH_ARGS ${N_CPU_MOE:+-ncmoe $N_CPU_MOE} -o md \
    2> "$OUT/$label.err" | tee "$OUT/$label.md" | grep -E "pp[0-9]+" | tee -a "$OUT/run.log"
done
log "DEPTH DONE"
