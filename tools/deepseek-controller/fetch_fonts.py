"""Fetch gitignored Swiss (and similar) OFL .ttf files into a project fonts/ dir.

Fonts are not shipped in Git (see root .gitignore). Scaffold calls this for swiss-motion.
Can also run standalone:

    python3 tools/deepseek-controller/fetch_fonts.py --project /path/to/film
    python3 tools/deepseek-controller/fetch_fonts.py --fonts-dir /path/to/fonts

Sources (raw.githubusercontent.com/google/fonts):
  - Archivo variable → Archivo-VF.ttf
  - DM Serif Display Regular
  - UnifrakturMaguntia Book → UnifrakturMaguntia-Regular.ttf (fonts.css name)

Fallback copy order when network fails:
  1) $LEMO_FONT_CACHE/<name>
  2) sibling project /workspace/films/*/fonts/<name> (best-effort)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

SWISS_FONTS: list[tuple[str, str]] = [
    (
        "Archivo-VF.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/Archivo%5Bwdth%2Cwght%5D.ttf",
    ),
    (
        "DMSerifDisplay-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/dmserifdisplay/DMSerifDisplay-Regular.ttf",
    ),
    (
        "UnifrakturMaguntia-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/unifrakturmaguntia/UnifrakturMaguntia-Book.ttf",
    ),
]

MIN_BYTES = 10_000


def _copy_fallback(name: str, dest: Path) -> bool:
    cache = os.environ.get("LEMO_FONT_CACHE", "").strip()
    candidates: list[Path] = []
    if cache:
        candidates.append(Path(cache) / name)
    # optional local e2e leftovers
    films = Path("/workspace/films")
    if films.is_dir():
        for p in films.glob(f"*/fonts/{name}"):
            candidates.append(p)
    for src in candidates:
        if src.is_file() and src.stat().st_size >= MIN_BYTES:
            shutil.copy2(src, dest)
            return True
    return False


def _download(url: str, dest: Path, timeout: float = 60.0) -> None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "lemo-deepseek-controller/fetch_fonts"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if len(data) < MIN_BYTES:
        raise RuntimeError(f"download too small ({len(data)} B) for {dest.name}")
    dest.write_bytes(data)


def ensure_swiss_fonts(fonts_dir: Path, *, force: bool = False) -> list[str]:
    """Ensure Swiss demo fonts exist under fonts_dir. Returns list of actions."""
    fonts_dir = Path(fonts_dir)
    fonts_dir.mkdir(parents=True, exist_ok=True)
    actions: list[str] = []
    missing: list[str] = []
    for name, url in SWISS_FONTS:
        dest = fonts_dir / name
        if dest.is_file() and dest.stat().st_size >= MIN_BYTES and not force:
            actions.append(f"ok {name}")
            continue
        try:
            _download(url, dest)
            actions.append(f"fetched {name}")
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as e:
            if _copy_fallback(name, dest):
                actions.append(f"copied-fallback {name}")
            else:
                missing.append(f"{name} ({e})")
    if missing:
        raise FileNotFoundError(
            "Swiss fonts missing and could not be fetched/copied:\n  - "
            + "\n  - ".join(missing)
            + "\nSet LEMO_FONT_CACHE or run: python3 tools/deepseek-controller/fetch_fonts.py --fonts-dir "
            + str(fonts_dir)
        )
    return actions


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", help="film project root (uses <project>/fonts)")
    ap.add_argument("--fonts-dir", help="fonts directory directly")
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    args = ap.parse_args(argv)
    if args.fonts_dir:
        fonts = Path(args.fonts_dir)
    elif args.project:
        fonts = Path(args.project).resolve() / "fonts"
    else:
        ap.error("need --project or --fonts-dir")
        return 2
    try:
        actions = ensure_swiss_fonts(fonts, force=args.force)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    for a in actions:
        print(a)
    print(f"OK fonts → {fonts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
