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
import pacing_profile as pp


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
    pad_under_target: bool = False,
    line_gap: float = 0.2,
    pacing: dict[str, Any] | None = None,
    outro_sec: float = 0.0,
) -> tuple[dict[str, Any], list[str]]:
    """Return (timeline, errors). Over-target → error (no silent K-scale).

    Duration follows content: the target is a ceiling. By default nothing pads the
    film up to the target; an optional outro/brand card (≤ OUTRO_MAX_SEC) may extend
    the last shot. Legacy pad_under_target=True still extends the last shot
    (hold-last-beat) to the target; shortfall stays visible via contentDurationSec /
    padSec / underTargetBeforePad (quality FAILs padding > OUTRO_MAX_SEC).

    `pacing` (pacing_profile.profile()) overrides enter/exit/settle/line_gap and adds
    beatPauseSec after lines marked "beat": true.
    """
    errors: list[str] = []
    beat_pause = 0.0
    if pacing:
        enter = float(pacing["enterSec"])
        exit_ = float(pacing["exitSec"])
        settle = float(pacing["settleSec"])
        line_gap = float(pacing["lineGapSec"])
        beat_pause = float(pacing.get("beatPauseSec") or 0.0)
    outro_sec = max(0.0, min(float(outro_sec or 0.0), pp.OUTRO_MAX_SEC))
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
        prev_beat = False
        vo_dur = 0.0
        vo_ids = []
        vo_offsets: list[float] = []  # start offset of each line within the shot VO run
        for ln in vo_list:
            lid = ln["id"]
            if vo_ids:
                vo_dur += line_gap  # multi-line shot: lines play back to back, never stacked
                if beat_pause and prev_beat:
                    vo_dur += beat_pause  # deliberate rhythm beat after the previous line
            if lid in durs:
                vo_offsets.append(round(vo_dur, 4))
                vo_dur += durs[lid]
                vo_ids.append(lid)
            elif require_all_vo:
                pass  # already recorded
            else:
                # estimate from text if no wav yet (planning mode)
                est = read_time_sec(ln.get("text") or "", pad=0.2,
                                    cjk_cps=float((pacing or {}).get("cps") or 4.5))
                vo_offsets.append(round(vo_dur, 4))
                vo_dur += est
                vo_ids.append(lid)
                errors.append(f"WARN: estimated VO for '{lid}' (no measured duration)")
            prev_beat = bool(ln.get("beat"))
        if beat_pause and vo_list and bool(vo_list[-1].get("beat")):
            vo_dur += beat_pause  # beat on the shot's last line holds before the cut

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
                "voOffsets": vo_offsets,
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
    applied_outro = 0.0
    if outro_sec and parsed_shots and not pad_under_target:
        applied_outro = round(min(outro_sec, max(0.0, target_duration - total)), 4)
        if applied_outro > 0:
            last = parsed_shots[-1]
            last["t1"] = round(last["t1"] + applied_outro, 4)
            last["dur"] = round(last["t1"] - last["t0"], 4)
            last["outroSec"] = applied_outro
            total = float(last["t1"])

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
        "outroSec": applied_outro,
        "durationPolicy": "ceiling" if not pad_under_target else "pad-to-target(legacy)",
        "pacing": (pacing or {}).get("name"),
        "pacingSource": (pacing or {}).get("source"),
        "shotOverheadSec": round(enter + exit_ + settle, 4),
        "lineGapSec": line_gap,
        "underTargetBeforePad": under_before_pad,
        "beatGridSec": beat_grid,
        "fitsTarget": total <= target_duration + 1e-6,
        "requireVo": bool(require_all_vo),
        "ok": ok,
        "errors": list(hard_errors),
        "warnings": list(warns),
        "shots": parsed_shots,
        "cues": [
            {"type": "voice", "id": vid, "shotId": s["id"],
             "t": round(s["t0"] + enter + (s["voOffsets"][i] if i < len(s["voOffsets"]) else 0.0), 4)}
            for s in parsed_shots
            for i, vid in enumerate(s["voIds"])
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
                    "beats": s.get("beatsAuthored", s.get("beats")),  # authored minimum, not last schedule
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
        help="(default now) never pad to target — kept for old scripts",
    )
    ap.add_argument(
        "--pad-under-target",
        action="store_true",
        help="LEGACY: hold-last-beat pad up to target (quality FAILs padding > 1.5s)",
    )
    ap.add_argument("--pacing", help="fast|standard|calm (default plan.json pacing / content_type → profile)")
    ap.add_argument("--outro", type=float, default=None,
                    help=f"outro/brand card seconds after the last line (≤{pp.OUTRO_MAX_SEC}; default plan.json outroSec, "
                         "else profile endCardSec when the last shot is an end/brand card, else 0)")
    ap.add_argument("--no-beats", action="store_true",
                    help="do not write beats_runtime.json (P1 sub-beats / keyword emphasis)")
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

    plan_d = pp.load_plan(project)
    try:
        prof = pp.profile(project, args.pacing, plan_d)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    outro = args.outro if args.outro is not None else pp.default_outro(plan_d, prof)
    timeline, errors = schedule(
        lines=lines,
        shots=shots,
        target_duration=float(target),
        beat_grid=float(grid),
        durs=durs,
        require_all_vo=args.require_vo,
        pad_under_target=bool(args.pad_under_target) and not args.no_pad,
        pacing=prof,
        outro_sec=outro,
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
    print(f"OK scheduled {timeline['scheduledDurationSec']}s{pad_note} pacing={prof['name']} "
          f"({prof['source']}) overhead={timeline['shotOverheadSec']}s/shot → {out}")

    # P1 visual sub-beats + {keyword} emphasis (all styles, page.mjs bridge). Opt out: --no-beats.
    if not args.no_beats and Path(out).resolve() == (project / "timeline.parsed.json").resolve():
        try:
            import beats as beats_mod

            old_rt = beats_mod._load(project / "beats_runtime.json", {}) or {}
            rt = beats_mod.build(project, prof["name"], drift=old_rt.get("drift"))
            beats_mod.write(project, rt)
            st = rt["stats"]
            print(f"OK beats {st['reframes']} reframes, {st['emphasis']} keyword frames; "
                  f"beat max {st['beatMaxSec']}s (edit shot max {st['editShotMaxSec']}s) → beats_runtime.json")
        except (SystemExit, Exception) as e:  # never block scheduling on the visual layer
            print(f"WARN: beats_runtime not written: {e}", file=sys.stderr)

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

    # Swiss: texts_runtime.json → page.mjs installs window.TEXTS (film.js unlocked not required).
    if style == "swiss-motion" and (
        (project / "lines.json").is_file() or (project / "content" / "lines.json").is_file()
    ):
        try:
            from apply_swiss_texts import apply_swiss_texts

            info = apply_swiss_texts(project)
            print(
                f"OK applied swiss texts_runtime entries={info['entryCount']} "
                f"holdPad={info['holdPadCount']}"
            )
        except Exception as e:
            print(f"WARN: swiss texts_runtime apply failed: {e}", file=sys.stderr)

    # Swiss: emit timeline.json for music_bed / mix_vo_only (DUR from film.js when locked).
    if style == "swiss-motion" and timeline.get("ok"):
        try:
            from quality import _engine_locked_dur
            import re as _re

            dur = _engine_locked_dur(project, "swiss-motion")
            if not dur:
                film = project / "film.js"
                if film.is_file():
                    m = _re.search(r"\bDUR\s*=\s*([0-9.]+)", film.read_text(encoding="utf-8"))
                    dur = float(m.group(1)) if m else None
            if not dur:
                dur = float(timeline.get("scheduledDurationSec") or 0)
            vo = {}
            for cue in timeline.get("cues") or []:
                lid = cue.get("id") or cue.get("lineId")
                t0 = cue.get("t0", cue.get("start"))
                if lid is not None and t0 is not None:
                    vo[str(lid)] = float(t0)
            if not vo:
                for sh in timeline.get("shots") or []:
                    for lid in sh.get("voIds") or []:
                        vo[str(lid)] = float(sh["t0"])
            if dur and vo:
                tl_out = {
                    "schemaVersion": 1,
                    "dur": float(dur),
                    "bpm": 100,
                    "scheduleBudgetSec": timeline.get("scheduledDurationSec"),
                    "vo": vo,
                    "source": "schedule-swiss",
                }
                dump_json(project / "timeline.json", tl_out)
                print(
                    f"OK wrote swiss timeline.json vo={len(vo)} dur={dur} "
                    f"(for mix / music_bed)"
                )
        except Exception as e:
            print(f"WARN: swiss timeline.json emit failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
