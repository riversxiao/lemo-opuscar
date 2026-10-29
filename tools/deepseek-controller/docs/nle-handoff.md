# Controller → NLE handoff

After mux + `--delivery` PASS, package the finished film for OpenFilm, HyperFrames,
or Premiere-adjacent (FCP XML) import.

```sh
# OpenFilm + HyperFrames (default)
python3 tools/deepseek-controller/cli.py handoff \
  --project /workspace/films/matrix-fuli-pictogram-controller \
  --target both --lint

# All three rails (adds premiere-handoff/)
python3 tools/deepseek-controller/cli.py handoff \
  --project /workspace/films/matrix-fuli-pictogram-controller \
  --target all

# Premiere / Resolve import only (xmeml — not .prproj)
python3 tools/deepseek-controller/cli.py handoff \
  --project /workspace/films/fensan-pictogram-finance-v001 \
  --target premiere
```

Frame size and rate: `--size WxH` (even, 16..8192) and `--fps` (24, 29.97 or
30000/1001) override; otherwise ffprobe of the master MP4 decides, and without
ffprobe the default is 1920x1080 @ 24fps. A 9:16 film therefore exports at
1080x1920 into `premiere.xml`, `film.html` and the HyperFrames `index.html`
without extra flags. `--json` reports the resolved values and their source
(`flag` | `probe` | `default`).

POSIX wrappers (extra flags such as `--size` pass through):

| Rail | Wrapper |
|---|---|
| OpenFilm | `bash tools/openfilm_handoff.sh <film>` |
| HyperFrames | `bash tools/hyperframes_export.sh <film>` |
| Premiere XML | `bash tools/premiere_handoff.sh <film>` |

## What you get

| Target | Folder | Key artifacts |
|---|---|---|
| openfilm | `openfilm-handoff/` | multi-shot `film.html`, `timeline.edl`, **`premiere.xml`**, `rebuild_shots.sh`, stems |
| hyperframes | `hyperframes-handoff/` | `index.html` + shot markers, `lemo-manifest.json` (`needsUser`) |
| premiere | `premiere-handoff/` | `premiere.xml` (xmeml v5) + `assets/master.mp4` + EDL |

OpenFilm packages now also include `premiere.xml` so one export covers Studio *and*
a direct Premiere/Resolve import path.

## Honest limits

- Premiere path is **FCP XML import**, not a native `.prproj` / AAF / Resolve `.drp`.
- Picture = trims of the finished mux (not a `frame(t)` port of locked engines).
- Paid desktop apps are **not** required on the box — exports are artifacts only.
- HyperFrames desktop / HeyGen cloud / skills install = needs-user.
- Handoff appends a **$0** line to the budget ledger unless `--no-budget`.

Full inventory: [`docs/integrations/nle-handoff.md`](../../../docs/integrations/nle-handoff.md).
