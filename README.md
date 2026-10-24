# Home-lab scripts

Small tools I wrote for my own machines: a GPU box that serves a local LLM, an Arch desktop, a self-hosted Gitea. I share them because each one solved a problem that took me longer than it should have, and someone with a similar setup may get there faster.

They are not polished products. Each script does one job, reads its settings from environment variables, and assumes Linux unless it says otherwise. Read a script before you run it; several of them stop and restart services.

The largest part is `llm-bench/`: the measurements behind running a 35B mixture-of-experts model at 128K context on one 12 GB RDNA2 card, with the experts of 24 of its 40 layers in system RAM.

## Contents

- [`llm-bench/`](#llm-bench): benchmarks for a local llama.cpp server
- [`omp-ppq-model-refresh`](#omp-ppq-model-refresh): keeps omp's ppq.ai model list current
- [`gen-cde-wallpapers`](#gen-cde-wallpapers): CDE-style wallpapers for Omarchy themes
- [`remote-makepkg.sh`](#remote-makepkgsh): builds an Arch PKGBUILD on another machine
- [`github-to-gitea.sh`](#github-to-giteash): copies GitHub repositories into Gitea

# llm-bench

Benchmarks and a health watcher for a llama.cpp server behind [llama-swap](https://github.com/mostlygeek/llama-swap) and an optional OpenAI-compatible gateway. They answer the questions that come up when tuning one consumer GPU: how many expert layers fit on the card, whether a new llama.cpp build or speculative-decoding mode is faster, and whether a different model is worth switching to.

Settings live in `llm-bench/config.sh`. Override any of them in the environment, or keep a file of your own and load it with `set -a; . ./my.env; set +a`.

| Variable | Meaning |
|---|---|
| `LLM_GATEWAY` | OpenAI-compatible endpoint that clients use |
| `LLAMA_SWAP`, `LLAMA_SWAP_CONFIG` | llama-swap's own address and its `config.yaml` |
| `MODEL` | Model name as llama-swap knows it |
| `SWAP_CONTAINER`, `SWAP_UNIT` | podman container and systemd user unit that run llama-swap |
| `GATEWAY_CONTAINER` | The gateway's container, if there is one |
| `MODELS_DIR` | GGUF directory, mounted into throwaway containers |
| `GPU_ENV` | Extra environment for those containers, for example `HSA_OVERRIDE_GFX_VERSION=10.3.0` on gfx1031 |
| `GPU_SYSFS` | sysfs directory of the GPU, for VRAM readings (AMD) |
| `RESULTS` | Where results go |

Every script that reloads a model first waits until the model has been idle for `IDLE_MINUTES` (default 10). Scripts that stop production restart it on any exit, including Ctrl-C. On RDNA2, overfilling VRAM can deadlock the amdgpu driver instead of failing with an error; keep about 500 MiB free.

Needs `podman` and `python3`. `add_model.py` needs PyYAML, the agent runs need [Pi](https://pi.dev), and `generalbench.sh` needs lm-eval with its `api` and `ifeval` extras.

### Shared

- **`config.sh`, `common.sh`**: default settings, and helpers the other scripts source: logging, VRAM readings, waiting for an idle model, loading a model.
- **`health.sh`**: run it in the background while you tune. Every 30 seconds it logs VRAM, free RAM, swap, processes stuck in the GPU driver and kernel GPU errors to `HEALTH_LOG`, with `ALERT` lines for anything critical. `splitbench.sh` stops when it sees one.
- **`add_model.py ORIGINAL TARGET NAME PATH NCMOE EXTRA SAMPLING CTX`**: writes a copy of a llama-swap config with one more model in it, for trying a candidate next to production. Expects a `server` macro in the config.

### `speed/`: how fast, and what fits

- **`speed.py`, `ctxprobe.py LABEL TOKENS`**: time a short prompt and one of TOKENS tokens. They report prompt reading and generation speed separately, because the two react differently to almost every setting.
- **`mtpbench.py SOURCE.py LABEL`**: generation speed and draft acceptance for speculative decoding. Runs two tasks at temperature 0 and 0.6: rewriting SOURCE.py with one function renamed, where drafts from the context pay off, and writing fresh code, where they do not.
- **`speedbench.sh MODEL SOURCE.py [RESTORE]`**: loads MODEL, runs `ctxprobe.py` and `mtpbench.py`, records peak VRAM, then reloads RESTORE.
- **`splitbench.sh`**: finds the lowest `--n-cpu-moe` the card survives. Moves one expert layer to the GPU per step, probes a long prompt at each step, and stops before free VRAM falls under 900 MiB. Restores the config afterwards.
- **`abtest.sh SOURCE.py`**: compares a candidate llama-swap image (`IMG`) with the running one, on the same model and config. Tries each speculative-decoding variant in `VARIANTS` (`same`, `adaptive`, `adaptive-ngram`, `adaptive-ngram64`, `mtp`, `mtp2`, `mtp2-ngram`; `mtp2` drafts at most 2 MTP tokens; `ngram-auto` leaves the n-gram draft length to llama.cpp). `arena-ncmoeN`, for rdna-boosts images, moves N layers' experts to system RAM and asks for an `ARENA_MIB` (default 2000) MoE expert cache in the VRAM freed. Each variant's server log is kept next to its results. Processes named in `PAUSE` are paused with SIGSTOP for the run, so CPU-heavy jobs do not skew it.
- **`prefilldepth.sh LABEL=IMAGE[,ENV=VALUE]...`**: llama-bench prompt reading at depth 0, 32K and 100K for each image and environment switch, with llama-swap stopped so each run owns the GPU. Takes `MODEL_FILE`, `BENCH_ARGS` and `N_CPU_MOE`. Use it to test a patched llama.cpp build or a kernel flag in isolation.

### `agent/`: tool calling and coding

- **`evaluate.py URL LABEL SAMPLING [all|tools|coding]`**: seven tool-calling cases, three times each, and twelve coding tasks scored by hidden unit tests. Model-written code runs in a `python:alpine` podman container.
- **`modelbench.sh [MODEL] [RUNS]`**: `evaluate.py`, then RUNS headless Pi agent runs of a multi-file refactoring task (`task.txt`) on a small project in `fixture/`. `check.py` scores each run on seven checks; `logstats.py` pulls speed figures from the server log.
- **`ngram-ab.sh`**: the same agent task with n-gram drafting (`--spec-type ngram-mod`) on and off, alternating. Edits `LLAMA_SWAP_CONFIG` and restores it.

### `general/`: everything that is not code

- **`generalbench.sh MODEL...`**: per model, MMLU-Pro and IFEval through lm-eval, then `mmlu.py`, `writing.py`, and `longctx.py` for models listed in `LONGCTX`. Talks to llama-swap directly, so a gateway's own tools never reach the prompts.
- **`mmlu.py MODEL SAMPLES_DIR OUT`**: reruns the MMLU-Pro questions of an lm-eval run zero-shot. lm-eval's 5-shot prompt shows worked answers without reasoning. Reasoning models then often answer inside their reasoning and leave the final message empty, which scores as wrong. `mmlu.py` reads the final message and falls back to the reasoning.
- **`writing.py LABEL`**: seven writing prompts: reflective, explanatory, story, rewrite, argument, and a German letter. Saves outputs and token counts for reading side by side; it does not score them.
- **`longctx.py LABEL [TOKENS]`**: hides four facts in a synthetic agent transcript of TOKENS (70,000 by default) and asks for them back. It offers tools, so a model that re-reads files instead of remembering scores lower.

### `swebench/`: SWE-bench Verified Mini

The 50-task SWE-bench Verified Mini with mini-swe-agent. It is the same harness as the official bash-only leaderboard, so scores compare task by task with published runs. Includes a 12-task slice for a 2.5-hour check and a reference result of 27/50. See [its README](llm-bench/swebench/README.md).

### Example

```bash
cd llm-bench
LLM_GATEWAY=http://gpu-box:4000 SWAP_CONTAINER=llama-swap agent/modelbench.sh my-model 3
MODEL=my-model SWAP_UNIT=llama-swap IMG=my-patched-image speed/abtest.sh some_module.py
```

# omp-ppq-model-refresh

Refreshes `~/.omp/agent/models.yml` with the current ppq.ai chat-model list. `./omp-ppq-model-refresh` updates the file and keeps the old one as `.bak`; `--check` only reports whether the list is stale. Set `PPQ_AI_API_KEY` in your environment: omp reads it at runtime, and the key is never written to the config.

# gen-cde-wallpapers

Generates 6K wallpapers in the style of the Common Desktop Environment for Solaris-inspired Omarchy themes. It reproduces the backdrop pipeline of NsCDE's `palette_colorgen` with the original Motif color math.

It takes one or more theme repository URLs and clones or updates each one level above this repository (`../`). From each theme's `palette.txt` it derives the Motif colorset (background, foreground, top and bottom shadow, selection). It then renders a set of NsCDE backdrop tiles into `../<theme>/backgrounds/<Pattern>-<light|dark>-6k.png`.

Each tile pixel becomes a sharp 2×2 block (`--scale`, default 2). The 6K image is a @2x render of a 3K design, so it stays crisp when scaled down to 1440p or 4K.

```bash
./gen-cde-wallpapers \
  https://github.com/circumspace/omarchy-solstice-daylight-theme \
  https://github.com/circumspace/omarchy-solstice-nightwatch-theme
```

| Option | Meaning |
|---|---|
| `--scale N` | Output pixels per tile pixel |
| `--width`, `--height` | Canvas size, default 6144×3456 |
| `--base ROLE` | `palette.txt` role for the base color; default `chrome`, then `surface`, then `canvas` |
| `--suffix light\|dark` | Overrides the suffix derived from brightness |
| `--patterns P1,P2` | NsCDE backdrop names |
| `--tag STR` | File name tag, default `6k` |

Requires ImageMagick 7 (`magick`). Downloaded tiles are cached in `.cde-tiles/`.

# remote-makepkg.sh

`BUILD_HOST=host ./remote-makepkg.sh PKGDIR [IMAGE]` builds one Arch PKGBUILD on another machine in a throwaway podman container (`archlinux` by default) and copies the finished packages back into PKGDIR. Useful when the desktop is a laptop and the build is heavy. `BUILD_HOST` is any SSH destination that runs podman.

# github-to-gitea.sh

One-off copy of GitHub repositories into a Gitea instance through Gitea's migration API. It includes issues, pull requests, releases and wiki unless `WITH_METADATA=0`. Set `GITEA_URL`, `GITEA_TOKEN` and `SYNC_PAIRS` (for example `"alice:alice acme:acme"`); `DRY_RUN=1` only prints what it would do. Repositories that already exist in Gitea are skipped. The full list of variables is at the top of the script. Requires `curl` and `jq`.
