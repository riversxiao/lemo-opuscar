"""Unified quality gate → quality.json (PASS|FAIL|NOT_CHECKED|NOT_APPLICABLE)."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

from common import ROOT, dump_json, load_json


STATUSES = ("PASS", "FAIL", "NOT_CHECKED", "NOT_APPLICABLE")

_DIGITS = str.maketrans("零〇一二三四五六七八九", "00123456789")


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


def _norm_zh(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower().translate(_DIGITS)
    return "".join(c for c in s if unicodedata.category(c)[0] in "LN")


def _load_homophone_classes() -> list[set[str]]:
    path = ROOT / "asr_homophones.json"
    if not path.is_file():
        return []
    raw = load_json(path)
    classes: list[set[str]] = []
    for group in raw.get("classes") or []:
        classes.append({_norm_zh(x) for x in group if x})
    return classes


def _apply_homophone_fold(s: str, classes: list[set[str]]) -> str:
    """Replace any member of a class with the canonical (sorted) representative."""
    out = _norm_zh(s)
    for cls in classes:
        if len(cls) < 2:
            continue
        canon = sorted(cls, key=len)[0]
        for member in sorted(cls, key=len, reverse=True):
            if member and member in out:
                out = out.replace(member, canon)
    return out


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
    integ = None
    tpeak = None
    m = re.search(r"\bI:\s*([+-]?\d+(?:\.\d+)?)\s*LUFS", log)
    if m:
        integ = float(m.group(1))
    m2 = re.search(r"True peak:\s*[^\n]*?([+-]?\d+(?:\.\d+)?)\s*dB", log)
    if not m2:
        m2 = re.search(r"Peak:\s*([+-]?\d+(?:\.\d+)?)\s*dBFS", log)
    if m2:
        tpeak = float(m2.group(1))
    if integ is None:
        return {"ok": False, "error": "could not parse ebur128", "log_tail": log[-500:]}
    return {"ok": True, "integrated_lufs": integ, "true_peak_dbtp": tpeak}


def _ensure_zh_words_rel(project: Path) -> None:
    """Best-effort: create sentence-level words_rel for CJK plans (never English words.py)."""
    try:
        from zh_words_rel import build as build_zh_words
    except ImportError:
        return
    lines_p = project / "content" / "lines.json"
    if not lines_p.is_file():
        lines_p = project / "lines.json"
    if not lines_p.is_file():
        return
    try:
        lines = load_json(lines_p)
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(lines, list):
        return
    cjk = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
    if not any(isinstance(L, dict) and cjk.search(str(L.get("text") or "")) for L in lines):
        return
    words = project / "voices" / "words_rel.json"
    if words.is_file():
        return
    try:
        build_zh_words(project)
    except (OSError, KeyError, TypeError, ValueError):
        pass


def run_readcheck(project: Path, *, style: str = "") -> dict[str, Any]:
    root = _repo_root()
    script = root / "core" / "render" / "readcheck.mjs"
    project = project.resolve()
    if not script.is_file():
        return check("readcheck", "NOT_CHECKED", "readcheck.mjs missing", required=True)
    if not (project / "index.html").is_file():
        return check(
            "readcheck",
            "NOT_CHECKED",
            f"no index.html in project {project} (engine not copied yet)",
            required=True,
        )

    # Swiss demo (and current scaffold) has no window.TEXTS(t) registry; film.js /
    # main.js / index.html are protected — cannot inject safely. Prefer N/A over
    # eternal blocking NOT_CHECKED (see docs/E2E-swiss.md).
    swiss_no_registry = style == "swiss-motion" or (
        (project / "content" / "engine.lock.json").is_file()
        and load_json(project / "content" / "engine.lock.json").get("style") == "swiss-motion"
    )
    # Quick static hint: film/main never define TEXTS
    if swiss_no_registry:
        film = project / "film.js"
        main = project / "main.js"
        blob = ""
        for p in (film, main):
            if p.is_file():
                try:
                    blob += p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    pass
        if "TEXTS" not in blob and "window.TEXTS" not in blob:
            return check(
                "readcheck",
                "NOT_APPLICABLE",
                "swiss-demo-without-registry: protected film.js/main.js/index.html "
                "have no window.TEXTS(t); cannot inject via touchables. "
                "Known gap — not a delivery block. Add a maintainer TEXTS hook in a "
                "future style version to enable readcheck.",
                required=False,
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
        no_texts = "no window.TEXTS" in detail or "has no window.TEXTS" in detail
        if no_texts and (style == "swiss-motion" or swiss_no_registry):
            return check(
                "readcheck",
                "NOT_APPLICABLE",
                "swiss-demo-without-registry: "
                + (detail or "page has no window.TEXTS(t)"),
                required=False,
            )
        return check("readcheck", "NOT_CHECKED", detail or "exit 2", required=True)
    return check("readcheck", "FAIL", detail or f"exit {proc.returncode}")


def _parse_asr_diffs(detail: str) -> list[tuple[str, str, str]]:
    """Parse 'DIFF id | want → got' lines from asr_check stdout."""
    out: list[tuple[str, str, str]] = []
    for line in detail.splitlines():
        m = re.match(
            r"DIFF\s+(\S+)\s+\|\s+(.+?)\s+→\s+(.+?)(?:\s{2,}|\s+\(similarity|\s*$)",
            line.strip(),
        )
        if m:
            out.append((m.group(1), m.group(2).strip(), m.group(3).strip()))
    return out


def run_asr(
    project: Path,
    has_vo: bool,
    *,
    asr_mode: str = "strict",
) -> dict[str, Any]:
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
    if not lines.is_file():
        lines = project / "lines.json"
    voices = project / "voices"
    if not script.is_file():
        return check("asr_check", "NOT_CHECKED", "asr_check.py missing", required=True)
    if not lines.is_file():
        return check("asr_check", "NOT_CHECKED", "content/lines.json missing", required=True)
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
    detail = ((proc.stdout or "") + (proc.stderr or ""))[-2000:]
    if proc.returncode == 0:
        return check("asr_check", "PASS", detail or "ASR OK")
    if proc.returncode == 2:
        return check("asr_check", "NOT_CHECKED", detail or "exit 2", required=True)

    # Strict default: keep FAIL (never silently override).
    if asr_mode != "zh-homophone-tolerant":
        return check("asr_check", "FAIL", detail or f"exit {proc.returncode}")

    # Tolerant mode: fold known finance homophone classes, re-compare DIFF lines.
    classes = _load_homophone_classes()
    diffs = _parse_asr_diffs(detail)
    if not diffs:
        return check(
            "asr_check",
            "FAIL",
            "asr_mode=zh-homophone-tolerant but could not parse DIFF lines; "
            "leaving strict FAIL.\n"
            + detail,
        )
    still_bad: list[str] = []
    tolerated: list[str] = []
    import difflib

    for lid, want, got in diffs:
        a = _apply_homophone_fold(want, classes)
        b = _apply_homophone_fold(got, classes)
        ratio = difflib.SequenceMatcher(None, a, b).ratio() if (a or b) else 1.0
        if a == b or ratio >= 0.92:
            tolerated.append(f"{lid}: '{want}'≈'{got}' (folded '{a}')")
        else:
            still_bad.append(f"{lid}: '{want}'→'{got}' folded '{a}'≠'{b}' sim={ratio:.2f}")
    if still_bad:
        return check(
            "asr_check",
            "FAIL",
            "zh-homophone-tolerant still failing:\n"
            + "\n".join(still_bad)
            + "\n--- raw ---\n"
            + detail,
        )
    return check(
        "asr_check",
        "PASS",
        "zh-homophone-tolerant: all DIFF lines match after lexicon fold. "
        "Strict ASR would FAIL; not silently overridden — mode flag required.\n"
        + "; ".join(tolerated)
        + "\n--- raw ---\n"
        + detail,
    )


def _schedule_check(
    project: Path,
    plan: dict[str, Any],
    *,
    require_vo: bool,
) -> dict[str, Any]:
    """Align with schedule --require-vo when VO is required / requested."""
    voice = plan.get("voice") or {}
    has_vo = voice.get("provider", "none") != "none" and bool(voice.get("lines"))
    need_vo = require_vo or has_vo

    tl_p = project / "timeline.parsed.json"
    if not tl_p.is_file():
        return check(
            "schedule_fits_target",
            "NOT_CHECKED",
            "timeline.parsed.json missing",
            required=True,
        )
    tl = load_json(tl_p)

    # Prefer explicit ok flag written by schedule.py
    if "ok" in tl and tl.get("ok") is False:
        errs = tl.get("errors") or []
        return check(
            "schedule_fits_target",
            "FAIL",
            "timeline.ok=false"
            + (f": {'; '.join(errs)}" if errs else "")
            + f" (scheduled {tl.get('scheduledDurationSec')}s, target {tl.get('targetDurationSec')}s)",
        )

    # Re-apply require-vo semantics even if an older diagnostic timeline marked fitsTarget
    if need_vo:
        lines = voice.get("lines") or []
        dur_p = project / "voices" / "dur.json"
        durs: dict[str, float] = {}
        if dur_p.is_file():
            raw = load_json(dur_p)
            if isinstance(raw, dict):
                for k, v in raw.items():
                    try:
                        durs[str(k)] = float(v)
                    except (TypeError, ValueError):
                        pass
        missing = []
        for ln in lines:
            lid = ln.get("id")
            if not lid:
                continue
            if lid not in durs or float(durs[lid]) <= 0:
                # also accept wav via timeline voDur > 0 for that id
                wav = project / "voices" / f"{lid}.wav"
                if not wav.is_file():
                    missing.append(lid)
        if missing:
            return check(
                "schedule_fits_target",
                "FAIL",
                "require-vo: missing measured VO duration for "
                + ", ".join(missing)
                + " (quality aligns with schedule --require-vo; fitsTarget alone is not enough)",
            )
        # If timeline was produced without requireVo and has WARN-style estimates only
        if tl.get("requireVo") is False and tl.get("warnings"):
            # still OK if durs now present — fitsTarget governs length
            pass

    if tl.get("fitsTarget") is False:
        return check(
            "schedule_fits_target",
            "FAIL",
            f"scheduled {tl.get('scheduledDurationSec')} > target {tl.get('targetDurationSec')}",
        )
    return check(
        "schedule_fits_target",
        "PASS",
        f"{tl.get('scheduledDurationSec')}s <= {tl.get('targetDurationSec')}s"
        + (" (require-vo OK)" if need_vo else ""),
    )


def gate(
    project: Path,
    *,
    media: Path | None = None,
    force_fail: list[str] | None = None,
    skip_heavy: bool = False,
    require_vo: bool = False,
    asr_mode: str = "strict",
) -> dict[str, Any]:
    project = Path(project).resolve()
    checks: list[dict[str, Any]] = []
    force_fail = force_fail or []

    # Ensure zh words_rel exists before readcheck (CJK never uses tools/words.py)
    _ensure_zh_words_rel(project)

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

    checks.append(_schedule_check(project, plan, require_vo=require_vo))

    media_path = media.resolve() if media else project / "out.mp4"
    if not media_path.is_file():
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
        # Still apply swiss N/A when we know registry is absent (avoid eternal block in CI)
        if style == "swiss-motion":
            checks.append(
                check(
                    "readcheck",
                    "NOT_APPLICABLE",
                    "swiss-demo-without-registry (+ skipped heavy run)",
                    required=False,
                )
            )
        else:
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
        checks.append(run_readcheck(project, style=style))
        checks.append(run_asr(project, has_vo, asr_mode=asr_mode))

    for name in force_fail:
        checks.append(check(name, "FAIL", "forced by fixture / --force-fail"))

    blocking = []
    for c in checks:
        if not c.get("required", True):
            if c["status"] == "FAIL":
                blocking.append(c)
            continue
        if c["status"] in ("FAIL", "NOT_CHECKED"):
            blocking.append(c)

    overall = "FAIL" if blocking else "PASS"
    report = {
        "schemaVersion": 1,
        "project": str(project),
        "style": style,
        "overall": overall,
        "deliveryAllowed": overall == "PASS",
        "asrMode": asr_mode,
        "requireVo": bool(require_vo or has_vo),
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
    ap.add_argument(
        "--require-vo",
        action="store_true",
        help="fail schedule check if measured VO missing (same as schedule --require-vo); "
        "also implied when plan.voice has lines",
    )
    ap.add_argument(
        "--asr-mode",
        choices=("strict", "zh-homophone-tolerant"),
        default="strict",
        help="strict (default): asr_check FAIL stays FAIL. "
        "zh-homophone-tolerant: fold known finance homophones from asr_homophones.json "
        "and PASS with detail when only those remain — never silent override",
    )
    ap.add_argument("-o", "--output", help="quality.json path")
    args = ap.parse_args(argv)

    project = Path(args.project).resolve()
    report = gate(
        project,
        media=Path(args.media).resolve() if args.media else None,
        force_fail=args.force_fail,
        skip_heavy=args.skip_heavy,
        require_vo=args.require_vo,
        asr_mode=args.asr_mode,
    )
    if args.allow_unchecked:
        report["blocking"] = [
            b for b in report["blocking"] if b["status"] != "NOT_CHECKED"
        ]
        report["overall"] = "FAIL" if report["blocking"] else "PASS"
        report["deliveryAllowed"] = report["overall"] == "PASS"

    out = Path(args.output) if args.output else project / "quality.json"
    if not out.is_absolute():
        out = (Path.cwd() / out).resolve()
    dump_json(out, report)
    print(f"overall={report['overall']} → {out}")
    if report["blocking"]:
        for b in report["blocking"]:
            print(f"  blocking: {b['name']}={b['status']}", file=sys.stderr)
    return 0 if report["deliveryAllowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
