# omp-ppq-model-refresh

Refreshes `~/.omp/agent/models.yml` with the current ppq.ai chat-model list. Run `./omp-ppq-model-refresh` to update (old file is backed up as `.bak`), or `./omp-ppq-model-refresh --check` to just report whether the list is stale. Set `PPQ_AI_API_KEY` in your environment — omp reads it at runtime for request auth; the key is never stored in the config.

# gen-cde-wallpapers

Generates classic CDE-style 6K wallpapers for solaris-inspired Omarchy themes, replicating NsCDE's `palette_colorgen` backdrop pipeline with authentic Motif/Xm color math. Takes one or more theme repo URLs, clones/updates them one level above this repo (`../`), reads each `palette.txt`, derives the Motif colorset (bg / fg / topShadow / bottomShadow / select) from the theme's base color, and renders a curated set of NsCDE backdrop tiles into `../<theme>/backgrounds/<Pattern>-<light|dark>-6k.png`.

Patterns render Retina-style: each XPM tile pixel covers a crisp 2×2 block of output pixels (`--scale`, default 2), so the 6K asset is a @2x render of a ~3K logical design and stays sharp when downscaled to 1440p/4K displays instead of smearing.

```bash
./gen-cde-wallpapers \
  https://github.com/circumspace/omarchy-solstice-daylight-theme \
  https://github.com/circumspace/omarchy-solstice-nightwatch-theme
```

Options: `--scale N` (px per tile pixel), `--width/--height` (canvas, default 6144×3456), `--base ROLE` (palette.txt role for the backdrop base; default `chrome`→`surface`→`canvas`), `--suffix light|dark` (override brightness-derived suffix), `--patterns P1,P2` (NsCDE backdrop names), `--tag STR` (filename tag, default `6k`). Requires `magick` (ImageMagick 7); `.pm` tiles are cached in `.cde-tiles/`.


# llm-bench

Benchmarks and a health watcher for a local llama.cpp server behind [llama-swap](https://github.com/mostlygeek/llama-swap) and an OpenAI-compatible gateway, built for one consumer GPU with MoE experts partly in system RAM. Settings live in `llm-bench/config.sh`; override them in the environment (`LLM_GATEWAY`, `LLAMA_SWAP`, `LLAMA_SWAP_CONFIG`, `SWAP_CONTAINER`, `MODEL`, `GPU_SYSFS`, `RESULTS`, …). Results go to `$RESULTS`.

| Script | What it does |
|---|---|
| `evaluate.py URL LABEL SAMPLING [all\|tools\|coding]` | 7 tool-calling cases × 3 and 12 coding tasks scored by hidden unit tests (run in a `python:alpine` podman container) |
| `modelbench.sh [MODEL] [RUNS]` | `evaluate.py` plus RUNS headless [Pi](https://pi.dev) runs of a multi-file refactoring task on `fixture/`, scored by `check.py` (7 checks) |
| `ngram-ab.sh` | The same Pi task with `--spec-type ngram-mod` on and off, alternating; edits and restores `$LLAMA_SWAP_CONFIG` |
| `splitbench.sh` | Finds a faster `--n-cpu-moe`: moves one expert layer to the GPU per step, probes a long prompt, stops before free VRAM drops under 900 MiB |
| `speed.py`, `ctxprobe.py` | Read/write speed on a short and a long prompt |
| `mtpbench.py SOURCE.py LABEL` | Decode speed and draft acceptance on a copy-heavy rewrite of SOURCE.py and on fresh code, at temperature 0 and 0.6 |
| `speedbench.sh MODEL SOURCE.py [RESTORE]` | Loads MODEL, runs `ctxprobe.py` and `mtpbench.py`, logs peak VRAM, reloads RESTORE |
| `abtest.sh SOURCE.py` | A/B of a candidate llama-swap image (`IMG`) against the running one, with the production config and each variant in `VARIANTS` (`same`, `adaptive`, `adaptive-ngram`, `adaptive-ngram64`); stops and restarts `SWAP_UNIT`, SIGSTOPs `PAUSE` jobs for the run |
| `prefilldepth.sh LABEL=IMAGE[,ENV=V]...` | llama-bench prompt processing at depth 0/32k/100k per image and environment switch (`MODEL_FILE`, `BENCH_ARGS`, `N_CPU_MOE`) |
| `generalbench.sh MODEL...` | Non-coding comparison: MMLU-Pro and IFEval through lm-eval (`LM_EVAL`), `mmlu.py`, `writing.py`, and `longctx.py` for models in `LONGCTX` |
| `mmlu.py MODEL SAMPLES_DIR OUT` | MMLU-Pro zero-shot on the questions an lm-eval run used; reads the answer from the final message, else from the reasoning |
| `writing.py LABEL` | Seven writing prompts (reflective, explanatory, story, rewrite, argument, German letter); outputs and token counts to `LABEL.writing.jsonl` |
| `longctx.py LABEL [TOKENS]` | Recall of four facts buried in a synthetic agent transcript of TOKENS (70k); offers tools, so a model that re-reads files instead of answering scores lower |
| `swebench/` | SWE-bench Verified Mini with mini-swe-agent, a 12-task slice and a reference result; see its README |
| `add_model.py` | Adds a candidate model to a llama-swap config (expects a `server` macro) |
| `health.sh` | Every 30 s logs VRAM, free RAM, swap, processes stuck in the amdgpu driver and kernel GPU errors; `ALERT` lines for anything critical |

Runners wait until the model has been idle for a few minutes before reloading anything. On RDNA2, overfilling VRAM can deadlock the amdgpu driver instead of failing gracefully; keep ~500 MiB free.

```bash
cd llm-bench
LLM_GATEWAY=http://gpu-box:4000 SWAP_CONTAINER=llama-swap ./modelbench.sh my-model 3
```

lm-eval's 5-shot MMLU-Pro sends its worked examples as chat turns without visible reasoning; reasoning models then often answer inside their reasoning and leave the final message empty, which scores as wrong. `mmlu.py` reruns the same questions zero-shot.

`abtest.sh`, `prefilldepth.sh` and `speedbench.sh` also read `SWAP_UNIT` (the systemd user unit running llama-swap), `MODELS_DIR`, and `GPU_ENV` (for example `HSA_OVERRIDE_GFX_VERSION=10.3.0` on gfx1031).

Needs `podman`, `python3` with PyYAML (`add_model.py`), `pi` for the agent runs, and lm-eval with its `api` and `ifeval` extras for `generalbench.sh`.
