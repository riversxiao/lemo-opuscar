"""ElevenLabs Text-to-Dialogue (multi-speaker) for tts_router.

Separate from single-narrator `elevenlabs.py`. Calls
`POST /v1/text-to-dialogue` with speaker-labeled turns. Explicit opt-in only
(`--provider elevenlabs-dialogue`); not in `--provider auto`.

Limits (official): ≤10 unique voice_ids; keep total characters across
`inputs[].text` ≤2000 per request — longer scripts are chunked.

Env:
  ELEVENLABS_API_KEY / ELEVEN_API_KEY     required (shared with single-speaker)
  WORDFILM_TTS_ELEVENLABS_BASE                default https://api.elevenlabs.io/v1
  WORDFILM_TTS_ELEVENLABS_DIALOGUE_MODEL      preferred eleven_v4 (fallback eleven_v3)
  ELEVENLABS_VOICE_MAP                    JSON object {"host":"<id>","guest":"<id>",…}
  ELEVENLABS_VOICE_MAP_FILE               path to the same JSON
  ELEVENLABS_VOICE_<SPEAKER>              e.g. ELEVENLABS_VOICE_HOST / _GUEST
  ELEVENLABS_VOICE_ID                     fallback default voice

Script lines (JSON list; same file the router already reads):
  {"id":"L01","speaker":"host","text":"你好。"}
  {"id":"L02","speaker":"guest","text":"你好啊。","voice_id":"<optional override>"}
Aliases: speaker_id → speaker; say → text; voice → voice_id when it looks like an EL id.

Outputs under out_dir/:
  dialogue.wav            full stitched track (24 kHz mono)
  dialogue_manifest.json  turns + estimated start/end (char-share; no API timestamps yet)
  <id>.wav                per-turn slices (same char-share estimate) + dur.json
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

import numpy as np
import soundfile as sf

from . import elevenlabs as EL
from . import env, http_speech

SR = EL.SR
MAX_CHARS = 2000
MAX_VOICES = 10
PREFERRED_MODEL = "eleven_v4"
FALLBACK_MODEL = "eleven_v3"


class DialogueError(EL.ElevenLabsError):
    pass


def dialogue_model() -> str:
    return (
        env("TTS_ELEVENLABS_DIALOGUE_MODEL")
        or PREFERRED_MODEL
    ).strip()


def _load_voice_map() -> dict[str, str]:
    raw = (os.environ.get("ELEVENLABS_VOICE_MAP") or "").strip()
    path = (os.environ.get("ELEVENLABS_VOICE_MAP_FILE") or "").strip()
    data: dict[str, Any] = {}
    if path:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    elif raw:
        data = json.loads(raw)
    out: dict[str, str] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if v:
                out[str(k).strip().lower()] = str(v).strip()
    return out


def resolve_voice(speaker: str, explicit: str | None = None, voice_map: dict[str, str] | None = None) -> str:
    if explicit and str(explicit).strip() and not str(explicit).startswith(("zh-", "en-")):
        return str(explicit).strip()
    sp = (speaker or "").strip().lower() or "host"
    vm = voice_map if voice_map is not None else _load_voice_map()
    if sp in vm:
        return vm[sp]
    env_key = f"ELEVENLABS_VOICE_{sp.upper()}"
    if os.environ.get(env_key, "").strip():
        return os.environ[env_key].strip()
    # common aliases
    for alias in (f"ELEVENLABS_VOICE_{sp.upper()}",):
        if os.environ.get(alias, "").strip():
            return os.environ[alias].strip()
    return EL.voice_id()


def normalize_turns(lines: list[dict[str, Any]], voice_map: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Normalize router lines → dialogue turns with resolved voice_id."""
    vm = voice_map if voice_map is not None else _load_voice_map()
    turns: list[dict[str, Any]] = []
    for i, L in enumerate(lines):
        if not isinstance(L, dict):
            raise DialogueError(f"line {i} is not an object")
        lid = str(L.get("id") or f"L{i+1:02d}")
        text = str(L.get("say") or L.get("text") or "").strip()
        if not text:
            raise DialogueError(f"line {lid!r} has empty text")
        speaker = str(L.get("speaker") or L.get("speaker_id") or L.get("role") or "host").strip()
        explicit = L.get("voice_id") or L.get("voice")
        vid = resolve_voice(speaker, explicit if isinstance(explicit, str) else None, vm)
        turns.append({"id": lid, "speaker": speaker, "text": text, "voice_id": vid})
    return turns


def chunk_turns(turns: list[dict[str, Any]], max_chars: int = MAX_CHARS, max_voices: int = MAX_VOICES) -> list[list[dict[str, Any]]]:
    """Split turns so each request stays within official limits."""
    chunks: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    chars = 0
    voices: set[str] = set()
    for t in turns:
        tchars = len(t["text"])
        if tchars > max_chars:
            raise DialogueError(
                f"turn {t['id']!r} alone is {tchars} chars (> {max_chars}); split the line"
            )
        new_voice = t["voice_id"] not in voices
        if cur and (chars + tchars > max_chars or (new_voice and len(voices) + 1 > max_voices)):
            chunks.append(cur)
            cur, chars, voices = [], 0, set()
        cur.append(t)
        chars += tchars
        voices.add(t["voice_id"])
    if cur:
        chunks.append(cur)
    return chunks


