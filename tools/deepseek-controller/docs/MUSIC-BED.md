# Controller music bed (no locked `music.py`)

## Problem

Style demos ship locked score scripts that do **not** track content EDL length:

| Style | Locked score | Why controller cannot use it as-is |
|---|---|---|
| pictogram-motion | `music/music.py` | Olympics 163.6 s / section asserts on demo `timeline.json` |
| caption-news | `audio/mix.py` | Needs freepats + `swarm.wav` bee natural sound |
| swiss-motion | `music/score.py` + `mix.py` | Freepats sampler + demo `events.json` / 44 s poster score |

Earlier E2E used **`mix_vo_only.py`** (VO + silence). Loudnorm still hit −14 LUFS, but films had no bed.

## Solution

`tools/deepseek-controller/music_bed.py` (also `cli.py mix`):

1. Synthesize a **placeholder procedural bed** (pure numpy softsine pad + soft pulse; **no freepats / scipy / huge samples in git**), **or** load `--bed path.wav`.
2. Place VO from `timeline.json` + `voices/*.wav`.
3. Duck bed under VO (~−9 dB).
4. Write touchable stem `music/bed.wav` + `music/bed_meta.json`, and `out/mix.wav` for `core/render/mux.sh`.

```bash
python3 tools/deepseek-controller/cli.py mix --project "$P" --preset soft-pulse
# or:
python3 tools/deepseek-controller/music_bed.py --project "$P"
# VO-only fallback:
python3 tools/deepseek-controller/cli.py mix --project "$P" --vo-only
```

Presets: `soft-pulse` (default) · `pad` · `silence` (VO-only equivalent).

Replace the stem anytime: drop a new WAV and re-run with `--bed music/my.wav`. Meta `label` always marks synthesized beds as **placeholder**.

## Freepats / sampler (optional upgrade)

Installable, **not** required for controller E2E:

```bash
sh tools/fetch.sh instruments freepats   # ~397 MB under core/audio/instruments/freepats (gitignored)
# sampler needs scipy — use the repo venv after music deps:
#   sh plugin/skills/lemo-opuscar/scripts/setup.sh deps music
.venv/bin/python -c "from core.audio import sampler as S; print('ok')"
```

See `core/audio/INSTRUMENTS.md` and `docs/integrations/local-music.md` (YuE2/Plenio person-operated path).  
Do **not** commit sample packs or long WAV beds into the library clone.

## E2E proof (box)

`/workspace/films/fensan-pictogram-finance-v001` remuxed with `mix --preset soft-pulse`:

- `music/bed.wav` + `out/mix.wav` → mux → **I=−14.2 LUFS / TP=−1.1 dBTP**
- `quality --delivery` → **PASS** (`evidence/quality-music-bed-delivery.json`)

Locked `music/music.py` hash untouched.
