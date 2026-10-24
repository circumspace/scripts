#!/bin/bash
# Usage: generalbench.sh MODEL...
# Non-coding comparison per model: MMLU-Pro (7 per subject, via lm-eval, which also records the
# questions for mmlu.py), IFEval (100), writing.py, and longctx.py at 120k for models in LONGCTX.
# Talks to llama-swap directly so a gateway's server-side tools never reach the prompts.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/../config.sh"
. "$HERE/../common.sh"
: "${LM_EVAL:=lm_eval}"
OUT=$RESULTS/general-$(date +%Y%m%d-%H%M)
mkdir -p "$OUT"
lm() {
  "$LM_EVAL" --model local-chat-completions \
    --model_args "model=$1,base_url=$LLAMA_SWAP/v1/chat/completions,num_concurrent=1,max_retries=3,tokenized_requests=False,tokenizer_backend=None,timeout=1800" \
    --apply_chat_template --gen_kwargs max_gen_toks=4096 --output_path "$OUT/$1" --log_samples "${@:2}" >> "$OUT/$1.lm_eval.log" 2>&1
}

wait_idle "${IDLE_MINUTES:-10}"
log "start: $*"
for m in "$@"; do
  log "$m mmlu_pro (lm-eval, 5-shot)"; lm "$m" --tasks mmlu_pro --num_fewshot 5 --fewshot_as_multiturn --limit 7
  log "$m mmlu (zero-shot)"; MODEL=$m python3 "$HERE/mmlu.py" "$m" "$OUT/$m" "$OUT/$m.mmlu.jsonl" | tee -a "$OUT/run.log"
  log "$m ifeval"; lm "$m" --tasks ifeval --limit 100
  log "$m writing"; MODEL=$m python3 "$HERE/writing.py" "$OUT/$m" >> "$OUT/run.log" 2>&1
  case " ${LONGCTX:-} " in *" $m "*) log "$m longctx"; MODEL=$m python3 "$HERE/longctx.py" "$OUT/$m" 120000 >> "$OUT/run.log" 2>&1;; esac
  grep -hE "^\|(mmlu_pro|ifeval) |prompt_level|inst_level" "$OUT/$m.lm_eval.log" | tee -a "$OUT/run.log"
done
log "GENERAL DONE"
