# omp-ppq-model-refresh

Refreshes `~/.omp/agent/models.yml` with the current ppq.ai chat-model list. Run `./omp-ppq-model-refresh` to update (old file is backed up as `.bak`), or `./omp-ppq-model-refresh --check` to just report whether the list is stale. Set `PPQ_AI_API_KEY` in your environment — omp reads it at runtime for request auth; the key is never stored in the config.
