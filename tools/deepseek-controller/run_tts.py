"""Controller TTS: resolve project lines → voices/ via core/tts/tts_router.

    python3 tools/deepseek-controller/cli.py tts --project <film> [--provider auto|edge|kokoro|…]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TTS_DIR = ROOT / "core" / "tts"
if str(TTS_DIR) not in sys.path:
    sys.path.insert(0, str(TTS_DIR))

from tts_router import synthesize as router_synthesize  # noqa: E402
from providers.runtime import list_statuses  # noqa: E402


def find_lines(project: Path, explicit: Path | None = None) -> Path:
    if explicit is not None:
        p = explicit.resolve()
        if not p.is_file():
            raise FileNotFoundError(f"lines not found: {p}")
        return p
    candidates = [
        project / "content" / "lines.json",
        project / "audio" / "lines.json",
        project / "lines.json",
    ]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    raise FileNotFoundError(
        f"no lines.json under {project} (tried content/, audio/, root)"
    )


def run_tts(
    project: Path,
    *,
    provider: str = "edge",
    fallback: str = "edge,kokoro",
    lines_path: Path | None = None,
    out_dir: Path | None = None,
    voice: str | None = None,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    post_words: bool = True,
) -> dict[str, Any]:
    project = project.resolve()
    lines_file = find_lines(project, lines_path)
    voices = (out_dir or (project / "voices")).resolve()
    voices.mkdir(parents=True, exist_ok=True)
    lines = json.loads(lines_file.read_text(encoding="utf-8"))
    fb = [p.strip() for p in fallback.split(",") if p.strip()] if fallback else []
    used, dur = router_synthesize(
        lines,
        str(voices),
        provider=provider,
        fallback=fb,
        voice=voice,
        rate=rate,
        pitch=pitch,
    )
    meta = {
        "provider": used,
        "lines": str(lines_file),
        "voices": str(voices),
        "dur": dur,
        "statuses": [s.as_dict() for s in list_statuses()],
    }
    meta_path = voices / "tts_router.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if post_words:
        try:
            from zh_words_rel import build, CJK

            if any(CJK.search(str(L.get("text") or "")) for L in lines if isinstance(L, dict)):
                wr = build(project)
                meta["wordsRel"] = str(wr)
        except Exception as e:
            meta["wordsRelError"] = str(e)
    return meta
