# TTS router contract (Chinese + multilingual)

Shared interface for every voice provider in this fork. Matches `core/tts/tts_zh.py` / `tts.py` I/O so timeline code does not care which synthesizer ran.

## CLI

```sh
# readiness (honest: ready | deps-missing | needs-server)
python core/tts/tts_router.py --list
python core/tts/tts_router.py --list --json

# synthesize
python core/tts/tts_router.py lines.json out_dir \
  [--provider edge|kokoro|qwen3|omnivoice|stepaudio|elevenlabs|elevenlabs-dialogue|auto] \
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
| `elevenlabs` | `providers/elevenlabs.py` | ElevenLabs cloud | **needs-key** until `ELEVENLABS_API_KEY` is set; explicit only (not in `auto`) |
| `elevenlabs-dialogue` | `providers/elevenlabs_dialogue.py` | ElevenLabs cloud | **needs-key**; multi-speaker Text-to-Dialogue; explicit only |

### StepAudio (StepFun free preview)

- Model allowlist: `stepaudio-3-gen-preview` (VO, `POST /v1/audio/generate`, voice designed by a text role
  description) and `stepaudio-3-music-preview` (instrumental bed, used by `music_bed.py --bed-source stepaudio`).
  Both are 限时免费 on the StepFun pricing page. Paid TTS (`/v1/audio/speech`, `stepaudio-3-tts`, `step-tts-*`) and
  ASR are refused in code.
- Env: `STEPFUN_API_KEY` (or `STEP_API_KEY`), `LEMO_TTS_STEPAUDIO_BASE` (default `https://api.stepfun.com/v1`),
  `LEMO_TTS_STEPAUDIO_ROLE` (voice description), `LEMO_TTS_STEPAUDIO_SPEED`, `LEMO_TTS_STEPAUDIO_TAKES` (default 4),
  `LEMO_TTS_STEPAUDIO_F0_TOL_ST` (default 2.0). Edge voice ids in `lines.json` are ignored.
- Limits: ≤4 concurrent, ≥0.7 s between requests (<100 RPM); 429/5xx retried with backoff; 401/402/404 stop.
- The preview has no voice lock: `voice` / `voice_label` are documented as unsupported (a `voice` field is accepted
  with HTTP 200 but ignored — measured: a female voice id returns the same default male voice), reference_to_audio is
  not open, and voice cloning is paid-TTS only. Separate requests therefore come back as different speakers.
- `LEMO_TTS_STEPAUDIO_MODE=session` (default): every line goes into ONE request as consecutive scripts of the same
  speaker (≤1000 chars total), then the take is cut per line by aligning local faster-whisper character timings to the
  script and snapping cuts into pauses (`providers/vo_split.py`; <85% aligned chars → hard fail, no fallback).
  `per-line`: one request per line, median-F0 retakes (>2 semitones off, ≤`LEMO_TTS_STEPAUDIO_TAKES`) — kept for
  comparison only. `voices/stepaudio_meta.json` records mode, bounds and alignment.
- One-voice gate: `cli.py quality` runs `core/tts/speaker_check.py` (Resemblyzer GE2E, CPU) — every line vs the others'
  centroid ≥0.80 and every pair ≥0.70, else high FAIL. Setup (not committed):
  `python3 -m venv /workspace/.venv-spk && /workspace/.venv-spk/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu && /workspace/.venv-spk/bin/pip install --no-deps resemblyzer && /workspace/.venv-spk/bin/pip install webrtcvad-wheels librosa`
  then `ln -s /workspace/.venv-spk .venv-spk` (or set `LEMO_SPK_PYTHON`).


### ElevenLabs

- Route: `POST /v1/text-to-speech/{voice_id}?output_format=pcm_24000` → 24 kHz mono WAV.
- Model default: `eleven_multilingual_v2` (Chinese VO). Override with `LEMO_TTS_ELEVENLABS_MODEL`.
- Env: **`ELEVENLABS_API_KEY`** (preferred; alias `ELEVEN_API_KEY`), `ELEVENLABS_VOICE_ID` (alias
  `LEMO_TTS_ELEVENLABS_VOICE`; default `21m00Tcm4TlvDq8ikWAM` / Rachel public demo voice),
  `LEMO_TTS_ELEVENLABS_BASE` (default `https://api.elevenlabs.io/v1`).
- Explicit only: `--provider elevenlabs` (not in `auto`). `--list` reports `needs-key` until the key is set.
- Key is never printed. Edge/Kokoro `*Neural` voice names in `--voice` are ignored in favour of the ElevenLabs voice id.



### ElevenLabs Text-to-Dialogue (multi-speaker)

Separate from single-narrator `elevenlabs` (which hits `/v1/text-to-speech/{voice_id}`).
This path is the dialogue TTS layer only — not a full podcast pipeline like podcastfy
(no RSS/article scrape, no music bed, no show notes); just speaker-labeled turns → audio.

