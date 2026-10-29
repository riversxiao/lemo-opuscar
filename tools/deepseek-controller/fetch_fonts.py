"""Fetch gitignored OFL font binaries into a project fonts/ dir.

Fonts are not shipped in Git (see root .gitignore). Scaffold calls this for
swiss-motion, pictogram-motion, and caption-news.

    python3 tools/deepseek-controller/fetch_fonts.py --project /path/to/film
    python3 tools/deepseek-controller/fetch_fonts.py --project /path --style pictogram-motion
    python3 tools/deepseek-controller/fetch_fonts.py --fonts-dir /path/to/fonts --style swiss-motion

Fallback copy order when network fails (or for caption woff2 subsets with no
stable raw URL):
  1) $LEMO_FONT_CACHE/<name>
  2) sibling <films root>/*/fonts/<name>, films root = $WORDFILM_FILMS, else
     <repo>/films, else /workspace/films (skipped when it does not exist)
  3) for caption: run <project>/tools/fonts.sh when present
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from common import films_root

# (dest_name, raw_url_or_None, min_bytes)
# url=None → copy-only / fonts.sh (caption glyph subsets)
SWISS_FONTS: list[tuple[str, str | None, int]] = [
    (
        "Archivo-VF.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/Archivo%5Bwdth%2Cwght%5D.ttf",
        10_000,
    ),
    (
        "DMSerifDisplay-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/dmserifdisplay/DMSerifDisplay-Regular.ttf",
        10_000,
    ),
    (
        "UnifrakturMaguntia-Regular.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/unifrakturmaguntia/UnifrakturMaguntia-Book.ttf",
        10_000,
    ),
]

PICTOGRAM_FONTS: list[tuple[str, str | None, int]] = [
    (
        "InterTightwght.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/intertight/InterTight%5Bwght%5D.ttf",
        10_000,
    ),
    (
        "DMMono-Medium.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/dmmono/DMMono-Medium.ttf",
        10_000,
    ),
    (
        "NotoSansSCwght.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf",
        10_000,
    ),
    (
        "NotoSansJPwght.ttf",
        "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf",
        10_000,
    ),
]

# Caption demo uses CSS API glyph subsets named it*.woff2 / sc*.woff2 — no stable
# raw full-font URL that matches those filenames. Prefer cache / sibling copy;
# optional tools/fonts.sh rebuild.
CAPTION_FONTS: list[tuple[str, str | None, int]] = [
    ("it500.woff2", None, 2_000),
    ("it600i.woff2", None, 2_000),
    ("it800.woff2", None, 2_000),
    ("sc500.woff2", None, 2_000),
    ("sc900.woff2", None, 2_000),
]

STYLE_FONTS: dict[str, list[tuple[str, str | None, int]]] = {
    "swiss-motion": SWISS_FONTS,
    "pictogram-motion": PICTOGRAM_FONTS,
    "caption-news": CAPTION_FONTS,
}

# Optional OFL license text copies (best-effort; not required for READY)
OFL_SIDECARS: dict[str, list[tuple[str, str]]] = {
    "swiss-motion": [
        ("OFL-Archivo.txt", "https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/OFL.txt"),
        ("OFL-DMSerifDisplay.txt", "https://raw.githubusercontent.com/google/fonts/main/ofl/dmserifdisplay/OFL.txt"),
        ("OFL-UnifrakturMaguntia.txt", "https://raw.githubusercontent.com/google/fonts/main/ofl/unifrakturmaguntia/OFL.txt"),
    ],
    "pictogram-motion": [
        ("OFL-intertight.txt", "https://raw.githubusercontent.com/google/fonts/main/ofl/intertight/OFL.txt"),
        ("OFL-dmmono.txt", "https://raw.githubusercontent.com/google/fonts/main/ofl/dmmono/OFL.txt"),
        ("OFL-notosanssc.txt", "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/OFL.txt"),
        ("OFL-notosansjp.txt", "https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/OFL.txt"),
    ],
    "caption-news": [
        ("OFL-intertight.txt", "https://raw.githubusercontent.com/google/fonts/main/ofl/intertight/OFL.txt"),
        ("OFL-notosanssc.txt", "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/OFL.txt"),
    ],
}


def _copy_fallback(name: str, dest: Path, min_bytes: int) -> bool:
    cache = os.environ.get("LEMO_FONT_CACHE", "").strip()
    candidates: list[Path] = []
    if cache:
        candidates.append(Path(cache) / name)
    films = films_root()
    if films.is_dir():
        for p in films.glob(f"*/fonts/{name}"):
            candidates.append(p)
    for src in candidates:
        if src.is_file() and src.stat().st_size >= min_bytes:
            shutil.copy2(src, dest)
            return True
    return False


def _download(url: str, dest: Path, timeout: float = 120.0) -> None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "lemo-deepseek-controller/fetch_fonts"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    dest.write_bytes(data)


def _try_caption_fonts_sh(project: Path | None) -> list[str]:
    """Run demo tools/fonts.sh when present (glyph subsets for READY)."""
    if project is None:
        return []
    script = project / "tools" / "fonts.sh"
    if not script.is_file():
        return []
    env = os.environ.copy()
    # Do not FORCE by default — only fill missing; FORCE=1 if user set it.
    try:
        subprocess.run(
            ["sh", str(script)],
            cwd=str(project),
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return [f"ran {script.relative_to(project)}"]
    except (OSError, subprocess.SubprocessError) as e:
        return [f"fonts.sh failed: {e}"]


def detect_style(project: Path | None) -> str | None:
    if project is None:
        return None
    lock = project / "content" / "engine.lock.json"
    if lock.is_file():
        try:
            import json

            st = json.loads(lock.read_text(encoding="utf-8")).get("style")
            if st in STYLE_FONTS:
                return str(st)
        except (OSError, ValueError):
            pass
    plan = project / "content" / "plan.json"
    if plan.is_file():
        try:
            import json

            st = json.loads(plan.read_text(encoding="utf-8")).get("style")
            if st in STYLE_FONTS:
                return str(st)
        except (OSError, ValueError):
            pass
    # Heuristic from filenames already expected
    fonts = project / "fonts"
    if (fonts / "Archivo-VF.ttf").exists() or (fonts / "fonts.css").exists():
        # swiss demo always has fonts.css
        if (project / "film.js").is_file():
            return "swiss-motion"
    if (project / "edl.js").is_file() and (project / "scenes.js").is_file():
        return "pictogram-motion"
    if (project / "main.js").is_file() and (project / "tools" / "fonts.sh").is_file():
        return "caption-news"
    return None


def ensure_fonts(
    fonts_dir: Path,
    style: str,
    *,
    force: bool = False,
    project: Path | None = None,
) -> list[str]:
    """Ensure style fonts exist under fonts_dir. Returns list of actions."""
    if style not in STYLE_FONTS:
        raise ValueError(f"unknown style for fonts: {style} (need {sorted(STYLE_FONTS)})")
    fonts_dir = Path(fonts_dir)
    fonts_dir.mkdir(parents=True, exist_ok=True)
    actions: list[str] = []
    missing: list[str] = []
    pack = STYLE_FONTS[style]

    # Caption: try fonts.sh once up front when anything missing (builds subsets).
    if style == "caption-news" and project is not None:
        need_sh = force or any(
            not ((fonts_dir / name).is_file() and (fonts_dir / name).stat().st_size >= mn)
            for name, _url, mn in pack
        )
        if need_sh:
            actions.extend(_try_caption_fonts_sh(project))

    for name, url, min_bytes in pack:
        dest = fonts_dir / name
        if dest.is_file() and dest.stat().st_size >= min_bytes and not force:
            actions.append(f"ok {name}")
            continue
        fetched = False
        if url:
            try:
                _download(url, dest)
                size = dest.stat().st_size
                if size < min_bytes:
                    dest.unlink(missing_ok=True)
                    raise RuntimeError(f"download too small ({size} B)")
                actions.append(f"fetched {name}")
                fetched = True
            except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as e:
                if _copy_fallback(name, dest, min_bytes):
                    actions.append(f"copied-fallback {name}")
                    fetched = True
                else:
                    missing.append(f"{name} ({e})")
        else:
            if _copy_fallback(name, dest, min_bytes):
                actions.append(f"copied-fallback {name}")
                fetched = True
            elif dest.is_file() and dest.stat().st_size >= min_bytes:
                actions.append(f"ok {name}")
                fetched = True
            else:
                missing.append(
                    f"{name} (no raw URL; set LEMO_FONT_CACHE or copy from a sibling film, "
                    f"or run tools/fonts.sh inside the caption project)"
                )
        if not fetched and name not in {m.split()[0] for m in missing}:
            pass

    # Best-effort OFL text
    for ofl_name, ofl_url in OFL_SIDECARS.get(style, []):
        dest = fonts_dir / ofl_name
        if dest.is_file() and dest.stat().st_size > 100 and not force:
            continue
        try:
            _download(ofl_url, dest, timeout=30)
            actions.append(f"fetched {ofl_name}")
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError):
            if _copy_fallback(ofl_name, dest, 100):
                actions.append(f"copied-fallback {ofl_name}")

    if missing:
        raise FileNotFoundError(
            f"{style} fonts missing and could not be fetched/copied:\n  - "
            + "\n  - ".join(missing)
            + "\nSet LEMO_FONT_CACHE or run: python3 tools/deepseek-controller/fetch_fonts.py "
            f"--fonts-dir {fonts_dir} --style {style}"
        )
    return actions


def ensure_swiss_fonts(fonts_dir: Path, *, force: bool = False) -> list[str]:
    """Back-compat wrapper used by glue_swiss."""
    return ensure_fonts(fonts_dir, "swiss-motion", force=force)


def ensure_pictogram_fonts(
    fonts_dir: Path, *, force: bool = False, project: Path | None = None
) -> list[str]:
    return ensure_fonts(fonts_dir, "pictogram-motion", force=force, project=project)


def ensure_caption_fonts(
    fonts_dir: Path, *, force: bool = False, project: Path | None = None
) -> list[str]:
    return ensure_fonts(fonts_dir, "caption-news", force=force, project=project)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", help="film project root (uses <project>/fonts)")
    ap.add_argument("--fonts-dir", help="fonts directory directly")
    ap.add_argument(
        "--style",
        choices=sorted(STYLE_FONTS) + ["auto"],
        default="auto",
        help="font pack (default: auto-detect from project)",
    )
    ap.add_argument("--force", action="store_true", help="re-download even if present")
    args = ap.parse_args(argv)
    project: Path | None = Path(args.project).resolve() if args.project else None
    if args.fonts_dir:
        fonts = Path(args.fonts_dir)
    elif project:
        fonts = project / "fonts"
    else:
        ap.error("need --project or --fonts-dir")
        return 2
    style = args.style
    if style == "auto":
        style = detect_style(project) or detect_style(fonts.parent if fonts.name == "fonts" else None)
        if not style:
            ap.error("could not auto-detect style; pass --style swiss-motion|pictogram-motion|caption-news")
            return 2
    try:
        actions = ensure_fonts(fonts, style, force=args.force, project=project)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    for a in actions:
        print(a)
    print(f"OK fonts style={style} → {fonts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
