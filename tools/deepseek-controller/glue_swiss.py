"""Thin Swiss glue: copy locked demo → adapt content → sync touchable root files only."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common import dump_json, load_json
from glue_base import (
    PROTECTED_BY_STYLE,
    engine_lines_from_content,
    finalize,
    prepare_project,
    reset_voices_dur,
    write_credits,
    write_palette_sidecar,
    write_project_md,
)

# Back-compat exports used by older imports / tests
PROTECTED_SWISS = PROTECTED_BY_STYLE["swiss-motion"]


def apply_touchables(project: Path, plan: dict[str, Any]) -> list[Path]:
    """Write only touchable root files from content/. Never touch ease.js / film.js / …"""
    content = project / "content"
    written: list[Path] = []

    lines_path = content / "lines.json"
    if not lines_path.is_file():
        raise FileNotFoundError(f"missing {lines_path} (run adapt first)")
    raw_lines = load_json(lines_path)
    if not isinstance(raw_lines, list):
        raise ValueError("content/lines.json must be a list")
    root_lines = project / "lines.json"
    dump_json(root_lines, engine_lines_from_content(raw_lines))
    written.append(root_lines)

    pal = write_palette_sidecar(project)
    if pal:
        written.append(pal)

    written.append(
        write_credits(
            project,
            plan,
            style="swiss-motion",
            protected_note="ease.js / film.js / main.js / mix.py / index.html",
        )
    )
    written.append(reset_voices_dur(project, voices_subdir="voices"))
    return written


def glue_swiss(
    plan_path: Path,
    out: Path,
    *,
    lib: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    plan, lib_root, demo, out, locks, written_adapt = prepare_project(
        plan_path, out, style="swiss-motion", lib=lib, force=force
    )
    written_touch = apply_touchables(out, plan)
    proj_md = write_project_md(
        out,
        plan,
        lib_root,
        style="swiss-motion",
        protected_list="`ease.js` · `film.js` · `main.js` · `mix.py` · `index.html` · `fonts/**` · `tools/**`",
        content_blurb=(
            "- `content/plan.json`, `content/shots.json`, `content/lines.json`, `content/palette.json`\n"
            "- Root `lines.json` / `palette.json` / `CREDITS` are synced touchables for the demo loader.\n"
            "- Palette sidecar does **not** rewrite `film.js` constants; visual C remains demo-locked."
        ),
        tts_lines=f"{out}/lines.json",
    )
    info = finalize(
        plan=plan,
        lib_root=lib_root,
        demo=demo,
        out=out,
        locks=locks,
        written_adapt=written_adapt,
        written_touch=written_touch,
        style="swiss-motion",
        mode="swiss-glue",
    )
    info["project_md"] = str(proj_md)
    return info
