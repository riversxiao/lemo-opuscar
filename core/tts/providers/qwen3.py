"""Qwen3-TTS stub — OpenAI-compatible POST /v1/audio/speech against a self-hosted server.

Not implemented in-process (weights are multi-GB). Point LEMO_TTS_QWEN3_BASE at a running
server, then implement the HTTP client in a follow-up sprint.

References:
- Models: Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice | VoiceDesign | Base (clone)
- Serving: vLLM-Omni speech API; community FastAPI (e.g. groxaxo/Qwen3-TTS-Openai-Fastapi)
- Env: LEMO_TTS_QWEN3_BASE=http://127.0.0.1:8091  LEMO_TTS_QWEN3_MODEL=tts-1-zh
"""
from __future__ import annotations

import os
import sys
from typing import Any


def synthesize(lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
    base = opts.get("base") or os.environ.get("LEMO_TTS_QWEN3_BASE", "")
    sys.exit(
        "tts_router: provider 'qwen3' is stubbed.\n"
        "  1) Start a Qwen3-TTS OpenAI-compatible server (vLLM-Omni or community FastAPI).\n"
        "  2) export LEMO_TTS_QWEN3_BASE=http://127.0.0.1:<port>\n"
        "  3) Implement HTTP client in core/tts/providers/qwen3.py (Sprint B).\n"
        f"  current LEMO_TTS_QWEN3_BASE={base!r}  lines={len(lines)} out_dir={out_dir}"
    )
