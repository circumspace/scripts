# Helpers shared by the shell runners. Source after config.sh.
log() { echo "$(date "+%m-%d %H:%M:%S") $*" | tee -a "$OUT/run.log"; }
vram() { echo $(( $(cat "$GPU_SYSFS/mem_info_vram_used") / 1048576 )); }
vram_total() { echo $(( $(cat "$GPU_SYSFS/mem_info_vram_total") / 1048576 )); }
# Requests in flight at the gateway; falls back to llama-swap's slot of $MODEL when the
# gateway exports no llm_gateway_requests_in_flight.
in_flight() {
  local m
  m=$(curl -s -m 5 "$LLM_GATEWAY/gateway/metrics" | awk '/^llm_gateway_requests_in_flight/ {s+=$2; n++} END {if (n) print s+0}')
  [ -n "$m" ] && { echo "$m"; return; }
  curl -s -m 5 "$LLAMA_SWAP/running" | grep -q '"state":"ready"' || { echo 0; return; }
  curl -s -m 5 "$LLAMA_SWAP/upstream/$MODEL/slots" | grep -c '"is_processing":true'
}
wait_idle() {
  log "waiting for $1 idle minutes"
  local idle=0
  while [ $idle -lt $(($1 * 2)) ]; do [ "$(in_flight)" = 0 ] && idle=$((idle + 1)) || idle=0; sleep 30; done
}
# Loads a model through llama-swap and waits until it answers.
load() {
  for _ in $(seq 120); do
    curl -fs -m 600 "$LLAMA_SWAP/v1/chat/completions" -H "Content-Type: application/json" \
      -d "{\"model\":\"$1\",\"max_tokens\":1,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}" >/dev/null && return 0
    sleep 5
  done
  return 1
}
