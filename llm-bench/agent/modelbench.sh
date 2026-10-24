#!/bin/bash
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/../config.sh"
MODEL=${1:-$MODEL}
RUNS=${2:-3}
GATEWAY=$LLM_GATEWAY
OUT=$RESULTS/$MODEL-$(date +%Y%m%d-%H%M)
mkdir -p "$OUT"

log() { echo "$(date +%H:%M:%S) $*" | tee -a "$OUT/summary.txt"; }

warm() {
  for _ in $(seq 120); do
    curl -s -m 900 "$GATEWAY/v1/chat/completions" -H "Content-Type: application/json" \
      -d "{\"model\":\"$MODEL\",\"server_tools\":false,\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}" | grep -q '"choices"' && return 0
    sleep 5
  done
  log "ERROR: $MODEL did not become ready"; exit 1
}

log "loading $MODEL"
warm
log "PART 1: tool-calling and coding tests"
(cd "$HERE" && python3 evaluate.py "$GATEWAY" "$MODEL" "{\"model\":\"$MODEL\"}" all) > "$OUT/part1.log" 2>&1
log "part 1: $(grep RESULT "$OUT/part1.log" | sed 's/.*"tool_score": \([0-9]*\).*"coding_score": \([0-9]*\).*"coding_avg_seconds": \([0-9.]*\).*/tools \1\/21, coding \2\/12, avg \3 s per coding task/')"

sed "s|__BASE_URL__|$GATEWAY|; s|__MODEL__|$MODEL|g" "$HERE/models.json" > "$OUT/models.json"
for n in $(seq "$RUNS"); do
  agent=$(mktemp -d); cp "$OUT/models.json" "$agent/models.json"
  echo "{ \"defaultProvider\": \"local\", \"defaultModel\": \"$MODEL\", \"defaultThinkingLevel\": \"medium\" }" > "$agent/settings.json"
  work=$(mktemp -d)/project; cp -r "$HERE/fixture" "$work"
  since=$(date --iso-8601=seconds); start=$(date +%s)
  (cd "$work" && timeout 2700 env PI_CODING_AGENT_DIR="$agent" pi -p --mode json --no-session --model "local/$MODEL" "$(cat "$HERE/task.txt")") > "$OUT/run$n.jsonl" 2> "$OUT/run$n.err"
  status=$?
  seconds=$(( $(date +%s) - start ))
  result=$(python3 "$HERE/check.py" "$work")
  stats=$(podman logs --since "$since" "$SWAP_CONTAINER" 2>&1 | python3 "$HERE/logstats.py")
  log "PI run $n: exit $status, ${seconds}s, check $result, server $stats"
  cp -r "$work" "$OUT/run$n-project"
done
log "DONE"
