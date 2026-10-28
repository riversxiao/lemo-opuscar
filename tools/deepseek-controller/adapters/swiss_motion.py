from __future__ import annotations

from pathlib import Path
from typing import Any

from common import dump_json, load_manifest


def adapt_swiss_motion(plan: dict[str, Any], out_dir: Path) -> list[Path]:
    man = load_manifest("swiss-motion")
    content = out_dir / "content"
    content.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    dump_json(content / "plan.json", plan)
    written.append(content / "plan.json")

    shots = []
    for sh in plan["shots"]:
        shots.append(
            {
                "id": sh["id"],
                "role": sh["role"],
                "text": sh["text"],
                "onScreenText": sh.get("onScreenText", sh["text"]),
                "motionPreset": sh["motionPreset"],
                "data": sh.get("data") or {},
                "allowDarkOpen": bool(sh.get("allowDarkOpen", False)),
            }
        )
    dump_json(content / "shots.json", {"style": "swiss-motion", "shots": shots})
    written.append(content / "shots.json")

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
    else:
        # still emit on-screen lines for silent films
        for sh in plan["shots"]:
            lines.append(
                {
                    "id": sh["id"],
                    "text": sh.get("onScreenText") or sh["text"],
                    "shotId": sh["id"],
                    "voice": None,
                    "speed": 1.0,
                }
            )
    dump_json(content / "lines.json", lines)
    written.append(content / "lines.json")

    pal = plan.get("palette") or {
        "page": "#EAE9E5",
        "paper": "#FFFFFF",
        "ink": "#111111",
        "signal": "#E30613",
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
        "# Swiss Motion — files the controller / Flash may touch\n\n"
        + "\n".join(f"- `{p}`" for p in man["touchableOutputs"])
        + "\n\n## Protected (do not edit)\n\n"
        + "\n".join(f"- `{g}`" for g in man["protectedGlobs"])
        + "\n\n"
        + "Copy `styles/swiss-motion/demo/` into the project first. "
        + "Adapter output lives under `content/`. Wire into the engine via thin project glue only — "
        + "never modify `ease.js` / `film.js` / `mix.py`.\n",
        encoding="utf-8",
    )
    written.append(touch)
    return written
