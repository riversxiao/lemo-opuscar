"""Shared thin-glue helpers for all controller styles."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from common import dump_json, load_json
from validate import validate_plan
from adapters import adapt

SKIP_COPY_NAMES = {".git", "__pycache__", ".DS_Store", "node_modules"}

STYLE_DEMO = {
    "swiss-motion": "styles/swiss-motion/demo",
    "pictogram-motion": "styles/pictogram-motion/demo",
    "caption-news": "styles/caption-news/demo",
}

PROTECTED_BY_STYLE: dict[str, tuple[str, ...]] = {
    "swiss-motion": ("ease.js", "film.js", "main.js", "mix.py", "index.html"),
    "pictogram-motion": ("engine.js", "edl.js", "scenes.js", "index.html", "render.mjs", "shot.mjs"),
    "caption-news": ("main.js", "index.html", "build.sh"),
}

STYLE_TITLE = {
    "swiss-motion": "Swiss Motion Graphics",
    "pictogram-motion": "Pictogram Motion",
    "caption-news": "Caption News",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_lib(lib: Path | None, *, need_style: str | None = None) -> Path:
    def ok(root: Path) -> bool:
        if need_style:
            return (root / STYLE_DEMO[need_style]).is_dir()
        return (root / "styles" / "swiss-motion" / "demo").is_dir()

    if lib is not None:
        p = Path(lib).resolve()
        if not ok(p):
            raise FileNotFoundError(f"LIB missing style demo: {p}")
        return p
    here = Path(__file__).resolve().parent
    for cand in [here.parent.parent, Path.cwd(), *Path.cwd().parents]:
        if ok(cand):
            return cand
    raise FileNotFoundError("could not find repo root with styles/*/demo")


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in SKIP_COPY_NAMES}


def copy_demo(demo: Path, project: Path) -> None:
    if project.exists():
        raise FileExistsError(f"project already exists: {project}")
    shutil.copytree(demo, project, ignore=_ignore)


def lock_protected(project: Path, demo: Path, names: tuple[str, ...]) -> dict[str, str]:
    locks: dict[str, str] = {}
    for name in names:
        src = demo / name
        dst = project / name
        if not src.is_file() or not dst.is_file():
            raise FileNotFoundError(f"protected file missing for lock: {name}")
        hs = sha256_file(src)
        hd = sha256_file(dst)
        if hs != hd:
            raise RuntimeError(f"copy corrupted protected file {name}")
        locks[name] = hs
    return locks


def verify_protected(project: Path, locks: dict[str, str]) -> list[str]:
    errs: list[str] = []
    for name, expected in locks.items():
        p = project / name
        if not p.is_file():
            errs.append(f"missing protected {name}")
            continue
        got = sha256_file(p)
        if got != expected:
            errs.append(f"protected {name} hash changed ({got[:12]}… ≠ {expected[:12]}…)")
    return errs


def engine_lines_from_content(content_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ln in content_lines:
        row: dict[str, Any] = {
            "id": ln["id"],
            "t": float(ln["t"]) if "t" in ln else 0.0,
            "text": ln["text"],
            "voice": ln.get("voice") or "zh-CN-YunxiNeural",
            "speed": float(ln.get("speed") or 1.0),
        }
        if ln.get("asr"):
            row["asr"] = ln["asr"]
        if ln.get("shotId"):
            row["shotId"] = ln["shotId"]
        out.append(row)
    return out


def write_credits(
    project: Path,
    plan: dict[str, Any],
    *,
    style: str,
    protected_note: str,
) -> Path:
    content = project / "content"
    credits_path = content / "credits.json"
    credits = load_json(credits_path) if credits_path.is_file() else plan.get("credits") or {}
    title = credits.get("title") or plan.get("topic") or "Untitled"
    author = credits.get("author") or "riversxiao"
    year = credits.get("year") or "2026"
    license_ = credits.get("license") or "CC BY 4.0"
    demo_rel = STYLE_DEMO[style]
    text = (
        f"{title} — {STYLE_TITLE.get(style, style)} · Lemo-DeepSeek · {author}\n\n"
        f"Year: {year}\n"
        f"License: {license_}\n\n"
        f"Engine cores copied from {demo_rel}/ (locked).\n"
        "Content from tools/deepseek-controller adapt + thin glue.\n"
        f"Do not edit: {protected_note}\n"
    )
    path = project / "CREDITS"
    path.write_text(text, encoding="utf-8")
    return path


def write_palette_sidecar(project: Path) -> Path | None:
    pal_path = project / "content" / "palette.json"
    if not pal_path.is_file():
        return None
    dest = project / "palette.json"
    dump_json(dest, load_json(pal_path))
    return dest


def reset_voices_dur(project: Path, *, voices_subdir: str = "voices") -> Path:
    voices = project / voices_subdir
    voices.mkdir(parents=True, exist_ok=True)
    dest = voices / "dur.json"
    dump_json(dest, {})
    for stale in ("words.json", "words_rel.json"):
        p = voices / stale
        if p.is_file():
            p.unlink()
    return dest


def write_project_md(
    project: Path,
    plan: dict[str, Any],
    lib: Path,
    *,
    style: str,
    protected_list: str,
    content_blurb: str,
    tts_lines: str,
) -> Path:
    topic = plan.get("topic", "film")
    rel_ctl = "tools/deepseek-controller"
    demo_rel = STYLE_DEMO[style]
    text = f"""# PROJECT — {topic} ({style})

