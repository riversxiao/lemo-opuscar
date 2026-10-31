"""OmniVoice via OpenAI-compatible speech endpoint (e.g. Docker OmniVoice-FastAPI).

Ready only when WORDFILM_TTS_OMNIVOICE_BASE is set. Optional WORDFILM_TTS_OMNIVOICE_API_KEY /
WORDFILM_TTS_OMNIVOICE_MODEL. No keys invented.

References:
- Model: k2-fsa/OmniVoice
- API example: diogod2r/OmniVoice-FastAPI → POST /v1/audio/speech on :8880
"""
from __future__ import annotations

import os
import sys
from typing import Any

from . import env, http_speech


def synthesize(lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
    base = (opts.get("base") or env("TTS_OMNIVOICE_BASE", "")).strip()
    if not base:
        sys.exit(
            "tts_router: provider 'omnivoice' needs a server URL.\n"
            "  Start OmniVoice (e.g. docker … omnivoice-fastapi) then:\n"
            "  export WORDFILM_TTS_OMNIVOICE_BASE=http://127.0.0.1:8880/v1\n"
            "  optional: WORDFILM_TTS_OMNIVOICE_MODEL=…  WORDFILM_TTS_OMNIVOICE_API_KEY=…\n"
            f"  lines={len(lines)} out_dir={out_dir}"
        )
    model = (
        opts.get("model")
        or env("TTS_OMNIVOICE_MODEL")
        or "omnivoice"
    )
    api_key = opts.get("api_key") or env("TTS_OMNIVOICE_API_KEY") or None
    voice = opts.get("voice")
    return http_speech.synthesize_lines(
        lines,
        out_dir,
        base=base,
        model=str(model),
        api_key=api_key,
        default_voice=voice,
    )