def _post_dialogue(
    inputs: list[dict[str, str]],
    *,
    model: str,
    language_code: str | None = None,
    timeout: float = 180.0,
) -> tuple[bytes, str | None, str]:
    """POST /text-to-dialogue. Returns (audio_bytes, content_type, model_used)."""
    key = EL.api_key()
    if not key:
        raise DialogueError("ELEVENLABS_API_KEY not set")
    url = f"{EL.base_url()}/text-to-dialogue?output_format=pcm_24000"
    body: dict[str, Any] = {"inputs": inputs, "model_id": model}
    if language_code:
        body["language_code"] = language_code
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
            return resp.read(), resp.headers.get("Content-Type"), model
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")[:500]
        raise DialogueError(f"ElevenLabs dialogue HTTP {e.code}: {err}") from None
    except urllib.error.URLError as e:
        raise DialogueError(f"ElevenLabs dialogue transport error: {e.reason}") from None


def post_dialogue_with_fallback(
    inputs: list[dict[str, str]],
    *,
    model: str | None = None,
    language_code: str | None = None,
) -> tuple[bytes, str | None, str]:
    primary = (model or dialogue_model()).strip()
    models = [primary]
    if primary != FALLBACK_MODEL:
        models.append(FALLBACK_MODEL)
    last: Exception | None = None
    for m in models:
        try:
            return _post_dialogue(inputs, model=m, language_code=language_code)
        except DialogueError as e:
            last = e
            msg = str(e).lower()
            # retry on model-not-found / validation pointing at model
            if m != models[-1] and ("model" in msg or "422" in msg or "400" in msg):
                continue
            raise
    raise last or DialogueError("dialogue failed")


def _char_share_bounds(turns: list[dict[str, Any]], total_sec: float) -> list[tuple[float, float]]:
    weights = [max(1, len(t["text"])) for t in turns]
    s = float(sum(weights))
    bounds: list[tuple[float, float]] = []
    t0 = 0.0
    for i, w in enumerate(weights):
        t1 = total_sec if i == len(weights) - 1 else t0 + total_sec * (w / s)
        bounds.append((round(t0, 3), round(t1, 3)))
        t0 = t1
    return bounds


def synthesize(lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
    """tts_router entry for multi-speaker dialogue."""
    if not EL.api_key():
        sys.exit(
            "tts_router: provider 'elevenlabs-dialogue' needs ELEVENLABS_API_KEY "
            "(alias ELEVEN_API_KEY)"
        )
    try:
        turns = normalize_turns(lines, opts.get("voice_map"))
    except DialogueError as e:
        sys.exit(f"tts_router: elevenlabs-dialogue: {e}")
    if not turns:
        sys.exit("tts_router: elevenlabs-dialogue: empty script")

    language = opts.get("language_code") or env("TTS_ELEVENLABS_LANGUAGE") or None
    model = opts.get("model") or dialogue_model()
    chunks = chunk_turns(turns)
    os.makedirs(out_dir, exist_ok=True)

    audio_parts: list[np.ndarray] = []
    manifest_turns: list[dict[str, Any]] = []
    models_used: list[str] = []
    offset = 0.0
    requests = 0

    for ci, chunk in enumerate(chunks):
        inputs = [{"text": t["text"], "voice_id": t["voice_id"]} for t in chunk]
        try:
            raw, ctype, used = post_dialogue_with_fallback(
                inputs, model=str(model), language_code=language
            )
            a = http_speech._trim(EL._decode_audio(raw, ctype), SR)
        except DialogueError as e:
            sys.exit(f"tts_router: elevenlabs-dialogue chunk {ci} failed: {e}")
        requests += 1
        models_used.append(used)
        sec = len(a) / float(SR)
        bounds = _char_share_bounds(chunk, sec)
        for t, (t0, t1) in zip(chunk, bounds):
            manifest_turns.append({
                "id": t["id"],
                "speaker": t["speaker"],
                "text": t["text"],
                "voice_id": t["voice_id"],
                "start": round(offset + t0, 3),
                "end": round(offset + t1, 3),
                "timing": "char-share-estimate",
                "chunk": ci,
            })
            # per-turn slice
            i0, i1 = int(t0 * SR), int(t1 * SR)
            clip = a[i0:i1] if i1 > i0 else a[:1]
            sf.write(os.path.join(out_dir, f"{t['id']}.wav"), clip, SR)
            print(t["id"], round(len(clip) / SR, 3), f"[{t['speaker']}]", t["text"])
        audio_parts.append(a)
        offset += sec

    full = np.concatenate(audio_parts) if audio_parts else np.zeros(0, dtype=np.float32)
    sf.write(os.path.join(out_dir, "dialogue.wav"), full, SR)
    dur = {m["id"]: round(m["end"] - m["start"], 3) for m in manifest_turns}
    with open(os.path.join(out_dir, "dur.json"), "w", encoding="utf-8") as f:
        json.dump(dur, f, indent=1, ensure_ascii=False)
    meta = {
        "provider": "elevenlabs-dialogue",
        "route": "/v1/text-to-dialogue",
        "models": models_used,
        "requests": requests,
        "totalSec": round(len(full) / SR, 3),
        "uniqueVoices": sorted({t["voice_id"] for t in turns}),
        "turns": manifest_turns,
        "note": "start/end are char-share estimates within each API chunk; not word timestamps",
    }
    with open(os.path.join(out_dir, "dialogue_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return dur
