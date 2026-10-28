# TTS router contract (Chinese + multilingual)

Shared interface for every voice provider in this fork. Matches `core/tts/tts_zh.py` / `tts.py` I/O so timeline code does not care which synthesizer ran.

## CLI

```sh
# readiness (honest: ready | deps-missing | needs-server)
python core/tts/tts_router.py --list
python core/tts/tts_router.py --list --json

# synthesize
python core/tts/tts_router.py lines.json out_dir \
  [--provider edge|kokoro|qwen3|omnivoice|auto] \
  [--fallback edge,kokoro] [--voice …] [--rate +0%] [--pitch +0Hz]
```

Controller mirror:

```sh
python3 tools/deepseek-controller/cli.py tts --list
python3 tools/deepseek-controller/cli.py tts --project /path/to/film \
  --provider auto --fallback kokoro,edge
```

Defaults: **`edge`** (Yunxi). Env overrides: `LEMO_TTS_PROVIDER`, `LEMO_TTS_FALLBACK`, `LEMO_TTS_PYTHON` (interpreter for subprocess providers).

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
- Provider-specific voice names belong in `voice` or provider env defaults. Kokoro strips Microsoft `*Neural` names and uses `zf_xiaoxiao` for CJK.

## Output · `out_dir/`

| Artifact | Meaning |
|---|---|
| `<id>.wav` | 24 kHz mono WAV, leading/trailing silence trimmed |
| `dur.json` | `{ "<id>": seconds, … }` |
| `tts_router.json` | (controller only) provider used + readiness snapshot |
| `.cache/` | edge-tts mp3 cache |

## Providers (this box)

| id | Module | Network | Status |
|---|---|---|---|
| `edge` | `tts_zh.py` / edge-tts | required (Microsoft) | **ready** · default Yunxi |
| `kokoro` | `tts.py` + `lang: cmn` | offline | **ready** when `.venv-voice` (or `LEMO_TTS_PYTHON`) has `kokoro-onnx` and weights exist |
| `qwen3` | `providers/http_speech.py` | optional HTTP | **needs-server** until `LEMO_TTS_QWEN3_BASE` is set |
| `omnivoice` | same HTTP client | optional HTTP | **needs-server** until `LEMO_TTS_OMNIVOICE_BASE` is set |

### Enable kokoro (offline second path)

Weights are already fetched by `sh tools/fetch.sh voice` (~350 MB under `core/tts/`). Create a 3.12 voice venv (not committed):

```sh
uv venv .venv-voice --python 3.12
uv pip install --python .venv-voice/bin/python kokoro-onnx soundfile numpy edge-tts
python core/tts/tts_router.py --list   # kokoro → ready
```

Or point `LEMO_TTS_PYTHON` at any interpreter that can `import kokoro_onnx`.

### Enable qwen3 / omnivoice (self-hosted)

HTTP client is implemented (stdlib + ffmpeg). **No API keys are shipped or invented.**

```sh
# example — only after YOU start a local OpenAI-compatible speech server
export LEMO_TTS_QWEN3_BASE=http://127.0.0.1:8091/v1
# optional:
# export LEMO_TTS_QWEN3_MODEL=tts-1
# export LEMO_TTS_QWEN3_API_KEY=…   # only if your server requires one

python core/tts/tts_router.py --list          # qwen3 → ready
python core/tts/tts_router.py lines.json out --provider qwen3
```

Same pattern for OmniVoice: `LEMO_TTS_OMNIVOICE_BASE=http://127.0.0.1:8880/v1`.

Self-host references (do not vendor weights here):

- Qwen3-TTS: `Qwen/Qwen3-TTS-12Hz-*` via vLLM-Omni or community FastAPI
- OmniVoice: `k2-fsa/OmniVoice`; Docker API e.g. `diogod2r/OmniVoice-FastAPI`

Extra notes: [`requirements-voice-extra.txt`](../requirements-voice-extra.txt).

## Selection rules

- `--provider edge|kokoro|…` — try that first; then `--fallback` list (skip entries that are not ready).
- `--provider auto` — first **ready** provider in the fallback / default order (`edge,kokoro`, then HTTP if configured).
- Empty `--fallback ''` disables retries.

## Completeness (all providers)

Skipping ASR **word** alignment for Chinese does **not** skip VO content checks. Whatever provider produced the WAVs:

1. Every `lines.json` id has a non-silent WAV and a `dur.json` entry.
2. Final mix still contains that speech (ebur128 / ffmpeg detect / asr_check when applicable).
3. On-screen / subtitle Chinese must match spoken content (allow punctuation); no silent shortenings.

See `AGENTS.deepseek.md` · VO / TTS notes.
