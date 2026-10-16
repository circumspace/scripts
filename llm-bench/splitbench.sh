#!/bin/bash
set -u
EVAL=$(cd "$(dirname "$0")" && pwd)
. "$EVAL/config.sh"
CONFIG=$LLAMA_SWAP_CONFIG
mkdir -p "$RESULTS"
OUT=$RESULTS/splitbench-$(date +%Y%m%d-%H%M).log
DEEP=${DEEP:-100000}
VRAM=$GPU_SYSFS/mem_info_vram_used
TOTAL=$(( $(cat "$GPU_SYSFS/mem_info_vram_total") / 1048576 ))
log() { echo "$(date "+%m-%d %H:%M:%S") $*" | tee -a "$OUT"; }
vram() { echo $(( $(cat $VRAM) / 1048576 )); }
active() {
  local busy recent
  busy=$(curl -s -m 5 "$LLAMA_SWAP/upstream/$MODEL/slots" | grep -c "\"is_processing\":true")
  recent=0
  [ -n "$GATEWAY_CONTAINER" ] && recent=$(podman logs --since 35s "$GATEWAY_CONTAINER" 2>&1 | grep -c "POST /v1/chat")
  [ "$busy" != "0" ] || [ "$recent" != "0" ]
}
stuck() { tail -n 2 "$HEALTH_LOG" 2>/dev/null | grep -q "process stuck"; }
ready() {
  for _ in $(seq 90); do
    curl -s "$LLAMA_SWAP/running" | grep -q "\"model\":\"$MODEL\",\"state\":\"ready\"" && curl -s "$LLAMA_SWAP/running" | grep -q "n-cpu-moe $1 " && return 0
    curl -s -m 600 "$LLAMA_SWAP/v1/chat/completions" -H "Content-Type: application/json" -d "{\"model\":\"$MODEL\",\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}" >/dev/null 2>&1
    sleep 5
  done
  return 1
}

log "waiting for 3 idle minutes"
idle=0; while [ $idle -lt 6 ]; do if active; then idle=0; else idle=$((idle + 1)); fi; sleep 30; done
cp "$CONFIG" "$OUT.config.orig"
base=$(grep -oE "n-cpu-moe [0-9]+" "$CONFIG" | head -1 | cut -d" " -f2)
log "production split is $base, deep prompt $DEEP tokens"
for n in $(seq $((base - 1)) -1 22); do
  sed "s/n-cpu-moe $base -c 131072/n-cpu-moe $n -c 131072/" "$OUT.config.orig" > "$CONFIG"
  sleep 15
  if ! ready "$n"; then log "n=$n did not load; stopping"; break; fi
  loaded=$(vram)
  log "n=$n loaded, VRAM ${loaded}/${TOTAL} MiB"
  peak=$loaded
  python3 "$EVAL/ctxprobe.py" "split-$n" "$DEEP" > "$OUT.n$n.json" 2>&1 &
  pid=$!
  while kill -0 $pid 2>/dev/null; do v=$(vram); [ "$v" -gt "$peak" ] && peak=$v; stuck && { log "ABORT: GPU process stuck"; cp "$OUT.config.orig" "$CONFIG"; exit 1; }; sleep 0.5; done
  log "n=$n peak VRAM ${peak}/${TOTAL} MiB (free $((TOTAL - peak))), result $(tail -1 "$OUT.n$n.json")"
  [ $((TOTAL - peak)) -ge 900 ] || { log "free VRAM below 900 MiB at n=$n; not going lower"; break; }
done
cp "$OUT.config.orig" "$CONFIG"
sleep 15; ready "$base" && log "production restored at n=$base" || log "WARNING: production did not come back at n=$base"
log "DONE"
