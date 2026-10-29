#!/usr/bin/env python3
"""Editable music bed + VO mix for controller E2E (no locked style music.py).

Generates a short **placeholder procedural bed** (pure numpy softsynth — no freepats /
sampler / Olympics music.py / bee swarm required), ducks it under VO, writes:

  music/bed.wav          stereo 48 kHz float stem (touchable; replace freely)
  music/bed_meta.json    provenance (preset, seed, label)
  out/mix.wav            bed + VO → mux.sh loudnorm (−14 LUFS)

Optional: --bed PATH to use an existing WAV instead of synthesizing.
Optional: --preset soft-pulse | pad | silence

  python3 tools/deepseek-controller/music_bed.py --project /path/to/film
  python3 tools/deepseek-controller/music_bed.py --project /path/to/film --bed music/custom.wav

Freepats / sampler path (optional upgrade, not required here):
  sh tools/fetch.sh instruments freepats   # ~397 MB, not in git
  .venv/bin/python  # needs scipy (setup.sh deps music)
  See docs/integrations/local-music.md and core/audio/INSTRUMENTS.md
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
PLACEHOLDER_LABEL = (
    "placeholder-procedural-bed: soft sine pad + pulse (not a licensed score; "
    "replace music/bed.wav or pass --bed)"
)


def _load_mono(path: Path, sr: int = SR) -> np.ndarray:
    x, file_sr = sf.read(str(path), always_2d=False)
    x = np.asarray(x, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if int(file_sr) != sr:
        x = soxr.resample(x, int(file_sr), sr).astype(np.float32)
    return x


def _load_stereo(path: Path, sr: int = SR) -> np.ndarray:
    x, file_sr = sf.read(str(path), always_2d=True)
    x = np.asarray(x, dtype=np.float32)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    elif x.shape[1] > 2:
        x = x[:, :2]
    if int(file_sr) != sr:
        # soxr works on 1d; resample each channel
        left = soxr.resample(x[:, 0], int(file_sr), sr).astype(np.float32)
        right = soxr.resample(x[:, 1], int(file_sr), sr).astype(np.float32)
        n = min(len(left), len(right))
        x = np.stack([left[:n], right[:n]], axis=1)
    return x


def _moving_average(x: np.ndarray, win: int) -> np.ndarray:
    win = max(1, int(win))
    if win == 1:
        return x
    kernel = np.ones(win, dtype=np.float64) / win
    pad = win // 2
    xp = np.pad(x.astype(np.float64), (pad, pad), mode="edge")
    y = np.convolve(xp, kernel, mode="valid")
    return y[: len(x)].astype(np.float32)


def _hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def synthesize_bed(
    dur: float,
    *,
    preset: str = "soft-pulse",
    bpm: float = 100.0,
    seed: int = 20261029,
) -> np.ndarray:
    """Return stereo float32 bed of length dur seconds @ SR."""
    n = max(1, int(round(dur * SR)))
    if preset == "silence":
        return np.zeros((n, 2), dtype=np.float32)

    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=np.float64) / SR
    spb = 60.0 / max(40.0, float(bpm))

    # --- soft detuned pad (root + fifth + octave) ---
    roots = [45.0, 48.0, 52.0]  # A2–ish triad-ish (A C E-ish shifted)
    if preset == "pad":
        roots = [45.0, 49.0, 52.0, 57.0]
    pad = np.zeros(n, dtype=np.float64)
    for i, m in enumerate(roots):
        f = _hz(m) * (1.0 + 0.0015 * (i - 1))
        amp = 0.11 if preset == "pad" else 0.07
        # slow tremolo / breathe
        breathe = 0.55 + 0.45 * np.sin(2 * np.pi * (0.05 + 0.01 * i) * t + i)
        pad += amp * breathe * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
        # quiet fifth above
        pad += amp * 0.35 * breathe * np.sin(2 * np.pi * f * 1.5 * t)

    # gentle brightness roll-off via moving average (~ lowpass ~2–3 kHz)
    pad = _moving_average(pad.astype(np.float32), win=max(3, int(SR / 2800)))

    # fade in/out edges
    fade = int(0.35 * SR)
    env = np.ones(n, dtype=np.float32)
    if fade * 2 < n:
        env[:fade] = np.linspace(0, 1, fade, dtype=np.float32)
        env[-fade:] = np.linspace(1, 0, fade, dtype=np.float32)
    pad = pad * env

    bed = np.zeros((n, 2), dtype=np.float64)
    # slight stereo width
    bed[:, 0] += pad * 0.92
    bed[:, 1] += pad * 1.08

    if preset == "soft-pulse":
        # soft kick / pulse on beats (not a drum kit — just a sine thump)
        n_beats = int(dur / spb) + 2
        for bi in range(n_beats):
            t0 = bi * spb
            i0 = int(round(t0 * SR))
            if i0 >= n:
                break
            d = 0.18
            nn = int(d * SR)
            tt = np.arange(nn) / SR
            # pitch drop
            f0, f1 = 72.0, 42.0
            phase = 2 * np.pi * (f0 * tt + (f1 - f0) * tt * tt / (2 * d))
            thump = np.sin(phase) * np.exp(-tt / 0.055)
            # quieter every other beat
            g = 0.22 if bi % 4 == 0 else (0.12 if bi % 2 == 0 else 0.06)
            thump *= g
            sl = slice(i0, min(n, i0 + nn))
            L = sl.stop - sl.start
            bed[sl, 0] += thump[:L] * 0.95
            bed[sl, 1] += thump[:L] * 1.05

        # very soft high tick (noise blip) on off-beats
        for bi in range(n_beats):
            t0 = bi * spb + spb * 0.5
            i0 = int(round(t0 * SR))
            if i0 >= n:
                break
            nn = int(0.025 * SR)
            blip = rng.standard_normal(nn).astype(np.float32) * 0.015
            blip *= np.linspace(1, 0, nn, dtype=np.float32)
            blip = _moving_average(blip, win=max(1, int(SR / 8000)))
            sl = slice(i0, min(n, i0 + nn))
            L = sl.stop - sl.start
            pan = 0.3 if bi % 2 == 0 else -0.3
            bed[sl, 0] += blip[:L] * (1 - pan) * 0.5
            bed[sl, 1] += blip[:L] * (1 + pan) * 0.5

    # peak normalize to leave headroom for VO
    peak = float(np.max(np.abs(bed))) if bed.size else 0.0
    if peak > 1e-9:
        bed *= 0.35 / peak

    return bed.astype(np.float32)


def _vo_and_vad(
    project: Path,
    vo_map: dict,
    n: int,
) -> tuple[np.ndarray, np.ndarray]:
    buf = np.zeros((n, 2), dtype=np.float32)
    vad = np.zeros(n, dtype=np.float32)
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
        g = 0.85
        buf[i0 : i0 + len(x), 0] += x * g
        buf[i0 : i0 + len(x), 1] += x * g
        vad[i0 : i0 + len(x)] = 1.0
        placed += 1
    if placed == 0:
        raise RuntimeError("no VO wavs placed")
    return buf, vad


def _duck_envelope(vad: np.ndarray) -> np.ndarray:
    """≈ −9 dB under VO; smooth attack/release without scipy."""
    # expand VO regions slightly
    attack = int(0.08 * SR)
    release = int(0.28 * SR)
    # box max-filter via cumulative trick approximation: dilate with moving max
    win = max(1, attack + release)
    # simple dilation: convolve with ones then threshold
    kernel = np.ones(win, dtype=np.float32)
    pad = win // 2
    vp = np.pad(vad, (pad, pad), mode="edge")
    smeared = np.convolve(vp, kernel, mode="valid")[: len(vad)]
    smeared = (smeared > 0.5).astype(np.float32)
    # smooth
    smeared = _moving_average(smeared, win=max(3, int(0.12 * SR)))
    duck = 1.0 - 0.65 * smeared  # ≈ −9 dB
    return duck.astype(np.float32)


STEPAUDIO_CAPTION = ("纯器乐，冷静克制的纪录片 / 财经新闻配乐，中慢速，钢琴与弦乐铺底，轻微电子脉冲，"
                     "温暖不煽情，无人声，无鼓点高潮，适合垫在旁白下面")
BED_RMS_DB = -25.0  # matches the procedural soft-pulse bed level the mix was tuned on


def fetch_stepaudio_bed(project: Path, dur: float, *, caption: str = STEPAUDIO_CAPTION,
                        out: Path | None = None, force: bool = False) -> tuple[Path, dict]:
    """StepFun stepaudio-3-music-preview (limited-time free) instrumental → music/stepaudio_bed.wav.

    Cached: an existing file with the same caption is reused (no new request). The raw
    model output is kept (music/stepaudio_raw.wav); the bed is cut to `dur` with fades
    and RMS-matched to BED_RMS_DB so mix/ducking behave like the procedural bed.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core" / "tts"))
    from providers import stepaudio as _sa  # noqa: E402

    project = Path(project).resolve()
    out = Path(out) if out else project / "music" / "stepaudio_bed.wav"
    meta_p = out.with_name("stepaudio_bed_meta.json")
    raw_p = out.with_name("stepaudio_raw.wav")
    if not force and out.is_file() and meta_p.is_file():
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        if meta.get("caption") == caption and abs(float(meta.get("bedDurSec", 0)) - dur) < 0.01:
            meta["cached"] = True
            return out, meta
    out.parent.mkdir(parents=True, exist_ok=True)
    if not force and raw_p.is_file() and meta_p.is_file() and \
            json.loads(meta_p.read_text(encoding="utf-8")).get("caption") == caption:
        a, sr = sf.read(str(raw_p), dtype="float32", always_2d=True)
        info = json.loads(meta_p.read_text(encoding="utf-8"))
    else:
        a, sr, info = _sa.music_instrumental(caption)
        sf.write(str(raw_p), a, sr, subtype="FLOAT")
    if sr != SR:
        a = soxr.resample(a, sr, SR, quality="HQ")
    n = int(round(dur * SR))
    loops = 0
    while len(a) < n:  # model length is 1–3 min; loop with a crossfade only if it came back short
        xf = int(2.0 * SR)
        ramp = np.linspace(0, 1, xf)[:, None]
        a = np.concatenate([a[:-xf], a[-xf:] * (1 - ramp) + a[:xf] * ramp, a[xf:]])
        loops += 1
    a = a[:n].copy()
    fi, fo = int(0.5 * SR), int(3.0 * SR)
    a[:fi] *= np.linspace(0, 1, fi)[:, None]
    a[-fo:] *= np.linspace(1, 0, fo)[:, None]
    rms = float(np.sqrt(np.mean(a ** 2))) or 1e-9
    gain = 10 ** (BED_RMS_DB / 20) / rms
    a *= gain
    sf.write(str(out), a.astype(np.float32), SR, subtype="FLOAT")
    meta = {**info, "kind": "stepaudio-music-bed", "caption": caption, "rawWav": raw_p.name,
            "rawDurSec": info.get("durSec"), "bedDurSec": dur, "loops": loops,
            "rmsMatchDb": BED_RMS_DB, "gainDb": round(20 * np.log10(gain), 2),
            "pricing": "stepaudio-3-music-preview 限时免费 (preview)", "cached": False}
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out, meta