- Route: `POST /v1/text-to-dialogue?output_format=pcm_24000` → stitched `dialogue.wav` + per-turn
  `<id>.wav` slices + `dialogue_manifest.json` (speaker/text/voice_id; start/end are **char-share
  estimates** inside each API chunk — word timestamps not wired yet).
- Model: preferred `eleven_v4`, automatic fallback to `eleven_v3` on model/validation errors.
  Override with `LEMO_TTS_ELEVENLABS_DIALOGUE_MODEL`.
- Limits: ≤10 unique `voice_id`s and ≤2000 characters total per request; longer scripts are chunked.
- Script (`lines.json` list): each object needs `text` (or `say`) and a speaker label
  (`speaker` / `speaker_id` / `role`). Optional per-line `voice_id`.
  ```json
  [
    {"id": "L01", "speaker": "host", "text": "今天谈流动性陷阱。"},
    {"id": "L02", "speaker": "guest", "text": "先从利率说起。"}
  ]
  ```
- Voice map (first hit wins): line `voice_id` → `ELEVENLABS_VOICE_MAP` JSON /
  `ELEVENLABS_VOICE_MAP_FILE` → `ELEVENLABS_VOICE_<SPEAKER>` (e.g. `ELEVENLABS_VOICE_HOST`,
  `ELEVENLABS_VOICE_GUEST`) → built-in defaults (host Tex, guest by content type, see below) →
  `ELEVENLABS_VOICE_ID` for other speakers.
- CLI: `python3 tools/deepseek-controller/cli.py tts --project P --provider elevenlabs-dialogue`
  (same key as single-speaker; explicit only, not in `auto`).
- **Default host:** Tex `TKaUqol7GKx4m7enpCpP` (English-leaning tech male). It's used for speaker `host`
  unless `ELEVENLABS_VOICE_HOST` / the voice map says otherwise.
- **Guest (female co-host) by content type**: `--content-type` (router + `cli.py tts`), or the config field
  `"content_type"` in the project's `plan.json`, or env `LEMO_TTS_ELEVENLABS_CONTENT_TYPE`.
  Applies to speakers `guest` / `cohost`. All voices are shared-library voices already added to the account.

  | content_type | Use for | Guest voice |
  |---|---|---|
  | `market` (default) | market / macro / news style: bonds, rates, index, 财经新闻 | Linda `t5SIDRTVMdbNUqrSAycs` |
  | `concept` | concept explainers, more English terms, bilingual teaching | Ladaisy `8RCmdqih4CKjJ7Bd3ZxT` |
  | `personal` | personal finance / lifestyle / 理财习惯: emergency fund, budgeting, saving | Shusita `iCrb0E1mQG2baVhfLIGF` |
  | `english` | English-heavy episodes, investing strategy: DCA, diversification | Joan `qgrPcGqsZG6TpPzso4fK` |

  Aliases (case-insensitive): macro/news/bonds/rates/index/财经新闻/宏观 → market; explainer/teaching/bilingual/概念
  → concept; lifestyle/budgeting/saving/理财习惯/个人理财 → personal; investing/strategy/dca/diversification/en →
  english. Unknown values fail fast. No type → `market` (Linda).
- **Precedence** (first hit wins): line `voice_id` → `ELEVENLABS_VOICE_MAP(_FILE)` → `ELEVENLABS_VOICE_<SPEAKER>`
  (so an explicit `ELEVENLABS_VOICE_GUEST` always overrides content type) → content-type table → defaults.
  Type source: CLI flag → `plan.json` `content_type` → env → `market`.
  ```sh
  python3 tools/deepseek-controller/cli.py tts --project P --provider elevenlabs-dialogue --content-type personal
  ```
  `dialogue_manifest.json` / `tts_router.json` record `contentType`. Mock test:
  `tools/deepseek-controller/tests/elevenlabs_content_type_mock.py`.
  Rejected after round 1: Skylar, Shasha, Kathy (female). Loh and Jerry stay as male alternates. Avoid
  high-usage premade/library voices (Rachel, Adam Li, Xiaoxi, …). Auditions: `films/elevenlabs-voice-audition/`
  (outside git).


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

## Pacing (P0)
`cli.py tts` options:
- `--pacing fast|standard|calm`: defaults to plan `pacing`, then `content_type`.
- `--rate`: edge. Defaults to the profile value, `+10%` for standard.
- `--speed`: StepAudio. Defaults to `LEMO_TTS_STEPAUDIO_SPEED`, then the profile value.
- `--no-trim`: skips the post-synthesis pause trim.

The router passes `speed` only to providers in `SPEED_PROVIDERS` (currently stepaudio). See `docs/PACING.md`.
