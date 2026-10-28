"""Schedule shots from measured VO durations (no silent global K-scale as final)."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import dump_json, load_json, load_manifest


def _cjk_count(s: str) -> int:
    return sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff")


def read_time_sec(text: str, *, cjk_cps: float = 4.5, latin_cps: float = 15.0, pad: float = 0.4) -> float:
    """Minimum hold after full text is visible."""
    cjk = _cjk_count(text)
    other = sum(1 for ch in text if not ch.isspace()) - cjk
    other = max(0, other)
    return max(0.6, cjk / cjk_cps + other / latin_cps + pad)


def snap(sec: float, grid: float) -> float:
    if grid <= 0:
        return sec
    return math.ceil(sec / grid - 1e-9) * grid


def ffprobe_duration(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return float(out)
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return None


def load_durations(
    lines: list[dict[str, Any]],
    dur_json: Path | None,
    voices_dir: Path | None,
) -> dict[str, float]:
    durs: dict[str, float] = {}
    if dur_json and dur_json.is_file():
        raw = load_json(dur_json)
        if isinstance(raw, dict):
            for k, v in raw.items():
                try:
                    durs[str(k)] = float(v)
                except (TypeError, ValueError):
                    pass
    if voices_dir and voices_dir.is_dir():
        for ln in lines:
            lid = ln["id"]
            if lid in durs:
                continue
            for name in (f"{lid}.wav", f"{lid}.mp3", f"{lid}.m4a"):
                p = voices_dir / name
                d = ffprobe_duration(p)
                if d is not None:
                    durs[lid] = d
                    break
    return durs


def schedule(
    *,
    lines: list[dict[str, Any]],
    shots: list[dict[str, Any]],
    target_duration: float,
    beat_grid: float,
    durs: dict[str, float],
    enter: float = 0.35,
    exit_: float = 0.25,
    settle: float = 0.35,
    require_all_vo: bool = False,
    pad_under_target: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """Return (timeline, errors). Over-target → error (no silent K-scale).

    When content end < targetDurationSec and pad_under_target, extend the last
    shot (hold-last-beat) so scheduledDurationSec reaches the target. Original
    shortfall stays visible via contentDurationSec / padSec / underTargetBeforePad.
    """
    errors: list[str] = []
    # Map shotId → vo lines
    by_shot: dict[str, list[dict[str, Any]]] = {}
    for ln in lines:
        sid = ln.get("shotId") or ln["id"]
        by_shot.setdefault(sid, []).append(ln)

    if require_all_vo:
        for ln in lines:
            if ln["id"] not in durs:
                errors.append(f"missing VO duration for line '{ln['id']}'")

    parsed_shots = []
    t = 0.0
    for sh in shots:
        sid = sh["id"]
        text = sh.get("onScreenText") or sh.get("text") or ""
        vo_list = by_shot.get(sid, [])
        vo_dur = 0.0
        vo_ids = []
        for ln in vo_list:
            lid = ln["id"]
            if lid in durs:
                vo_dur += durs[lid]
                vo_ids.append(lid)
            elif require_all_vo:
                pass  # already recorded
            else:
                # estimate from text if no wav yet (planning mode)
                est = read_time_sec(ln.get("text") or "", pad=0.2)
                vo_dur += est
                vo_ids.append(lid)
                errors.append(f"WARN: estimated VO for '{lid}' (no measured duration)")

        read = read_time_sec(text)
        need = max(vo_dur, read) + enter + exit_ + settle
        if sh.get("beats") and beat_grid:
            need = max(need, float(sh["beats"]) * beat_grid)
        length = snap(need, beat_grid)
        parsed_shots.append(
            {
                "id": sid,
                "t0": round(t, 4),
                "t1": round(t + length, 4),
                "dur": round(length, 4),
                "voIds": vo_ids,
                "voDur": round(vo_dur, 4),
                "readSec": round(read, 4),
                "text": text,
                "motionPreset": sh.get("motionPreset"),
                "role": sh.get("role"),
            }
        )
        t += length

    total = snap(t, beat_grid) if parsed_shots else 0.0
    # if last t1 already snapped per-shot, total is last t1
    if parsed_shots:
        total = parsed_shots[-1]["t1"]

    content_duration = float(total)
    pad_sec = 0.0
    pad_mode = "none"
    under_before_pad = False

    # Pad under-target by holding the last beat (extend last shot to target).
    # Over-target still hard-fails — never silent K-scale shrink.
    if (
        pad_under_target
        and parsed_shots
        and total + 1e-6 < target_duration
    ):
        under_before_pad = True
        pad_sec = round(target_duration - total, 4)
        last = parsed_shots[-1]
        last["t1"] = round(target_duration, 4)
        last["dur"] = round(last["t1"] - last["t0"], 4)
        last["padSec"] = pad_sec
        last["padMode"] = "hold-last-beat"
        total = float(target_duration)
        pad_mode = "hold-last-beat"
        errors.append(
            f"WARN: padded {pad_sec:.2f}s (hold-last-beat) — content was "
            f"{content_duration:.2f}s under target {target_duration:.2f}s"
        )

    hard_errors = [e for e in errors if not e.startswith("WARN:")]
    if total > target_duration + 1e-6:
        hard_errors.append(
            f"scheduled duration {total:.2f}s exceeds target {target_duration:.2f}s — "
            f"cut copy / drop a shot (controller will not silent K-scale as final)"
        )

    warns = [e for e in errors if e.startswith("WARN:")]
    all_errors = hard_errors + warns
    ok = len(hard_errors) == 0
    timeline = {
        "targetDurationSec": target_duration,
        "scheduledDurationSec": total,
        "contentDurationSec": content_duration,
        "padSec": pad_sec,
        "padMode": pad_mode,
        "underTargetBeforePad": under_before_pad,
        "beatGridSec": beat_grid,
        "fitsTarget": total <= target_duration + 1e-6,
        "requireVo": bool(require_all_vo),
        "ok": ok,
        "errors": list(hard_errors),
        "warnings": list(warns),
        "shots": parsed_shots,
        "cues": [
            {"type": "voice", "id": vid, "shotId": s["id"], "t": s["t0"] + enter}
            for s in parsed_shots
            for vid in s["voIds"]
        ],
    }
    return timeline, all_errors


def _load_shots_from_project(project: Path) -> list[dict[str, Any]]:
    for rel in (
        "content/shots.json",
        "content/edl_content.json",
        "content/timeline_content.json",
        "content/plan.json",
    ):
        p = project / rel
        if not p.is_file():
            continue
        data = load_json(p)
        if rel.endswith("shots.json"):
            return data["shots"]
        if rel.endswith("edl_content.json"):
            return [
                {
                    "id": s["id"],
                    "text": s.get("zh") or s.get("en") or "",
                    "onScreenText": s.get("zh"),
                    "motionPreset": s.get("motionPreset"),
                    "role": s.get("role"),
                    "beats": s.get("beats"),
                    "pose": s.get("pose"),
                }
                for s in data["shots"]
            ]
        if rel.endswith("timeline_content.json"):
            return [
                {
                    "id": c["id"],
                    "text": c.get("zh") or c.get("en") or "",
                    "onScreenText": c.get("zh"),
                    "motionPreset": c.get("k"),
                    "role": c.get("role"),
                }
                for c in data["caps"]
            ]
        if rel.endswith("plan.json"):
            return data["shots"]
    raise FileNotFoundError(f"no shots/content found under {project}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="VO-driven shot schedule (no silent K-scale)")
    ap.add_argument("--project", required=True, help="project dir with content/")
    ap.add_argument("--lines", help="lines.json (default: content/lines.json)")
    ap.add_argument("--dur", help="voices/dur.json map id→seconds")
    ap.add_argument("--voices-dir", help="directory of per-line wavs")
    ap.add_argument("--target", type=float, help="override target duration sec")
    ap.add_argument("--grid", type=float, help="override beat grid sec")
    ap.add_argument("--style", help="style slug for manifest grid")
    ap.add_argument("--require-vo", action="store_true", help="fail if any line missing measured dur")
    ap.add_argument(
        "--no-pad",
        action="store_true",
        help="do not extend last shot when content < target (diagnostic; default pads hold-last-beat)",
    )
    ap.add_argument("-o", "--output", help="timeline.parsed.json path")
    args = ap.parse_args(argv)

    project = Path(args.project)
    lines_path = Path(args.lines) if args.lines else project / "content" / "lines.json"
    lines = load_json(lines_path) if lines_path.is_file() else []
    if not isinstance(lines, list):
        print("lines.json must be an array", file=sys.stderr)
        return 1

    shots = _load_shots_from_project(project)
    style = args.style
    if not style:
        plan_p = project / "content" / "plan.json"
        if plan_p.is_file():
            style = load_json(plan_p).get("style")
    grid = args.grid
    target = args.target
    if style:
        man = load_manifest(style)
        grid = grid if grid is not None else man.get("beatGridSec", 0.25)
        if target is None:
            plan_p = project / "content" / "plan.json"
            target = float(load_json(plan_p)["targetDurationSec"]) if plan_p.is_file() else man["durationSec"]["max"]
    grid = 0.25 if grid is None else grid
    if target is None:
        print("--target required when style/plan missing", file=sys.stderr)
        return 1

    dur_path = Path(args.dur) if args.dur else project / "voices" / "dur.json"
    voices_dir = Path(args.voices_dir) if args.voices_dir else project / "voices"
    durs = load_durations(lines, dur_path if dur_path.is_file() else None, voices_dir)

    timeline, errors = schedule(
        lines=lines,
        shots=shots,
        target_duration=float(target),
        beat_grid=float(grid),
        durs=durs,
        require_all_vo=args.require_vo,
        pad_under_target=not args.no_pad,
    )
    out = Path(args.output) if args.output else project / "timeline.parsed.json"
    dump_json(out, timeline)

    warns = [e for e in errors if e.startswith("WARN:")]
    hard = [e for e in errors if not e.startswith("WARN:")]
    for w in warns:
        print(w, file=sys.stderr)
    if hard:
        print("SCHEDULE FAIL:", file=sys.stderr)
        for e in hard:
            print(f"  - {e}", file=sys.stderr)
        print(f"wrote (diagnostic) {out}", file=sys.stderr)
        return 1
    pad_note = ""
    if timeline.get("padSec"):
        pad_note = (
            f" (padded {timeline['padSec']}s {timeline.get('padMode')}; "
            f"content {timeline.get('contentDurationSec')}s)"
        )
    print(f"OK scheduled {timeline['scheduledDurationSec']}s{pad_note} → {out}")

    # Caption News: push cues into touchable timeline.json (main.js SHOTS/DUR stay locked).
    if style == "caption-news" and (project / "timeline.json").is_file():
        try:
            from apply_caption_timeline import apply_caption_timeline

            info = apply_caption_timeline(project, parsed=timeline)
            print(
                f"OK applied caption timeline.json vo={info['voCount']} "
                f"dur={info['dur']} (engine={info.get('engineDurSec')})"
            )
        except Exception as e:
            print(f"WARN: caption timeline apply failed: {e}", file=sys.stderr)

    # Pictogram: compile edl_runtime.json (page.mjs overlay) + timeline.json for mix_vo_only.
    if style == "pictogram-motion" and (
        (project / "content" / "edl_content.json").is_file()
        or (project / "edl_content.json").is_file()
    ):
        try:
            from apply_pictogram_edl import apply_pictogram_edl

            info = apply_pictogram_edl(project, parsed=timeline)
            print(
                f"OK applied pictogram edl_runtime shots={info['shotCount']} "
                f"dur={info['dur']} vo={info['voCount']}"
            )
        except Exception as e:
            print(f"WARN: pictogram edl apply failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
