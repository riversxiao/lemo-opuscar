"""Minimal OpenAI-compatible POST /v1/audio/speech client (stdlib only).

Used by qwen3 / omnivoice when LEMO_TTS_*_BASE is set. Writes 24 kHz mono WAV
matching tts_zh.py / tts.py layout. No API keys are invented — pass via env.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

import numpy as np
import soundfile as sf

SR = 24000


def _join_speech_url(base: str) -> str:
    b = base.rstrip("/")
    if b.endswith("/audio/speech"):
        return b
    if b.endswith("/v1"):
        return b + "/audio/speech"
    return b + "/v1/audio/speech"


def _to_wav_bytes(raw: bytes, content_type: str | None) -> tuple[np.ndarray, int]:
    """Decode response body to float32 mono @ SR."""
    ct = (content_type or "").lower()
    # Prefer ffmpeg for mp3/opus/aac; soundfile for wav/flac.
    if "wav" in ct or "x-wav" in ct or raw[:4] == b"RIFF":
        a, sr = sf.read(io.BytesIO(raw), dtype="float32")
    else:
        try:
            r = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    "pipe:0",
                    "-ar",
                    str(SR),
                    "-ac",
                    "1",
                    "-f",
                    "wav",
                    "pipe:1",
                ],
                input=raw,
                capture_output=True,
                check=True,
            )
        except FileNotFoundError:
            sys.exit("http_speech: ffmpeg required to decode non-WAV speech responses")
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or b"").decode("utf-8", "replace")[:400]
            sys.exit(f"http_speech: ffmpeg decode failed: {msg}")
        a, sr = sf.read(io.BytesIO(r.stdout), dtype="float32")
    if getattr(a, "ndim", 1) > 1:
        a = a.mean(axis=1)
    if sr != SR:
        # crude resample via ffmpeg would be better; ask ffmpeg path above usually hits SR
        ratio = SR / float(sr)
        idx = (np.arange(int(len(a) * ratio)) / ratio).astype(np.int64)
        idx = np.clip(idx, 0, len(a) - 1)
        a = a[idx]
        sr = SR
    return a.astype(np.float32), sr


def _trim(a: np.ndarray, sr: int) -> np.ndarray:
    if not len(a):
        return a
    thr = float(np.abs(a).max()) * 0.02
    nz = np.where(np.abs(a) > thr)[0]
    if not len(nz):
        return a
    return a[max(0, nz[0] - int(0.03 * sr)) : nz[-1] + int(0.08 * sr)]


def post_speech(
    *,
    base: str,
    text: str,
    model: str,
    voice: str | None = None,
    api_key: str | None = None,
    timeout: float = 120.0,
    extra: dict[str, Any] | None = None,
) -> tuple[bytes, str | None]:
    url = _join_speech_url(base)
    body: dict[str, Any] = {"model": model, "input": text, "response_format": "wav"}
    if voice:
        body["voice"] = voice
    if extra:
        body.update(extra)
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "*/*"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")[:500]
        sys.exit(f"http_speech: HTTP {e.code} from {url}: {err}")
    except urllib.error.URLError as e:
        sys.exit(f"http_speech: cannot reach {url}: {e.reason}")


def synthesize_lines(
    lines: list[dict[str, Any]],
    out_dir: str,
    *,
    base: str,
    model: str,
    api_key: str | None = None,
    default_voice: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, float]:
    if not base:
        sys.exit("http_speech: empty base URL")
    os.makedirs(out_dir, exist_ok=True)
    dur: dict[str, float] = {}
    for L in lines:
        lid = L["id"]
        text = L.get("say") or L.get("text") or ""
        if not str(text).strip():
            sys.exit(f"http_speech: line {lid!r} has empty text")
        voice = L.get("voice") or default_voice
        raw, ctype = post_speech(
            base=base,
            text=str(text),
            model=L.get("model") or model,
            voice=voice,
            api_key=api_key,
            extra=extra,
        )
        a, sr = _to_wav_bytes(raw, ctype)
        a = _trim(a, sr)
        path = os.path.join(out_dir, f"{lid}.wav")
        sf.write(path, a, sr)
        dur[lid] = round(len(a) / float(sr), 3)
        print(lid, dur[lid], text)
    with open(os.path.join(out_dir, "dur.json"), "w", encoding="utf-8") as f:
        json.dump(dur, f, indent=1, ensure_ascii=False)
    return dur
