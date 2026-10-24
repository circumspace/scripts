#!/bin/bash
# Usage: IMG=<candidate llama-swap image> abtest.sh SOURCE.py
# A/B of a candidate llama-swap image against the running one on $MODEL: the production
# server first, then the candidate in a throwaway container with the production config and with
# each speculative-decoding variant in $VARIANTS. Production is stopped while the candidate
# holds the GPU and restarted on any exit. Jobs named in $PAUSE are SIGSTOPped for the run.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/../config.sh"
. "$HERE/../common.sh"
SOURCE=$1
: "${IMG:?set IMG to the candidate image}"
: "${SWAP_UNIT:?set SWAP_UNIT to the systemd --user unit that runs llama-swap}"
: "${PROD_SPEC:=--spec-type draft-mtp,ngram-mod --spec-ngram-mod-n-max 256}"
: "${VARIANTS:=same adaptive adaptive-ngram}"
PORT=${LLAMA_SWAP##*:}
OUT=$RESULTS/abtest-$(date +%Y%m%d-%H%M)
mkdir -p "$OUT"
bench() {
  local label=$1 peak
  peak=$(vram); log "$label loaded, VRAM $peak/$(vram_total) MiB"
  ( MODEL=$MODEL python3 "$HERE/ctxprobe.py" "$label" "${DEEP:-100000}"
    MODEL=$MODEL python3 "$HERE/mtpbench.py" "$SOURCE" "$label" ) > "$OUT/$label.json" 2>&1 &
  local pid=$!
  while kill -0 $pid 2>/dev/null; do v=$(vram); [ "$v" -gt "$peak" ] && peak=$v; sleep 0.5; done
  log "$label peak VRAM $peak/$(vram_total) MiB"; tee -a "$OUT/run.log" < "$OUT/$label.json"
}
PAUSED=()
PROD_STOPPED=0
cleanup() {
  if [ $PROD_STOPPED = 1 ]; then
    podman rm -f llm-ab >/dev/null 2>&1
    systemctl --user start "$SWAP_UNIT"
    load "$MODEL" && log "production restored" || log "WARNING: production did not come back"
  fi
  for p in "${PAUSED[@]}"; do kill -CONT "$p"; done; log "resumed: ${PAUSED[*]:-none}"
}
trap cleanup EXIT
trap 'exit 1' INT TERM HUP

grep -qF -- "$PROD_SPEC" "$LLAMA_SWAP_CONFIG" || { log "production config lacks '$PROD_SPEC'; aborting"; exit 1; }
wait_idle "${IDLE_MINUTES:-10}"
for name in ${PAUSE:-}; do for p in $(pgrep -x "$name"); do kill -STOP "$p" && PAUSED+=("$p"); done; done
log "paused: ${PAUSED[*]:-none}"
load "$MODEL" || { log "production $MODEL not ready; aborting"; exit 1; }
bench production

PROD_STOPPED=1
systemctl --user stop "$SWAP_UNIT"
gpu_env=(); for e in $GPU_ENV; do gpu_env+=(-e "$e"); done
for v in $VARIANTS; do
  ncmoe=; v_env=()
  case $v in
    same) spec=$PROD_SPEC ;;
    ngram-auto) spec="--spec-type draft-mtp,ngram-mod" ;;
    arena-ncmoe*) spec="--spec-type draft-mtp,ngram-mod"; ncmoe=${v#arena-ncmoe}
      v_env=(-e "MOE_EXPERT_CACHE_MIB=${ARENA_MIB:-2000}" -e "LLAMA_ARG_MOE_CACHE_MIB=${ARENA_MIB:-2000}") ;;
    adaptive) spec="--spec-type draft-mtp-adaptive" ;;
    adaptive-ngram) spec="--spec-type draft-mtp-adaptive,ngram-mod --spec-ngram-mod-n-max 256" ;;
    adaptive-ngram64) spec="--spec-type draft-mtp-adaptive,ngram-mod --spec-ngram-mod-n-max 64" ;;
    mtp) spec="--spec-type draft-mtp" ;;
    mtp2) spec="--spec-type draft-mtp --spec-draft-n-max 2" ;;
    mtp2-ngram) spec="--spec-type draft-mtp,ngram-mod --spec-ngram-mod-n-max 256 --spec-draft-n-max 2" ;;
    *) log "unknown variant $v"; continue ;;
  esac
  mkdir -p "$OUT/cfg-$v"
  edits=(-e "s|$PROD_SPEC|$spec|")
  [ -n "$ncmoe" ] && edits+=(-e "s|--n-cpu-moe [0-9]*|--n-cpu-moe $ncmoe|")
  sed "${edits[@]}" "$LLAMA_SWAP_CONFIG" > "$OUT/cfg-$v/config.yaml"
  podman rm -f llm-ab >/dev/null 2>&1
  podman run -d --name llm-ab --device /dev/dri --device /dev/kfd "${gpu_env[@]}" "${v_env[@]}" --ulimit memlock=-1:-1 \
    -p "127.0.0.1:$PORT:8080" -v "$MODELS_DIR:/models:ro,z" -v "$OUT/cfg-$v:/config:ro,z" "$IMG" >/dev/null
  if ! load "$MODEL"; then log "candidate-$v did not load"; podman logs --tail 30 llm-ab >> "$OUT/candidate-$v.load.log" 2>&1; continue; fi
  bench "candidate-$v"
  podman logs llm-ab > "$OUT/candidate-$v.server.log" 2>&1
  grep -E "moe_cache_report|moe_cache_disable|slab_init" "$OUT/candidate-$v.server.log" | tail -5 | tee -a "$OUT/run.log"
done
log "AB DONE"
