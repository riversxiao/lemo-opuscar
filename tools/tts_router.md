# TTS router contract (Chinese + multilingual)

Shared interface for every voice provider in this fork. Matches `core/tts/tts_zh.py` / `tts.py` I/O so timeline code does not care which synthesizer ran.

## CLI

```sh
# readiness (honest: ready | deps-missing | needs-server)
python core/tts/tts_router.py --list
python core/tts/tts_router.py --list --json

# synthesize
python core/tts/tts_router.py lines.json out_dir \
  [--provider edge|kokoro|qwen3|omnivoice|stepaudio|auto] \
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
| `stepaudio` | `providers/stepaudio.py` | StepFun cloud | **needs-key** until `STEPFUN_API_KEY` is set; explicit only (not in `auto`) |

### StepAudio (StepFun free preview)

- Model allowlist: `stepaudio-3-gen-preview` (VO, `POST /v1/audio/generate`, voice designed by a text role
  description) and `stepaudio-3-music-preview` (instrumental bed, used by `music_bed.py --bed-source stepaudio`).
  Both are 限时免费 on the StepFun pricing page. Paid TTS (`/v1/audio/speech`, `stepaudio-3-tts`, `step-tts-*`) and
  ASR are refused in code.
- Env: `STEPFUN_API_KEY` (or `STEP_API_KEY`), `LEMO_TTS_STEPAUDIO_BASE` (default `https://api.stepfun.com/v1`),
  `LEMO_TTS_STEPAUDIO_ROLE` (voice description), `LEMO_TTS_STEPAUDIO_SPEED`, `LEMO_TTS_STEPAUDIO_TAKES` (default 4),
  `LEMO_TTS_STEPAUDIO_F0_TOL_ST` (default 2.0). Edge voice ids in `lines.json` are ignored.
- Limits: ≤4 concurrent, ≥0.7 s between requests (<100 RPM); 429/5xx retried with backoff; 401/402/404 stop.
- No voice id/seed exists in the preview, so the provider measures median F0 per line, sets the film target to the median
  of medians, and re-takes lines >2 semitones off (keeps the closest take). `voices/stepaudio_meta.json` records it.

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
