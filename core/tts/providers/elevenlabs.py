"""ElevenLabs cloud TTS provider for tts_router.

HTTP Text-to-Speech (`POST /v1/text-to-speech/{voice_id}`) with the multilingual
model suitable for Chinese VO. Ready only when a key is present; never invents or
logs secrets. Explicit opt-in only (not in `--provider auto`).

Env (preferred name first):
  ELEVENLABS_API_KEY          required (alias: ELEVEN_API_KEY)
  ELEVENLABS_VOICE_ID         voice uuid (alias: WORDFILM_TTS_ELEVENLABS_VOICE);
                              default 21m00Tcm4TlvDq8ikWAM (Rachel, public demo voice)
  WORDFILM_TTS_ELEVENLABS_MODEL   default eleven_multilingual_v2
  WORDFILM_TTS_ELEVENLABS_BASE    default https://api.elevenlabs.io/v1
  WORDFILM_TTS_ELEVENLABS_LANGUAGE  default language for lines without `lang` (auto: CJK → zh, else en)
  WORDFILM_TTS_ELEVENLABS_MIXED   single (default) | split — how `lang: mixed` lines are synthesized
  WORDFILM_TTS_ELEVENLABS_SEED    optional integer seed (best-effort determinism)

Language (Cantonese drift fix, 贝塔 pilot 2026-10-29): eleven_v4 supports both Mandarin (`zh`)
and Cantonese (`yue`); both are written in hanzi, so without `language_code` the model guesses
per request and short Chinese lines sometimes come out in 粤语. Every request now carries an
explicit language_code. Per line (`lang` in lines.json / plan voice line):
  zh     (default for CJK text)  Mandarin, one request with language_code=zh
  en     (default for text with no CJK) English, language_code=en
  mixed  Chinese with English words/sentences. Default `single`: ONE request with language_code=zh
         (no seams; tested 2026-10-29: Tex + v4 + zh still reads embedded English in English —
         「英文 Value at Risk」 → Whisper "value at risk" p≥0.96). `split` (opt-in): zh / en runs as
         separate requests with their own language_code + previous_text/next_text, same voice + seed,
         joined with a punctuation pause or a short equal-power crossfade; segment offsets →
         spoken.json (the dialect gate then checks the zh runs only).
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

import numpy as np
import soundfile as sf

from . import env, http_speech

SR = 24000
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel — public multilingual demo voice
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_BASE = "https://api.elevenlabs.io/v1"


class ElevenLabsError(RuntimeError):
    pass


def api_key() -> str | None:
    return (
        os.environ.get("ELEVENLABS_API_KEY")
        or os.environ.get("ELEVEN_API_KEY")
        or ""
    ).strip() or None


def base_url() -> str:
    return (env("TTS_ELEVENLABS_BASE") or DEFAULT_BASE).rstrip("/")


def voice_id(explicit: str | None = None) -> str:
    if explicit and str(explicit).strip() and not str(explicit).startswith(("zh-", "en-")):
        # Reject edge/kokoro Neural names; those are not ElevenLabs voice ids.
        return str(explicit).strip()
    return (
        os.environ.get("ELEVENLABS_VOICE_ID")
        or env("TTS_ELEVENLABS_VOICE")
        or DEFAULT_VOICE_ID
    ).strip()


def model_id() -> str:
    return (env("TTS_ELEVENLABS_MODEL") or DEFAULT_MODEL).strip()


def _decode_pcm24(raw: bytes) -> np.ndarray:
    """pcm_24000 = signed 16-bit little-endian mono @ 24 kHz."""
    if len(raw) < 2:
        raise ElevenLabsError("empty PCM body from ElevenLabs")
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return a


def _decode_audio(raw: bytes, content_type: str | None) -> np.ndarray:
    ct = (content_type or "").lower()
    if "wav" in ct or raw[:4] == b"RIFF":
        a, _ = http_speech._to_wav_bytes(raw, ct or "audio/wav")
        return a
    if "mpeg" in ct or "mp3" in ct or raw[:3] == b"ID3" or raw[:2] == b"\xff\xfb":
        a, _ = http_speech._to_wav_bytes(raw, "audio/mpeg")
        return a
    # Default request asks for pcm_24000 (no container).
    return _decode_pcm24(raw)


SPEED_MIN, SPEED_MAX = 0.7, 1.2   # ElevenLabs docs: recommended speed range (1.0 = normal)


def voice_settings(model: str, speed: float | None = None) -> dict[str, Any]:
    """voice_settings body. `speed` is clamped to 0.7–1.2 and omitted on Eleven v4 models
    (docs: v4 ignores speed/style; pace with punctuation instead)."""
    vs: dict[str, Any] = {"stability": 0.5, "similarity_boost": 0.75}
    if speed and abs(float(speed) - 1.0) > 1e-6 and not str(model).startswith("eleven_v4"):
        vs["speed"] = round(min(SPEED_MAX, max(SPEED_MIN, float(speed))), 3)
    return vs


def _post_tts(text: str, *, voice: str, model: str, timeout: float = 120.0,
              speed: float | None = None, language: str | None = None,
              previous_text: str | None = None, next_text: str | None = None,
              seed: int | None = None) -> tuple[bytes, str | None]:
    key = api_key()
    if not key:
        raise ElevenLabsError("ELEVENLABS_API_KEY not set")
    url = f"{base_url()}/text-to-speech/{voice}?output_format=pcm_24000"
    body = {
        "text": text,
        "model_id": model,
        "voice_settings": voice_settings(model, speed),
    }
    if language and not str(model).startswith("eleven_multilingual_v2"):  # v2 rejects language_code
        body["language_code"] = language
    if previous_text:
        body["previous_text"] = previous_text
    if next_text:
        body["next_text"] = next_text
    if seed is not None:
        body["seed"] = int(seed)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "xi-api-key": key,
            "Content-Type": "application/json",
            "Accept": "audio/pcm",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")[:400]
        raise ElevenLabsError(f"ElevenLabs HTTP {e.code}: {err}") from None
    except urllib.error.URLError as e:
        raise ElevenLabsError(f"ElevenLabs transport error: {e.reason}") from None


CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
# an English run: Latin words (with digits, apostrophes, hyphens, inner spaces/punctuation)
EN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9'’\-]*(?:[\s,.;:!?%&/]+[A-Za-z0-9][A-Za-z0-9'’\-]*)*[.!?]?")
XFADE_SEC = 0.04


def norm_voice(v: Any) -> str | None:
    """Accept `elevenlabs:<id>` (台词教父 drafts) as well as a bare id."""
    if v is None:
        return None
    v = str(v).strip()
    if v.lower().startswith("elevenlabs:"):
        v = v.split(":", 1)[1].strip()
    return v or None


def line_lang(L: dict[str, Any], text: str) -> str:
    lg = str(L.get("lang") or "").strip().lower()
    if lg in ("zh", "en", "mixed", "yue"):
        return lg
    default = env("TTS_ELEVENLABS_LANGUAGE").strip().lower()
    if default:
        return default
    return "zh" if CJK_RE.search(text) else "en"


def split_lang(text: str) -> list[tuple[str, str]]:
    """'叫贝塔，英文叫 Beta。' → [('zh','叫贝塔，英文叫'), ('en','Beta'), ('zh','。')] merged:
    punctuation-only runs are glued onto the previous run."""
    segs: list[tuple[str, str]] = []
    pos = 0
    for m in EN_RUN.finditer(text):
        if not re.search(r"[A-Za-z]{2,}", m.group(0)):   # single capitals stay in the zh run
            continue
        if m.start() > pos:
            segs.append(("zh", text[pos:m.start()]))
        segs.append(("en", m.group(0)))
        pos = m.end()
    if pos < len(text):
        segs.append(("zh", text[pos:]))
    out: list[tuple[str, str]] = []
    for lg, t in segs:
        if out and not re.search(r"[A-Za-z0-9\u3400-\u9fff]", t):
            out[-1] = (out[-1][0], out[-1][1] + t)
        elif t.strip():
            out.append((lg, t.strip()))
    return out or [("zh", text)]


PAUSE_SEC = 0.16   # split mode: a run ending in ，/。 gets a breath instead of a crossfade (trim ate it)


def _xfade_join(parts: list[np.ndarray], sr: int = SR, gaps: list[float] | None = None
                ) -> tuple[np.ndarray, list[tuple[int, int]]]:
    n = int(XFADE_SEC * sr)
    out = parts[0].astype(np.float32)
    spans = [(0, len(out))]
    for idx, p in enumerate(parts[1:]):
        p = p.astype(np.float32)
        g = (gaps or [])[idx] if gaps and idx < len(gaps) else 0.0
        if g > 0:
            out = np.concatenate([out, np.zeros(int(g * sr), np.float32)])
        k = 0 if g > 0 else min(n, len(out), len(p))
        if k > 0:
            t = np.linspace(0, np.pi / 2, k, dtype=np.float32)
            mid = out[-k:] * np.cos(t) + p[:k] * np.sin(t)
            start = len(out) - k
            out = np.concatenate([out[:-k], mid, p[k:]])
        else:
            start = len(out)
            out = np.concatenate([out, p])
        spans.append((start, len(out)))
    return out, spans


def synthesize(lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
    """tts_router entry: write <id>.wav (24 kHz mono) + dur.json + spoken.json (langs, segments)."""
    if not api_key():
        sys.exit(
            "tts_router: provider 'elevenlabs' needs ELEVENLABS_API_KEY in the environment "
            "(alias ELEVEN_API_KEY also accepted)"
        )
    voice = voice_id(norm_voice(opts.get("voice")))
    model = str(opts.get("model") or model_id())
    speed = opts.get("speed")
    if speed is None and env("TTS_ELEVENLABS_SPEED"):
        speed = float(env("TTS_ELEVENLABS_SPEED"))
    seed = env("TTS_ELEVENLABS_SEED")
    seed = int(seed) if seed else None
    mixed_mode = (env("TTS_ELEVENLABS_MIXED") or "single").strip().lower()
    os.makedirs(out_dir, exist_ok=True)
    dur: dict[str, float] = {}
    spoken: dict[str, str] = {}
    langs: dict[str, str] = {}
    segments: dict[str, list[dict[str, Any]]] = {}
    texts = [spoken_text(L) for L in lines]
    for i, L in enumerate(lines):
        lid = L["id"]
        text = texts[i]
        if not text.strip():
            sys.exit(f"tts_router: elevenlabs line {lid!r} has empty text")
        spoken[lid] = text
        line_voice = voice_id(norm_voice(L.get("voice")) or voice)
        lg = line_lang(L, text)
        langs[lid] = lg
        prev_line = texts[i - 1] if i else None
        next_line = texts[i + 1] if i + 1 < len(texts) else None
        if lg == "mixed" and mixed_mode == "split":
            segs = split_lang(text)
        else:
            segs = [("zh" if lg == "mixed" else lg, text)]
        parts = []
        try:
            for j, (slg, st) in enumerate(segs):
                prev_t = "".join(t for _, t in segs[:j]) or prev_line
                next_t = "".join(t for _, t in segs[j + 1:]) or next_line
                raw, ctype = _post_tts(st, voice=line_voice, model=L.get("model") or model, speed=speed,
                                       language=slg, previous_text=prev_t, next_text=next_t, seed=seed)
                parts.append(http_speech._trim(_decode_audio(raw, ctype), SR))
        except ElevenLabsError as e:
            sys.exit(f"tts_router: elevenlabs failed on {lid}: {e}")
        a, spans = _xfade_join(parts, gaps=[PAUSE_SEC if re.search(r"[，,、：:；;。.!?！？]\s*$", t) else 0.0
                                            for _, t in segs[:-1]])
        if len(segs) > 1:
            segments[lid] = [{"lang": slg, "text": st, "start": round(s0 / SR, 3), "end": round(s1 / SR, 3)}
                             for (slg, st), (s0, s1) in zip(segs, spans)]
        path = os.path.join(out_dir, f"{lid}.wav")
        sf.write(path, a, SR)
        dur[lid] = round(len(a) / float(SR), 3)
        print(lid, dur[lid], lg, text)
    with open(os.path.join(out_dir, "dur.json"), "w", encoding="utf-8") as f:
        json.dump(dur, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, "spoken.json"), "w", encoding="utf-8") as f:
        json.dump({"voice": voice, "model": model, "chars": sum(len(t) for t in spoken.values()),
                   "seed": seed, "mixedMode": mixed_mode, "langs": langs, "segments": segments,
                   "lines": spoken}, f, indent=1, ensure_ascii=False)
    return dur


def spoken_text(L: dict[str, Any]) -> str:
    """say (or text); in Chinese lines Arabic numbers are spelled in Chinese words
    (97.5% → 百分之九十七点五) — ElevenLabs voices otherwise read them in English.
    WORDFILM_TTS_ELEVENLABS_ZH_NUMBERS=0 (legacy LEMO_TTS_ELEVENLABS_ZH_NUMBERS) turns this off."""
    text = str(L.get("say") or L.get("text") or "")
    if env("TTS_ELEVENLABS_ZH_NUMBERS", "1") != "0" and re.search(r"[\u4e00-\u9fff]", text):
        try:
            import zh_num  # noqa: PLC0415  (core/tts on sys.path via tts_router)
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import zh_num  # noqa: PLC0415
        text = zh_num.spell_numbers(text)
        # say spells acronyms for StepAudio (V-A-R, E-S); eleven_v4 reads the hyphens as Chinese
        # syllables (E-S → "意义 S" in ASR) but plain capitals letter by letter (ES → ES).
        if env("TTS_ELEVENLABS_JOIN_LETTERS", "1") != "0":
            text = re.sub(r"(?<![A-Za-z])[A-Z](?:-[A-Z])+(?![A-Za-z])", lambda m: m.group(0).replace("-", ""), text)
    return text
