# core/: the shared production tools

Command reference for `core/` and `tools/`. How the pieces fit together is in [`TECHNIQUE.md`](../TECHNIQUE.md). Run commands from the library root (`$LIB` in skill mode); Python is the library's `.venv/bin/python`. `<demo>` is any folder with an `index.html`.

## Install

| Command | What it does |
|---|---|
| `sh plugin/skills/lemo-opuscar/scripts/setup.sh` | find, clone or update the library; prints `LIB=<path>` |
| `… setup.sh deps` | core tier: npm packages, headless browser, `.venv` from `requirements.txt` |
| `… setup.sh deps voice` | adds `requirements-voice.txt` (kokoro-onnx, edge-tts, faster-whisper) and the Kokoro model |
| `… setup.sh deps music` | adds `requirements-music.txt` (numba, for `pluck.py`; `sampler.py` needs only the core) |
| `… setup.sh demo <slug>` | adds one style's demo source and poster (to read, not to render) |
| `sh tools/fetch.sh voice` \| `hdri` \| `instruments <lib>` \| `instruments all` | Kokoro model · HDRIs · a sample library (`freepats`, `karoryfer`, `salamander`, `vcsl`, `vsco2ce`) |

Sizes are in TECHNIQUE.md §1.

## The page contract

| Global | Required | Meaning |
|---|---|---|
| `window.READY = true` | yes | set once fonts and images are loaded |
| `window.render(t)` | yes | draw the frame at second `t`; deterministic |
| `window.DUR` | video, events, readcheck | film length in seconds |
| `window.EV = [{t, type, …}]` | no | sound and cue events, exported by `events.mjs` |
| `window.TEXTS(t)` | readcheck | `[{id, text, x0, y0, x1, y1}]`: every on-screen text visible at `t`, with its box in pixels. Report an element's **full** text from its first visible frame (a typewriter that reports only the typed letters fails the check) |

The viewport is 1920×1080 at device scale 1, or `--size WxH`; the page reads its frame from `innerWidth` × `innerHeight` (a demo that hardcodes 1920×1080 is cropped, not re-laid out, at other sizes: see **Portrait reframe** below). `--q 'k=v&…'` reaches the page as `location.search`. A page error, or an HTTP error on a script, module or the page, stops the tool (exit 1). Other missing files (fetch, images, fonts) print `optional file missing: <URL>` and the tool carries on. The tools wait up to 180 s for `window.READY`.

## Render

| Command | What it does |
|---|---|
| `node core/render/still.mjs <demo> <t> [<t> …] [--range a:b:step] [--prefix t_] [--out dir] [--native \| --reframe]` | review stills as JPEGs (default `<demo>/stills/t_<t>.jpg`) |
| `node core/render/video.mjs <demo> [--fps 24] [--workers 3] [--out <demo>/out/video.mp4] [--native \| --reframe]` | every frame to a video; up to 6 workers for a single render. Each parallel version needs its own `--out` |
| `node core/render/events.mjs <demo> [--out <file>]` | export `{dur, ev}` to `<demo>/events.json` |
| `node core/render/readcheck.mjs <demo> [--step 0.04] [--latin-cps 15] [--cjk-cps 4.5] [--pad 1.5] [--min 1.5]` | reading-time check (below) |
| `.venv/bin/python core/render/sheet.py out.jpg img… [--cols 4] [--w 480]` | contact sheet |
| `.venv/bin/python core/render/srt.py cues.json out.srt` | subtitles from `[{t0, t1, text}]` |
| `sh core/render/mux.sh video.mp4 mix.wav out.mp4 [fps=24] [grain=2]` | mux and master (below) |

All four page tools take `--size WxH` (default `1920x1080`, even numbers) and `--q 'k=v'`. Pass the same size to all of them for one film, e.g. `--size 1080x1920` for vertical; `readcheck` checks the boxes against that frame.

**Portrait reframe.** Every `styles/<slug>/style.json` says `"portrait": "native"` (the demo has its own 9:16 layout: Caption News, Swiss Motion) or `"reframe"` (every other style: its demo is a 16:9 film laid out for 1920×1080). For a portrait `--size` (height above width) and a `reframe` style, `still.mjs` and `video.mjs` render the page at 1920×1080 and place the **whole** 16:9 frame, scaled to the width and centred (1080×608 at y 656 in 1080×1920), over a darkened, blurred copy of the same frame, or over a flat colour when `style.json` has `"portraitFill": "#rrggbb"`. Nothing is cropped, so no text is lost; it is a letterbox, not a portrait composition, and the tool prints one `[reframe]` line saying so. `video.mjs` does it in the ffmpeg encode (one filter, little extra cost); `readcheck.mjs` checks the 1920×1080 page. `--native` renders the page at the requested size instead (what you want once a page lays itself out for 9:16), `--reframe` forces the reframe. Folders without a `style.json` (your film) are native: the page gets the size you ask for. Landscape sizes are never reframed. To give a style a native portrait layout, branch on `innerWidth` / `innerHeight` (the `P(land, port)` helper in `styles/caption-news/demo/main.js` picks a value per frame shape), keep the 16:9 branch exactly as it was, then set `"portrait": "native"` and add `"9:16"` to `aspects` (code in `core/render/reframe.mjs`).

