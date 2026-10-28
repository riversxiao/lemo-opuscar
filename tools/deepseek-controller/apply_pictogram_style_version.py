#!/usr/bin/env python3
"""Apply a pictogram-motion maintainer style version (unlocks scenes.js structure only).

Default scaffold keeps styles/pictogram-motion/demo/scenes.js locked. This tool copies a
versioned scenes.js into an existing project and updates engine.lock.json so:

- engine.js / edl.js / index.html / render.mjs / shot.mjs stay demo-protected
- scenes.js moves to versionSha256 + styleVersion (no longer demo protectedSha256)
- locked-demo scaffold tests remain valid (they never call this)

Usage:
  python3 tools/deepseek-controller/apply_pictogram_style_version.py \\
    --project /path/to/film --version finance-v001
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from common import dump_json, load_json, ROOT


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def default_lib() -> Path:
    # tools/deepseek-controller → repo root
    return ROOT.parent.parent


def resolve_version_dir(lib: Path, version: str) -> Path:
    d = lib / "styles" / "pictogram-motion" / "versions" / version
    if not d.is_dir():
        raise FileNotFoundError(f"style version not found: {d}")
    scenes = d / "scenes.js"
    if not scenes.is_file():
        raise FileNotFoundError(f"missing {scenes}")
    return d


def apply_style_version(
    project: Path,
    version: str,
    *,
    lib: Path | None = None,
) -> dict[str, Any]:
    project = project.resolve()
    lib_root = (lib or default_lib()).resolve()
    ver_dir = resolve_version_dir(lib_root, version)
    src_scenes = ver_dir / "scenes.js"
    dst_scenes = project / "scenes.js"
    if not dst_scenes.is_file():
        raise FileNotFoundError(f"project has no scenes.js: {project}")

    lock_p = project / "content" / "engine.lock.json"
    if not lock_p.is_file():
        raise FileNotFoundError(f"missing {lock_p} (scaffold first)")
    lock = load_json(lock_p)
    if lock.get("style") not in (None, "pictogram-motion"):
        raise ValueError(f"engine.lock style is {lock.get('style')!r}, need pictogram-motion")

    shutil.copy2(src_scenes, dst_scenes)
    ver_hash = _sha256(dst_scenes)

    protected = dict(lock.get("protectedSha256") or {})
    # scenes.js leaves demo protection; recorded under versionSha256 instead
    protected.pop("scenes.js", None)
    version_sha = dict(lock.get("versionSha256") or {})
    version_sha["scenes.js"] = ver_hash

    lock["style"] = "pictogram-motion"
    lock["styleVersion"] = version
    lock["styleVersionPath"] = str(
        (Path("styles") / "pictogram-motion" / "versions" / version).as_posix()
    )
    lock["protectedSha256"] = protected
    lock["versionSha256"] = version_sha
    lock["unlocked"] = sorted(set(list(lock.get("unlocked") or []) + ["scenes.js"]))
    lock["note"] = (
        f"styleVersion={version}: scenes.js is maintainer overlay (intro/finale structure). "
        "engine.js/edl.js remain demo-locked; edl_runtime.json still overlays EDL."
    )
    dump_json(lock_p, lock)

    brand_p = project / "brand_strings.json"
    if brand_p.is_file():
        try:
            brand = load_json(brand_p)
            brand["applyLiterals"] = False
            brand["note"] = (
                (brand.get("note") or "")
                + f" styleVersion={version}: applyLiterals=false "
                "(scenes overlay owns strings; __BRAND_STRINGS still used)."
            ).strip()
            dump_json(brand_p, brand)
        except (OSError, ValueError, TypeError):
            pass

    # Marker for docs / quality
    marker = project / "content" / "STYLE_VERSION.md"
    marker.write_text(
        f"# Style version: `{version}`\n\n"
        f"Applied from `{lock['styleVersionPath']}/scenes.js`.\n\n"
        f"SHA-256 scenes.js: `{ver_hash}`\n\n"
        "Demo lock path unchanged for projects that never run this tool.\n",
        encoding="utf-8",
    )

    return {
        "project": str(project),
        "version": version,
        "scenes": str(dst_scenes),
        "scenesSha256": ver_hash,
        "lock": str(lock_p),
        "unlocked": lock["unlocked"],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Apply pictogram-motion style version (scenes.js)")
    p.add_argument("--project", required=True, help="scaffolded pictogram project")
    p.add_argument("--version", required=True, help="e.g. finance-v001")
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
    print(f"  scenesSha256: {info['scenesSha256'][:16]}…")
    print(f"  unlocked: {info['unlocked']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
