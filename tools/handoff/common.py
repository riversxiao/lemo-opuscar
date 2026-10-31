"""Shared helpers for NLE / alternate-rail handoffs."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def find_master_mp4(film_dir: Path) -> Path:
    """Prefer out/final.mp4, then out/*.mp4, then <name>.mp4, then any root *.mp4."""
    film_dir = film_dir.resolve()
    candidates: list[Path] = []
    final = film_dir / "out" / "final.mp4"
    if final.is_file():
        return final
    out_dir = film_dir / "out"
    if out_dir.is_dir():
        candidates.extend(sorted(out_dir.glob("*.mp4")))
    named = film_dir / f"{film_dir.name}.mp4"
    if named.is_file():
        candidates.append(named)
    candidates.extend(sorted(p for p in film_dir.glob("*.mp4") if p.is_file()))
    # de-dupe preserving order
    seen: set[Path] = set()
    for p in candidates:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        if rp.is_file() and rp.stat().st_size > 0:
            return rp
    raise FileNotFoundError(
        f"no .mp4 under {film_dir} (looked for out/final.mp4, out/*.mp4, *.mp4)"
    )


DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_FPS = 24.0
DEFAULT_DURATION = 30.0


def parse_size(spec: str) -> tuple[int, int]:
    """Parse 'WxH' like core/render/page.mjs takeSize: even ints in 16..8192."""
    s = str(spec).strip().lower()
    parts = s.split("x")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"--size expects WxH (e.g. 1080x1920), got {spec!r}")
    w, h = int(parts[0]), int(parts[1])
    for v in (w, h):
        if v < 16 or v > 8192 or v % 2:
            raise ValueError(
                f"--size {spec!r}: width and height must be even integers in 16..8192"
            )
    return w, h


def parse_fps(spec: str | float | int) -> float:
    """Parse '24', '29.97' or '30000/1001' into a positive float."""
    if isinstance(spec, (int, float)):
        val = float(spec)
    else:
        s = str(spec).strip()
        try:
            if "/" in s:
                num, den = s.split("/", 1)
                val = float(num) / float(den)
            else:
                val = float(s)
        except (ValueError, ZeroDivisionError):
            raise ValueError(f"--fps expects a number or N/D, got {spec!r}") from None
    if not (0 < val <= 240):
        raise ValueError(f"--fps out of range (0, 240]: {spec!r}")
    return val


def fps_timebase(fps: float) -> tuple[int, bool]:
    """Integer timebase + NTSC flag for xmeml/EDL (29.97 -> (30, True))."""
    tb = max(1, int(round(fps)))
    ntsc = abs(fps - tb) > 0.005 and abs(fps * 1.001 - tb) < 0.01
    return tb, ntsc


def _ffprobe_json(path: Path) -> dict[str, Any] | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,r_frame_rate:format=duration",
                "-of",
                "json",
                str(path),
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return json.loads(out)
    except (subprocess.CalledProcessError, ValueError, OSError):
        return None


def probe_video(path: Path) -> dict[str, Any]:
    """Return {width, height, fps, duration, probed, fpsProbed} for the first video stream.

    Falls back to 1920x1080 @ 24fps / 30s (probed=False) when ffprobe is
    missing or the file cannot be read. Fields that ffprobe does return are
    kept even if others are missing. ``probed`` covers width/height and
    ``fpsProbed`` the frame rate: a stream with a size but an unusable
    r_frame_rate (``0/0``, or above 240 for VFR) keeps the 24fps default with
    fpsProbed=False.
    """
    info: dict[str, Any] = {
        "width": DEFAULT_WIDTH,
        "height": DEFAULT_HEIGHT,
        "fps": DEFAULT_FPS,
        "duration": DEFAULT_DURATION,
        "probed": False,
        "fpsProbed": False,
    }
    data = _ffprobe_json(path)
    if not data:
        return info
    streams = data.get("streams") or []
    st = streams[0] if streams else {}
    try:
        w, h = int(st.get("width") or 0), int(st.get("height") or 0)
        if w > 0 and h > 0:
            info["width"], info["height"] = w, h
            info["probed"] = True
    except (TypeError, ValueError):
        pass
    rate = st.get("r_frame_rate")
    if rate:
        try:
            info["fps"] = round(parse_fps(rate), 3)
            info["fpsProbed"] = True
        except ValueError:
            pass
    try:
        dur = float((data.get("format") or {}).get("duration"))
        if dur > 0:
            info["duration"] = dur
    except (TypeError, ValueError):
        pass
    return info


def probe_duration(path: Path) -> float:
    return float(probe_video(path)["duration"])


def probe_fps(path: Path, default: int = 24) -> int:
    """Integer timebase of the master's frame rate (30 for a 30fps render), via
    probe_video; `default` when ffprobe is missing or the rate is unreadable.
    Handoff writers use resolve_frame (keeps 29.97 as NTSC); this is the
    integer shorthand upstream callers expect."""
    pv = probe_video(path)
    return fps_timebase(float(pv["fps"]))[0] if pv["fpsProbed"] else default


def resolve_frame(
    mp4: Path,
    *,
    size: tuple[int, int] | None = None,
    fps: float | None = None,
) -> dict[str, Any]:
    """Resolve width/height/fps: explicit flag > ffprobe of master > default.

    Returns {width, height, fps, duration, sizeSource, fpsSource} where the
    sources are 'flag' | 'probe' | 'default'.
    """
    pv = probe_video(mp4)
    if size:
        w, h = size
        size_src = "flag"
    elif pv["probed"]:
        w, h = pv["width"], pv["height"]
        size_src = "probe"
    else:
        w, h = DEFAULT_WIDTH, DEFAULT_HEIGHT
        size_src = "default"
    if fps:
        f = float(fps)
        fps_src = "flag"
    elif pv["fpsProbed"]:
        f = float(pv["fps"])
        fps_src = "probe"
    else:
        f = DEFAULT_FPS
        fps_src = "default"
    return {
        "width": int(w),
        "height": int(h),
        "fps": f,
        "duration": float(pv["duration"]),
        "sizeSource": size_src,
        "fpsSource": fps_src,
    }


def _shot_from_dict(d: dict[str, Any], idx: int) -> dict[str, Any]:
    t0 = float(d.get("t0", d.get("start", 0.0)) or 0.0)
    if "t1" in d and d["t1"] is not None:
        t1 = float(d["t1"])
    elif "dur" in d and d["dur"] is not None:
        t1 = t0 + float(d["dur"])
    elif "duration" in d and d["duration"] is not None:
        t1 = t0 + float(d["duration"])
    else:
        t1 = t0
    dur = max(0.0, t1 - t0)
    text = (
        d.get("text")
        or d.get("zh")
        or d.get("title")
        or d.get("en")
        or d.get("id")
        or f"shot-{idx}"
    )
    return {
        "id": str(d.get("id") or f"s{idx:02d}"),
        "t0": round(t0, 6),
        "t1": round(t1, 6),
        "dur": round(dur, 6),
        "text": str(text),
        "role": d.get("role") or d.get("kind") or d.get("motionPreset") or "",
        "voIds": list(d.get("voIds") or []),
    }


def load_shots(film_dir: Path) -> tuple[list[dict[str, Any]], str, float | None]:
    """Return (shots, source_label, timeline_dur_hint).

    Preference: timeline.parsed.json shots → edl_runtime.json shots →
    timeline.json caps/vo → single full-duration fallback (caller fills dur).
    """
    film_dir = film_dir.resolve()
    parsed = film_dir / "timeline.parsed.json"
    if parsed.is_file():
        data = json.loads(parsed.read_text(encoding="utf-8"))
        shots_raw = data.get("shots") or []
        if shots_raw:
            shots = [_shot_from_dict(s, i) for i, s in enumerate(shots_raw)]
            dur = data.get("scheduledDurationSec") or data.get("targetDurationSec")
            return shots, "timeline.parsed.json", float(dur) if dur is not None else None

    edl = film_dir / "edl_runtime.json"
    if edl.is_file():
        data = json.loads(edl.read_text(encoding="utf-8"))
        shots_raw = data.get("shots") or []
        if shots_raw:
            shots = [_shot_from_dict(s, i) for i, s in enumerate(shots_raw)]
            return shots, "edl_runtime.json", None

    timeline = film_dir / "timeline.json"
    if timeline.is_file():
        data = json.loads(timeline.read_text(encoding="utf-8"))
        caps = data.get("caps") or []
        if caps:
            shots = [_shot_from_dict(c, i) for i, c in enumerate(caps)]
            # prepend hook if present
            hook = data.get("hook")
            if isinstance(hook, dict) and ("t0" in hook or "t1" in hook):
                shots.insert(0, _shot_from_dict({**hook, "id": "hook"}, 0))
                for i, s in enumerate(shots):
                    if not s["id"] or s["id"].startswith("s"):
                        s["id"] = f"s{i:02d}"
            dur = data.get("engineDurSec") or data.get("dur") or data.get("scheduleBudgetSec")
            return shots, "timeline.json", float(dur) if dur is not None else None

    return [], "none", None


def copy_stem_audio(film_dir: Path, assets: Path) -> dict[str, str]:
    """Copy known stem WAVs into assets/; return relative path map."""
    film_dir = film_dir.resolve()
    assets.mkdir(parents=True, exist_ok=True)
    found: dict[str, str] = {}

    # Mixed VO / master mix
    for rel in ("mix.wav", "out/mix.wav", "audio/mix.wav"):
        src = film_dir / rel
        if src.is_file():
            dst = assets / "mix.wav"
            shutil.copy2(src, dst)
            found["mix"] = "assets/mix.wav"
            break

    # VO directory of line WAVs
    voices = film_dir / "voices"
    if voices.is_dir():
        vo_out = assets / "vo"
        vo_out.mkdir(parents=True, exist_ok=True)
        n = 0
        for wav in sorted(voices.glob("*.wav")):
            shutil.copy2(wav, vo_out / wav.name)
            n += 1
        if n:
            found["vo_dir"] = "assets/vo"

    for cand in (
        film_dir / "audio" / "vo.wav",
        film_dir / "voices" / "vo.wav",
    ):
        if cand.is_file():
            shutil.copy2(cand, assets / "vo.wav")
            found["vo"] = "assets/vo.wav"
            break

    for cand in (
        film_dir / "music" / "bed.wav",
        film_dir / "audio" / "music.wav",
        film_dir / "audio" / "bed.wav",
        film_dir / "music" / "score.wav",
    ):
        if cand.is_file():
            shutil.copy2(cand, assets / "music.wav")
            found["music"] = "assets/music.wav"
            break

    return found


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_cmx3600_edl(
    path: Path,
    *,
    title: str,
    shots: list[dict[str, Any]],
    fps: float = 24,
) -> None:
    """Minimal CMX3600-style EDL (picture events only; reel MASTER).

    Frames are counted at the real rate (round(sec * 29.97)), the same count
    write_xmeml uses, and labelled as non-drop timecode on the integer
    timebase (29.97 -> 30). So for NTSC masters the EDL and premiere.xml from
    one export name the same frames; the timecode runs 0.1% behind the wall
    clock, as non-drop NTSC timecode always does.
    """
    real = float(fps)
    tb = fps_timebase(real)[0]

    def tc(sec: float) -> str:
        total = max(0, int(round(float(sec) * real)))
        ff = total % tb
        total //= tb
        ss = total % 60
        total //= 60
        mm = total % 60
        hh = total // 60
        return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

    lines = [f"TITLE: {title}", f"FCM: NON-DROP FRAME", ""]
    for i, sh in enumerate(shots, start=1):
        src_in = tc(sh["t0"])
        src_out = tc(sh["t1"])
        rec_in = tc(sh["t0"])
        rec_out = tc(sh["t1"])
        lines.append(
            f"{i:03d}  MASTER  V     C        {src_in} {src_out} {rec_in} {rec_out}"
        )
        note = (sh.get("text") or sh["id"]).replace("\n", " ")[:60]
        lines.append(f"* FROM CLIP NAME: {note}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_ffmpeg_concat(
    path: Path,
    shots: list[dict[str, Any]],
    *,
    master_rel: str = "assets/master.mp4",
) -> None:
    """Write a shell script that rebuilds master from shot trims (re-encode safe)."""
    # Also write a concat list expecting shots/NN.mp4 if extracted.
    concat_list = path.with_name("ffmpeg_concat.txt")
    lines = []
    for i, sh in enumerate(shots):
        lines.append(f"file 'shots/{i:02d}_{sh['id']}.mp4'")
    concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

    script = path
    body = [
        "#!/usr/bin/env bash",
        "# Rebuild a linear MP4 from per-shot trims of assets/master.mp4",
        "set -euo pipefail",
        'ROOT="$(cd "$(dirname "$0")" && pwd)"',
        'cd "$ROOT"',
        'MASTER="${MASTER:-assets/master.mp4}"',
        'mkdir -p shots',
        'rm -f shots/*.mp4',
    ]
    for i, sh in enumerate(shots):
        out = f"shots/{i:02d}_{sh['id']}.mp4"
        # re-encode for frame-accurate cuts (stream-copy drifts on non-keyframes)
        body.append(
            f'ffmpeg -y -hide_banner -loglevel error -ss {sh["t0"]} -to {sh["t1"]} '
            f'-i "$MASTER" -an -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p '
            f'"{out}"'
        )
    body += [
        'ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i ffmpeg_concat.txt '
        '-c copy rebuilt_picture.mp4',
        'echo "wrote $ROOT/rebuilt_picture.mp4"',
    ]
    script.write_text("\n".join(body) + "\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | 0o111)
