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
"""
from __future__ import annotations

import io
import json
import os
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


def _post_tts(text: str, *, voice: str, model: str, timeout: float = 120.0) -> tuple[bytes, str | None]:
    key = api_key()
    if not key:
        raise ElevenLabsError("ELEVENLABS_API_KEY not set")
    url = f"{base_url()}/text-to-speech/{voice}?output_format=pcm_24000"
    body = {
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
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
    os.makedirs(out_dir, exist_ok=True)
    dur: dict[str, float] = {}
    for L in lines:
        lid = L["id"]
        text = str(L.get("say") or L.get("text") or "")
        if not text.strip():
            sys.exit(f"tts_router: elevenlabs line {lid!r} has empty text")
        line_voice = voice_id(L.get("voice") or voice)
        try:
            raw, ctype = _post_tts(text, voice=line_voice, model=L.get("model") or model)
            a = http_speech._trim(_decode_audio(raw, ctype), SR)
        except ElevenLabsError as e:
            sys.exit(f"tts_router: elevenlabs failed on {lid}: {e}")
        path = os.path.join(out_dir, f"{lid}.wav")
        sf.write(path, a, SR)
        dur[lid] = round(len(a) / float(SR), 3)
        print(lid, dur[lid], text)
    with open(os.path.join(out_dir, "dur.json"), "w", encoding="utf-8") as f:
        json.dump(dur, f, indent=1, ensure_ascii=False)
    return dur
