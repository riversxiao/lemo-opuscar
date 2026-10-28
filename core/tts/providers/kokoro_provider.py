"""Offline Kokoro via core/tts/tts.py. Ensures lang=cmn for CJK lines."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from typing import Any

from .runtime import resolve_voice_python

HERE = os.path.dirname(os.path.abspath(__file__))
TTS = os.path.join(HERE, "..", "tts.py")


def synthesize(lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
    fixed = []
    for L in lines:
        row = dict(L)
        text = row.get("say") or row.get("text") or ""
        lang = str(row.get("lang", "")).lower()
        if any("\u4e00" <= ch <= "\u9fff" for ch in text) and not lang.startswith("cmn") and not lang.startswith("zh"):
            row["lang"] = "cmn"
            # Prefer zf_xiaoxiao; strip edge-tts voice names that Kokoro rejects.
            v = row.get("voice") or ""
            if not v or "Neural" in str(v) or str(v).startswith("zh-CN"):
                row["voice"] = opts.get("voice") or "zf_xiaoxiao"
        elif opts.get("voice") and not row.get("voice"):
            row["voice"] = opts["voice"]
        fixed.append(row)
    python = opts.get("python") or resolve_voice_python(need_kokoro=True)
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False)
        path = f.name
    try:
        r = subprocess.run([python, TTS, path, out_dir])
        if r.returncode != 0:
            sys.exit(r.returncode or 1)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    with open(os.path.join(out_dir, "dur.json"), encoding="utf-8") as f:
        return json.load(f)
