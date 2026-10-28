#!/usr/bin/env python3
"""VO-only mix for controller E2E when style score packs are unavailable.

Reads timeline.json vo{id→start} + voices|audio/vo/<id>.wav → out/mix.wav (48 kHz stereo).
Loudness is finalized by core/render/mux.sh (−14 LUFS).

  python3 tools/deepseek-controller/mix_vo_only.py --project /path/to/film
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr

SR = 48000


def _load_mono(path: Path, sr: int = SR) -> np.ndarray:
    x, file_sr = sf.read(str(path), always_2d=False)
    x = np.asarray(x, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if int(file_sr) != sr:
        x = soxr.resample(x, int(file_sr), sr).astype(np.float32)
    return x


def mix_vo_only(project: Path, *, out: Path | None = None) -> Path:
    project = Path(project).resolve()
    tl_path = project / "timeline.json"
    if not tl_path.is_file():
        raise FileNotFoundError(tl_path)
    tl = json.loads(tl_path.read_text(encoding="utf-8"))
    dur = float(tl.get("dur") or 0)
    if dur <= 0:
        raise ValueError("timeline.json dur must be > 0")
    vo_map = tl.get("vo") or {}
    if not isinstance(vo_map, dict) or not vo_map:
        raise ValueError("timeline.json vo map empty")

    n = int(round(dur * SR))
    buf = np.zeros((n, 2), dtype=np.float32)

    voices_dirs = [project / "voices", project / "audio" / "vo"]
    placed = 0
    for lid, t0 in vo_map.items():
        wav = None
        for d in voices_dirs:
            for ext in (".wav", ".mp3", ".m4a"):
                cand = d / f"{lid}{ext}"
                if cand.is_file():
                    wav = cand
                    break
            if wav:
                break
        if wav is None:
            print(f"WARN: missing wav for {lid}", file=sys.stderr)
            continue
        x = _load_mono(wav)
        i0 = int(round(float(t0) * SR))
        if i0 >= n:
            continue
        x = x[: max(0, n - i0)]
        # center pan, gentle gain so mux has headroom
        g = 0.85
        buf[i0 : i0 + len(x), 0] += x * g
        buf[i0 : i0 + len(x), 1] += x * g
        placed += 1

    if placed == 0:
        raise RuntimeError("no VO wavs placed")

    peak = float(np.max(np.abs(buf))) if buf.size else 0.0
    if peak > 0.99:
        buf *= 0.99 / peak

    out = Path(out) if out else project / "out" / "mix.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), buf, SR, subtype="PCM_16")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", help="default: <project>/out/mix.wav")
    args = ap.parse_args(argv)
    try:
        out = mix_vo_only(Path(args.project), out=Path(args.out) if args.out else None)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK mix_vo_only → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
