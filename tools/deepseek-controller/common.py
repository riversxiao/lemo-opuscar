"""Shared paths and helpers for the DeepSeek film controller."""
from __future__ import annotations

import json
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


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


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
