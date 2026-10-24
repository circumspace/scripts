#!/bin/bash
# Usage: speedbench.sh MODEL SOURCE.py [RESTORE_MODEL]
# Loads MODEL through llama-swap, runs ctxprobe.py (short and $DEEP-token prompts) and
# mtpbench.py (rewrite SOURCE.py, write fresh code), logs peak VRAM, then reloads RESTORE_MODEL.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/config.sh"
. "$HERE/common.sh"
MODEL=$1 SOURCE=$2 RESTORE=${3:-}
OUT=$RESULTS/speedbench-$MODEL-$(date +%Y%m%d-%H%M)
mkdir -p "$OUT"

wait_idle "${IDLE_MINUTES:-10}"
load "$MODEL" || { log "$MODEL did not load"; exit 1; }
peak=$(vram); log "$MODEL loaded, VRAM $peak/$(vram_total) MiB"
( MODEL=$MODEL python3 "$HERE/ctxprobe.py" "$MODEL" "${DEEP:-100000}"
  MODEL=$MODEL python3 "$HERE/mtpbench.py" "$SOURCE" "$MODEL" ) >> "$OUT/run.log" 2>&1 &
pid=$!
while kill -0 $pid 2>/dev/null; do v=$(vram); [ "$v" -gt "$peak" ] && peak=$v; sleep 0.5; done
log "$MODEL peak VRAM $peak/$(vram_total) MiB"
[ -n "$RESTORE" ] && { load "$RESTORE" && log "$RESTORE restored" || log "WARNING: $RESTORE did not load"; }
