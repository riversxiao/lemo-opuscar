#!/usr/bin/env python3
"""Visual sub-beats + keyword emphasis frames (pacing P1) — style-agnostic.

  python3 beats.py --project P [--pacing standard] [--dry-run]

Writes <project>/beats_runtime.json. core/render/page.mjs installs it after READY for ANY style
(Caption / Swiss / Pictogram — including locked demos): it wraps window.render(t) and applies a
CSS reframe on the film layer + an accent emphasis frame on a separate overlay, and maps
window.TEXTS boxes through the same transform so readcheck / visual-check stay box-accurate.
Disk film.js / main.js / scenes.js are never edited.

Sub-beats: every timeline shot longer than the profile maxShotSec is split into ceil(dur/max)
sub-beats, boundaries snapped to line starts (±1.2 s) so a reframe lands on a new sentence.
Sub-beat 0 keeps the shot's own framing (identity); later sub-beats alternate push-in / offset
framings (scale 0.965–0.985, pull-back so nothing leaves title-safe). Shots already ≤ maxShotSec are left alone (no over-correction).

Keyword emphasis: lines whose `cap` (or text) carries {关键词} get ONE emphasis pulse when the
keyword is spoken (voices/words.json char timing; proportional fallback), never within 0.5 s of
a reframe and at most one per 2 s. Pulse = 1.5 % pull-back thump + accent border, 0.4 s.

Rework hook (pacing_rework.py): `drift` windows (slow 1.5 % pull-out) are added over frozen stretches.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import pacing_profile as pp

SCHEMA = 1
SNAP_SEC = 1.2
# (scale, ox px, oy px) for sub-beats 1, 2, 3… (sub-beat 0 = identity). Pull-back framings (<1):
# every element moves INWARD, so HUD / subtitle bars / text never enter the 5 % title-safe margin
# (a push-in did — measured on M19 A2 r1: 25 outside_title_safe). The revealed edge is filled with
# the page background colour by page.mjs.
FRAMINGS = [
    (0.965, 14.0, 8.0),
    (0.98, -12.0, 6.0),
    (0.97, -10.0, -6.0),
    (0.985, 12.0, -4.0),
]
DRIFT = -0.012      # slow pull-out across a long sub-beat / rework window
EMPH = {"dur": 0.4, "punch": -0.015, "border": 6, "minGap": 2.5, "avoidBeat": 0.5}
_PUNCT = re.compile(r"[\s，。、！？；：,.!?;:“”\"'（）()《》【】\-—…·|]")


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def keywords(line: dict[str, Any]) -> list[str]:
    for field in ("cap", "text", "say"):
        kws = re.findall(r"\{([^}]+)\}", str(line.get(field) or ""))
        if kws:
            return [k.strip() for k in kws if k.strip()]
    return []


def keyword_time(line: dict[str, Any], kw: str, start: float, dur: float,
                 words: list | None) -> tuple[float, str]:
    """Absolute time the keyword is spoken. ('words'|'text-ratio'|'fallback')."""
    text = _PUNCT.sub("", re.sub(r"[{}]", "", str(line.get("text") or line.get("say") or "")))
    k = _PUNCT.sub("", kw)
    idx = text.find(k) if k else -1
    if idx < 0 and k:
        idx = text.find(k[0])
    if idx < 0:
        return round(start + 0.4 * dur, 3), "fallback"
    if words:
        chars: list[tuple[str, float]] = []
        for w in words:
            try:
                tok, a, b = str(w[0]), float(w[1]), float(w[2])
            except (IndexError, TypeError, ValueError):
                continue
            tok = _PUNCT.sub("", tok)
            n = max(1, len(tok))
            a = max(0.0, a)
            for j, ch in enumerate(tok):
                chars.append((ch, a + (b - a) * j / n))
        if chars and abs(len(chars) - len(text)) <= 2:
            j = min(idx, len(chars) - 1)
            return round(start + min(chars[j][1], dur), 3), "words"
    return round(start + dur * idx / max(1, len(text)), 3), "text-ratio"


def split_shot(t0: float, t1: float, cue_starts: list[float], max_sec: float) -> list[float]:
    """Interior boundaries for one shot so each sub-beat ≤ max_sec, using as few sub-beats as
    possible (ceil(dur/max)); each boundary snaps to the nearest line start within ±SNAP_SEC that
    keeps both sides feasible, else falls on the even split."""
    dur = t1 - t0
    if dur <= max_sec + 1e-6:
        return []
    n = math.ceil(dur / max_sec)
    cands = sorted(c for c in cue_starts if t0 + 0.8 < c < t1 - 0.8)
    out: list[float] = []
    prev = t0
    for k in range(n - 1, 0, -1):          # k = sub-beats still to place after this boundary
        target = prev + (t1 - prev) / (k + 1)
        lo, hi = max(prev + 0.8, t1 - k * max_sec), min(prev + max_sec, t1 - 0.8)
        near = [c for c in cands if lo - 1e-6 <= c <= hi + 1e-6 and abs(c - target) <= SNAP_SEC]
        cut = min(near, key=lambda c: abs(c - target)) if near else min(max(target, lo), hi)
        out.append(round(cut, 3))
        prev = cut
    return out


def build(project: Path, pacing: str | None = None, *, drift: list[dict] | None = None,
          max_shot: float | None = None) -> dict[str, Any]:
    project = project.resolve()
    tl = _load(project / "timeline.parsed.json", None)
    if not tl or not tl.get("shots"):
        raise SystemExit(f"beats: no timeline.parsed.json shots in {project} (run schedule first)")
    prof = pp.profile(project, pacing)
    max_sec = float(max_shot or prof["maxShotSec"])
    lines = _load(project / "content" / "lines.json", [])
    if isinstance(lines, dict):
        lines = lines.get("lines") or []
    by_id = {str(l.get("id")): l for l in lines}
    durs = _load(project / "voices" / "dur.json", {})
    words = _load(project / "voices" / "words.json", {})
    cues = [c for c in tl.get("cues") or [] if c.get("type", "voice") == "voice"]
    cue_starts = [float(c["t"]) for c in cues]
    pal = _load(project / "palette.json", {}) or (_load(project / "content" / "plan.json", {}).get("palette") or {})
    accent = pal.get("signal") or pal.get("accent") or "#FFC21A"

    beats: list[dict[str, Any]] = []
    for s in tl["shots"]:
        t0, t1 = float(s["t0"]), float(s["t1"])
        bounds = split_shot(t0, t1, cue_starts, max_sec)
        edges = [t0] + bounds + [t1]
        for i in range(len(edges) - 1):
            sc, ox, oy = (1.0, 0.0, 0.0) if i == 0 else FRAMINGS[(i - 1) % len(FRAMINGS)]
            b = {"t0": round(edges[i], 3), "t1": round(edges[i + 1], 3), "shotId": s.get("id"),
                 "sub": i, "scale": sc, "ox": ox, "oy": oy, "kind": "shot" if i == 0 else "reframe"}
            # long sub-beats inside a split shot get a slow push so they never sit frozen
            if bounds and b["t1"] - b["t0"] >= 2.5:
                b["drift"] = DRIFT
            beats.append(b)
    beat_edges = sorted({b["t0"] for b in beats if b["kind"] == "reframe"} | {float(s["t0"]) for s in tl["shots"]})

    emphasis: list[dict[str, Any]] = []
    last_t = -1e9
    for c in cues:
        lid = str(c.get("id"))
        ln = by_id.get(lid) or {}
        kws = keywords(ln)
        if not kws:
            continue
        d = float(durs.get(lid) or 0.0) or 2.5
        t, how = keyword_time(ln, kws[0], float(c["t"]), d, words.get(lid) if isinstance(words, dict) else None)
        if any(abs(t - e) < EMPH["avoidBeat"] for e in beat_edges):
            continue
        if t - last_t < EMPH["minGap"]:
            continue
        emphasis.append({"t": t, "dur": EMPH["dur"], "lineId": lid, "keyword": kws[0], "timing": how})
        last_t = t

    reframes = sum(1 for b in beats if b["kind"] == "reframe")
    return {
        "schemaVersion": SCHEMA, "pacing": prof["name"], "pacingSource": prof["source"],
        "maxShotSec": max_sec, "dur": float(tl.get("scheduledDurationSec") or tl["shots"][-1]["t1"]),
        "accent": accent, "punch": EMPH["punch"], "border": EMPH["border"],
        "beats": beats, "emphasis": emphasis, "drift": list(drift or []),
        "stats": {"shots": len(tl["shots"]), "reframes": reframes, "emphasis": len(emphasis),
                  "beatMaxSec": round(max(b["t1"] - b["t0"] for b in beats), 3),
                  "editShotMaxSec": round(max(float(s["dur"]) for s in tl["shots"]), 3)},
    }


def write(project: Path, rt: dict[str, Any]) -> Path:
    out = project / "beats_runtime.json"
    out.write_text(json.dumps(rt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--pacing", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    p = Path(a.project)
    old = _load(p / "beats_runtime.json", {}) or {}
    rt = build(p, a.pacing, drift=old.get("drift"))
    st = rt["stats"]
    print(f"beats: pacing={rt['pacing']} max {rt['maxShotSec']}s → {st['reframes']} reframes, "
          f"{st['emphasis']} keyword frames; beat max {st['beatMaxSec']}s (edit shot max {st['editShotMaxSec']}s)")
    if not a.dry_run:
        print(f"→ {write(p, rt)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
