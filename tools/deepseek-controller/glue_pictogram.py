"""Thin Pictogram glue: copy locked demo → adapt → touchable sidecars (never edit engine.js/edl.js)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common import dump_json, load_json
from fetch_fonts import ensure_pictogram_fonts
from glue_base import (
    engine_lines_from_content,
    finalize,
    prepare_project,
    reset_voices_dur,
    write_credits,
    write_palette_sidecar,
    write_project_md,
)


def apply_touchables(project: Path, plan: dict[str, Any]) -> list[Path]:
    content = project / "content"
    written: list[Path] = []

    edl_src = content / "edl_content.json"
    if not edl_src.is_file():
        raise FileNotFoundError(f"missing {edl_src} (run adapt first)")
    # Root sidecar — schedule/apply compile this into edl_runtime.json (page.mjs bridge)
    dump_json(project / "edl_content.json", load_json(edl_src))
    written.append(project / "edl_content.json")

    lines_path = content / "lines.json"
    if lines_path.is_file():
        raw = load_json(lines_path)
        if isinstance(raw, list):
            dump_json(project / "lines.json", engine_lines_from_content(raw))
            written.append(project / "lines.json")

    pal = write_palette_sidecar(project)
    if pal:
        written.append(pal)

    written.append(
        write_credits(
            project,
            plan,
            style="pictogram-motion",
            protected_note="engine.js / edl.js / scenes.js / render.mjs / shot.mjs / poses/** / index.html",
        )
    )
    written.append(reset_voices_dur(project, voices_subdir="voices"))
    return written


def glue_pictogram(
    plan_path: Path,
    out: Path,
    *,
    lib: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    plan, lib_root, demo, out, locks, written_adapt = prepare_project(
        plan_path, out, style="pictogram-motion", lib=lib, force=force
    )
    font_actions = ensure_pictogram_fonts(out / "fonts", project=out)
    written_touch = apply_touchables(out, plan)
    proj_md = write_project_md(
        out,
        plan,
        lib_root,
        style="pictogram-motion",
        protected_list="`engine.js` · `edl.js` · `scenes.js` · `render.mjs` · `shot.mjs` · `poses/**` · `index.html` · `fonts/**`",
        content_blurb=(
            "- `content/plan.json`, `content/edl_content.json`, `content/lines.json`, `content/palette.json`\n"
            "- Root `edl_content.json` / `lines.json` / `palette.json` / `CREDITS` are synced touchables.\n"
            "- After schedule: `apply_pictogram_edl.py` writes `edl_runtime.json` + `timeline.json` (VO).\n"
            "- `core/render/page.mjs` loads `edl_runtime.json` after READY and re-evals `scenes.js` — "
            "`edl.js` / `scenes.js` hashes stay locked.\n"
            "- Scaffold fetches OFL `.ttf` into `fonts/` via `fetch_fonts.py` (or `$LEMO_FONT_CACHE`).\n"
            "- Optional `brand_strings.json` (from apply_pictogram_edl) rewrites Olympics HUD/intro/"
            "finale *literals* in the eval'd scenes.js source only — disk hash untouched.\n"
            "- Locked music.py is Olympics-length; E2E uses `mix_vo_only.py` (VO + silence)."
        ),
        tts_lines=f"{out}/lines.json",
        extra_steps="\n".join(
            [
                "# After TTS + schedule, compile runtime EDL (auto-run by schedule for pictogram)",
                f"python3 tools/deepseek-controller/apply_pictogram_edl.py --project {out}",
                "",
                f"python3 tools/deepseek-controller/cli.py quality --project {out} --delivery",
            ]
        ),
    )
    info = finalize(
        plan=plan,
        lib_root=lib_root,
        demo=demo,
        out=out,
        locks=locks,
        written_adapt=written_adapt,
        written_touch=written_touch,
        style="pictogram-motion",
        mode="pictogram-glue",
    )
    info["project_md"] = str(proj_md)
    info["fonts"] = font_actions
    return info
