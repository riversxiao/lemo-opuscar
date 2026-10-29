#!/usr/bin/env python3
"""Shrink dead air inside / around each VO line (free, local, numpy only).

    python3 tools/deepseek-controller/pause_trim.py --project <film> [--pacing standard] [--dry-run]

Silence is found by energy (10 ms RMS < -38 dB re the line's 95th-percentile level),
so a cut can never land on speech. Every intra-line silence longer than the profile's
maxPauseSec is shrunk to keepPauseSec (8 ms crossfade); leading silence is cut to 30 ms
and trailing silence to 60 ms. Lines marked "beat": true keep their internal pauses
(deliberate rhythm beats — the only pauses that survive).

voices/words.json (local whisper timings from asr_check) is remapped onto the trimmed
audio and used to label each cut with the words it sits between. Originals are kept once
in voices/_pretrim/; voices/dur.json is rewritten; report → voices/pause_trim.json.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

import pacing_profile as pp

FRAME = 0.01
REL_DB = -38.0
LEAD_KEEP = 0.03
TAIL_KEEP = 0.06
XFADE = 0.008


def quiet_runs(a: np.ndarray, sr: int, rel_db: float = REL_DB) -> tuple[list[tuple[int, int]], int]:
    """Return ([(start_frame, end_frame)) quiet runs], n_frames)."""
    hop = max(1, int(FRAME * sr))
    n = len(a) // hop
    if n == 0:
        return [], 0
    rms = np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    ref = float(np.percentile(rms, 95)) or 1e-9
    quiet = 20 * np.log10(rms / ref) < rel_db
    runs, i = [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1
    return runs, n


def plan_cuts(a: np.ndarray, sr: int, *, max_pause: float, keep_pause: float,
              keep_internal: bool = False) -> list[tuple[float, float]]:
    """Return sorted [(cut_start_s, cut_end_s)] regions to REMOVE."""
    runs, n = quiet_runs(a, sr)
    if n == 0:
        return []
    total = len(a) / sr
    cuts: list[tuple[float, float]] = []
    for i, j in runs:
        s, e = i * FRAME, min(total, j * FRAME)
        if i == 0:  # leading
            if e - s > LEAD_KEEP:
                cuts.append((0.0, e - LEAD_KEEP))
            continue
        if j >= n:  # trailing (incl. the sub-frame remainder)
            if total - s > TAIL_KEEP:
                cuts.append((s + TAIL_KEEP, total))
            continue
        if keep_internal:
            continue
        if e - s > max_pause:
            half = keep_pause / 2
            cuts.append((s + half, e - half))
    return [(round(x, 4), round(y, 4)) for x, y in cuts if y - x > 0.02]


def apply_cuts(a: np.ndarray, sr: int, cuts: list[tuple[float, float]]) -> np.ndarray:
    if not cuts:
        return a
    xf = int(XFADE * sr)
    out = np.zeros(0, dtype=a.dtype)
    prev = 0
    for c0, c1 in cuts:
        i0, i1 = int(round(c0 * sr)), int(round(c1 * sr))
        seg = a[prev:i0]
        out = _join(out, seg, xf)
        prev = i1
    out = _join(out, a[prev:], xf)
    return out


def _join(x: np.ndarray, y: np.ndarray, xf: int) -> np.ndarray:
    if len(x) == 0:
        return y.copy()
    if len(y) == 0:
        return x
    k = min(xf, len(x), len(y))
    if k <= 1:
        return np.concatenate([x, y])
    ramp = np.linspace(0.0, 1.0, k, dtype=np.float32)
    mid = x[-k:] * (1 - ramp) + y[:k] * ramp
    return np.concatenate([x[:-k], mid, y[k:]])


def remap(t: float, cuts: list[tuple[float, float]]) -> float:
    """Old time → new time after removing `cuts` (times inside a cut clamp to its start)."""
    shift = 0.0
    for c0, c1 in cuts:
        if t >= c1:
            shift += c1 - c0
        elif t > c0:
            return round(c0 - shift, 3)
        else:
            break
    return round(max(0.0, t - shift), 3)


def _label(cut: tuple[float, float], words: list) -> str | None:
    if not words:
        return None
    before = [w for w in words if float(w[2]) <= cut[0] + 0.15]
    after = [w for w in words if float(w[1]) >= cut[1] - 0.15]
    a = str(before[-1][0]) if before else "^"
    b = str(after[0][0]) if after else "$"
    return f"{a}|{b}"


def _load_lines(project: Path) -> dict[str, dict[str, Any]]:
    for rel in ("content/lines.json", "audio/lines.json", "lines.json"):
        p = project / rel
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8"))
            d = d.get("lines", []) if isinstance(d, dict) else d
            return {str(L.get("id")): L for L in d if isinstance(L, dict)}
    return {}


def trim_project(project: Path, *, pacing: str | None = None, voices_dir: Path | None = None,
                 dry_run: bool = False) -> dict[str, Any]:
    project = Path(project).resolve()
    prof = pp.profile(project, pacing)
    vd = Path(voices_dir) if voices_dir else project / "voices"
    dur_p = vd / "dur.json"
    if not dur_p.is_file():
        raise FileNotFoundError(f"{dur_p} missing — run tts first")
    durs = json.loads(dur_p.read_text(encoding="utf-8"))
    words_p = vd / "words.json"
    words = json.loads(words_p.read_text(encoding="utf-8")) if words_p.is_file() else {}
    lines = _load_lines(project)
    bak = vd / "_pretrim"
    rep_lines: dict[str, Any] = {}
    new_durs: dict[str, float] = {}
    new_words: dict[str, Any] = dict(words)
    removed_total = 0.0
    for lid in durs:
        wav = vd / f"{lid}.wav"
        if not wav.is_file():
            new_durs[lid] = durs[lid]
            continue
        a, sr = sf.read(str(wav), dtype="float32")
        mono = a.mean(axis=1) if a.ndim > 1 else a
        beat = bool((lines.get(lid) or {}).get("beat"))
        cuts = plan_cuts(mono, sr, max_pause=float(prof["maxPauseSec"]),
                         keep_pause=float(prof["keepPauseSec"]), keep_internal=beat)
        out = apply_cuts(mono, sr, cuts)
        removed = round((len(mono) - len(out)) / sr, 3)
        removed_total += removed
        new_durs[lid] = round(len(out) / sr, 3)
        w = words.get(lid) or []
        rep_lines[lid] = {
            "before": round(len(mono) / sr, 3), "after": new_durs[lid], "removed": removed,
            "beat": beat,
            "cuts": [{"t0": c0, "t1": c1, "len": round(c1 - c0, 3), "between": _label((c0, c1), w)}
                     for c0, c1 in cuts],
        }
        if w:
            new_words[lid] = [[x[0], remap(max(0.0, float(x[1])), cuts), remap(float(x[2]), cuts)] for x in w]
        if not dry_run and cuts:
            bak.mkdir(exist_ok=True)
            if not (bak / wav.name).is_file():
                shutil.copy2(wav, bak / wav.name)
            sf.write(str(wav), out, sr)
    report = {
        "schemaVersion": 1, "pacing": prof["name"], "pacingSource": prof["source"],
        "maxPauseSec": prof["maxPauseSec"], "keepPauseSec": prof["keepPauseSec"],
        "relDb": REL_DB, "leadKeep": LEAD_KEEP, "tailKeep": TAIL_KEEP,
        "removedSec": round(removed_total, 3), "dryRun": dry_run,
        "wordsRemapped": bool(words), "lines": rep_lines,
    }
    if not dry_run:
        if not (bak / "dur.json").is_file() and bak.is_dir():
            shutil.copy2(dur_p, bak / "dur.json")
            if words_p.is_file():
                shutil.copy2(words_p, bak / "words.json")
        dur_p.write_text(json.dumps(new_durs, ensure_ascii=False, indent=1), encoding="utf-8")
        if words:
            words_p.write_text(json.dumps(new_words, ensure_ascii=False, indent=0), encoding="utf-8")
        (vd / "pause_trim.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--voices-dir")
    ap.add_argument("--pacing", help="fast|standard|calm (default: plan.json pacing / content_type)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        rep = trim_project(Path(a.project), pacing=a.pacing,
                           voices_dir=Path(a.voices_dir) if a.voices_dir else None, dry_run=a.dry_run)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    n = sum(len(v["cuts"]) for v in rep["lines"].values())
    print(f"OK pause_trim pacing={rep['pacing']} ({rep['pacingSource']}) cuts={n} "
          f"removed={rep['removedSec']}s{' (dry-run)' if rep['dryRun'] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
