"""Unified quality gate → quality.json (PASS|FAIL|NOT_CHECKED|NOT_APPLICABLE)."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import dump_json, load_json


STATUSES = ("PASS", "FAIL", "NOT_CHECKED", "NOT_APPLICABLE")


def check(
    name: str,
    status: str,
    detail: str = "",
    *,
    required: bool = True,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(status)
    return {"name": name, "status": status, "detail": detail, "required": required}


def _repo_root() -> Path:
    # tools/deepseek-controller → repo root
    return Path(__file__).resolve().parents[2]


def probe_media(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"ok": False, "error": "missing"}
    if not shutil.which("ffprobe"):
        return {"ok": False, "error": "ffprobe not found"}
    try:
        raw = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,width,height,r_frame_rate,sample_rate,channels",
                "-of",
                "json",
                str(path),
            ],
            text=True,
        )
        return {"ok": True, "data": json.loads(raw)}
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        return {"ok": False, "error": str(e)}


def ebur128(path: Path) -> dict[str, Any]:
    """Return integrated LUFS and true peak dBTP if measurable."""
    if not path.is_file() or not shutil.which("ffmpeg"):
        return {"ok": False, "error": "ffmpeg/media missing"}
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-nostats",
                "-i",
                str(path),
                "-filter_complex",
                "ebur128=peak=true",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        log = (proc.stderr or "") + (proc.stdout or "")
    except (subprocess.SubprocessError, OSError) as e:
        return {"ok": False, "error": str(e)}
    # Parse summary lines
    import re

    integ = None
    tpeak = None
    # I:     -14.0 LUFS
    m = re.search(r"\bI:\s*([+-]?\d+(?:\.\d+)?)\s*LUFS", log)
    if m:
        integ = float(m.group(1))
    # Peak:  -1.2 dBFS  or True peak variants
    m2 = re.search(r"True peak:\s*[^\n]*?([+-]?\d+(?:\.\d+)?)\s*dB", log)
    if not m2:
        m2 = re.search(r"Peak:\s*([+-]?\d+(?:\.\d+)?)\s*dBFS", log)
    if m2:
        tpeak = float(m2.group(1))
    if integ is None:
        return {"ok": False, "error": "could not parse ebur128", "log_tail": log[-500:]}
    return {"ok": True, "integrated_lufs": integ, "true_peak_dbtp": tpeak}


def run_readcheck(project: Path) -> dict[str, Any]:
    root = _repo_root()
    script = root / "core" / "render" / "readcheck.mjs"
    if not script.is_file():
        return check("readcheck", "NOT_CHECKED", "readcheck.mjs missing", required=True)
    if not (project / "index.html").is_file():
        return check(
            "readcheck",
            "NOT_CHECKED",
            "no index.html in project (engine not copied yet)",
            required=True,
        )
    try:
        proc = subprocess.run(
            ["node", str(script), str(project)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(root),
        )
    except (OSError, subprocess.SubprocessError) as e:
        return check("readcheck", "NOT_CHECKED", f"failed to run: {e}", required=True)
    detail = ((proc.stdout or "") + (proc.stderr or ""))[-800:]
    if proc.returncode == 0:
        return check("readcheck", "PASS", detail or "all text holds OK")
    if proc.returncode == 2:
        return check("readcheck", "NOT_CHECKED", detail or "exit 2", required=True)
    return check("readcheck", "FAIL", detail or f"exit {proc.returncode}")


def run_asr(project: Path, has_vo: bool) -> dict[str, Any]:
    if not has_vo:
        return check(
            "asr_check",
            "NOT_APPLICABLE",
            "no voice lines / provider none",
            required=False,
        )
    root = _repo_root()
    script = root / "core" / "tts" / "asr_check.py"
    lines = project / "content" / "lines.json"
    voices = project / "voices"
    if not script.is_file():
        return check("asr_check", "NOT_CHECKED", "asr_check.py missing", required=True)
    if not lines.is_file():
        return check("asr_check", "NOT_CHECKED", "content/lines.json missing", required=True)
    # Prefer skip heavy whisper if no wavs
    wavs = list(voices.glob("*.wav")) if voices.is_dir() else []
    if not wavs:
        return check(
            "asr_check",
            "NOT_CHECKED",
            "voices/*.wav missing — cannot claim ASR pass",
            required=True,
        )
    try:
        proc = subprocess.run(
            [sys.executable, str(script), str(lines), str(voices)],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(root),
        )
    except (OSError, subprocess.SubprocessError) as e:
        return check("asr_check", "NOT_CHECKED", f"failed to run: {e}", required=True)
    detail = ((proc.stdout or "") + (proc.stderr or ""))[-800:]
    if proc.returncode == 0:
        return check("asr_check", "PASS", detail or "ASR OK")
    if proc.returncode == 2:
        return check("asr_check", "NOT_CHECKED", detail or "exit 2", required=True)
    return check("asr_check", "FAIL", detail or f"exit {proc.returncode}")


def gate(
    project: Path,
    *,
    media: Path | None = None,
    force_fail: list[str] | None = None,
    skip_heavy: bool = False,
) -> dict[str, Any]:
    project = Path(project)
    checks: list[dict[str, Any]] = []
    force_fail = force_fail or []

    # plan present
    plan_p = project / "content" / "plan.json"
    if plan_p.is_file():
        plan = load_json(plan_p)
        checks.append(check("plan_present", "PASS", str(plan_p)))
        voice = plan.get("voice") or {}
        has_vo = voice.get("provider", "none") != "none" and bool(voice.get("lines"))
        style = plan.get("style", "")
        target = plan.get("targetDurationSec")
    else:
        plan = {}
        has_vo = False
        style = ""
        target = None
        checks.append(check("plan_present", "FAIL", "content/plan.json missing"))

    # timeline
    tl_p = project / "timeline.parsed.json"
    if tl_p.is_file():
        tl = load_json(tl_p)
        if tl.get("fitsTarget") is False:
            checks.append(
                check(
                    "schedule_fits_target",
                    "FAIL",
                    f"scheduled {tl.get('scheduledDurationSec')} > target {tl.get('targetDurationSec')}",
                )
            )
        else:
            checks.append(
                check(
                    "schedule_fits_target",
                    "PASS",
                    f"{tl.get('scheduledDurationSec')}s <= {tl.get('targetDurationSec')}s",
                )
            )
    else:
        checks.append(
            check(
                "schedule_fits_target",
                "NOT_CHECKED",
                "timeline.parsed.json missing",
                required=True,
            )
        )

    # media / loudness
    media_path = media or project / "out.mp4"
    if not media_path.is_file():
        # try common names
        for cand in ("final.mp4", "film.mp4", "mux.mp4"):
            if (project / cand).is_file():
                media_path = project / cand
                break

    if media_path.is_file():
        info = probe_media(media_path)
        if info.get("ok"):
            checks.append(check("ffprobe_media", "PASS", f"{media_path.name} readable"))
            dur = None
            try:
                dur = float(info["data"]["format"]["duration"])
            except (KeyError, TypeError, ValueError):
                pass
            if target and dur is not None:
                # allow +2s headroom for end card
                if dur > float(target) + 2.5:
                    checks.append(
                        check(
                            "media_duration",
                            "FAIL",
                            f"media {dur:.2f}s > target {target}+2.5",
                        )
                    )
                else:
                    checks.append(
                        check("media_duration", "PASS", f"{dur:.2f}s vs target {target}")
                    )
        else:
            checks.append(
                check("ffprobe_media", "NOT_CHECKED", info.get("error", ""), required=True)
            )

        loud = ebur128(media_path)
        if loud.get("ok"):
            i = loud["integrated_lufs"]
            tp = loud.get("true_peak_dbtp")
            ok_i = abs(i - (-14.0)) <= 1.0 + 1e-6
            detail = f"I={i} LUFS"
            st = "PASS" if ok_i else "FAIL"
            if not ok_i:
                detail += " (want −14±1)"
            if tp is not None:
                detail += f", TP={tp} dBTP"
                if tp > -1.0 + 1e-6:
                    st = "FAIL"
                    detail += " (want ≤ −1 dBTP)"
            checks.append(check("loudness_ebur128", st, detail))
        else:
            checks.append(
                check(
                    "loudness_ebur128",
                    "NOT_CHECKED",
                    loud.get("error", "unmeasured"),
                    required=True,
                )
            )
    else:
        checks.append(
            check(
                "ffprobe_media",
                "NOT_CHECKED",
                "no out.mp4/final.mp4 yet",
                required=False,
            )
        )
        checks.append(
            check(
                "loudness_ebur128",
                "NOT_CHECKED",
                "no media for ebur128",
                required=False,
            )
        )
        checks.append(
            check(
                "media_duration",
                "NOT_CHECKED",
                "no media",
                required=False,
            )
        )

    if skip_heavy:
        checks.append(
            check("readcheck", "NOT_CHECKED", "skipped (--skip-heavy)", required=True)
        )
        if has_vo:
            checks.append(
                check("asr_check", "NOT_CHECKED", "skipped (--skip-heavy)", required=True)
            )
        else:
            checks.append(
                check(
                    "asr_check",
                    "NOT_APPLICABLE",
                    "no VO",
                    required=False,
                )
            )
    else:
        checks.append(run_readcheck(project))
        checks.append(run_asr(project, has_vo))

    for name in force_fail:
        checks.append(check(name, "FAIL", "forced by fixture / --force-fail"))

    # Aggregate
    blocking = []
    for c in checks:
        if not c.get("required", True):
            if c["status"] == "FAIL":
                blocking.append(c)
            continue
        if c["status"] in ("FAIL", "NOT_CHECKED"):
            blocking.append(c)

    overall = "FAIL" if blocking else "PASS"
    # If only NOT_APPLICABLE / PASS → PASS
    report = {
        "schemaVersion": 1,
        "project": str(project),
        "style": style,
        "overall": overall,
        "deliveryAllowed": overall == "PASS",
        "checks": checks,
        "blocking": [{"name": b["name"], "status": b["status"]} for b in blocking],
        "standards": {
            "loudness_lufs": {"target": -14.0, "tol": 1.0},
            "true_peak_dbtp_max": -1.0,
        },
    }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write quality.json and gate delivery")
    ap.add_argument("--project", required=True)
    ap.add_argument("--media", help="mp4 to probe")
    ap.add_argument("--force-fail", action="append", default=[], help="inject FAIL check name")
    ap.add_argument(
        "--skip-heavy",
        action="store_true",
        help="do not run Playwright readcheck / Whisper ASR (still marks them NOT_CHECKED if required)",
    )
    ap.add_argument(
        "--allow-unchecked",
        action="store_true",
        help="treat required NOT_CHECKED as non-blocking (dev only)",
    )
    ap.add_argument("-o", "--output", help="quality.json path")
    args = ap.parse_args(argv)

    project = Path(args.project)
    report = gate(
        project,
        media=Path(args.media) if args.media else None,
        force_fail=args.force_fail,
        skip_heavy=args.skip_heavy,
    )
    if args.allow_unchecked:
        report["blocking"] = [
            b for b in report["blocking"] if b["status"] != "NOT_CHECKED"
        ]
        report["overall"] = "FAIL" if report["blocking"] else "PASS"
        report["deliveryAllowed"] = report["overall"] == "PASS"

    out = Path(args.output) if args.output else project / "quality.json"
    dump_json(out, report)
    print(f"overall={report['overall']} → {out}")
    if report["blocking"]:
        for b in report["blocking"]:
            print(f"  blocking: {b['name']}={b['status']}", file=sys.stderr)
    return 0 if report["deliveryAllowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
