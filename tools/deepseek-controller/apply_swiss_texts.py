#!/usr/bin/env python3
"""Build texts_runtime.json for Swiss Motion — window.TEXTS(t) without editing film.js.

Locked demo main.js/film.js never register window.TEXTS. core/render/page.mjs, after
READY, fetches texts_runtime.json (if present) and installs window.TEXTS(t) so
readcheck.mjs can run. Disk hashes of film.js/main.js/index.html stay intact.

Boxes mirror film.js drawLine layout (page / center / wall). Hold windows follow
LAYOUT end times; when locked LAYOUT is shorter than readcheck need, t1 is padded
(holdPad) while boxes stay fully in-frame — documented in the JSON meta.

Frame size follows the project aspect (content/engine.lock.json, else
content/plan.json): 16:9 → 1920x1080 landscape boxes, 9:16 → 1080x1920 portrait
boxes. Every box is clamped inside that frame.

Usage:
  python3 tools/deepseek-controller/apply_swiss_texts.py --project /path/to/film [--aspect 9:16]
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import Any

from common import ASPECT_SIZES, DEFAULT_ASPECT, dump_json, load_json, project_aspect

# Mirrored from styles/swiss-motion/demo/film.js (do not import — keep Python-side).
# LAYOUT[id] = (endSec, pos, soft?)
LAYOUT: dict[str, tuple[float, str, int]] = {
    "l1": (7.8, "page", 0),
    "l2": (11.8, "page", 0),
    "l3": (15.8, "page", 0),
    "l4": (19.85, "page", 0),
    "l4b": (22.15, "page", 1),
    "l5": (99.0, "page", 0),
    "l5b": (27.4, "center", 0),
    "l6": (39.95, "wall", 0),
}

# pageOut starts sliding page text off-screen (film.js T.pageOut)
PAGE_OUT = 24.5
FX0 = 96.0  # film.js fx(0) with FM=96
# Frame size is not fixed here: build_texts_runtime clamps to ASPECT_SIZES[aspect].

# drawLine anchors: (ySmall, yBig, bigSize) — boxes cover small+big statement band
POS_BOX: dict[str, tuple[float, float, float, float]] = {
    # x0, y0, x1, y1 — generous in-frame boxes matching drawLine(fx(0), ySmall, yBig)
    "page": (FX0, 140.0, 1100.0, 290.0),
    "center": (FX0, 740.0, 1100.0, 880.0),
    "wall": (FX0, 900.0, 1100.0, 1040.0),
}

# 9:16 (1080x1920) portrait layout of film.js (PORT: margin FM=72, fx(0)=72, text
# column 72..1008, statements wrap at a 936 px measure on a 90 px line). Page band:
# small line y 350, big lines 440/530. Center and wall bands (poster above them):
# small y 1340, big lines 1430/1520. film.js keeps a statement to those two big lines
# (fitLine steps the type down from 76 px, min 36 px, when copy would wrap to a third
# line; Chinese copy breaks between characters, so it wraps like English), so the boxes
# hold about 50 hanzi of big copy (two lines at 36 px), more for Latin text; past that
# film.js warns and draws a third line. Keep in sync with film.js PORT.
FX0_PORTRAIT = 72.0
POS_BOX_PORTRAIT: dict[str, tuple[float, float, float, float]] = {
    "page": (FX0_PORTRAIT, 300.0, 1008.0, 560.0),
    "center": (FX0_PORTRAIT, 1300.0, 1008.0, 1560.0),
    "wall": (FX0_PORTRAIT, 1300.0, 1008.0, 1560.0),
}

POS_BOX_BY_ASPECT: dict[str, dict[str, tuple[float, float, float, float]]] = {
    "16:9": POS_BOX,
    "9:16": POS_BOX_PORTRAIT,
}

CJK = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
# readcheck defaults
CJK_CPS, LATIN_CPS, PAD, MIN_HOLD = 4.5, 15.0, 1.5, 1.5


def _need_hold(text: str) -> float:
    cjk = other = 0
    for ch in text:
        if ch.isspace():
            continue
        if CJK.search(ch):
            cjk += 1
        else:
            other += 1
    return max(MIN_HOLD, cjk / CJK_CPS + other / LATIN_CPS + PAD)


def _split_small_big(text: str) -> tuple[str, str]:
    """Match film.js setLines: split on first '. ' (Swiss ASCII hack for CJK)."""
    t = text or ""
    i = t.find(". ")
    if i < 0:
        # tolerate Chinese comma/period as content-side punctuation
        for sep in ("，", "。", ", "):
            j = t.find(sep)
            if j >= 0:
                small = t[: j + len(sep)].rstrip()
                big = t[j + len(sep) :].lstrip()
                return small, big or t
        return "", t
    return t[: i + 1], t[i + 2 :]


def _layout_for(line_id: str, t0: float) -> tuple[float, str]:
    if line_id in LAYOUT:
        end, pos, _soft = LAYOUT[line_id]
        return end, pos
    # Unknown id: page slot until pageOut, then center
    if t0 < PAGE_OUT - 0.5:
        return min(t0 + 4.0, PAGE_OUT), "page"
    return t0 + 4.0, "center"


def build_texts_runtime(
    lines: list[dict[str, Any]],
    *,
    dur: float | None = None,
    aspect: str = DEFAULT_ASPECT,
) -> dict[str, Any]:
    """Build TEXTS registry from engine lines.json rows for the aspect's frame."""
    if aspect not in ASPECT_SIZES:
        raise ValueError(f"unknown aspect {aspect!r} (need one of {list(ASPECT_SIZES)})")
    fw, fh = (float(v) for v in ASPECT_SIZES[aspect])
    boxes = POS_BOX_BY_ASPECT[aspect]
    entries: list[dict[str, Any]] = []
    hold_pads: list[dict[str, Any]] = []
    engine_dur = float(dur) if dur and dur > 0 else 44.0

    for ln in lines:
        if not isinstance(ln, dict):
            continue
        lid = str(ln.get("id") or "")
        if not lid:
            continue
        raw = str(ln.get("text") or "").strip()
        if not raw:
            continue
        t0 = float(ln.get("t") or 0.0)
        end, pos = _layout_for(lid, t0)
        small, big = _split_small_big(raw)
        # Prefer big statement (primary readable band); fall back to full
        report = big.strip() if big.strip() else raw
        # Visual window: page text leaves at PAGE_OUT
        t1_visual = float(end)
        if pos == "page":
            t1_visual = min(t1_visual, PAGE_OUT)
        t1_visual = max(t1_visual, t0 + 0.05)

        need = _need_hold(report)
        t1 = t1_visual
        padded = 0.0
        if t1 - t0 < need - 1e-6:
            t1 = min(t0 + need + 0.05, engine_dur)
            padded = round(t1 - t1_visual, 4)
            hold_pads.append(
                {
                    "id": lid,
                    "visualHoldSec": round(t1_visual - t0, 4),
                    "needSec": round(need, 4),
                    "padSec": padded,
                    "note": "locked LAYOUT shorter than readcheck need; TEXTS t1 extended, box stays in-frame",
                }
            )

        x0, y0, x1, y1 = boxes.get(pos, boxes["page"])
        # Clamp fully inside viewport (readcheck rejects partial)
        x0 = max(0.0, min(x0, fw - 2))
        y0 = max(0.0, min(y0, fh - 2))
        x1 = max(x0 + 1, min(x1, fw))
        y1 = max(y0 + 1, min(y1, fh))

        entries.append(
            {
                "id": lid,
                "text": report,
                "fullText": raw,
                "small": small,
                "t0": round(t0, 4),
                "t1": round(t1, 4),
                "t1Visual": round(t1_visual, 4),
                "pos": pos,
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
            }
        )

    return {
        "schemaVersion": 1,
        "bridge": "lines→texts_runtime",
        "style": "swiss-motion",
        "aspect": aspect,
        "frame": {"width": int(fw), "height": int(fh)},
        "engineDurSec": engine_dur,
        "pageOutSec": PAGE_OUT,
        "holdPad": hold_pads,
        "entries": entries,
        "note": (
            "page.mjs installs window.TEXTS(t) from this file after READY. "
            "film.js/main.js hashes unchanged. German poster TX literals stay demo-locked; "
            "registry covers touchable VO/statement lines only."
        ),
    }


