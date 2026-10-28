#!/usr/bin/env python3
"""Apply timeline.parsed.json cues into Caption News touchable timeline.json.

Never edits main.js (SHOTS/DUR stay engine-locked). Only rewrites:
  timeline.json  → vo starts, hook/caps times, dur field for mix
  audio/lines.json t= (optional alignment)
  lines.json t=

Usage:
  python3 tools/deepseek-controller/apply_caption_timeline.py --project /path/to/film
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from common import dump_json, load_json


def _engine_dur(project: Path) -> float | None:
    """Read DUR from main.js when present (locked or not — informational for mix length)."""
    import re

    main = project / "main.js"
    if not main.is_file():
        return None
    try:
        blob = main.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.search(r"\bDUR\s*=\s*(\d+(?:\.\d+)?)\b", blob)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def apply_caption_timeline(
    project: Path,
    *,
    parsed: dict[str, Any] | None = None,
    enter: float = 0.35,
) -> dict[str, Any]:
    project = Path(project).resolve()
    parsed_path = project / "timeline.parsed.json"
    tl_path = project / "timeline.json"
    if parsed is None:
        if not parsed_path.is_file():
            raise FileNotFoundError(f"missing {parsed_path}")
        parsed = load_json(parsed_path)
    if not isinstance(parsed, dict):
        raise ValueError("timeline.parsed.json must be an object")
    if not tl_path.is_file():
        raise FileNotFoundError(f"missing {tl_path} (scaffold caption first)")

    tl = load_json(tl_path)
    if not isinstance(tl, dict):
        raise ValueError("timeline.json must be an object")

    shots = {s["id"]: s for s in (parsed.get("shots") or []) if isinstance(s, dict) and "id" in s}
    cues = [c for c in (parsed.get("cues") or []) if isinstance(c, dict)]

    vo: dict[str, float] = {}
    for c in cues:
        if c.get("type") != "voice":
            continue
        lid = c.get("id")
        if not lid:
            continue
        vo[str(lid)] = round(float(c.get("t") or 0.0), 4)

    # Fallback: distribute lines by shot t0+enter when cues missing
    if not vo:
        for s in parsed.get("shots") or []:
            for vid in s.get("voIds") or []:
                vo[str(vid)] = round(float(s["t0"]) + enter, 4)

    tl["vo"] = vo

    # Hook = first shot (or existing hook text with new times)
    shot_list = parsed.get("shots") or []
    if shot_list:
        first = shot_list[0]
        hook = tl.get("hook") if isinstance(tl.get("hook"), dict) else {}
        hook = dict(hook)
        hook["t0"] = round(float(first["t0"]), 4)
        hook["t1"] = round(float(first["t1"]), 4)
        if first.get("text") and not hook.get("zh"):
            hook["zh"] = str(first["text"]).replace("|", " ").replace("{", "").replace("}", "")
        tl["hook"] = hook

    # Re-time caps that carry an id matching a scheduled shot; keep unmatched as-is
    caps_in = tl.get("caps") if isinstance(tl.get("caps"), list) else []
    # Also pull from content/timeline_content for zh if caps empty of times
    caps_out: list[dict[str, Any]] = []
    # Build ordered non-hook shots for sequential caps if caps lack ids
    content_shots = [s for s in shot_list if s.get("role") != "hook"]
    # Prefer id-keyed update
    used_ids: set[str] = set()
    for i, c in enumerate(caps_in):
        if not isinstance(c, dict):
            continue
        row = dict(c)
        cid = row.get("id")
        match = shots.get(cid) if cid else None
        if match is None and i < len(content_shots):
            # positional: hook was stripped from engine caps in glue
            match = content_shots[i]
        if match is not None:
            row["t0"] = round(float(match["t0"]), 4)
            row["t1"] = round(float(match["t1"]), 4)
            used_ids.add(str(match["id"]))
        caps_out.append(row)

    # If timeline had no caps yet, synthesize from parsed shots (skip hook → TL.hook)
    if not caps_out and shot_list:
        for s in shot_list:
            if s.get("role") == "hook":
                continue
            caps_out.append(
                {
                    "t0": round(float(s["t0"]), 4),
                    "t1": round(float(s["t1"]), 4),
                    "zh": s.get("text") or "",
                    "en": s.get("text") or "",
                }
            )
    tl["caps"] = caps_out

    scheduled = float(parsed.get("scheduledDurationSec") or 0.0)
    engine_dur = _engine_dur(project)
    # Mix/audio length should cover the full engine render when DUR is locked.
    if engine_dur and engine_dur > 0:
        tl["dur"] = engine_dur
        tl["scheduleBudgetSec"] = scheduled
        tl["engineDurSec"] = engine_dur
    else:
        tl["dur"] = scheduled or float(tl.get("dur") or 30)

    dump_json(tl_path, tl)

    # Align line start times on touchable lines sidecars
    for rel in ("lines.json", "audio/lines.json", "content/lines.json"):
        lp = project / rel
        if not lp.is_file():
            continue
        raw = load_json(lp)
        if not isinstance(raw, list):
            continue
        changed = False
        for ln in raw:
            if not isinstance(ln, dict):
                continue
            lid = str(ln.get("id") or "")
            if lid in vo:
                ln["t"] = vo[lid]
                changed = True
        if changed:
            dump_json(lp, raw)

    return {
        "timeline": str(tl_path),
        "voCount": len(vo),
        "capsCount": len(caps_out),
        "dur": tl["dur"],
        "engineDurSec": engine_dur,
        "scheduledDurationSec": scheduled,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--enter", type=float, default=0.35)
    args = ap.parse_args(argv)
    try:
        info = apply_caption_timeline(Path(args.project), enter=args.enter)
    except (OSError, ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(
        f"OK caption timeline: vo={info['voCount']} caps={info['capsCount']} "
        f"dur={info['dur']} (scheduleBudget={info['scheduledDurationSec']}) → {info['timeline']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
