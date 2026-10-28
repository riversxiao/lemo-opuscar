# Touchable vs protected files

Controller / Flash / thin glue may **only** write content-side artifacts. Engine cores stay byte-identical to the style demo until a maintainer publishes a new style version.

## Always protected (never rewrite in a film project)

Typical globs (see each `manifests/*.json` → `protectedGlobs`):

- Motion / ease / shaders: `ease.js`, `engine.js`, `film.js`, `*.frag`, `*.vert`, `poses/**`
- Page shell: `index.html`, `main.js` (Swiss), `cover.html`
- Mix / build scripts: `mix.py`, `mux.sh`, `build.sh`, `tools/**`
- Bundled fonts: `fonts/**`

Changing these requires an expert PR + regression — not a per-film Flash edit.

## Touchable (controller + thin glue)

Written under `<project>/` by `adapt` / `scaffold`:

| Path | Role |
|---|---|
| `content/plan.json` | Validated plan snapshot |
| `content/lines.json` | VO / subtitle source lines |
| `content/shots.json` / `edl_content.json` / `timeline_content.json` | Style-shaped shot list |
| `content/palette.json` | Palette constants (sidecar; Swiss demo `film.js` `C` is still protected) |
| `content/credits.json` | Title / author / license |
| `content/TOUCHABLES.md` | Per-project copy of this contract |
| `content/engine.lock.json` | SHA-256 of protected files right after demo copy |
| `lines.json` (Swiss root) | Engine-fetched lines (synced from `content/lines.json`) |
| `palette.json` (root sidecar) | Same palette for tooling; does **not** patch `film.js` |
| `CREDITS` | Human-readable credits text |
| `voices/dur.json`, `timeline.parsed.json`, `quality.json` | After TTS / schedule / quality |
| `PROJECT.md` | Next commands |

## Swiss thin glue specifically

1. Copy `styles/swiss-motion/demo/` → project.
2. `adapt` → `content/*`.
3. Sync root `lines.json` + `CREDITS` + root `palette.json` sidecar.
4. Leave `events.json` for later (`events.mjs` / schedule cues) — do not hand-edit foley timelines in Flash.
5. Hash-check protected files vs `content/engine.lock.json`.

Pictogram / Caption scaffolds today: **copy demo + adapt only** (no deep wire into `scenes.js` / caption `main.js` yet).
