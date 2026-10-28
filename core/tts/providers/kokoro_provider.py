"""Offline Kokoro via core/tts/tts.py. Ensures lang=cmn for CJK lines."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from typing import Any

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
            row.setdefault("voice", "zf_xiaoxiao")
        fixed.append(row)
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(fixed, f, ensure_ascii=False)
        path = f.name
    try:
        r = subprocess.run([sys.executable, TTS, path, out_dir])
        if r.returncode != 0:
            sys.exit(r.returncode)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    with open(os.path.join(out_dir, "dur.json"), encoding="utf-8") as f:
        return json.load(f)
