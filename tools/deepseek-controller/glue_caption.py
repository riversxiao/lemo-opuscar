"""Thin Caption News glue: copy locked demo → adapt → timeline/lines sidecars (never edit main.js)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common import dump_json, load_json
from fetch_fonts import ensure_caption_fonts
from glue_base import (
    engine_lines_from_content,
    finalize,
    prepare_project,
    reset_voices_dur,
    write_credits,
    write_palette_sidecar,
    write_project_md,
)


def _timeline_from_content(content: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Build engine-loadable timeline.json from timeline_content.json (times filled later by schedule)."""
    caps_in = content.get("caps") or []
    caps_out = []
    hook = None
    for i, c in enumerate(caps_in):
        zh = c.get("zh") or ""
        en = c.get("en") or c.get("zh") or ""
        row = {
            "t0": float(c.get("t0") or 0.0),
            "t1": float(c.get("t1") or 0.0),
            "zh": zh,
            "en": en,
        }
        if c.get("big"):
            row["big"] = c["big"]
        if c.get("role") == "hook" or c.get("k") == "hook" or i == 0:
            if hook is None:
                hook = {
                    "t0": row["t0"],
                    "t1": max(row["t1"], row["t0"] + 1.0),
                    "zh": zh.replace("|", " ").replace("{", "").replace("}", ""),
                    "en": en,
                }
                continue  # hook lives in TL.hook; remaining caps follow
        caps_out.append(row)

    target = float(plan.get("targetDurationSec") or content.get("targetDurationSec") or 30)
    return {
        "note": "Scaffolded by DeepSeek controller; times from schedule/timeline.parsed.json later.",
        "fps": int(content.get("fps") or 30),
        "dur": target,
        "bpm": 120,
        "vo": {},
        "hook": hook
        or {
            "t0": 0.0,
            "t1": 1.0,
            "zh": plan.get("topic") or "",
            "en": plan.get("topic") or "",
        },
        "caps": caps_out,
        "music": {"silences": [], "hits": {}},
    }


def _facts_md(facts: dict[str, Any], plan: dict[str, Any]) -> str:
    topic = plan.get("topic") or facts.get("topic") or "Untitled"
    lines = [
        f"# Facts · {topic}",
        "",
        "Generated from `content/facts.json` by thin glue. Replace with verified sources before formal delivery.",
        "",
    ]
    series = facts.get("series") or []
    if series:
        lines.append("| id | data |")
        lines.append("|---|---|")
        for row in series:
            rid = row.get("id", "")
            data = {k: v for k, v in row.items() if k != "id"}
            lines.append(f"| {rid} | `{data}` |")
        lines.append("")
    else:
        lines.append("_No numeric series in plan yet._")
        lines.append("")
    return "\n".join(lines)


def apply_touchables(project: Path, plan: dict[str, Any]) -> list[Path]:
    content = project / "content"
    written: list[Path] = []

    tc_path = content / "timeline_content.json"
    if not tc_path.is_file():
        raise FileNotFoundError(f"missing {tc_path} (run adapt first)")
    tc = load_json(tc_path)
    # timeline.json is the engine-fetched content file (main.js stays locked)
    tl = _timeline_from_content(tc if isinstance(tc, dict) else {}, plan)
    dump_json(project / "timeline.json", tl)
    written.append(project / "timeline.json")

    lines_path = content / "lines.json"
    raw_lines: list = []
    if lines_path.is_file():
        raw = load_json(lines_path)
        if isinstance(raw, list):
            raw_lines = raw
    engine_lines = engine_lines_from_content(raw_lines)
    dump_json(project / "lines.json", engine_lines)
    written.append(project / "lines.json")
    audio = project / "audio"
    audio.mkdir(exist_ok=True)
    dump_json(audio / "lines.json", engine_lines)
    written.append(audio / "lines.json")

    facts_path = content / "facts.json"
    if facts_path.is_file():
        facts = load_json(facts_path)
        dump_json(project / "facts.json", facts)
        written.append(project / "facts.json")
        md = project / "FACTS.md"
        md.write_text(_facts_md(facts if isinstance(facts, dict) else {}, plan), encoding="utf-8")
        written.append(md)

    pal = write_palette_sidecar(project)
    if pal:
        written.append(pal)

    written.append(
        write_credits(
            project,
            plan,
            style="caption-news",
            protected_note="main.js / index.html / build.sh / fonts/** / tools/** / assets/**",
        )
    )
    # Caption demo uses audio/vo; also keep voices/ for controller schedule --require-vo
    written.append(reset_voices_dur(project, voices_subdir="voices"))
    vo = project / "audio" / "vo"
    vo.mkdir(parents=True, exist_ok=True)
    dump_json(vo / "dur.json", {})
    written.append(vo / "dur.json")
    return written


def glue_caption(
    plan_path: Path,
    out: Path,
    *,
    lib: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    plan, lib_root, demo, out, locks, written_adapt = prepare_project(
        plan_path, out, style="caption-news", lib=lib, force=force
    )
    font_actions = ensure_caption_fonts(out / "fonts", project=out)
    written_touch = apply_touchables(out, plan)
    proj_md = write_project_md(
        out,
        plan,
        lib_root,
        style="caption-news",
        protected_list="`main.js` · `index.html` · `build.sh` · `fonts/**` · `tools/**` · `assets/**`",
        content_blurb=(
            "- `content/plan.json`, `content/timeline_content.json`, `content/facts.json`, `content/lines.json`\n"
            "- Root `timeline.json` / `lines.json` / `audio/lines.json` / `FACTS.md` / `palette.json` / `CREDITS` are synced touchables.\n"
            "- `main.js` (including hardcoded SHOTS) stays byte-locked; caption/VO content rides on `timeline.json`.\n"
            "- Scaffold fills `fonts/*.woff2` via `fetch_fonts.py` (copy cache / sibling / `tools/fonts.sh`).\n"
            "- Locked bee score/music path unused in controller E2E — use `mix_vo_only.py`."
        ),
        tts_lines=f"{out}/audio/lines.json",
    )
    info = finalize(
        plan=plan,
        lib_root=lib_root,
        demo=demo,
        out=out,
        locks=locks,
        written_adapt=written_adapt,
        written_touch=written_touch,
        style="caption-news",
        mode="caption-glue",
    )
    info["project_md"] = str(proj_md)
    info["fonts"] = font_actions
    return info
