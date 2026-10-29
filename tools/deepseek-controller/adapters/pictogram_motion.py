from __future__ import annotations

from pathlib import Path
from typing import Any
from common import dump_json, load_manifest

POSE_ALIASES = {"stand": "golf", "point": "fencing", "group": "relay"}
EN_GLOSS = {
    "分散投资": "DIVERSIFY", "资产": "ASSETS", "股票": "STOCKS",
    "债券": "BONDS", "现金": "CASH", "别押一把": "NO SINGLE BET",
    "组合": "PORTFOLIO", "资产类别": "ASSET CLASSES", "为何分散": "WHY DIVERSIFY",
}


def adapt_pictogram_motion(plan: dict[str, Any], out_dir: Path) -> list[Path]:
    man = load_manifest("pictogram-motion")
    content = out_dir / "content"
    content.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    dump_json(content / "plan.json", plan)
    written.append(content / "plan.json")

    edl_shots = []
    for sh in plan["shots"]:
        kind = "card"
        if sh["role"] == "chapter":
            kind = "chapter"
        elif sh["role"] in ("hook",):
            kind = "intro"
        elif sh["role"] in ("end", "credits", "payoff"):
            kind = "finale" if sh["motionPreset"] == "finale" else sh["role"]
        elif sh["motionPreset"] in ("intro", "chapter", "card", "finale"):
            kind = sh["motionPreset"]
        zh = sh.get("onScreenText") or sh["text"]
        pose = sh.get("pose")
        if pose in POSE_ALIASES:
            pose = POSE_ALIASES[pose]
        # Chapters: multi (catalogue); cards inherit; explain/risk cards: red
        if kind == "chapter":
            pal = "multi"
        elif sh.get("role") in ("explain",):
            pal = "red"
        else:
            pal = "multi"
        entry = {
            "id": sh["id"],
            "kind": kind,
            "role": sh["role"],
            "zh": zh,
            "en": sh.get("onScreenTextEn") or EN_GLOSS.get(zh) or (
                sh["text"] if plan.get("language") != "zh" else zh
            ),
            "pose": pose,
            "beats": sh.get("beats") or (8 if kind == "chapter" else 4),
            "motionPreset": sh["motionPreset"],
            "pal": pal,
            "data": sh.get("data") or {},
        }
        edl_shots.append(entry)

    dump_json(
        content / "edl_content.json",
        {
            "style": "pictogram-motion",
            "bpm": 150,
            "beatSec": man.get("beatGridSec", 0.4),
            "shots": edl_shots,
        },
    )
    written.append(content / "edl_content.json")

    lines = []
    voice = plan.get("voice") or {}
    if voice.get("provider", "none") != "none":
        for ln in voice.get("lines") or []:
            lines.append(
                {
                    "id": ln["id"],
                    "text": ln["text"],
                    "shotId": ln.get("shotId"),
                    **({"function": ln["role"]} if ln.get("role") else {}),
                    **({"cap": ln["cap"]} if ln.get("cap") else {}),
                    **({"say": ln["say"]} if ln.get("say") else {}),
                    "voice": voice.get("voiceId") or "zh-CN-YunxiNeural",
                    "speed": 1.0,
                }
            )
    dump_json(content / "lines.json", lines)
    written.append(content / "lines.json")

    pal = plan.get("palette") or {
        "page": "#0B0B0B",
        "ink": "#F5F0E8",
        "signal": "#E30613",
        "accent": "#C9A227",
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
        "# Pictogram Motion — touchable files\n\n"
        + "\n".join(f"- `{p}`" for p in man["touchableOutputs"])
        + "\n\n## Protected\n\n"
        + "\n".join(f"- `{g}`" for g in man["protectedGlobs"])
        + "\n\nPrefer Chinese as primary on-screen title for `language: zh`.\n"
        + "Do not edit `engine.js` / `scenes.js` / `poses/**`.\n",
        encoding="utf-8",
    )
    written.append(touch)
    return written
