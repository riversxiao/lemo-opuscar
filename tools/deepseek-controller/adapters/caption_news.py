from __future__ import annotations

from pathlib import Path
from typing import Any
from common import dump_json, load_manifest


def adapt_caption_news(plan: dict[str, Any], out_dir: Path) -> list[Path]:
    man = load_manifest("caption-news")
    content = out_dir / "content"
    content.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    dump_json(content / "plan.json", plan)
    written.append(content / "plan.json")

    caps = []
    facts = {"topic": plan["topic"], "series": []}
    for sh in plan["shots"]:
        zh = sh.get("onScreenText") or sh["text"]
        caps.append(
            {
                "id": sh["id"],
                "role": sh["role"],
                "k": sh["motionPreset"],
                "zh": zh,
                "en": sh["text"],
                "data": sh.get("data") or {},
                "allowDarkOpen": bool(sh.get("allowDarkOpen", False)),
            }
        )
        if sh.get("data"):
            facts["series"].append({"id": sh["id"], **sh["data"]})

    dump_json(
        content / "timeline_content.json",
        {
            "style": "caption-news",
            "fps": 30,
            "targetDurationSec": plan["targetDurationSec"],
            "caps": caps,
            "note": "Times filled by schedule_from_voice / timeline.parsed.json; this file is content only.",
        },
    )
    written.append(content / "timeline_content.json")
    dump_json(content / "facts.json", facts)
    written.append(content / "facts.json")

    lines = []
    voice = plan.get("voice") or {}
    if voice.get("provider", "none") != "none":
        for ln in voice.get("lines") or []:
            lines.append(
                {
                    "id": ln["id"],
                    "text": ln["text"],
                    "shotId": ln.get("shotId"),
                    "voice": voice.get("voiceId") or "zh-CN-YunxiNeural",
                    "speed": 1.0,
                }
            )
    dump_json(content / "lines.json", lines)
    written.append(content / "lines.json")

    pal = plan.get("palette") or {
        "page": "#0E0E0C",
        "ink": "#F7F5EF",
        "signal": "#FFC21A",
        "accent": "#FF4A3D",
    }
    dump_json(content / "palette.json", pal)
    written.append(content / "palette.json")

    credits = plan.get("credits") or {
        "title": plan["topic"],
        "author": "riversxiao",
        "year": "2026",
        "license": "CC BY 4.0",
    }
    dump_json(content / "credits.json", credits)
    written.append(content / "credits.json")

    touch = content / "TOUCHABLES.md"
    touch.write_text(
        "# Caption News — touchable files\n\n"
        + "\n".join(f"- `{p}`" for p in man["touchableOutputs"])
        + "\n\n## Protected\n\n"
        + "\n".join(f"- `{g}`" for g in man["protectedGlobs"])
        + "\n\nPure-graphic presets only (stock|loss|stress|end|…). Do not pull live-action packs.\n",
        encoding="utf-8",
    )
    written.append(touch)
    return written