def seed_from_library(project: Path, lib: Path) -> str:
    """Copy a persistent library bed (<lib>/raw.wav + meta.json) into <project>/music/ so
    fetch_stepaudio_bed reuses it without a new StepAudio request. Returns its caption."""
    import shutil
    lib = Path(lib)
    meta = json.loads((lib / "meta.json").read_text(encoding="utf-8"))
    mdir = Path(project).resolve() / "music"
    mdir.mkdir(parents=True, exist_ok=True)
    raw = mdir / "stepaudio_raw.wav"
    if not raw.is_file() or raw.stat().st_size != (lib / meta.get("file", "raw.wav")).stat().st_size:
        shutil.copyfile(lib / meta.get("file", "raw.wav"), raw)
    pm = mdir / "stepaudio_bed_meta.json"
    old = json.loads(pm.read_text(encoding="utf-8")) if pm.is_file() else {}
    if old.get("caption") != meta["caption"] or old.get("libraryId") != meta.get("id"):
        pm.write_text(json.dumps({"taskId": meta.get("taskId"), "model": meta.get("model"), "caption": meta["caption"],
                                  "rewrittenCaption": meta.get("rewrittenCaption"), "sr": meta.get("sr"),
                                  "durSec": meta.get("durSec"), "libraryId": meta.get("id"), "libraryDir": str(lib),
                                  "bedDurSec": -1}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:  # record usage in the library meta
        used = meta.setdefault("usedBy", [])
        name = Path(project).resolve().name
        if name not in used:
            used.append(name)
            (lib / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
    return meta["caption"]


def mix_bed_vo(
    project: Path,
    *,
    out: Path | None = None,
    bed_out: Path | None = None,
    bed_path: Path | None = None,
    preset: str = "soft-pulse",
    bpm: float | None = None,
    seed: int = 20261029,
    bed_gain: float = 1.0,
    bed_source: str = "procedural",
    music_caption: str | None = None,
    music_library: Path | None = None,
) -> dict:
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

    if bpm is None:
        bpm = float(tl.get("bpm") or 100.0)

    n = int(round(dur * SR))

    meta = {
        "kind": "controller-music-bed",
        "label": PLACEHOLDER_LABEL,
        "preset": preset,
        "seed": seed,
        "bpm": bpm,
        "dur": dur,
        "sr": SR,
        "source": None,
        "lockedMusicPy": "not used — Olympics/bee demo music.py stays untouched",
    }

    sa_meta = None
    if bed_source == "stepaudio" and bed_path is None:
        if music_library:
            music_caption = seed_from_library(project, Path(music_library))
        bed_path, sa_meta = fetch_stepaudio_bed(project, dur, caption=music_caption or STEPAUDIO_CAPTION)
    if bed_path is not None:
        bed_path = Path(bed_path)
        if not bed_path.is_file():
            raise FileNotFoundError(bed_path)
        bed = _load_stereo(bed_path)
        if len(bed) < n:
            bed = np.pad(bed, ((0, n - len(bed)), (0, 0)))
        else:
            bed = bed[:n]
        meta["source"] = str(bed_path)
        meta["preset"] = "external"
        meta["label"] = f"external bed: {bed_path.name}"
        if sa_meta is not None:
            meta["preset"] = "stepaudio"
            meta["label"] = "StepFun stepaudio-3-music-preview instrumental (limited-time free preview)"
            meta["stepaudio"] = {k: sa_meta.get(k) for k in ("taskId", "model", "caption", "rewrittenCaption",
                                                             "rawDurSec", "gainDb", "loops", "cached")}
    else:
        bed = synthesize_bed(dur, preset=preset, bpm=bpm, seed=seed)
        meta["source"] = "synthesize_bed"

    bed = bed * float(bed_gain)

    vo, vad = _vo_and_vad(project, vo_map, n)
    duck = _duck_envelope(vad)
    mus = bed * duck[:, None]

    mix = mus + vo
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 0.99:
        mix *= 0.99 / peak

    bed_out = Path(bed_out) if bed_out else project / "music" / "bed.wav"
    bed_out.parent.mkdir(parents=True, exist_ok=True)
    # write unducked bed stem for editing / reuse
    sf.write(str(bed_out), bed, SR, subtype="FLOAT")
    meta_path = bed_out.with_name("bed_meta.json")
    meta["bedWav"] = str(bed_out.relative_to(project)) if bed_out.is_relative_to(project) else str(bed_out)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out = Path(out) if out else project / "out" / "mix.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), mix.astype(np.float32), SR, subtype="PCM_16")

    return {
        "mix": out,
        "bed": bed_out,
        "meta": meta_path,
        "metaObj": meta,
        "peak": peak,
        "dur": dur,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", help="default: <project>/out/mix.wav")
    ap.add_argument("--bed-out", help="default: <project>/music/bed.wav")
    ap.add_argument("--bed", help="use existing bed WAV instead of synthesizing")
    ap.add_argument(
        "--preset",
        choices=("soft-pulse", "pad", "silence"),
        default="soft-pulse",
        help="soft-pulse=pad+beat thumps (default); pad=drones only; silence=VO-only equivalent",
    )
    ap.add_argument("--bpm", type=float, default=None, help="default: timeline.json bpm or 100")
    ap.add_argument("--seed", type=int, default=20261029)
    ap.add_argument("--bed-gain", type=float, default=1.0)
    ap.add_argument("--bed-source", choices=("procedural", "stepaudio"), default="procedural")
    ap.add_argument("--music-caption", default=None)
    ap.add_argument("--music-library", default=None, help="persistent bed dir (raw.wav + meta.json)")
    args = ap.parse_args(argv)
    try:
        info = mix_bed_vo(
            Path(args.project),
            out=Path(args.out) if args.out else None,
            bed_out=Path(args.bed_out) if args.bed_out else None,
            bed_path=Path(args.bed) if args.bed else None,
            preset=args.preset,
            bpm=args.bpm,
            seed=args.seed,
            bed_gain=args.bed_gain,
            bed_source=args.bed_source,
            music_caption=args.music_caption,
            music_library=Path(args.music_library) if args.music_library else None,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK music_bed → mix={info['mix']}")
    print(f"   bed={info['bed']}  meta={info['meta']}")
    print(f"   preset={info['metaObj'].get('preset')}  dur={info['dur']}  peak={info['peak']:.3f}")
    print(f"   label={info['metaObj'].get('label')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
