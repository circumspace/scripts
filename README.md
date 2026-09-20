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

