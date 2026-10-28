# Touchable vs protected files

Controller / Flash / thin glue may **only** write content-side artifacts. Engine cores stay byte-identical to the style demo until a maintainer publishes a new style version.

## Always protected (never rewrite in a film project)

Typical globs (see each `manifests/*.json` → `protectedGlobs` / `glue_base.PROTECTED_BY_STYLE`):

| Style | Locked cores |
|---|---|
| swiss-motion | `ease.js`, `film.js`, `main.js`, `mix.py`, `index.html`, `fonts/**`, `tools/**` |
| pictogram-motion | `engine.js`, `edl.js`, `scenes.js`, `render.mjs`, `shot.mjs`, `poses/**`, `index.html`, `fonts/**` |
| caption-news | `main.js`, `index.html`, `build.sh`, `fonts/**`, `tools/**`, `assets/**` |

Changing these requires an expert PR + regression — not a per-film Flash edit.

## Touchable (controller + thin glue)

Written under `<project>/` by `adapt` / `scaffold`:

| Path | Role |
|---|---|
| `content/plan.json` | Validated plan snapshot |
| `content/lines.json` | VO / subtitle source lines |
| `content/shots.json` / `edl_content.json` / `timeline_content.json` | Style-shaped shot list |
| `content/palette.json` | Palette constants |
| `content/credits.json` | Title / author / license |
| `content/TOUCHABLES.md` | Per-project contract |
| `content/engine.lock.json` | SHA-256 of protected files after demo copy |
| Root / audio sidecars | Style-specific (see below) |
| `voices/dur.json`, `timeline.parsed.json`, `quality.json` | After TTS / schedule / quality |
| `PROJECT.md` | Next commands |

## Per-style thin glue

All three: copy `styles/<slug>/demo/` → project → `adapt` → sync touchables → lock hashes → `PROJECT.md`.

### Swiss
Sync root `lines.json`, `palette.json` sidecar, `CREDITS`. Leave `events.json` for later. Do **not** patch `film.js` `C`.

### Pictogram
Sync root `edl_content.json`, `lines.json`, `palette.json`, `CREDITS`. Do **not** rewrite `edl.js` / `engine.js` / `scenes.js`.

### Caption
Sync root `timeline.json` (engine-fetched), `lines.json`, `audio/lines.json`, `facts.json`, `FACTS.md`, `palette.json`, `CREDITS`. Do **not** rewrite `main.js` (including hardcoded `SHOTS`).
