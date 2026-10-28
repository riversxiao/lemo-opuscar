# NLE / alternate-rail handoff (OpenFilm · HyperFrames)

**Status (2026-10-29):** export path is **real** on this box — not stub-only docs.

| Rail | Command | Writes | Verified here |
|---|---|---|---|
| **OpenFilm** | `bash tools/openfilm_handoff.sh <film_dir>` | `<film>/openfilm-handoff/` multi-shot `film.html`, `timeline.edl`, `rebuild_shots.sh`, `manifest.json`, stems | `npx openfilm look` contact sheet OK; Studio `open` needs one-time browser download |
| **HyperFrames** | `bash tools/hyperframes_export.sh <film_dir>` | `<film>/hyperframes-handoff/` `index.html` + `lemo-manifest.json` | `npx hyperframes lint` OK; desktop/cloud/skills = **needs-user** |
| **Controller** | `python3 tools/deepseek-controller/cli.py handoff --project <film> --target both [--lint]` | both | fixture tests in `test_mvp.sh` |

Python package: `tools/handoff/` (`openfilm`, `hyperframes`, `common`).

## What is claimed vs what runs

| Claim | Reality |
|---|---|
| Single-clip MP4 pack | **Superseded** — v2 emits one `<video #t=in,out>` per timeline shot |
| Full lemo → `frame(t)` OpenFilm pages | **Still not done** (and not required for NLE handoff) |
| Premiere / Resolve XML | **Not done** — use CMX3600 `timeline.edl` + master, or Studio export |
| HyperFrames replaces Playwright mux | **No** — export wraps finished mux; default rail unchanged |
| Opuscar Studio connect | **No** — unrelated; see `tools/deepseek-controller/docs/STUDIO.md` |

## Hard blockers (honest)

- **OpenFilm Studio GUI:** first `npx openfilm open` downloads Chromium (~100MB). Headless `look` works after that cache exists.
- **HyperFrames desktop / HeyGen cloud / `auth` / interactive skills:** needs the person; local `lint` / optional `render` do not.
- **Paid paths:** do not call `hyperframes cloud` or paste keys unless the user asks.

## Example (finished controller film)

```sh
FILM=/workspace/films/fensan-pictogram-finance-v001
bash tools/openfilm_handoff.sh "$FILM"
bash tools/hyperframes_export.sh "$FILM"   # includes --lint

cd "$FILM/openfilm-handoff" && npx -y openfilm@latest look
cd "$FILM/hyperframes-handoff" && npx -y hyperframes@0.8.212 lint
```
