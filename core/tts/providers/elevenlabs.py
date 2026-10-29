"""ElevenLabs cloud TTS provider for tts_router.

HTTP Text-to-Speech (`POST /v1/text-to-speech/{voice_id}`) with the multilingual
model suitable for Chinese VO. Ready only when a key is present; never invents or
logs secrets. Explicit opt-in only (not in `--provider auto`).

Env (preferred name first):
  ELEVENLABS_API_KEY          required (alias: ELEVEN_API_KEY)
  ELEVENLABS_VOICE_ID         voice uuid (alias: LEMO_TTS_ELEVENLABS_VOICE);
                              default 21m00Tcm4TlvDq8ikWAM (Rachel, public demo voice)
  LEMO_TTS_ELEVENLABS_MODEL   default eleven_multilingual_v2
  LEMO_TTS_ELEVENLABS_BASE    default https://api.elevenlabs.io/v1
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

from . import http_speech

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
    return (os.environ.get("LEMO_TTS_ELEVENLABS_BASE") or DEFAULT_BASE).rstrip("/")


def voice_id(explicit: str | None = None) -> str:
    if explicit and str(explicit).strip() and not str(explicit).startswith(("zh-", "en-")):
        # Reject edge/kokoro Neural names; those are not ElevenLabs voice ids.
        return str(explicit).strip()
    return (
        os.environ.get("ELEVENLABS_VOICE_ID")
        or os.environ.get("LEMO_TTS_ELEVENLABS_VOICE")
        or DEFAULT_VOICE_ID
    ).strip()


def model_id() -> str:
    return (os.environ.get("LEMO_TTS_ELEVENLABS_MODEL") or DEFAULT_MODEL).strip()


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
              speed: float | None = None) -> tuple[bytes, str | None]:
    key = api_key()
    if not key:
        raise ElevenLabsError("ELEVENLABS_API_KEY not set")
    url = f"{base_url()}/text-to-speech/{voice}?output_format=pcm_24000"
    body = {
        "text": text,
        "model_id": model,
        "voice_settings": voice_settings(model, speed),
    }
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


def synthesize(lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
    """tts_router entry: write <id>.wav (24 kHz mono) + dur.json."""
    if not api_key():
        sys.exit(
            "tts_router: provider 'elevenlabs' needs ELEVENLABS_API_KEY in the environment "
            "(alias ELEVEN_API_KEY also accepted)"
        )
    voice = voice_id(opts.get("voice"))
    model = str(opts.get("model") or model_id())
    speed = opts.get("speed")
    if speed is None and os.environ.get("LEMO_TTS_ELEVENLABS_SPEED"):
        speed = float(os.environ["LEMO_TTS_ELEVENLABS_SPEED"])
    os.makedirs(out_dir, exist_ok=True)
    dur: dict[str, float] = {}
    spoken: dict[str, str] = {}
    for L in lines:
        lid = L["id"]
        text = spoken_text(L)
        if not text.strip():
            sys.exit(f"tts_router: elevenlabs line {lid!r} has empty text")
        spoken[lid] = text
        line_voice = voice_id(L.get("voice") or voice)
        try:
            raw, ctype = _post_tts(text, voice=line_voice, model=L.get("model") or model, speed=speed)
            a = http_speech._trim(_decode_audio(raw, ctype), SR)
        except ElevenLabsError as e:
            sys.exit(f"tts_router: elevenlabs failed on {lid}: {e}")
        path = os.path.join(out_dir, f"{lid}.wav")
        sf.write(path, a, SR)
        dur[lid] = round(len(a) / float(SR), 3)
        print(lid, dur[lid], text)
    with open(os.path.join(out_dir, "dur.json"), "w", encoding="utf-8") as f:
        json.dump(dur, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, "spoken.json"), "w", encoding="utf-8") as f:
        json.dump({"voice": voice, "model": model, "chars": sum(len(t) for t in spoken.values()), "lines": spoken}, f, indent=1, ensure_ascii=False)
    return dur


def spoken_text(L: dict[str, Any]) -> str:
    """say (or text); in Chinese lines Arabic numbers are spelled in Chinese words
    (97.5% → 百分之九十七点五) — ElevenLabs voices otherwise read them in English.
    LEMO_TTS_ELEVENLABS_ZH_NUMBERS=0 turns this off."""
    text = str(L.get("say") or L.get("text") or "")
    if os.environ.get("LEMO_TTS_ELEVENLABS_ZH_NUMBERS", "1") != "0" and re.search(r"[\u4e00-\u9fff]", text):
        try:
            import zh_num  # noqa: PLC0415  (core/tts on sys.path via tts_router)
        except ImportError:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            import zh_num  # noqa: PLC0415
        text = zh_num.spell_numbers(text)
        # say spells acronyms for StepAudio (V-A-R, E-S); eleven_v4 reads the hyphens as Chinese
        # syllables (E-S → "意义 S" in ASR) but plain capitals letter by letter (ES → ES).
        if os.environ.get("LEMO_TTS_ELEVENLABS_JOIN_LETTERS", "1") != "0":
            text = re.sub(r"(?<![A-Za-z])[A-Z](?:-[A-Z])+(?![A-Za-z])", lambda m: m.group(0).replace("-", ""), text)
    return text
