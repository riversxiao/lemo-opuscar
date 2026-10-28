# HyperFrames · alternate HTML→MP4 rail

**Status:** export path live (2026-10-29) via `tools/hyperframes_export.sh` / `tools/handoff/`. **Not** the default mux rail — Playwright `still.mjs` / `video.mjs` remain delivery. Desktop Studio / HeyGen cloud / skills install = **needs-user** (see `lemo-manifest.json`).

## What it is

[HeyGen HyperFrames](https://github.com/heygen-com/hyperframes) (Apache-2.0) turns HTML / CSS / media / seekable animations into deterministic MP4s. Agents install skills; CLI scaffolds and renders.

- Homepage: https://hyperframes.heygen.com
- Guide example: https://hyperframes.app/docs/3-guides/1-website-to-video
- Skills install: `npx skills add heygen-com/hyperframes` or `npx hyperframes skills update` (core set)

## When to offer it

| Prefer **lemo / Playwright** | Consider **HyperFrames** |
|---|---|
| User asked for an Opuscar / DeepSeek demo style (`styles/<slug>/demo`) | Greenfield HTML motion piece that is **not** locked to an Opus demo |
| Engine-lock film (Swiss / Pictogram / Caption…) | Website→video capture pipeline, or HyperFrames composition skills |
| Need identical still/video contract + `sheet.py` / blackdetect path | User already has HyperFrames skills installed and wants that loop |

Never replace a locked demo engine with a HyperFrames rewrite “for convenience”.

## Install / run (upstream; verify on their machine)

```sh
# Node 22+ and ffmpeg required (upstream README)
npx skills add heygen-com/hyperframes          # interactive picker; agents prefer:
npx hyperframes skills update                  # core skill set from main

npx hyperframes init my-video
cd my-video
npx hyperframes preview
npx hyperframes render --output my-video.mp4
```

Claude Code plugin path (optional): marketplace `heygen-com/hyperframes`, then `/hyperframes:…`.

## Auth / secrets

- Local preview/render: no HeyGen account required for the open-source CLI path described upstream.
- Do **not** echo, commit, or paste provider API keys. If a hosted authoring flow asks for keys, the person enters them in their own UI / env; agents only reference env var **names**.
- Never store keys in `films/` or this library.

## Relation to OpenFilm

OpenFilm and HyperFrames are **different** stacks (OpenFilm: `film.html` + `frame(t)` + Studio NLE export; HyperFrames: composition HTML + `hyperframes render`). Pick one alternate rail per project; do not dual-render unless the user asks for a bake-off.

## Fork follow-ups

- [x] Export wrapper: `tools/hyperframes_export.sh` + `tools/handoff/hyperframes.py` (no secret handling)
- [x] Document needs-user blockers in export `lemo-manifest.json` / README
- [ ] Decision in BRIEF: `render_rail: playwright | hyperframes` (only if a greenfield film opts in)
- [ ] Quality gate parity (`quality.json`) if HyperFrames becomes a second delivery path
- [ ] Do **not** fake Opuscar Studio connect

## Export from a finished lemo film

```sh
bash tools/hyperframes_export.sh /path/to/film   # writes hyperframes-handoff/, runs lint
```

Composition = A-roll of the muxed MP4 + shot-label overlays from `timeline.parsed.json`. This is a handoff/bake-off package, not a migration of locked demo engines.
