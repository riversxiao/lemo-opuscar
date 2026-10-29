"""Shared paths and helpers for the DeepSeek film controller."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
MANIFESTS = ROOT / "manifests"
SCHEMA_PATH = ROOT / "plan.schema.json"
STYLES = ("swiss-motion", "pictogram-motion", "caption-news")

# Keys / string values that look like code, shaders, or filesystem control
FORBIDDEN_KEY_RE = re.compile(
    r"(shader|glsl|wgsl|eval|Function|require|import\b|__proto__|constructor|"
    r"prototype|process\.|child_process|fs\.|path\.|shell|execSync|"
    r"\.mjs$|\.jsx?$|\.ts$|\.py$|\.wasm$)",
    re.I,
)
FORBIDDEN_VALUE_RE = re.compile(
    r"(^\s*(import|export|function|const|let|var|class)\b|"
    r"\brequire\s*\(|\beval\s*\(|new\s+Function\b|"
    r"gl\.(?:compile|shader)|#include\s|<script|"
    r"(?:^|[\"'])(?:\.\./|\./)?(?:styles|core|node_modules)/|"
    r"/etc/|/usr/|\.ssh/)",
    re.I,
)
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
ID_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,31}$")

# plan.aspect → render size (core/render/*.mjs --size WxH). 16:9 is the default.
ASPECT_SIZES: dict[str, tuple[int, int]] = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
DEFAULT_ASPECT = "16:9"
# Output frame rate of each locked demo (STYLE.md / build.sh); --fps for video.mjs + mux.sh
STYLE_FPS: dict[str, int] = {"swiss-motion": 24, "caption-news": 30, "pictogram-motion": 60}


# Where rendered films live (outside git). The matrix tracker and older notes record
# them under LEGACY_FILMS_ROOT; on other machines set WORDFILM_FILMS or use <repo>/films.
LEGACY_FILMS_ROOT = "/workspace/films"


def films_root() -> Path:
    """$WORDFILM_FILMS, else <repo>/films when it exists, else /workspace/films.

    The result may not exist (callers check is_dir() and skip)."""
    env = os.environ.get("WORDFILM_FILMS", "").strip()
    if env:
        return Path(env).expanduser()
    local = ROOT.parent.parent / "films"
    if local.is_dir():
        return local
    return Path(LEGACY_FILMS_ROOT)


def film_path(raw: str | Path) -> Path:
    """Map a recorded /workspace/films/... path onto films_root()."""
    s = str(raw)
    if s == LEGACY_FILMS_ROOT or s.startswith(LEGACY_FILMS_ROOT + "/"):
        return films_root() / s[len(LEGACY_FILMS_ROOT):].lstrip("/")
    return Path(s)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def plan_aspect(plan: dict[str, Any] | None) -> str:
    """Aspect of a plan dict ('16:9' when absent)."""
    if isinstance(plan, dict) and isinstance(plan.get("aspect"), str):
        return plan["aspect"]
    return DEFAULT_ASPECT


def render_size(plan_or_aspect: dict[str, Any] | str | None) -> tuple[int, int]:
    """(width, height) for a plan dict or an aspect string; unknown aspect raises ValueError."""
    aspect = plan_or_aspect if isinstance(plan_or_aspect, str) else plan_aspect(plan_or_aspect)
    if aspect not in ASPECT_SIZES:
        raise ValueError(f"unknown aspect {aspect!r} (need one of {list(ASPECT_SIZES)})")
    return ASPECT_SIZES[aspect]


def size_arg(size: tuple[int, int]) -> str:
    """(1080, 1920) → '1080x1920' (the --size value for core/render tools)."""
    return f"{int(size[0])}x{int(size[1])}"


def project_aspect(project: Path) -> str:
    """Aspect of a scaffolded project: engine.lock.json > content/plan.json > 16:9."""
    project = Path(project)
    for rel in ("content/engine.lock.json", "content/plan.json"):
        p = project / rel
        if not p.is_file():
            continue
        try:
            data = load_json(p)
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("aspect") in ASPECT_SIZES:
            return data["aspect"]
    return DEFAULT_ASPECT


def project_size(project: Path) -> tuple[int, int]:
    """Render size of a scaffolded project (see project_aspect)."""
    return ASPECT_SIZES[project_aspect(project)]


def dump_json(path: Path, data: Any, *, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")


def load_manifest(slug: str) -> dict:
    path = MANIFESTS / f"{slug}.json"
    if not path.is_file():
        raise FileNotFoundError(f"manifest not found: {path}")
    return load_json(path)


def walk_forbidden(obj: Any, path: str = "$") -> list[str]:
    """Return error strings for forbidden keys/values that look like code/paths."""
    errs: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if FORBIDDEN_KEY_RE.search(str(k)):
                errs.append(f"{p}: forbidden key (looks like code/path/shader)")
            errs.extend(walk_forbidden(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            errs.extend(walk_forbidden(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        if FORBIDDEN_VALUE_RE.search(obj):
            errs.append(f"{path}: forbidden string value (looks like code/path)")
        # bare absolute unix paths outside allowlisted short ids
        if obj.startswith("/") and len(obj) > 1 and not HEX.match(obj):
            errs.append(f"{path}: absolute path not allowed in plan")
    return errs
