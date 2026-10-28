"""Default provider: delegates to core/tts/tts_zh.py (edge-tts)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from typing import Any

from .runtime import resolve_voice_python

HERE = os.path.dirname(os.path.abspath(__file__))
TTS_ZH = os.path.join(HERE, "..", "tts_zh.py")


def synthesize(lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
    voice = opts.get("voice") or "zh-CN-YunxiNeural"
    rate = opts.get("rate") or "+0%"
    pitch = opts.get("pitch") or "+0Hz"
    python = opts.get("python") or resolve_voice_python(need_kokoro=False)
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(lines, f, ensure_ascii=False)
        path = f.name
    try:
        cmd = [python, TTS_ZH, path, out_dir, "--voice", voice, "--rate", rate, "--pitch", pitch]
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.exit(r.returncode or 1)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    dur_path = os.path.join(out_dir, "dur.json")
    with open(dur_path, encoding="utf-8") as f:
        return json.load(f)
