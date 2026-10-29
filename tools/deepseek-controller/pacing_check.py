#!/usr/bin/env python3
"""Pacing gate: measure a delivered film's rhythm and grade it against its pacing profile.

    python3 tools/deepseek-controller/pacing_check.py --project <film> [--media film.mp4] [--json]

Local + free only: timeline.parsed.json cues, voices/dur.json, voices/words.json (local
whisper timings, optional), lines.json, and ffmpeg (scene detect + freezedetect) on the mp4.

Metrics (see docs/PACING.md): articulation 字/秒 (chars over word-span speech time),
overall 字/秒 (chars over film length), speech ratio, inter-line gap mean/max (beat-marked
lines exempt), longest intra-line pause, first-VO time, hook end, tail silence, pad,
shot mean/sd/max, visual changes / 10 s, longest stretch without a change, frozen frames.

Severity: each metric has (warn, fail) thresholds from pacing_profile.gate_thresholds().
Only FAIL-level misses are "major". P0 ships report-only (quality shows WARN, never
blocks); P1 `enforce=True` makes FAIL block delivery and drive ≤ 2 rework rounds.
Writes <project>/evidence/pacing-check.json.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics as st
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pacing_profile as pp

CJK = re.compile(r"[\u4e00-\u9fff]")
EN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
NUM = re.compile(r"(\d+(?:\.\d+)?)(%?)")
_ZH_DIG = "零一二三四五六七八九"


def _zh_int_len(n: int) -> int:
    """Syllables of a Mandarin integer reading (九十九=3, 一百万=3, 两千零五=4)."""
    if n == 0:
        return 1
    s, out, units = str(n), 0, len(str(n))
    if n >= 10 ** 8:
        return _zh_int_len(n // 10 ** 8) + 1 + (_zh_int_len(n % 10 ** 8) if n % 10 ** 8 else 0)
    if n >= 10 ** 4:
        return _zh_int_len(n // 10 ** 4) + 1 + (_zh_int_len(n % 10 ** 4) if n % 10 ** 4 else 0)
    zero = False
    for i, ch in enumerate(s):
        pos = units - 1 - i
        if ch == "0":
            zero = True
            continue
        if zero:
            out += 1  # 零
            zero = False
        out += 1 if (pos == 1 and ch == "1" and i == 0) else (2 if pos else 1)  # 十 vs 一十; 九十 = 2
    return out


def spoken_units(txt: str) -> int:
    """Spoken syllables of a zh line: Han chars + Arabic numbers read in Mandarin
    (99% → 百分之九十九 = 6, 97.5% → 8) + Latin acronyms letter by letter (VaR = 3, ES = 2;
    words longer than 4 letters ≈ len/3 syllables). Digits and Latin are spoken, so counting
    only Han chars undercounts finance/concept lines and fakes a slow cps."""
    n = len(CJK.findall(txt))
    for m in NUM.finditer(txt):
        whole, _, frac = m.group(1).partition(".")
        n += _zh_int_len(int(whole)) + (1 + len(frac) if frac else 0) + (3 if m.group(2) else 0)
    for w in EN.findall(txt):
        n += len(w) if len(w) <= 4 else max(1, round(len(w) / 3))
    return n
SCENE_TH = 0.08


def _ff(args: list[str]) -> str:
    try:
        return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args],
                              capture_output=True, text=True, timeout=900).stderr
    except (OSError, subprocess.TimeoutExpired):
        return ""


def media_duration(p: Path) -> float | None:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=60).stdout
        return float(out.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def visual_metrics(media: Path, dur: float) -> dict[str, Any]:
    sc = _ff(["-i", str(media), "-vf", f"scale=320:-2,select='gt(scene,{SCENE_TH})',showinfo",
              "-an", "-f", "null", "-"])
    ts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", sc)]
    pts = [0.0] + ts + [dur]
    longest = max((b - a for a, b in zip(pts, pts[1:])), default=dur)
    fz = _ff(["-i", str(media), "-vf", "scale=320:-2,freezedetect=n=0.002:d=1.0", "-an", "-f", "null", "-"])
    fs = [float(x) for x in re.findall(r"freeze_start: ([\d.]+)", fz)]
    fd = [float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", fz)]
    if len(fs) > len(fd):
        fd.append(max(0.0, dur - fs[-1]))
    return {
        "frozenSpans": [[round(a, 2), round(a + b, 2)] for a, b in zip(fs, fd)],
        "sceneChangeTimes": [round(x, 2) for x in ts],
        "sceneChanges": len(ts),
        "changesPer10s": round(len(ts) / dur * 10, 2) if dur else 0.0,
        "longestNoChangeSec": round(longest, 2),
        "frozenTotalSec": round(sum(fd), 2),
        "frozenMaxSec": round(max(fd), 2) if fd else 0.0,
        "frozenPct": round(sum(fd) / dur * 100, 1) if dur else 0.0,
    }


def _lines(project: Path) -> dict[str, dict[str, Any]]:
    for rel in ("content/lines.json", "audio/lines.json", "lines.json"):
        p = project / rel
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8"))
            d = d.get("lines", []) if isinstance(d, dict) else d
            return {str(L.get("id")): L for L in d if isinstance(L, dict)}
    return {}


def find_media(project: Path, media: Path | None = None) -> Path | None:
    if media and Path(media).is_file():
        return Path(media)
    for cand in ("out.mp4", f"{project.name}.mp4", "final.mp4", "film.mp4", "mux.mp4"):
        if (project / cand).is_file():
            return project / cand
    return None


def measure(project: Path, media: Path | None = None, *, visual: bool = True) -> dict[str, Any]:
    project = Path(project).resolve()
    tl = json.loads((project / "timeline.parsed.json").read_text(encoding="utf-8"))
    vd = project / "voices"
    durs = json.loads((vd / "dur.json").read_text(encoding="utf-8")) if (vd / "dur.json").is_file() else {}
    words = json.loads((vd / "words.json").read_text(encoding="utf-8")) if (vd / "words.json").is_file() else {}
    lines = _lines(project)
    media = find_media(project, media)
    D = (media_duration(media) if media else None) or float(tl.get("scheduledDurationSec") or 0)
    cues = sorted((c for c in tl.get("cues") or [] if c.get("type", "voice") == "voice"), key=lambda c: float(c["t"]))
    chars = en = 0
    spans: list[float] = []
    per_line: list[float] = []
    intra: list[float] = []
    segs: list[tuple[float, float, str]] = []
    words_used = 0
    for c in cues:
        lid = str(c["id"])
        t = float(c["t"])
        L = lines.get(lid) or {}
        txt = str(L.get("say") or L.get("text") or "")
        n = spoken_units(txt) if CJK.search(txt) else 0
        chars += n
        en += len(EN.findall(txt)) if not n else 0
        d = float(durs.get(lid) or 0.0)
        w = words.get(lid) or []
        if w and d and float(w[-1][2]) <= d + 0.3:
            words_used += 1
            s0, s1 = max(0.0, float(w[0][1])), min(d, float(w[-1][2]))
            for a, b in zip(w, w[1:]):
                g = float(b[1]) - float(a[2])
                if g > 0.25 and not L.get("beat"):
                    intra.append(round(g, 2))
        else:
            s0, s1 = 0.0, d
        span = max(0.05, s1 - s0)
        spans.append(span)
        if n:
            per_line.append(n / span)
        segs.append((t + s0, t + s1, lid))
    gaps = []
    for (a0, a1, aid), (b0, _b1, _bid) in zip(segs, segs[1:]):
        if (lines.get(aid) or {}).get("beat"):
            continue
        gaps.append(round(b0 - a1, 2))
    speech = sum(b - a for a, b, _ in segs)
    edit_shots = [float(s["dur"]) for s in tl.get("shots") or []]
    shots, shot_src = edit_shots, "timeline"
    br = project / "beats_runtime.json"
    if br.is_file():   # P1 visual sub-beats (beats.py → page.mjs): a reframe is a visual cut
        try:
            bb = json.loads(br.read_text(encoding="utf-8")).get("beats") or []
            if bb:
                shots = [round(float(b["t1"]) - float(b["t0"]), 3) for b in bb]
                shot_src = "beats_runtime"
        except (OSError, ValueError, KeyError, TypeError):
            pass
    hook_end = None
    for a0, a1, lid in segs:
        if (lines.get(lid) or {}).get("function") == "hook":
            hook_end = round(a1, 2)
            break
    m: dict[str, Any] = {
        "durationSec": round(D, 2),
        "targetSec": tl.get("targetDurationSec"),
        "contentSec": tl.get("contentDurationSec"),
        "padSec": float(tl.get("padSec") or 0.0),
        "outroSec": float(tl.get("outroSec") or 0.0),
        "lines": len(cues),
        "chars": chars,
        "enWords": en,
        "avgCharsPerLine": round(chars / max(1, len(cues)), 1),
        "articulationCps": round(chars / sum(spans), 2) if spans and chars else None,
        "lineCpsMin": round(min(per_line), 2) if per_line else None,
        "lineCpsMax": round(max(per_line), 2) if per_line else None,
        "overallCps": round(chars / D, 2) if D and chars else None,
        "enWps": round(en / sum(spans), 2) if en and spans else None,
        "speechRatio": round(speech / D, 3) if D else None,
        "interLineGapMean": round(st.mean(gaps), 2) if gaps else 0.0,
        "interLineGapMax": max(gaps) if gaps else 0.0,
        "intraPauseMax": max(intra) if intra else 0.0,
        "intraPauses": len(intra),
        "firstVoSec": round(segs[0][0], 2) if segs else None,
        "hookEndSec": hook_end,
        "tailSilenceSec": round(D - segs[-1][1], 2) if segs else None,
        "shots": len(shots),
        "shotMeanSec": round(st.mean(shots), 2) if shots else None,
        "shotSdSec": round(st.pstdev(shots), 2) if shots else None,
        "shotMaxSec": max(shots) if shots else None,
        "shotSource": shot_src,
        "editShotMaxSec": max(edit_shots) if edit_shots else None,
        "wordsTimingsUsed": words_used,
        "media": str(media) if media else None,
    }
    if visual and media:
        m.update(visual_metrics(media, D))
    return m


# metric key → (threshold key, direction)
RULES = [
    ("articulationCps", "articulation_cps_min", "min"),
    ("overallCps", "overall_cps_min", "min"),
    ("speechRatio", "speech_ratio_min", "min"),
    ("interLineGapMax", "inter_line_gap_max", "max"),
    ("intraPauseMax", "intra_pause_max", "max"),
    ("tailSilenceSec", "tail_silence_max", "max"),
    ("padSec", "pad_max", "max"),
    ("shotMaxSec", "shot_max_max", "max"),
    ("frozenMaxSec", "frozen_max_max", "max"),
    ("changesPer10s", "changes_per_10s_min", "min"),
    ("firstVoSec", "first_vo_max", "max"),
    ("hookEndSec", "hook_end_max", "max"),
]


def evaluate(m: dict[str, Any], pacing: str) -> dict[str, Any]:
    th = pp.gate_thresholds(pacing)
    items = []
    for key, tkey, d in RULES:
        v = m.get(key)
        if v is None:
            continue
        warn, fail = th[tkey]
        if d == "min":
            level = "FAIL" if v < fail else "WARN" if v < warn else "PASS"
        else:
            level = "FAIL" if v > fail else "WARN" if v > warn else "PASS"
        items.append({"metric": key, "value": v, "warn": warn, "fail": fail, "dir": d, "level": level})
    status = "FAIL" if any(i["level"] == "FAIL" for i in items) else (
        "WARN" if any(i["level"] == "WARN" for i in items) else "PASS")
    return {"status": status, "pacing": pacing, "items": items,
            "fails": [i for i in items if i["level"] == "FAIL"],
            "warns": [i for i in items if i["level"] == "WARN"]}


def run(project: Path, media: Path | None = None, *, pacing: str | None = None,
        visual: bool = True, write: bool = True) -> dict[str, Any]:
    project = Path(project).resolve()
    prof = pp.profile(project, pacing)
    m = measure(project, media, visual=visual)
    ev = evaluate(m, prof["name"])
    rep = {"schemaVersion": 1, "project": str(project), "pacingSource": prof["source"],
           "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "metrics": m, **ev}
    if write:
        d = project / "evidence"
        d.mkdir(parents=True, exist_ok=True)
        (d / "pacing-check.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return rep


def summary(rep: dict[str, Any]) -> str:
    bad = rep["fails"] + rep["warns"]
    parts = [f"{i['level']} {i['metric']}={i['value']} ({'≥' if i['dir'] == 'min' else '≤'}"
             f"{i['warn']} warn / {i['fail']} fail)" for i in bad]
    return f"pacing={rep['pacing']} {rep['status']}" + (": " + "; ".join(parts) if parts else "")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--media")
    ap.add_argument("--pacing")
    ap.add_argument("--no-visual", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--enforce", action="store_true", help="exit 1 on FAIL (P1); default report-only exit 0")
    a = ap.parse_args(argv)
    try:
        rep = run(Path(a.project), Path(a.media) if a.media else None, pacing=a.pacing, visual=not a.no_visual)
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(json.dumps(rep, ensure_ascii=False, indent=1) if a.json else summary(rep))
    return 1 if (a.enforce and rep["status"] == "FAIL") else 0


if __name__ == "__main__":
    raise SystemExit(main())
