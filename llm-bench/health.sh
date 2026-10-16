#!/bin/bash
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/config.sh"
LOG=$HEALTH_LOG
mkdir -p "$(dirname "$LOG")"
VRAM=$GPU_SYSFS/mem_info_vram_used
VRAM_TOTAL=$(( $(cat "$GPU_SYSFS/mem_info_vram_total") / 1048576 ))
since=$(date "+%Y-%m-%d %H:%M:%S")
declare -A seen
while true; do
  now=$(date "+%m-%d %H:%M:%S")
  vram=$(( $(cat $VRAM) / 1048576 ))
  avail=$(( $(awk "/MemAvailable/{print \$2}" /proc/meminfo) / 1024 ))
  swap=$(( ( $(awk "/SwapTotal/{print \$2}" /proc/meminfo) - $(awk "/SwapFree/{print \$2}" /proc/meminfo) ) / 1024 ))
  stuck=$(ps -eo pid,stat,etimes,wchan:32,comm --no-headers | awk "\$2 ~ /^D/ && \$3 > 60 && \$4 ~ /amdgpu|drm|kfd|ttm/ {print \$1\"(\"\$5\",\"\$4\")\"}" | tr "\n" " ")
  echo "$now vram=${vram}/${VRAM_TOTAL}MiB ram_avail=${avail}MiB swap_used=${swap}MiB stuck=[${stuck}]" >> $LOG
  [ "$vram" -gt $(( VRAM_TOTAL - 150 )) ] && echo "$now ALERT vram nearly full: ${vram}/${VRAM_TOTAL} MiB" >> $LOG
  [ "$avail" -lt 2048 ] && echo "$now ALERT low RAM: ${avail} MiB available" >> $LOG
  [ -n "$stuck" ] && echo "$now ALERT process stuck in GPU driver >60s: $stuck" >> $LOG
  journalctl -k --since "$since" --no-pager -o short-iso 2>/dev/null | grep -iE "amdgpu.*(error|fault|timeout|reset|hang)|hung_task|gpu reset|ring .* timeout" | while read -r line; do
    echo "$now ALERT kernel: ${line:0:200}" >> $LOG
  done
  since=$(date "+%Y-%m-%d %H:%M:%S")
  tail -n 20000 $LOG > $LOG.tmp && mv $LOG.tmp $LOG
  sleep 30
done
