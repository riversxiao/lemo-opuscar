"""Thin Swiss glue: copy locked demo → adapt content → sync touchable root files only."""
from __future__ import annotations

import re
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
from fetch_fonts import ensure_swiss_fonts
from zh_words_rel import build as build_zh_words_rel

# Back-compat exports used by older imports / tests
PROTECTED_SWISS = PROTECTED_BY_STYLE["swiss-motion"]

CJK = re.compile("[\u3040-\u30ff\u4e00-\u9fff]")


def _plan_is_zh(plan: dict[str, Any]) -> bool:
    if str(plan.get("language") or "").startswith("zh"):
        return True
    voice = plan.get("voice") or {}
    for ln in voice.get("lines") or []:
        if CJK.search(str(ln.get("text") or "")):
            return True
    for sh in plan.get("shots") or []:
        if CJK.search(str(sh.get("text") or "")) or CJK.search(
            str(sh.get("onScreenText") or "")
        ):
            return True
    return False


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

    # CJK: sentence-level words_rel (never English tools/words.py). Safe before TTS.
    if _plan_is_zh(plan):
        wr = build_zh_words_rel(project)
        written.append(wr)

    # TEXTS overlay for readcheck (page.mjs); never edits film.js/main.js.
    try:
        from apply_swiss_texts import apply_swiss_texts

        info = apply_swiss_texts(project)
        written.append(project / "texts_runtime.json")
        _ = info
    except (OSError, ValueError, FileNotFoundError):
        pass

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
    # Fill gitignored .ttf so readcheck / browser are not blocked by missing fonts.
    # fonts/** is "protected" from Flash edits; scaffold may still fetch missing binaries.
    font_actions = ensure_swiss_fonts(out / "fonts")
    written_touch = apply_touchables(out, plan)
    blurb = "\n".join(
        [
            "- `content/plan.json`, `content/shots.json`, `content/lines.json`, `content/palette.json`",
            "- Root `lines.json` / `palette.json` / `CREDITS` are synced touchables for the demo loader.",
            "- Palette sidecar does **not** rewrite `film.js` constants; visual C remains demo-locked.",
            "- Scaffold fetches OFL `.ttf` into `fonts/` (gitignored upstream). Re-run: "
            "`python3 tools/deepseek-controller/fetch_fonts.py --project <proj>`",
            "- zh plans get `voices/words_rel.json` via `zh_words_rel.py` (not `tools/words.py`).",
            "- `texts_runtime.json` (from glue/schedule) → `page.mjs` installs "
            "`window.TEXTS(t)` after READY; film.js/main.js hashes stay locked.",
            "- Without texts_runtime: readcheck `NOT_APPLICABLE` "
            "`swiss-demo-without-registry` (not eternal NOT_CHECKED).",
        ]
    )
    extra = "\n".join(
        [
            "# After TTS, refresh zh words_rel (scaffold already wrote a stub)",
            f"python3 tools/deepseek-controller/zh_words_rel.py --project {out}",
            "",
            "# Quality: VO required when plan has lines; optional ASR tolerant mode for finance homophones",
            f"python3 tools/deepseek-controller/cli.py quality --project {out} "
            "--require-vo --asr-mode=zh-homophone-tolerant",
        ]
    )
    proj_md = write_project_md(
        out,
        plan,
        lib_root,
        style="swiss-motion",
        protected_list=(
            "`ease.js` · `film.js` · `main.js` · `mix.py` · `index.html` · "
            "`fonts/**` (Flash) · `tools/**`"
        ),
        content_blurb=blurb,
        tts_lines=f"{out}/lines.json",
        extra_steps=extra,
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
    info["fonts"] = font_actions
    return info
