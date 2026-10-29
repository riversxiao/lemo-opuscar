"""Controller TTS: resolve project lines → voices/ via core/tts/tts_router.

    python3 tools/deepseek-controller/cli.py tts --project <film> [--provider auto|edge|kokoro|…]
"""
from __future__ import annotations

import json
import os
import shutil
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
    rate: str | None = None,
    pitch: str = "+0Hz",
    post_words: bool = True,
    content_type: str | None = None,
    pacing: str | None = None,
    speed: float | None = None,
    trim_pauses: bool = True,
) -> dict[str, Any]:
    """rate/speed default to the pacing profile (edgeRate / stepaudioSpeed); explicit
    args win, then env LEMO_TTS_STEPAUDIO_SPEED for speed. After synthesis, pause_trim
    shrinks intra-line silences per profile (beat-marked lines keep theirs)."""
    import pacing_profile as pp

    project = project.resolve()
    prof = pp.profile(project, pacing)
    if not rate:
        rate = str(prof["edgeRate"])
    speeds: dict[str, float] = {}
    if speed is None:
        env_speed = os.environ.get("LEMO_TTS_STEPAUDIO_SPEED")
        speed = float(env_speed) if env_speed else float(prof["stepaudioSpeed"])
        env_el = os.environ.get("LEMO_TTS_ELEVENLABS_SPEED")
        speeds = {"stepaudio": speed,
                  "elevenlabs": float(env_el) if env_el else float(prof["elevenlabsSpeed"])}
    else:   # explicit --speed applies to every speed-capable provider
        speeds = {"stepaudio": float(speed), "elevenlabs": float(speed)}
    if content_type is None:
        # config field: plan.json {"content_type": "market|concept|personal|english"}
        plan = project / "plan.json"
        if plan.is_file():
            try:
                content_type = (json.loads(plan.read_text(encoding="utf-8")) or {}).get("content_type") or None
            except (OSError, ValueError, AttributeError):
                content_type = None
    lines_file = find_lines(project, lines_path)
    voices = (out_dir or (project / "voices")).resolve()
    voices.mkdir(parents=True, exist_ok=True)
    # previous take's word timings / trim backups no longer describe the new audio
    for stale in ("words.json", "pause_trim.json"):
        if (voices / stale).is_file():
            (voices / stale).unlink()
    if (voices / "_pretrim").is_dir():
        shutil.rmtree(voices / "_pretrim")
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
        content_type=content_type,
        speed=speeds,
    )
    trim = None
    if trim_pauses:
        import pause_trim

        trim = pause_trim.trim_project(project, pacing=prof["name"], voices_dir=voices)
        dur = json.loads((voices / "dur.json").read_text(encoding="utf-8"))
    meta = {
        "provider": used,
        "lines": str(lines_file),
        "voices": str(voices),
        "dur": dur,
        "contentType": content_type,
        "pacing": prof["name"],
        "pacingSource": prof["source"],
        "rate": rate,
        "speed": speeds.get(used),
        "pauseTrim": ({"removedSec": trim["removedSec"], "maxPauseSec": trim["maxPauseSec"]}
                      if trim else None),
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
