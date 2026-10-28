#!/usr/bin/env python3
"""Apply a caption-news maintainer style version (unlocks main.js content only).

Default scaffold keeps styles/caption-news/demo/main.js locked. This tool copies a
versioned main.js into an existing project and updates engine.lock.json so:

- index.html / build.sh stay demo-protected
- main.js moves to versionSha256 + styleVersion (no longer demo protectedSha256)
- locked-demo scaffold tests / liudong-controller-e2e remain valid (they never call this)

Usage:
  python3 tools/deepseek-controller/apply_caption_style_version.py \\
    --project /path/to/film --version liquidity-v001
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any

from common import dump_json, load_json, ROOT


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def default_lib() -> Path:
    return ROOT.parent.parent


def resolve_version_dir(lib: Path, version: str) -> Path:
    d = lib / "styles" / "caption-news" / "versions" / version
    if not d.is_dir():
        raise FileNotFoundError(f"style version not found: {d}")
    main = d / "main.js"
    if not main.is_file():
        raise FileNotFoundError(f"missing {main}")
    return d


def apply_style_version(
    project: Path,
    version: str,
    *,
    lib: Path | None = None,
) -> dict[str, Any]:
    import shutil

    project = project.resolve()
    lib_root = (lib or default_lib()).resolve()
    ver_dir = resolve_version_dir(lib_root, version)
    src_main = ver_dir / "main.js"
    dst_main = project / "main.js"
    if not dst_main.is_file():
        raise FileNotFoundError(f"project has no main.js: {project}")

    lock_p = project / "content" / "engine.lock.json"
    if not lock_p.is_file():
        raise FileNotFoundError(f"missing {lock_p} (scaffold first)")
    lock = load_json(lock_p)
    if lock.get("style") not in (None, "caption-news"):
        raise ValueError(f"engine.lock style is {lock.get('style')!r}, need caption-news")

    shutil.copy2(src_main, dst_main)
    ver_hash = _sha256(dst_main)

    protected = dict(lock.get("protectedSha256") or {})
    protected.pop("main.js", None)
    version_sha = dict(lock.get("versionSha256") or {})
    version_sha["main.js"] = ver_hash

    lock["style"] = "caption-news"
    lock["styleVersion"] = version
    lock["styleVersionPath"] = str(
        (Path("styles") / "caption-news" / "versions" / version).as_posix()
    )
    lock["protectedSha256"] = protected
    lock["versionSha256"] = version_sha
    lock["unlocked"] = sorted(set(list(lock.get("unlocked") or []) + ["main.js"]))
    lock["note"] = (
        f"styleVersion={version}: main.js is maintainer overlay (SHOTS/TEXTS/DUR). "
        "index.html/build.sh remain demo-locked. Default e2e scaffold never runs this."
    )
    dump_json(lock_p, lock)

    marker = project / "content" / "STYLE_VERSION.md"
    marker.write_text(
        f"# Style version: `{version}`\n\n"
        f"Applied from `{lock['styleVersionPath']}/main.js`.\n\n"
        f"SHA-256 main.js: `{ver_hash}`\n\n"
        "Demo lock path unchanged for projects that never run this tool.\n",
        encoding="utf-8",
    )

    # Keep PROJECT.md honest about unlocked surface
    proj_md = project / "PROJECT.md"
    if proj_md.is_file():
        try:
            body = proj_md.read_text(encoding="utf-8")
            note = (
                f"\n\n## Style version `{version}`\n\n"
                f"`main.js` unlocked via `apply_caption_style_version.py` "
                f"(`styles/caption-news/versions/{version}/`). "
                "Default `liudong-controller-e2e` demo hash path is untouched.\n"
            )
            if f"Style version `{version}`" not in body:
                proj_md.write_text(body.rstrip() + note, encoding="utf-8")
        except OSError:
            pass

    return {
        "project": str(project),
        "version": version,
        "main": str(dst_main),
        "mainSha256": ver_hash,
        "lock": str(lock_p),
        "unlocked": lock["unlocked"],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Apply caption-news style version (main.js)")
    p.add_argument("--project", required=True, help="scaffolded caption project")
    p.add_argument("--version", required=True, help="e.g. liquidity-v001")
    p.add_argument("--lib", help="repo root (default: detect)")
    args = p.parse_args(argv)
    try:
        info = apply_style_version(
            Path(args.project),
            args.version,
            lib=Path(args.lib) if args.lib else None,
        )
    except (OSError, ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK style-version {info['version']} → {info['project']}")
    print(f"  mainSha256: {info['mainSha256'][:16]}…")
    print(f"  unlocked: {info['unlocked']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
