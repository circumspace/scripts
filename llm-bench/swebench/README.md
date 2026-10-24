# SWE-bench Verified Mini

[mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) against an OpenAI-compatible
endpoint, on the 50-task
[SWE-bench Verified Mini](https://huggingface.co/datasets/MariusHobbhahn/swe-bench-verified-mini)
subset (Django and Sphinx issues only). It is the same harness as the official bash-only
leaderboard, so scores compare task by task with the runs published in
[SWE-bench/experiments](https://github.com/SWE-bench/experiments).

## Setup

```sh
cd llm-bench/swebench
uv venv -p 3.12 .venv && uv pip install -p .venv mini-swe-agent swebench datasets mcp
LLM_GATEWAY=http://gpu-box:4000 MODEL=my-model ./run.sh <name> [instance regex]
```

`run.sh` waits for `$IDLE_MINUTES` (10) without requests, then runs one task at a time and
grades into `$RESULTS/swebench/<name>`. Task containers run under podman; grading reaches
podman through its Docker-compatible socket. A full run on one consumer GPU took about 10.5
hours and pulls about 60 GB of task images.

`local.yaml` overrides mini-swe-agent's `swebench.yaml`: 150 steps per task, no cost limit,
temperature 0.6, and a 20-minute request timeout for full-context re-reads. The endpoint and
model come from `LLM_GATEWAY` and `MODEL`; `CONFIG=<file>` layers another config on top, for
example a different model's sampling.

`quick12.tsv` is a 12-task slice of mini50, about 2.5 hours: six tasks the reference run below
solved and six it failed, across all difficulty bands.

```sh
./run.sh <name> "^($(tail -n +2 quick12.tsv | cut -f1 | paste -sd'|' -))$"
```

Public SWE-bench tasks are old enough to be in recent models' training data: a model that
reproduces upstream fixes word for word, changelog lines included, is recalling them. For a
clean comparison use tasks created after the models' training cutoff, such as
[SWE-bench-Live](https://github.com/microsoft/SWE-bench-Live)'s monthly sets.

## Reference result

`mini50.tsv`, 2026-10-19: [Qwen3.6-35B-A3B heretic IQ4_XS](https://huggingface.co/hermeticvm/Qwen3.6-35B-A3B-heretic-MTP-IQ4_XS-GGUF)
on one RX 6700 XT 12 GB with experts partly in system RAM, 128k context, thinking budget 2048,
temperature 0.6. **27/50 solved.**

| Difficulty | Solved |
|---|---|
| under 15 min | 13/19 |
| 15 min – 1 h | 13/23 |
| 1–4 h | 1/7 |
| over 4 h | 0/1 |

Of the 23 failures, 14 were wrong fixes, 4 hit the step limit and 5 submitted without writing
the patch file mini-swe-agent asks for.

Same 50 tasks from the leaderboard runs (full-precision APIs, mostly without a step cap):
Claude 4.5 Opus 37, Claude 4.5 Haiku 31, Kimi K2 Thinking 27, Devstral Small 2512 25,
Qwen3-Coder 480B 22, gpt-oss-120b 13. Models solving 27–28 of these score 60–66 % on the full 500.