Scaffolded by DeepSeek controller thin glue.
Lib: `{lib}`
Style demo locked from: `{demo_rel}/`

## Do not edit

{protected_list}

See `content/TOUCHABLES.md` and `content/engine.lock.json`.

## Next commands (from repo root)

```bash
# 1) TTS → measured durations (skip if voice.provider is none)
python3 core/tts/tts_zh.py {tts_lines} {project}/voices \\
  --voice zh-CN-YunxiNeural
# or: python3 core/tts/tts_router.py …

# 2) VO-driven schedule (fails if over target — no silent K-scale)
python3 {rel_ctl}/cli.py schedule --project {project} --require-vo

# 3) Stills / video / mix / mux (Playwright path — heavy; not CI)
# follow styles/{style}/STYLE.md or project build.sh

# 4) Quality gate (omit --allow-unchecked for formal delivery)
python3 {rel_ctl}/cli.py quality --project {project} --media {project}/out.mp4
```

## Content source of truth

{content_blurb}
"""
    path = project / "PROJECT.md"
    path.write_text(text, encoding="utf-8")
    return path


def prepare_project(
    plan_path: Path,
    out: Path,
    *,
    style: str,
    lib: Path | None,
    force: bool,
) -> tuple[dict[str, Any], Path, Path, Path, dict[str, str], list[Path]]:
    """Validate, copy demo, lock protected, adapt. Returns plan, lib, demo, out, locks, adapt_paths."""
    if style not in STYLE_DEMO:
        raise ValueError(f"unsupported style: {style}")
    lib_root = resolve_lib(lib, need_style=style)
    demo = lib_root / STYLE_DEMO[style]
    if not demo.is_dir():
        raise FileNotFoundError(demo)

    plan = load_json(Path(plan_path))
    errors = validate_plan(plan, strict_manifest=True)
    if errors:
        raise ValueError("invalid plan:\n  - " + "\n  - ".join(errors))
    if plan.get("style") != style:
        raise ValueError(f"expected style {style}, got {plan.get('style')}")

    out = Path(out).resolve()
    if out.exists():
        if not force:
            raise FileExistsError(f"refusing to overwrite {out} (pass force=True)")
        shutil.rmtree(out)

    copy_demo(demo, out)
    protected = PROTECTED_BY_STYLE[style]
    locks = lock_protected(out, demo, protected)
    written_adapt = adapt(plan, out)
    return plan, lib_root, demo, out, locks, written_adapt


def finalize(
    *,
    plan: dict[str, Any],
    lib_root: Path,
    demo: Path,
    out: Path,
    locks: dict[str, str],
    written_adapt: list[Path],
    written_touch: list[Path],
    style: str,
    mode: str,
) -> dict[str, Any]:
    lock_path = out / "content" / "engine.lock.json"
    demo_rel = STYLE_DEMO[style]
    try:
        demo_s = str(demo.relative_to(lib_root))
    except ValueError:
        demo_s = str(demo)
    dump_json(
        lock_path,
        {
            "style": style,
            "demo": demo_s or demo_rel,
            "protectedSha256": locks,
            "glue": mode,
        },
    )
    post_errs = verify_protected(out, locks)
    if post_errs:
        raise RuntimeError("protected files changed after glue:\n  - " + "\n  - ".join(post_errs))
    return {
        "project": str(out),
        "lib": str(lib_root),
        "style": style,
        "mode": mode,
        "adapt": [str(p) for p in written_adapt],
        "touchables": [str(p) for p in written_touch],
        "lock": str(lock_path),
        "protectedSha256": locks,
    }
