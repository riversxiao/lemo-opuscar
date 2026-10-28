# TTS router contract (Chinese + multilingual)

Shared interface for every voice provider in this fork. Matches `core/tts/tts_zh.py` / `tts.py` I/O so timeline code does not care which synthesizer ran.

## CLI

```sh
python core/tts/tts_router.py lines.json out_dir [--provider edge|kokoro|qwen3|omnivoice] [provider flags…]
```

Default provider: **`edge`** (`tts_zh.py`, Yunxi / Xiaoxiao Neural via Microsoft edge-tts).

## Input · `lines.json`

```json
[
  {
    "id": "s1",
    "text": "字幕与画面用的句子。",
    "say": "可选：实际送去朗读的文本",
    "voice": "zh-CN-YunxiNeural",
    "rate": "+0%",
    "pitch": "+0Hz",
    "speed": 1.0
  }
]
```

- `text` — canonical line (subtitles / on-screen); VO completeness checks compare against this (or `say` when present — see AGENTS.deepseek).
- `say` — optional speak-as form (numbers expanded, etc.).
- `rate` / `pitch` — edge-tts style; numeric `speed` accepted as multiplier (same as `tts_zh.py`).
- Provider-specific voice names belong in `voice` or provider env defaults.

## Output · `out_dir/`

| Artifact | Meaning |
|---|---|
| `<id>.wav` | 24 kHz mono WAV, leading/trailing silence trimmed (same as `tts_zh.py`) |
| `dur.json` | `{ "<id>": seconds, … }` |
| `.cache/` | provider cache (optional; edge uses this today) |

## Providers

| id | Module | Network | Status |
|---|---|---|---|
| `edge` | `core/tts/tts_zh.py` | required (Microsoft) | **default · implemented** |
| `kokoro` | `core/tts/tts.py` + `lang: cmn` | offline | implemented (plain timbre) |
| `qwen3` | HTTP OpenAI-compatible `/v1/audio/speech` | local server | **stub** — see `providers/qwen3.py` |
| `omnivoice` | HTTP OpenAI-compatible `/v1/audio/speech` | local server | **stub** — see `providers/omnivoice.py` |

Self-host references (do not vendor weights here):

- Qwen3-TTS: `Qwen/Qwen3-TTS-12Hz-*` via vLLM-Omni speech API or community FastAPI (`groxaxo/Qwen3-TTS-Openai-Fastapi`, `second-state/qwen3_audio_api`)
- OmniVoice: `k2-fsa/OmniVoice`; Docker API e.g. `diogod2r/OmniVoice-FastAPI` (`POST /v1/audio/speech`)

Extra Python deps for future local clients: [`requirements-voice-extra.txt`](../requirements-voice-extra.txt) (comments only until a provider is switched on).

## Completeness (all providers)

Skipping ASR **word** alignment for Chinese does **not** skip VO content checks. Whatever provider produced the WAVs:

1. Every `lines.json` id has a non-silent WAV and a `dur.json` entry.
2. Final mix still contains that speech (ebur128 / ffmpeg detect / asr_check when applicable).
3. On-screen / subtitle Chinese must match spoken content (allow punctuation); no silent shortenings.

See `AGENTS.deepseek.md` · VO / TTS notes.
