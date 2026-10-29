"""Pluggable TTS providers for tts_router.py. Contract: lines.json → <id>.wav + dur.json."""
import os

PROVIDERS = ("edge", "kokoro", "qwen3", "omnivoice", "stepaudio", "elevenlabs", "elevenlabs-dialogue")


def env(name: str, default: str = "") -> str:
    """Setting `name` (e.g. "TTS_STEPAUDIO_MODE"): $WORDFILM_<name>, else the upstream
    $LEMO_<name>, else `default`. Empty values count as unset. Read at call time."""
    for key in ("WORDFILM_" + name, "LEMO_" + name):
        val = os.environ.get(key)
        if val:
            return val
    return default
