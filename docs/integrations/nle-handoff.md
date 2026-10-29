# NLE / alternate-rail handoff (OpenFilm · HyperFrames · Premiere XML)

**Status (2026-10-29):** export path is **real** on this box — OpenFilm + HyperFrames
packages plus honest FCP `xmeml` for Premiere/Resolve **import**.

| Rail | Command | Writes | Verified here |
|---|---|---|---|
| **OpenFilm** | `bash tools/openfilm_handoff.sh <film_dir>` | `<film>/openfilm-handoff/` multi-shot `film.html`, `timeline.edl`, **`premiere.xml`**, `rebuild_shots.sh`, `manifest.json`, stems | `npx openfilm look` contact sheet OK; Studio `open` needs one-time browser download |
| **HyperFrames** | `bash tools/hyperframes_export.sh <film_dir>` | `<film>/hyperframes-handoff/` `index.html` + `lemo-manifest.json` | `npx hyperframes lint` OK; desktop/cloud/skills = **needs-user** |
| **Premiere XML** | `bash tools/premiere_handoff.sh <film_dir>` | `<film>/premiere-handoff/` `premiere.xml` (xmeml v5) + master + EDL | artifact only on box (no Premiere installed); import on a desktop NLE |
| **Controller** | `python3 tools/deepseek-controller/cli.py handoff --project <film> --target all` | openfilm + hyperframes + premiere | fixture tests in `test_mvp.sh` |

Python package: `tools/handoff/` (`openfilm`, `hyperframes`, `premiere`, `common`).

## What is claimed vs what runs

| Claim | Reality |
|---|---|
| Single-clip MP4 pack | **Superseded** — v2 emits one `<video #t=in,out>` per timeline shot |
| Full lemo → `frame(t)` OpenFilm pages | **Still not done** (and not required for NLE handoff) |
| Premiere / Resolve XML | **Done as xmeml v5** — import path only; **not** `.prproj` / AAF / `.drp` |
| HyperFrames replaces Playwright mux | **No** — export wraps finished mux; default rail unchanged |
| Opuscar Studio connect | **No** — unrelated; see `tools/deepseek-controller/docs/STUDIO.md` |

## Hard blockers (honest)

- **OpenFilm Studio GUI:** first `npx openfilm open` downloads Chromium (~100MB). Headless `look` works after that cache exists.
- **HyperFrames desktop / HeyGen cloud / `auth` / interactive skills:** needs the person; local `lint` / optional `render` do not.
- **Premiere / Resolve:** not installed on the box; verify `premiere.xml` import on a desktop. Keep `premiere.xml` beside `assets/master.mp4`.
- **Paid paths:** do not call `hyperframes cloud` or paste keys unless the user asks.

## Example (matrix / controller film)

```sh
FILM=/workspace/films/matrix-fuli-pictogram-controller
# or: FILM=/workspace/films/fensan-pictogram-finance-v001

bash tools/openfilm_handoff.sh "$FILM"
bash tools/hyperframes_export.sh "$FILM"   # includes --lint
bash tools/premiere_handoff.sh "$FILM"

cd "$FILM/openfilm-handoff" && npx -y openfilm@latest look
# Premiere desktop: File → Import → premiere.xml (from openfilm-handoff/ or premiere-handoff/)
cd "$FILM/hyperframes-handoff" && npx -y hyperframes@0.8.212 lint
```
