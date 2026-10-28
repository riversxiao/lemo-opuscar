"""Scaffold a film project from a validated plan (full thin glue for all three styles)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from common import load_json
from validate import validate_plan
from glue_base import STYLE_DEMO
from glue_swiss import glue_swiss
from glue_pictogram import glue_pictogram
from glue_caption import glue_caption

GLUE = {
    "swiss-motion": glue_swiss,
    "pictogram-motion": glue_pictogram,
    "caption-news": glue_caption,
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
    if style not in GLUE:
        raise ValueError(f"unsupported style for scaffold: {style} (need one of {sorted(GLUE)})")
    if style not in STYLE_DEMO:
        raise ValueError(f"no demo path for style: {style}")
    return GLUE[style](plan_path, out, lib=lib, force=force)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Scaffold film project from plan JSON (swiss / pictogram / caption)"
    )
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
