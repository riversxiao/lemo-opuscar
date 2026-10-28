# Local music tier · YuE2 / Plenio

**Status:** research note (medium). Default music path stays lemo sampler / `requirements-music.txt` / hand-written beds. External Suno remains a **person-operated** option, not an agent secret flow.

## Why

Word-card films often need a short bed that is not a one-bar `pluck` loop. Local full-song models reduce cloud dependency for music tier experiments.

## Options

| Stack | What | Hardware / license notes |
|---|---|---|
| **YuE2** ([M·A·P / YuE](https://github.com/multimodal-art-projection/YuE)) | Lyrics + style → song; editable melody/chord plan | Official path: Linux, Python 3.12, NVIDIA BF16, **~24 GB VRAM**; weights often **CC BY-NC** with creator carve-outs — companies need a commercial check |
| **Plenio** ([jplenio/Plenio-Music-Production-System](https://github.com/jplenio/Plenio-Music-Production-System)) | ComfyUI nodes around YuE2 / MiniMax Music 3, Song Sheet, stems, mastering | Apache-2.0 code; still inherits model weight licenses; runs in ComfyUI |

## Integration sketch (future)

1. Person runs YuE2/Plenio **outside** the lemo venv; exports 30–45 s bed WAV (or stem).
2. Drop into film `audio/music.wav` (or `bed.wav`); lemo `mix.py` ducks under VO as today.
3. BRIEF records: model name, seed/prompt, license, file hash — same spirit as VO provenance in `quality.json` plans.

Do **not** download YuE2 weights into this library clone by default.

## Relation to OpenFilm `get`

OpenFilm Studio can pull music via connected providers; that is separate from local YuE2. Prefer one music source per film for rights clarity.

## Controller placeholder bed

For DeepSeek controller E2E (when locked demo `music.py` / freepats / swarm are unavailable), use:

`tools/deepseek-controller/music_bed.py` or `cli.py mix` → `music/bed.wav` + ducked VO → `out/mix.wav`.

Documented in `tools/deepseek-controller/docs/MUSIC-BED.md`. Freepats remains optional via `sh tools/fetch.sh instruments freepats`.

