"""OmniVoice stub — OpenAI-compatible speech endpoint (e.g. Docker OmniVoice-FastAPI).

References:
- Model: k2-fsa/OmniVoice (clone via ref_audio)
- API example: diogod2r/OmniVoice-FastAPI → POST /v1/audio/speech on :8880
- Env: LEMO_TTS_OMNIVOICE_BASE=http://127.0.0.1:8880/v1
"""
from __future__ import annotations

import os
import sys
from typing import Any


def synthesize(lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
    base = opts.get("base") or os.environ.get("LEMO_TTS_OMNIVOICE_BASE", "")
    sys.exit(
        "tts_router: provider 'omnivoice' is stubbed.\n"
        "  Start OmniVoice (e.g. docker run … diogod2r/omnivoice-fastapi) then implement\n"
        "  the HTTP client here. export LEMO_TTS_OMNIVOICE_BASE=http://127.0.0.1:8880/v1\n"
        f"  current base={base!r}  lines={len(lines)} out_dir={out_dir}"
    )
