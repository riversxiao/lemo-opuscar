"""Thin Swiss glue: copy locked demo → adapt content → sync touchable root files only."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from common import dump_json, load_json, load_manifest
from validate import validate_plan
from adapters import adapt

PROTECTED_SWISS = (
    "ease.js",
    "film.js",
    "main.js",
    "mix.py",
    "index.html",
)

SKIP_COPY_NAMES = {".git", "__pycache__", ".DS_Store", "node_modules"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_lib(lib: Path | None) -> Path:
    if lib is not None:
        p = Path(lib).resolve()
        if not (p / "styles" / "swiss-motion" / "demo").is_dir():
            raise FileNotFoundError(f"LIB missing styles/swiss-motion/demo: {p}")
        return p
    # walk up from this file, then cwd
    here = Path(__file__).resolve().parent
    for cand in [here.parent.parent, Path.cwd(), *Path.cwd().parents]:
        if (cand / "styles" / "swiss-motion" / "demo").is_dir():
            return cand
    raise FileNotFoundError("could not find repo root (styles/swiss-motion/demo)")


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in SKIP_COPY_NAMES}


def copy_demo(demo: Path, project: Path) -> None:
    if project.exists():
        # refuse clobbering a non-empty non-scaffold dir without force handled by caller
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
    """Map content/lines.json → Swiss root lines.json shape (id/text/voice/speed/t)."""
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

    pal_path = content / "palette.json"
    if pal_path.is_file():
        pal = load_json(pal_path)
        # Sidecar only — film.js `C` stays locked; tooling/Flash may read this later.
        dump_json(project / "palette.json", pal)
        written.append(project / "palette.json")

    credits_path = content / "credits.json"
    credits = load_json(credits_path) if credits_path.is_file() else plan.get("credits") or {}
    title = credits.get("title") or plan.get("topic") or "Untitled"
    author = credits.get("author") or "riversxiao"
    year = credits.get("year") or "2026"
    license_ = credits.get("license") or "CC BY 4.0"
    credits_txt = (
        f"{title} — Swiss Motion Graphics · Lemo-DeepSeek · {author}\n\n"
        f"Year: {year}\n"
        f"License: {license_}\n\n"
        "Engine cores copied from styles/swiss-motion/demo/ (locked).\n"
        "Content from tools/deepseek-controller adapt + thin glue.\n"
        "Do not edit ease.js / film.js / main.js / mix.py / index.html in this project.\n"
    )
    cred = project / "CREDITS"
    cred.write_text(credits_txt, encoding="utf-8")
    written.append(cred)

    # Reset demo VO metadata so TTS regenerates for new lines
    voices = project / "voices"
    voices.mkdir(exist_ok=True)
    dump_json(voices / "dur.json", {})
    written.append(voices / "dur.json")
    for stale in ("words.json", "words_rel.json"):
        p = voices / stale
        if p.is_file():
            p.unlink()

    return written


def write_project_md(project: Path, plan: dict[str, Any], lib: Path) -> Path:
    topic = plan.get("topic", "film")
    rel_ctl = "tools/deepseek-controller"
    text = f"""# PROJECT — {topic} (swiss-motion)

Scaffolded by DeepSeek controller thin glue.
Lib: `{lib}`
Style demo locked from: `styles/swiss-motion/demo/`

## Do not edit

`ease.js` · `film.js` · `main.js` · `mix.py` · `index.html` · `fonts/**` · `tools/**`

See `content/TOUCHABLES.md` and `content/engine.lock.json`.

## Next commands (from repo root)

```bash
# 1) TTS → voices/*.wav + voices/dur.json  (edge / router)
python3 core/tts/tts_zh.py {project}/lines.json {project}/voices \\
  --voice zh-CN-YunxiNeural
# or: python3 core/tts/tts_router.py …

# 2) VO-driven schedule (fails if over target — no silent K-scale)
python3 {rel_ctl}/cli.py schedule --project {project} --require-vo

# 3) Optional: refresh foley/voice events from timeline (do not hand-edit events.json)
# node core/render/events.mjs {project}

# 4) Stills / video / mix / mux (Playwright path — heavy)
# bash {project}/build.sh   # or still.mjs / video.mjs / mix.py / mux per STYLE.md

# 5) Quality gate (omit --allow-unchecked for formal delivery)
python3 {rel_ctl}/cli.py quality --project {project} --media {project}/out.mp4
```

## Content source of truth

- `content/plan.json`, `content/shots.json`, `content/lines.json`, `content/palette.json`
- Root `lines.json` / `palette.json` / `CREDITS` are synced touchables for the demo loader.
- Palette sidecar does **not** rewrite `film.js` constants; visual C remains demo-locked until a future content bridge.
"""
    path = project / "PROJECT.md"
    path.write_text(text, encoding="utf-8")
    return path


def glue_swiss(
    plan_path: Path,
    out: Path,
    *,
    lib: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    lib_root = resolve_lib(lib)
    demo = lib_root / "styles" / "swiss-motion" / "demo"
    if not demo.is_dir():
        raise FileNotFoundError(demo)

    plan = load_json(Path(plan_path))
    errors = validate_plan(plan, strict_manifest=True)
    if errors:
        raise ValueError("invalid plan:\n  - " + "\n  - ".join(errors))
    if plan.get("style") != "swiss-motion":
        raise ValueError(f"glue_swiss expects style swiss-motion, got {plan.get('style')}")

    out = Path(out).resolve()
    if out.exists():
        if not force:
            raise FileExistsError(f"refusing to overwrite {out} (pass force=True)")
        shutil.rmtree(out)

    copy_demo(demo, out)
    locks = lock_protected(out, demo, PROTECTED_SWISS)

    written_adapt = adapt(plan, out)
    written_touch = apply_touchables(out, plan)

    lock_path = out / "content" / "engine.lock.json"
    dump_json(
        lock_path,
        {
            "style": "swiss-motion",
            "demo": str(demo.relative_to(lib_root)) if demo.is_relative_to(lib_root) else str(demo),
            "protectedSha256": locks,
        },
    )

    proj_md = write_project_md(out, plan, lib_root)

    post_errs = verify_protected(out, locks)
    if post_errs:
        raise RuntimeError("protected files changed after glue:\n  - " + "\n  - ".join(post_errs))

    return {
        "project": str(out),
        "lib": str(lib_root),
        "adapt": [str(p) for p in written_adapt],
        "touchables": [str(p) for p in written_touch],
        "lock": str(lock_path),
        "project_md": str(proj_md),
        "protectedSha256": locks,
    }
