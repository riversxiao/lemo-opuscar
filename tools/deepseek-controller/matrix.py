"""18-film comparison matrix tracker (read-only status helper).

Full factorial topic × style × path (3×3×2). The original 12-cell epic (M01–M12)
is preserved; M13–M18 are the cross-style × flash follow-up.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULT_TRACKER = ROOT / "fixtures" / "matrix-18.json"


def load_matrix(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_TRACKER
    data = json.loads(p.read_text(encoding="utf-8"))
    cells = data.get("cells")
    if not isinstance(cells, list):
        raise ValueError(f"matrix tracker has no cells list: {p}")
    dims = data.get("dimensions") or {}
    full = 1
    for axis in ("topic", "style", "path"):
        full *= len(dims.get(axis) or [])
    if full and len(cells) != full:
        raise ValueError(f"matrix tracker must have {full} cells (full factorial), got {len(cells)}: {p}")
    keys = [(c.get("topic"), c.get("style"), c.get("path")) for c in cells]
    if len(set(keys)) != len(keys):
        raise ValueError(f"matrix tracker has duplicate topic/style/path cells: {p}")
    ids = [c.get("id") for c in cells]
    if len(set(ids)) != len(ids):
        raise ValueError(f"matrix tracker has duplicate cell ids: {p}")
    return data


def resolve_film_dir(cell: dict[str, Any]) -> Path | None:
    for key in ("alias", "canonical"):
        raw = cell.get(key)
        if not raw:
            continue
        p = Path(raw)
        if p.is_dir():
            return p
    return None


def enrich_cell(cell: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with live filesystem hints."""
    out = dict(cell)
    film = resolve_film_dir(cell)
    out["filmDirExists"] = bool(film)
    mp4 = cell.get("mp4")
    if mp4:
        out["mp4Exists"] = Path(mp4).is_file()
    elif film:
        matches = list(film.glob("*.mp4"))
        out["mp4Exists"] = bool(matches)
        if matches and not out.get("mp4"):
            out["mp4Discovered"] = str(matches[0])
    else:
        out["mp4Exists"] = False
    ev = cell.get("evidence")
    out["evidenceExists"] = bool(ev and Path(ev).is_file())
    return out


def summary(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or load_matrix()
    cells = [enrich_cell(c) for c in data["cells"]]
    by_status: dict[str, int] = {}
    for c in cells:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
    filled = [c for c in cells if c["status"] != "empty"]
    return {
        "title": data.get("title"),
        "updated": data.get("updated"),
        "total": len(cells),
        "filled": len(filled),
        "byStatus": by_status,
        "nextKnife": data.get("nextKnife") or [],
        "cells": cells,
    }


def format_table(
    data: dict[str, Any] | None = None,
    *,
    filled_only: bool = False,
    cell_id: str | None = None,
    path: str | None = None,
) -> str:
    data = data or load_matrix()
    labels = data.get("topicLabels") or {}
    rows = []
    for c in data["cells"]:
        if cell_id and c["id"].upper() != cell_id.upper():
            continue
        if filled_only and c["status"] == "empty":
            continue
        if path and c.get("path") != path:
            continue
        e = enrich_cell(c)
        topic = labels.get(c["topic"], c["topic"])
        loc = e.get("alias") or e.get("canonical") or ""
        mp = "mp4✓" if e.get("mp4Exists") else "mp4·"
        ev = "ev✓" if e.get("evidenceExists") else "ev·"
        rows.append(
            f"{c['id']:<4} {c['topic']:<8} {c['style']:<10} {c['path']:<10} "
            f"{c['role']:<8} {c['status']:<14} {mp} {ev}  {topic}  {loc}"
        )
    header = (
        f"{'ID':<4} {'topic':<8} {'style':<10} {'path':<10} "
        f"{'role':<8} {'status':<14} media     label  location"
    )
    body = "\n".join(rows) if rows else "(no cells)"
    s = summary(data)
    foot = (
        f"\nfilled {s['filled']}/{s['total']}  "
        f"byStatus={s['byStatus']}  nextKnife={s['nextKnife']}"
    )
    return header + "\n" + body + foot


def cell_by_id(cell_id: str, data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    data = data or load_matrix()
    for c in data["cells"]:
        if c["id"].upper() == cell_id.upper():
            return enrich_cell(c)
    return None