def _engine_dur(project: Path) -> float:
    lock_p = project / "content" / "engine.lock.json"
    # Prefer DUR from film.js export if readable
    film = project / "film.js"
    if film.is_file():
        m = re.search(r"\bDUR\s*=\s*([0-9.]+)", film.read_text(encoding="utf-8", errors="ignore"))
        if m:
            return float(m.group(1))
    return 44.0


def apply_swiss_texts(project: Path, *, aspect: str | None = None) -> dict[str, Any]:
    project = project.resolve()
    aspect = aspect or project_aspect(project)
    lines_p = project / "lines.json"
    if not lines_p.is_file():
        lines_p = project / "content" / "lines.json"
    if not lines_p.is_file():
        raise FileNotFoundError(f"no lines.json under {project}")
    lines = load_json(lines_p)
    if not isinstance(lines, list):
        raise ValueError("lines.json must be a list")

    dur = _engine_dur(project)
    runtime = build_texts_runtime(lines, dur=dur, aspect=aspect)
    out = project / "texts_runtime.json"
    dump_json(out, runtime)
    return {
        "path": str(out),
        "entryCount": len(runtime["entries"]),
        "holdPadCount": len(runtime["holdPad"]),
        "engineDurSec": dur,
        "aspect": aspect,
        "frame": runtime["frame"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Apply swiss lines → texts_runtime (no film.js edit)")
    ap.add_argument("--project", required=True)
    ap.add_argument(
        "--aspect",
        choices=sorted(ASPECT_SIZES),
        default=None,
        help="override the project aspect (default: engine.lock.json / content/plan.json, else 16:9)",
    )
    args = ap.parse_args(argv)
    try:
        info = apply_swiss_texts(Path(args.project), aspect=args.aspect)
    except (OSError, ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(
        f"OK texts_runtime entries={info['entryCount']} "
        f"holdPad={info['holdPadCount']} dur={info['engineDurSec']}s "
        f"frame={info['frame']['width']}x{info['frame']['height']} → {info['path']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
