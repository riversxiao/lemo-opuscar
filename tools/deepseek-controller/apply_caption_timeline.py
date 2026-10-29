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


def _project_lines(project: Path) -> list[dict[str, Any]]:
    for rel in ("content/lines.json", "audio/lines.json", "lines.json"):
        lp = project / rel
        if lp.is_file():
            raw = load_json(lp)
            if isinstance(raw, list):
                return [r for r in raw if isinstance(r, dict)]
    return []


def _per_line_caps(project: Path, shot_list: list[dict[str, Any]], vo: dict[str, float]) -> list[dict[str, Any]]:
    """capsMode=per-line: one caption card per VO line (zh = line.cap keyword blocks,
    en row = the full spoken sentence), timed from the line cue to the next cue in
    the same shot (or the shot end). Hook-role shots keep TL.hook instead."""
    lines = {str(ln.get("id")): ln for ln in _project_lines(project)}
    caps: list[dict[str, Any]] = []
    for sh in shot_list:
        if sh.get("role") == "hook":
            continue
        ids = [str(i) for i in (sh.get("voIds") or []) if str(i) in vo]
        for j, lid in enumerate(ids):
            ln = lines.get(lid, {})
            t0 = vo[lid]
            t1 = vo[ids[j + 1]] if j + 1 < len(ids) else float(sh["t1"])
            text = str(ln.get("text") or "")
            caps.append({
                "id": lid,
                "t0": round(max(float(sh["t0"]), t0 - 0.1), 4),
                "t1": round(t1, 4),
                "zh": str(ln.get("cap") or text),
                "en": text,
            })
    return caps


def _main_js_unlocked(project: Path) -> bool:
    lock_p = project / "content" / "engine.lock.json"
    if not lock_p.is_file():
        return False
    try:
        lock = load_json(lock_p)
    except (OSError, ValueError):
        return False
    return "main.js" in (lock.get("unlocked") or []) and "main.js" not in (lock.get("protectedSha256") or {})


def locked_engine_dur(project: Path, tl: dict[str, Any] | None = None) -> float | None:
    """main.js DUR when the render length is fixed, else None.

    timeline.json syncShots=true on an unlocked style-version main.js rewrites DUR
    from the schedule (sync_main_shots), so copy longer than the current DUR is
    not an overrun there. Everywhere else the render stops at DUR.
    """
    if tl is None:
        tl_path = project / "timeline.json"
        try:
            tl = load_json(tl_path) if tl_path.is_file() else {}
        except (OSError, ValueError):
            tl = {}
    if isinstance(tl, dict) and tl.get("syncShots") and _main_js_unlocked(project):
        return None
    return _engine_dur(project)


def sync_main_shots(project: Path, shot_list: list[dict[str, Any]], dur: float) -> bool:
    """timeline.json syncShots=true: rewrite project-copy main.js SHOTS a/b (in order)
    and DUR from the schedule. Only when engine.lock.json lists main.js as unlocked
    (style-version overlay); a hash-locked demo main.js is never touched."""
    import re

    main = project / "main.js"
    if not main.is_file() or not shot_list:
        return False
    if not _main_js_unlocked(project):
        raise ValueError("syncShots refused: main.js is not an unlocked style-version copy")
    src = main.read_text(encoding="utf-8")
    m = re.search(r"const SHOTS = \[(.*?)\n\];", src, re.S)
    if not m:
        raise ValueError("syncShots: `const SHOTS = [ ... ];` block not found in main.js")
    body = m.group(1)
    entries = list(re.finditer(r"\{\s*a:\s*[0-9.]+\s*,\s*b:\s*[0-9.]+\s*,", body))
    if len(entries) != len(shot_list):
        raise ValueError(f"syncShots: main.js has {len(entries)} SHOTS but schedule has {len(shot_list)} shots")
    out, last = [], 0
    for e, sh in zip(entries, shot_list):
        out.append(body[last:e.start()])
        out.append(f"{{ a: {float(sh['t0']):.2f}, b: {float(sh['t1']):.2f},")
        last = e.end()
    out.append(body[last:])
    src = src[:m.start(1)] + "".join(out) + src[m.end(1):]
    if dur > 0:
        src = re.sub(r"\bDUR = [0-9.]+", f"DUR = {dur:g}", src, count=1)
    main.write_text(src, encoding="utf-8")
    return True


def apply_caption_timeline(
    project: Path,
    *,
    parsed: dict[str, Any] | None = None,
    enter: float = 0.35,
    force: bool = False,
) -> dict[str, Any]:
    """Raises ValueError (unless force) when the parsed schedule failed or its
    copy runs past main.js DUR: applying it would render captions/VO that the
    locked picture cuts off."""
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

    if not force:
        if parsed.get("ok") is False:
            errs = "; ".join(str(e) for e in parsed.get("errors") or []) or "ok=false"
            raise ValueError(
                f"schedule did not pass ({errs}); fix the copy and re-run schedule "
                f"before applying (--force applies it anyway, diagnostics only)"
            )
        # syncShots on a locked main.js is refused below (sync_main_shots).
        locked = None if tl.get("syncShots") else locked_engine_dur(project, tl)
        content = float(parsed.get("contentDurationSec") or parsed.get("scheduledDurationSec") or 0.0)
        if locked and content > locked + 1e-6:
            raise ValueError(
                f"copy overruns the locked caption-news timeline by {content - locked:.2f}s: "
                f"content {content:.2f}s > main.js DUR {locked:.2f}s; trim captions/VO "
                f"and re-run schedule (--force applies it anyway, diagnostics only)"
            )

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
    if tl.get("capsMode") == "per-line":
        caps_out = _per_line_caps(project, shot_list, vo)
    tl["caps"] = caps_out

    scheduled = float(parsed.get("scheduledDurationSec") or 0.0)
    shots_synced = False
    if tl.get("syncShots"):
        shots_synced = sync_main_shots(project, shot_list, scheduled)
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
        "shotsSynced": shots_synced,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--enter", type=float, default=0.35)
    ap.add_argument(
        "--force",
        action="store_true",
        help="apply a failed or overrunning schedule anyway (diagnostics only, not for delivery)",
    )
    args = ap.parse_args(argv)
    try:
        info = apply_caption_timeline(Path(args.project), enter=args.enter, force=args.force)
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
