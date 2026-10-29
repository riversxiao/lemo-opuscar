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
| `content/engine.lock.json` | SHA-256 of protected files after demo copy, plus `aspect` (`16:9` / `9:16`) and render `size` (`1920x1080` / `1080x1920`) |
| Root / audio sidecars | Style-specific (see below) |
| `voices/dur.json`, `timeline.parsed.json`, `quality.json` | After TTS / schedule / quality |
| `PROJECT.md` | Next commands |

## Aspect (16:9 / 9:16)

Plan `aspect` is optional (default `16:9`). Allowed per style: `manifests/<slug>.json` → `aspects` (caption-news and swiss-motion: `16:9`, `9:16`; pictogram-motion: `16:9`). The aspect is content, not engine: it only changes the `--size` passed to `core/render/*.mjs` (recorded in `engine.lock.json` and `PROJECT.md`) and the frame used by touchable overlays such as Swiss `texts_runtime.json`. Locked cores are never edited to change the frame.

## Per-style thin glue

All three: copy `styles/<slug>/demo/` → project → `adapt` → sync touchables → lock hashes → `PROJECT.md`.

### Swiss
Sync root `lines.json`, `palette.json` sidecar, `CREDITS`. Leave `events.json` for later. Do **not** patch `film.js` `C`.
Scaffold also fetches missing `fonts/*.ttf` (gitignored binaries; Flash still must not edit fonts) and writes zh `voices/words_rel.json`.
Touchable `texts_runtime.json` → `page.mjs` installs `window.TEXTS(t)` (film.js/main.js hashes locked). Without it: readcheck `NOT_APPLICABLE` (`swiss-demo-without-registry`).
`apply_swiss_texts.py` uses the project aspect: 16:9 boxes in 1920x1080, 9:16 portrait boxes (`POS_BOX_PORTRAIT`) in 1080x1920, all clamped inside the frame.

### Pictogram
Sync root `edl_content.json`, `lines.json`, `palette.json`, `CREDITS`. Do **not** rewrite `edl.js` / `engine.js` / `scenes.js`.

### Caption
Sync root `timeline.json` (engine-fetched), `lines.json`, `audio/lines.json`, `facts.json`, `FACTS.md`, `palette.json`, `CREDITS`. Do **not** rewrite `main.js` (including hardcoded `SHOTS`).

## Caption style versions

`apply_caption_style_version.py --version liquidity-v001` unlocks **main.js only** on a sibling project. Default scaffold / `liudong-controller-e2e` keep demo `main.js` hash-locked.
