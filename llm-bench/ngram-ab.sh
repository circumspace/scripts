#!/bin/bash
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/config.sh"
CONFIG=$LLAMA_SWAP_CONFIG
GATEWAY=$LLM_GATEWAY
OUT=$RESULTS/ngram-ab-$(date +%Y%m%d-%H%M)
mkdir -p "$OUT"
cp "$CONFIG" "$OUT/config.yaml.orig"

log() { echo "$(date +%H:%M:%S) $*" | tee -a "$OUT/summary.txt"; }

busy() { curl -s -m 5 "$LLAMA_SWAP/upstream/$MODEL/slots" | grep -c '"is_processing":true'; }

wait_idle() {
  local idle=0
  while [ $idle -lt "$1" ]; do
    [ "$(busy)" = "0" ] && idle=$((idle + 1)) || idle=0
    sleep 30
  done
}

wait_ready() {
  for _ in $(seq 120); do
    curl -s -m 600 "$GATEWAY/v1/chat/completions" -H "Content-Type: application/json" \
      -d "{\"model\":\"$MODEL\",\"server_tools\":false,\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}" | grep -q '"choices"' && return 0
    sleep 5
  done
  log "ERROR: $MODEL did not become ready"
  return 1
}

set_ngram() {
  if [ "$1" = on ]; then
    cp "$OUT/config.yaml.orig" "$CONFIG"
  else
    sed 's/--spec-type ngram-mod //' "$OUT/config.yaml.orig" > "$CONFIG"
  fi
  for _ in $(seq 60); do
    running=$(curl -s "$LLAMA_SWAP/running")
    if [ "$1" = on ]; then echo "$running" | grep -q "ngram-mod" && break; else echo "$running" | grep -q "ngram-mod" || break; fi
    sleep 5
  done
  sleep 10
  wait_ready
}

log "waiting for $MODEL to be idle for 5 minutes"
wait_idle 10

log "PART 1: tool-calling and coding tests against production"
(cd "$HERE" && python3 evaluate.py "$GATEWAY" "$MODEL" "{\"model\":\"$MODEL\"}" all) > "$OUT/part1.log" 2>&1
log "part 1: $(grep RESULT "$OUT/part1.log" | sed 's/.*"tool_score": \([0-9]*\).*"coding_score": \([0-9]*\).*"coding_avg_seconds": \([0-9.]*\).*/tools \1\/21, coding \2\/12, avg \3 s per coding task/')"

n=0
for variant in on off on off; do
  n=$((n + 1))
  log "PART 2 run $n: ngram-mod $variant"
  set_ngram "$variant" || continue
  agent=$(mktemp -d)
  sed "s|__BASE_URL__|$GATEWAY|; s|__MODEL__|$MODEL|g" "$HERE/models.json" > "$agent/models.json"
  echo "{ \"defaultProvider\": \"local\", \"defaultModel\": \"$MODEL\", \"defaultThinkingLevel\": \"medium\" }" > "$agent/settings.json"
  work=$(mktemp -d)/project; cp -r "$HERE/fixture" "$work"
  since=$(date --iso-8601=seconds); start=$(date +%s)
  (cd "$work" && timeout 2700 env PI_CODING_AGENT_DIR="$agent" pi -p --mode json --no-session --model "local/$MODEL" "$(cat "$HERE/task.txt")") > "$OUT/run$n-$variant.jsonl" 2> "$OUT/run$n-$variant.err"
  status=$?
  seconds=$(( $(date +%s) - start ))
  result=$(python3 "$HERE/check.py" "$work")
  stats=$(podman logs --since "$since" "$SWAP_CONTAINER" 2>&1 | python3 "$HERE/logstats.py")
  log "run $n ($variant): exit $status, ${seconds}s, check $result, server $stats"
  cp -r "$work" "$OUT/run$n-$variant-project"
done

log "restoring production config"
cp "$OUT/config.yaml.orig" "$CONFIG"
sleep 15
wait_ready && log "production restored: $(curl -s "$LLAMA_SWAP/running" | grep -o 'ngram-mod' | head -1 || echo 'ngram-mod MISSING')"
log "DONE"
