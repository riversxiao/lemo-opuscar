"""Qwen3-TTS via OpenAI-compatible POST /v1/audio/speech (self-hosted).

Ready only when LEMO_TTS_QWEN3_BASE is set. No API keys are invented.
Optional: LEMO_TTS_QWEN3_API_KEY, LEMO_TTS_QWEN3_MODEL (default tts-1).

References:
- Models: Qwen/Qwen3-TTS-12Hz-*
- Serving: vLLM-Omni speech API; community FastAPI (groxaxo/Qwen3-TTS-Openai-Fastapi)
"""
from __future__ import annotations

import os
import sys
from typing import Any

from . import http_speech


def synthesize(lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
    base = (opts.get("base") or os.environ.get("LEMO_TTS_QWEN3_BASE", "")).strip()
    if not base:
        sys.exit(
            "tts_router: provider 'qwen3' needs a server URL.\n"
            "  1) Start a Qwen3-TTS OpenAI-compatible /v1/audio/speech server.\n"
            "  2) export LEMO_TTS_QWEN3_BASE=http://127.0.0.1:<port>/v1\n"
            "  3) optional: LEMO_TTS_QWEN3_MODEL=…  LEMO_TTS_QWEN3_API_KEY=…\n"
            "  No cloud key is shipped; leave unset to keep this provider inactive.\n"
            f"  lines={len(lines)} out_dir={out_dir}"
        )
    model = (
        opts.get("model")
        or os.environ.get("LEMO_TTS_QWEN3_MODEL")
        or "tts-1"
    )
    api_key = opts.get("api_key") or os.environ.get("LEMO_TTS_QWEN3_API_KEY") or None
    voice = opts.get("voice")
    return http_speech.synthesize_lines(
        lines,
        out_dir,
        base=base,
        model=str(model),
        api_key=api_key,
        default_voice=voice,
    )