**readcheck** asks the page for `window.TEXTS(t)` at every step. Each text must stay fully in frame, unchanged, for at least CJK characters ÷ 4.5 + other non-space characters ÷ 15 + 1.5 s, and never less than `--min`. A new `text` under the same `id` starts a new piece. Subtitles are checked by their `.srt`, not here.

**mux** runs a two-pass `loudnorm` to −14 LUFS / true peak −1.2 dB, adds film grain (`grain` 0 = none) and prints the measured loudness. Silent audio is left at its level with a warning; short audio is padded, long audio cut at the picture's end; missing, damaged or truncated audio is refused. It never leaves a partial file.

## Audio

| Command | What it does |
|---|---|
| `.venv/bin/python core/tts/tts.py lines.json out_dir` | Kokoro, offline. `lines.json` = `[{id, text, voice?, speed?, lang?}]` (defaults `af_bella`, `0.92`, `en-us`; Chinese: `"lang": "cmn"`, a `zf_*`/`zm_*` voice). Writes `<id>.wav` (24 kHz, trimmed) and `dur.json`. Needs a library path under 160 bytes (espeak-ng); it checks |
| `.venv/bin/python core/tts/tts_zh.py lines.json out_dir [--voice zh-CN-XiaoxiaoNeural] [--rate +0%] [--pitch +0Hz]` | edge-tts (Microsoft), online; same outputs as `tts.py`. Per line: `voice`, `rate`, `pitch`, `say` (what is spoken when it differs from `text`). Caches in `out_dir/.cache/`. Voices: `.venv/bin/python -m edge_tts --list-voices` |
| `.venv/bin/python core/tts/asr_check.py lines.json voices_dir [--lang en\|zh\|auto] [--threshold 0.92] [--model base]` | speech-to-text check of every `<id>.wav`; writes `words.json` (word timestamps). English must match word for word (0–999 count the same as their words); Chinese, Japanese, Korean compare by character similarity ≥ `--threshold`. An `asr` field in a line overrides the expected text (names, decimals, times: write it as Whisper does) |
| `core/audio/sfx.py` | procedural foley and mix helpers: filters, envelopes, `click`, `whoosh`, `thump`, `ding`…, `compress`, `limit`, `add(buf, sound, at, gain, pan)` |
| `core/audio/sampler.py`, `core/audio/pluck.py` | sampled instruments and plucked-string modelling ([`audio/INSTRUMENTS.md`](audio/INSTRUMENTS.md)). A missing library is named in the error with its `fetch.sh instruments <lib>` command. `credits(names)` writes the CREDITS lines |

## Picture helpers

| File | What it is |
|---|---|
| `core/lib.js` | seeded random `mulberry`, `hash`, `vnoise`, `clamp(x,a,b)`, `lerp(a,b,t)`, `seg(t,a,b)` (0→1 between a and b), easing on 0–1 (`ss(t)`, `eio(t)`, `eo(t)`, `ei(t)`, `back(t,s)`, `spring(t,k,z)`), `monotone`/`track` interpolation, envelope `env` |
| `core/three/post.js` | three.js post: physical depth of field, GTAO, bloom, colour grade, 2× supersampling |
| `core/post/crt.js` | WebGL2 CRT / VHS pass over a 2D canvas |
| `core/fonts/` | Fredoka, Lilita One, IM Fell English, ZCOOL KuaiLe (OFL, [`fonts/OFL.md`](fonts/OFL.md)) as subsets; ZCOOL holds only ≈ 200 characters |
| `core/assets/polyhaven/` | CC0 HDRIs and models (`SOURCES.md`) |

## Environment variables

| Variable | Meaning |
|---|---|
| `WORDFILM_HOME` | where `setup.sh` keeps the library (default `~/wordfilm`; an existing `~/lemo-opuscar` library is still used when `~/wordfilm` does not exist). The old name `LEMO_OPUSCAR_HOME` still works; `WORDFILM_REPO` and `WORDFILM_PIN` (old names `LEMO_OPUSCAR_REPO`, `LEMO_OPUSCAR_PIN`) choose the clone URL and a commit for the DeepSeek setup |
| `PLAYWRIGHT_CHROME` | a Chrome / headless-shell executable instead of Playwright's |
| `LEMO_ANGLE` | WebGL backend (default `metal` on macOS; `default` passes none) |
| `RENDER_SLOTS` | optional; limits concurrent full renders across processes |
| `LEMO_COLOR=bt709` | `mux.sh` writes limited-range BT.709 instead of the default full-range output |
| `WHISPER_MODEL` | Whisper model name or local folder for `asr_check.py` (same as `--model`; default `base.en` for English, `small` for Chinese, `base` otherwise) |
| `HF_ENDPOINT` | Hugging Face mirror for the Whisper download |

## Exit codes

| Tool | 0 | 1 | 2 |
|---|---|---|---|
| render tools | done | page error, missing required file, ffmpeg failure | usage, no `index.html`, `--out` already being written |
| `readcheck.mjs` | all texts long enough | some too short or never fully visible | could not check (no `TEXTS`) |
| `mux.sh` | film written | any failure | – |
| `tts.py`, `srt.py` | done | bad input, missing model, path too long | usage |
| `tts_zh.py` | done | bad input | network unreachable |
| `asr_check.py` | all lines pass | mismatches | model failed to load |
