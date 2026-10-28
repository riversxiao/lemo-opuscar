"""Scaffold a film project from a validated plan (Swiss full glue; others copy+adapt stubs)."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

from common import dump_json, load_json
from validate import validate_plan
from adapters import adapt
from glue_swiss import (
    PROTECTED_SWISS,
    SKIP_COPY_NAMES,
    glue_swiss,
    resolve_lib,
    sha256_file,
    verify_protected,
)

STYLE_DEMO = {
    "swiss-motion": "styles/swiss-motion/demo",
    "pictogram-motion": "styles/pictogram-motion/demo",
    "caption-news": "styles/caption-news/demo",
}

PROTECTED_BY_STYLE = {
    "swiss-motion": PROTECTED_SWISS,
    "pictogram-motion": ("engine.js", "edl.js", "scenes.js", "index.html", "render.mjs"),
    "caption-news": ("main.js", "index.html", "timeline.json"),
}


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in SKIP_COPY_NAMES}


def scaffold_stub(
    plan: dict[str, Any],
    out: Path,
    *,
    lib_root: Path,
    force: bool = False,
) -> dict[str, Any]:
    style = plan["style"]
    rel = STYLE_DEMO[style]
    demo = lib_root / rel
    if not demo.is_dir():
        raise FileNotFoundError(demo)

    out = Path(out).resolve()
    if out.exists():
        if not force:
            raise FileExistsError(f"refusing to overwrite {out} (pass --force)")
        shutil.rmtree(out)

    shutil.copytree(demo, out, ignore=_ignore)
    protected = PROTECTED_BY_STYLE.get(style, ())
    locks: dict[str, str] = {}
    for name in protected:
        src, dst = demo / name, out / name
        if src.is_file() and dst.is_file():
            locks[name] = sha256_file(src)
            if sha256_file(dst) != locks[name]:
                raise RuntimeError(f"copy corrupted {name}")

    written = adapt(plan, out)
    if locks:
        dump_json(
            out / "content" / "engine.lock.json",
            {
                "style": style,
                "demo": rel,
                "protectedSha256": locks,
                "glue": "stub-copy-adapt-only",
            },
        )
        errs = verify_protected(out, locks)
        if errs:
            raise RuntimeError("protected files changed after stub scaffold:\n  - " + "\n  - ".join(errs))

    # Minimal PROJECT.md for stubs
    md = out / "PROJECT.md"
    md.write_text(
        f"""# PROJECT — {plan.get('topic', 'film')} ({style})

Stub scaffold: demo copied + `content/` adapted.
**Deep wire into engine not implemented yet** (Swiss has full thin glue).

Protected (do not edit): {', '.join(protected) or '(see manifest)'}

```bash
python3 tools/deepseek-controller/cli.py schedule --project {out} --require-vo
python3 tools/deepseek-controller/cli.py quality --project {out} --skip-heavy --allow-unchecked
```
""",
        encoding="utf-8",
    )
    return {
        "project": str(out),
        "lib": str(lib_root),
        "style": style,
        "mode": "stub",
        "adapt": [str(p) for p in written],
        "protectedSha256": locks,
        "project_md": str(md),
    }


def scaffold(
    plan_path: Path,
    out: Path,
    *,
    lib: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    plan = load_json(Path(plan_path))
    errors = validate_plan(plan, strict_manifest=True)
    if errors:
        raise ValueError("invalid plan:\n  - " + "\n  - ".join(errors))
    style = plan["style"]
    if style == "swiss-motion":
        return {**glue_swiss(plan_path, out, lib=lib, force=force), "style": style, "mode": "swiss-glue"}
    if style not in STYLE_DEMO:
        raise ValueError(f"unsupported style for scaffold: {style}")
    lib_root = resolve_lib(lib)
    # resolve_lib checks swiss demo; also ensure this style exists
    if not (lib_root / STYLE_DEMO[style]).is_dir():
        raise FileNotFoundError(lib_root / STYLE_DEMO[style])
    return scaffold_stub(plan, out, lib_root=lib_root, force=force)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Scaffold film project from plan JSON")
    p.add_argument("plan", help="path to plan JSON")
    p.add_argument("-o", "--out", required=True, help="project output directory")
    p.add_argument("--lib", help="repo root containing styles/*/demo")
    p.add_argument("--force", action="store_true", help="overwrite existing project dir")
    args = p.parse_args(argv)
    try:
        info = scaffold(
            Path(args.plan),
            Path(args.out),
            lib=Path(args.lib) if args.lib else None,
            force=args.force,
        )
    except (ValueError, FileExistsError, FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK scaffold {info.get('style')} mode={info.get('mode')} → {info['project']}")
    for k in ("lock", "project_md"):
        if k in info:
            print(f"  {k}: {info[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
