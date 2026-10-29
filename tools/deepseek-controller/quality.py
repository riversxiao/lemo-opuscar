"""Unified quality gate → quality.json (PASS|FAIL|NOT_CHECKED|NOT_APPLICABLE)."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

from common import ROOT, dump_json, load_json


from pacing_profile import OUTRO_MAX_SEC

STATUSES = ("PASS", "FAIL", "NOT_CHECKED", "NOT_APPLICABLE", "WARN")  # WARN never blocks

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
    s = unicodedata.normalize("NFKC", s).lower()
    # Whisper writes spoken 百分之六 / 零点五 as 6% / 0.5 — same words, different notation.
    s = re.sub(r"(\d+(?:\.\d+)?)%", r"百分之\1", s)
    s = re.sub(r"(\d)\.(\d)", r"\1点\2", s)
    s = s.translate(_DIGITS)
    return "".join(c for c in s if unicodedata.category(c)[0] in "LN")


def _load_homophone_classes() -> list[dict[str, set[str]]]:
    """Load asr_homophones.json.

    Supports schema v2 objects ``{members, short?}`` and legacy plain string lists.
    Returns [{members: set[str], short: set[str]}, ...] with norm_zh applied.
    1-char entries in members are moved into short.
    """
    path = ROOT / "asr_homophones.json"
    if not path.is_file():
        return []
    raw = load_json(path)
    classes: list[dict[str, set[str]]] = []
    for group in raw.get("classes") or []:
        if isinstance(group, dict):
            members = {_norm_zh(x) for x in (group.get("members") or []) if x}
            shorts = {_norm_zh(x) for x in (group.get("short") or []) if x}
        elif isinstance(group, list):
            members = {_norm_zh(x) for x in group if x}
            shorts = set()
        else:
            continue
        shorts |= {m for m in members if len(m) == 1}
        members = {m for m in members if len(m) >= 2}
        if members or shorts:
            classes.append({"members": members, "short": shorts})
    return classes


def _apply_homophone_fold(s: str, classes: list) -> str:
    """Legacy multi-char substring fold (no short forms). Kept for tests/callers."""
    out = _norm_zh(s)
    for cls in classes:
        members: set[str]
        if isinstance(cls, dict):
            members = set(cls.get("members") or [])
        else:
            members = {m for m in cls if len(m) >= 2}
        if len(members) < 1:
            continue
        canon = sorted(members, key=lambda x: (len(x), x))[0]
        for member in sorted(members, key=len, reverse=True):
            if member and member in out:
                out = out.replace(member, canon)
    return out


def _homophone_tokenize(s: str, classes: list[dict[str, set[str]]]) -> str:
    """Longest-match tokenize: multi-char members first (all classes), then shorts.

    Each class match becomes «i» so 利息/利席/力 share a token while 富力 still
    binds to the 复利 class before 力 can steal the trailing char.
    """
    s = _norm_zh(s)
    multi: list[tuple[str, int]] = []
    shorts: list[tuple[str, int]] = []
    for i, cls in enumerate(classes):
        for m in cls.get("members") or []:
            multi.append((m, i))
        for m in cls.get("short") or []:
            shorts.append((m, i))
    multi.sort(key=lambda x: (-len(x[0]), x[0]))
    shorts.sort(key=lambda x: (-len(x[0]), x[0]))
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        hit = False
        for m, ci in multi:
            if m and s.startswith(m, i):
                out.append(f"«{ci}»")
                i += len(m)
                hit = True
                break
        if hit:
            continue
        for m, ci in shorts:
            if m and s.startswith(m, i):
                out.append(f"«{ci}»")
                i += len(m)
                hit = True
                break
        if hit:
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _homophone_tolerant_match(
    want: str,
    got: str,
    classes: list[dict[str, set[str]]],
    *,
    min_ratio: float = 0.88,
) -> tuple[bool, str, str, float]:
    """Return (ok, tokenized_want, tokenized_got, ratio).

    Full-string compare uses ``min_ratio``. Whisper *leading clip* is handled
    separately: drop ≤10 tokenized chars from the reference and ≤2 particle
    chars (是/的/了/…) from the hypothesis, but only accept when the remainders
    are equal or ≥0.97 similar — so a shared suffix cannot turn 蝙蝠 into 复利.
    """
    import difflib

    a = _homophone_tokenize(want, classes)
    b = _homophone_tokenize(got, classes)
    if not (a or b):
        return (True, a, b, 1.0)
    sm = difflib.SequenceMatcher
    ratio = sm(None, a, b).ratio()
    if a == b or ratio >= min_ratio:
        return (True, a, b, ratio)

    best = ratio
    _got_noise = set("是的了吗呢啊吧嘛")
    if len(b) >= 6:
        max_want_drop = min(10, max(0, len(a) - 5))
        max_got_drop = min(2, max(0, len(b) - 5))
        for i in range(0, max_want_drop + 1):
            for j in range(0, max_got_drop + 1):
                if i == 0 and j == 0:
                    continue
                if j and any(ch not in _got_noise for ch in b[:j]):
                    continue
                aa, bb = a[i:], b[j:]
                if not aa or not bb:
                    continue
                r = sm(None, aa, bb).ratio()
                if r > best:
                    best = r
                if aa == bb or r >= 0.97:
                    return (True, a, b, r)
    return (False, a, b, best)



def _engine_locked_dur(project: Path, style: str) -> float | None:
    """Duration the mux must match under a hash-locked engine.

    Swiss → film.js DUR; Caption → main.js DUR.
    Pictogram with edl_runtime.json → runtime DUR (content overlay; edl.js bytes
    stay locked at Olympics length, but page.mjs swaps window.DUR after READY).
    Pictogram without runtime → parse edl.js DUR (demo length) so quality refuses
    a short mux that still shows Olympics timeline.
    plan.targetDurationSec remains the schedule budget only.
    """
    lock_p = project / "content" / "engine.lock.json"
    if not lock_p.is_file():
        return None
    try:
        lock = load_json(lock_p)
    except (OSError, json.JSONDecodeError):
        return None
    protected = lock.get("protectedSha256") or {}
    lock_style = lock.get("style") or style

    # Pictogram content bridge: edl_runtime.json is the authoritative picture length.
    if lock_style == "pictogram-motion" or "edl.js" in protected:
        runtime_p = project / "edl_runtime.json"
        if runtime_p.is_file():
            try:
                rt = load_json(runtime_p)
                dur = float(rt.get("DUR") or 0)
                if dur > 0:
                    return dur
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass

    candidates: list[str] = []
    if "film.js" in protected:
        candidates.append("film.js")
    if "main.js" in protected:
        candidates.append("main.js")
    if "edl.js" in protected and not (project / "edl_runtime.json").is_file():
        candidates.append("edl.js")
    if not candidates:
        return None
    for name in candidates:
        path = project / name
        if not path.is_file():
            continue
        try:
            blob = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = re.search(r"\bDUR\s*=\s*(\d+(?:\.\d+)?)\b", blob)
        if not m:
            # edl.js uses `DUR: b * BEAT` object form — last numeric after DUR:
            m = re.search(r"\bDUR\s*[:=]\s*(\d+(?:\.\d+)?)", blob)
        if not m:
            continue
        try:
            return float(m.group(1))
        except ValueError:
            continue
    return None


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
    # ebur128=peak=true prints per-frame "I: -70.0 LUFS" before audio starts; the
    # final value is under "Summary:" (or the last framelog line). Never take the first match.
    m = re.search(
        r"Summary:.*?Integrated loudness:\s*I:\s*([+-]?\d+(?:\.\d+)?)\s*LUFS",
        log,
        re.S,
    )
    if m:
        integ = float(m.group(1))
    else:
        matches = re.findall(r"\bI:\s*([+-]?\d+(?:\.\d+)?)\s*LUFS", log)
        if matches:
            integ = float(matches[-1])
    m2 = re.search(
        r"Summary:.*?True peak:.*?Peak:\s*([+-]?\d+(?:\.\d+)?)\s*dBFS",
        log,
        re.S,
    )
    if m2:
        tpeak = float(m2.group(1))
    else:
        m2 = re.search(r"True peak:\s*[^\n]*?([+-]?\d+(?:\.\d+)?)\s*dB", log)
        if m2:
            tpeak = float(m2.group(1))
        else:
            peaks = re.findall(
                r"\bTPK:\s*([+-]?\d+(?:\.\d+)?)\s+[+-]?\d+(?:\.\d+)?\s*dBFS", log
            )
            if peaks:
                tpeak = float(peaks[-1])
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



def _caption_locked_main(project: Path, style: str) -> bool:
    """True when Caption News main.js is hash-locked (SHOTS/TEXTS not touchable).

    styleVersion overlays (e.g. liquidity-v001) unlock main.js — return False so
    quality runs real readcheck against content-driven TEXTS.
    """
    lock_p = project / "content" / "engine.lock.json"
    if not lock_p.is_file():
        return False
    try:
        lock = load_json(lock_p)
    except (OSError, json.JSONDecodeError):
        return False
    lock_style = lock.get("style") or ""
    if style == "caption-news" or lock_style == "caption-news":
        pass
    else:
        return False
    if lock_style and lock_style != "caption-news":
        return False
    if lock.get("styleVersion"):
        return False
    unlocked = lock.get("unlocked") or []
    if "main.js" in unlocked:
        return False
    protected = lock.get("protectedSha256") or {}
    return "main.js" in protected and (project / "main.js").is_file()


def _pictogram_style_version(project: Path) -> str | None:
    lock_p = project / "content" / "engine.lock.json"
    if not lock_p.is_file():
        return None
    try:
        lock = load_json(lock_p)
    except (OSError, json.JSONDecodeError):
        return None
    if (lock.get("style") or "") != "pictogram-motion":
        return None
    ver = lock.get("styleVersion")
    return str(ver) if ver else None


def _caption_style_version(project: Path) -> str | None:
    lock_p = project / "content" / "engine.lock.json"
    if not lock_p.is_file():
        return None
    try:
        lock = load_json(lock_p)
    except (OSError, json.JSONDecodeError):
        return None
    if (lock.get("style") or "") != "caption-news":
        return None
    ver = lock.get("styleVersion")
    return str(ver) if ver else None


def _pictogram_locked_edl(project: Path, style: str = "") -> bool:
    """True when pictogram still uses *demo* scenes.js (Olympics intro/finale structure).

    styleVersion overlays (e.g. finance-v001) unlock scenes.js — return False so
    quality does not claim Olympics structure is still locked.
    """
    lock_p = project / "content" / "engine.lock.json"
    if not lock_p.is_file():
        return style == "pictogram-motion"
    try:
        lock = load_json(lock_p)
    except (OSError, json.JSONDecodeError):
        return style == "pictogram-motion"
    if lock.get("styleVersion"):
        return False
    unlocked = lock.get("unlocked") or []
    if "scenes.js" in unlocked:
        return False
    if lock.get("style") == "pictogram-motion":
        return True
    protected = lock.get("protectedSha256") or {}
    return "edl.js" in protected and (project / "edl.js").is_file()


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

    # Swiss: locked film.js/main.js have no TEXTS. Prefer texts_runtime.json overlay
    # (page.mjs installs window.TEXTS after READY) so readcheck can run for real.
    # Without the overlay → NOT_APPLICABLE (not eternal NOT_CHECKED). See E2E-swiss.md.
    swiss_no_registry = style == "swiss-motion" or (
        (project / "content" / "engine.lock.json").is_file()
        and load_json(project / "content" / "engine.lock.json").get("style") == "swiss-motion"
    )
    texts_runtime = (project / "texts_runtime.json").is_file()
    if swiss_no_registry and not texts_runtime:
        film = project / "film.js"
        main = project / "main.js"
        blob = ""
        for pth in (film, main):
            if pth.is_file():
                try:
                    blob += pth.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    pass
        if "TEXTS" not in blob and "window.TEXTS" not in blob:
            return check(
                "readcheck",
                "NOT_APPLICABLE",
                "swiss-demo-without-registry: protected film.js/main.js/index.html "
                "have no window.TEXTS(t) and no texts_runtime.json overlay. "
                "Run apply_swiss_texts / schedule to enable readcheck, or keep N/A.",
                required=False,
            )

    # Pictogram style-version: intro/finale structure unlocked, but box-accurate
    # window.TEXTS(t) is not fully instrumented yet — N/A until a later pass.
    ver = _pictogram_style_version(project)
    if ver:
        return check(
            "readcheck",
            "NOT_APPLICABLE",
            f"pictogram-style-version({ver}): scenes.js overlay replaces Olympics "
            "intro/finale structure (content-driven). Box-accurate window.TEXTS(t) "
            "not yet instrumented — not a delivery block.",
            required=False,
        )

    # Pictogram: no TEXTS registry; intro/finale/HUD structure stays in locked scenes.js.
    # brand_strings.json may rewrite Olympics literals at eval time (disk hash intact).
    if _pictogram_locked_edl(project, style):
        brand = (project / "brand_strings.json").is_file()
        return check(
            "readcheck",
            "NOT_APPLICABLE",
            "pictogram-locked-demo-texts: no window.TEXTS(t); protected scenes.js "
            "keeps Olympics intro/finale/HUD structure. edl_runtime overlays card/chapter "
            "copy"
            + ("; brand_strings.json rewrites literals in eval(scenes.js)" if brand else "")
            + ". Full readcheck needs a style version that externalizes TEXTS.",
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
        if no_texts and (style == "swiss-motion" or swiss_no_registry) and not texts_runtime:
            return check(
                "readcheck",
                "NOT_APPLICABLE",
                "swiss-demo-without-registry: "
                + (detail or "page has no window.TEXTS(t)"),
                required=False,
            )
        if no_texts and _pictogram_locked_edl(project, style):
            return check(
                "readcheck",
                "NOT_APPLICABLE",
                "pictogram-locked-demo-texts: "
                + (detail or "page has no window.TEXTS(t)"),
                required=False,
            )
        return check("readcheck", "NOT_CHECKED", detail or "exit 2", required=True)

    # Caption News: TEXTS live inside hash-locked main.js (bee demo SHOTS/labels).
    # Controller may only rewrite timeline.json captions/VO — cannot retune locked
    # map/sem labels (加州 / 瓦螨 …). Treat FAIL as N/A under that lock (Swiss-like).
    if _caption_locked_main(project, style):
        return check(
            "readcheck",
            "NOT_APPLICABLE",
            "caption-locked-demo-texts: protected main.js owns SHOTS/TEXTS; "
            "controller touchables only rewrite timeline.json VO/caps. "
            "Readcheck asserts locked bee-demo labels — not a delivery block until "
            "a content-driven TEXTS/SHOTS bridge ships. "
            + (detail or f"exit {proc.returncode}"),
            required=False,
        )
    if _pictogram_locked_edl(project, style):
        brand = (project / "brand_strings.json").is_file()
        return check(
            "readcheck",
            "NOT_APPLICABLE",
            "pictogram-locked-demo-texts: protected scenes.js keeps Olympics "
            "intro/finale/HUD structure; edl_runtime overlays card/chapter copy"
            + ("; brand_strings.json may rewrite literals at eval time" if brand else "")
            + ". " + (detail or f"exit {proc.returncode}"),
            required=False,
        )
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

    # Tolerant mode: longest-match class tokens (+ documented short truncations),
    # re-compare DIFF lines. Never silent — requires --asr-mode=zh-homophone-tolerant.
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

    for lid, want, got in diffs:
        ok, a, b, ratio = _homophone_tolerant_match(want, got, classes, min_ratio=0.88)
        if ok:
            tolerated.append(
                f"{lid}: '{want}'≈'{got}' (tokens '{a}' vs '{b}', sim={ratio:.2f})"
            )
        else:
            still_bad.append(
                f"{lid}: '{want}'→'{got}' tokens '{a}'≠'{b}' sim={ratio:.2f}"
            )
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
        "zh-homophone-tolerant: all DIFF lines match after lexicon tokenize "
        "(members + documented short truncations). "
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
    detail = f"{tl.get('scheduledDurationSec')}s <= {tl.get('targetDurationSec')}s"
    if need_vo:
        detail += " (require-vo OK)"
    pad = float(tl.get("padSec") or 0.0)
    if pad > OUTRO_MAX_SEC + 1e-6:
        # Duration follows content: padding the film up to the target is dead air.
        return check(
            "schedule_fits_target",
            "FAIL",
            f"padded {pad}s {tl.get('padMode') or 'hold-last-beat'} > {OUTRO_MAX_SEC}s outro allowance "
            f"(contentDurationSec={tl.get('contentDurationSec')}, target {tl.get('targetDurationSec')}s is a ceiling) "
            "— re-run `schedule` without --pad-under-target",
        )
    if pad:
        detail += (
            f"; padded {pad}s {tl.get('padMode') or 'hold-last-beat'} (≤{OUTRO_MAX_SEC}s allowance)"
            f" (contentDurationSec={tl.get('contentDurationSec')})"
        )
    elif tl.get("underTargetBeforePad"):
        detail += f"; underTargetBeforePad contentDurationSec={tl.get('contentDurationSec')}"
    return check(
        "schedule_fits_target",
        "PASS",
        detail,
    )



def resolve_delivery_asr_mode(
    plan: dict[str, Any],
    *,
    asr_mode: str | None,
    delivery: bool,
) -> str:
    """Pick ASR mode for quality.

    - Explicit strict / zh-homophone-tolerant always wins.
    - auto: zh* → tolerant, else strict.
    - None + --delivery + plan.language zh/zh-en → zh-homophone-tolerant.
    - None otherwise → strict (English never silently weakened).
    """
    if asr_mode in ("strict", "zh-homophone-tolerant"):
        return asr_mode
    lang = str((plan or {}).get("language") or "").lower()
    zhish = lang == "zh" or lang.startswith("zh") or lang.startswith("zh-")
    if asr_mode == "auto":
        return "zh-homophone-tolerant" if zhish else "strict"
    if delivery and zhish:
        return "zh-homophone-tolerant"
    return "strict"


def _dialogue_check(project: Path) -> dict[str, Any]:
    """DIALOGUE.md gate: required once lines carry `function` (dialogue-layer projects)."""
    import dialogue_check as _dc

    try:
        lp = _dc.find_lines(project)
        raw = load_json(lp)
    except (OSError, ValueError, FileNotFoundError):
        return check("dialogue_gate", "NOT_APPLICABLE", "no lines.json", required=False)
    rows = raw if isinstance(raw, list) else []
    if not any(isinstance(r, dict) and "function" in r for r in rows):
        return check("dialogue_gate", "NOT_APPLICABLE",
                     "legacy lines without `function` (pre-DIALOGUE project)", required=False)
    try:
        rep = _dc.run(project, write=True)
    except (OSError, ValueError) as e:
        return check("dialogue_gate", "NOT_CHECKED", f"failed: {e}", required=True)
    d = rep.get("duration") or {}
    detail = f"{d.get('totalChars')}字 ≈ {d.get('estSec')}s vs target {d.get('targetSec')}s"
    if rep["fails"]:
        detail += "; " + " | ".join(rep["fails"][:4])
    if rep["warns"]:
        detail += f"; {len(rep['warns'])} warn"
    st = "PASS" if rep["status"] in ("PASS", "SKIP") else "FAIL"
    return check("dialogue_gate", st, detail, required=True)


def _dialogue_loop_check(project: Path) -> dict[str, Any]:
    """Self-loop optimizer gate: required once lines carry `function`; PASS + same lines sha."""
    import dialogue_check as _dc
    import dialogue_loop as _dl

    try:
        rows = load_json(_dc.find_lines(project))
    except (OSError, ValueError, FileNotFoundError):
        return check("dialogue_loop", "NOT_APPLICABLE", "no lines.json", required=False)
    rows = rows if isinstance(rows, list) else []
    if not any(isinstance(r, dict) and "function" in r for r in rows):
        return check("dialogue_loop", "NOT_APPLICABLE", "legacy lines without `function`", required=False)
    ok, why = _dl.gate_status(project)
    return check("dialogue_loop", "PASS" if ok else "FAIL", why, required=True)


def _spk_python() -> str | None:
    import shutil
    cands = [os.environ.get("LEMO_SPK_PYTHON"), str(_repo_root() / ".venv-spk" / "bin" / "python"),
             str(_repo_root() / ".venv-voice" / "bin" / "python"), shutil.which("python3")]
    for c in cands:
        if c and Path(c).exists():
            r = subprocess.run([c, "-c", "import resemblyzer"], capture_output=True)
            if r.returncode == 0:
                return c
    return None



def run_visual_check_gate(project: Path, media: Path | None, delivery: bool) -> dict[str, Any]:
    """Reads evidence/visual-check.json written by `cli.py visual-check` (it is not re-run here:
    OCR + optional free vision model are heavy). Required for --delivery.

    PASS only when the report belongs to this media file, the media was not changed after the
    check, and no high-severity issue is left (finalStatus PASS). BEST_EFFORT / FAIL → FAIL.
    Semantic layer NOT_AVAILABLE does not block (it is reported in the detail)."""
    p = Path(project) / "evidence" / "visual-check.json"
    req = bool(delivery)
    if not p.is_file():
        return check("visual_check", "NOT_CHECKED", "evidence/visual-check.json missing — run `cli.py visual-check --project P --media M`", required=req)
    try:
        rep = load_json(p)
    except Exception as e:  # noqa: BLE001
        return check("visual_check", "FAIL", f"unreadable visual-check.json: {e}", required=req)
    if media is not None:
        rm = rep.get("media")
        if not rm or Path(rm).resolve() != Path(media).resolve():
            return check("visual_check", "NOT_CHECKED", f"visual-check.json is for {rm}, not {media}", required=req)
        try:
            if Path(media).stat().st_mtime > p.stat().st_mtime + 1:
                return check("visual_check", "NOT_CHECKED", "media changed after visual-check — re-run it", required=req)
        except OSError:
            pass
    fs = rep.get("finalStatus") or rep.get("status")
    sem = (rep.get("semantic") or {})
    tail = f"; semantic={sem.get('status')} model={sem.get('model')}"
    hi = [i for i in rep.get("issues", []) if i.get("severity") == "high"]
    if fs == "PASS" and not hi:
        return check("visual_check", "PASS", f"0 high, {rep.get('medium', 0)} medium{tail}", required=req)
    kinds = sorted({i.get("kind") for i in hi})
    return check("visual_check", "FAIL", f"severity=high: {fs}, {len(hi)} high ({', '.join(kinds)}){tail}", required=req)

def run_speaker_check(project: Path, has_vo: bool) -> dict[str, Any]:
    """ONE-narrator gate for multi-line VO: speaker-embedding cosine (Resemblyzer, local, free).

    FAIL (high) when any line's similarity to the other lines' centroid is < 0.80 or any
    pair < 0.70 (calibrated: edge Yunxi 22 lines → min 0.866 / pair 0.785; per-line
    StepAudio gen-preview requests → 0.746 / 0.589, audibly different speakers).
    """
    import dialogue_check as _dc

    if not has_vo:
        return check("speaker_consistency", "NOT_APPLICABLE", "no VO", required=False)
    try:
        rows = load_json(_dc.find_lines(project))
    except (OSError, ValueError, FileNotFoundError):
        return check("speaker_consistency", "NOT_CHECKED", "lines.json missing", required=True)
    rows = rows if isinstance(rows, list) else (rows.get("lines") or [])
    ids = [r["id"] for r in rows if isinstance(r, dict) and r.get("id")]
    if len(ids) < 3:
        return check("speaker_consistency", "NOT_APPLICABLE", f"{len(ids)} VO line(s) (<3)", required=False)
    voices = project / "voices"
    missing = [i for i in ids if not (voices / f"{i}.wav").is_file()]
    if missing:
        return check("speaker_consistency", "NOT_CHECKED", f"missing wav: {missing[:5]}", required=True)
    py = _spk_python()
    if not py:
        return check("speaker_consistency", "NOT_CHECKED",
                     "resemblyzer not installed (python -m venv .venv-spk && .venv-spk/bin/pip install torch "
                     "--index-url https://download.pytorch.org/whl/cpu resemblyzer webrtcvad-wheels librosa); "
                     "or LEMO_SPK_PYTHON", required=True)
    script = _repo_root() / "core" / "tts" / "speaker_check.py"
    try:
        r = subprocess.run([py, str(script), str(voices), "--ids", ",".join(ids)],
                           capture_output=True, text=True, timeout=900)
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except (subprocess.SubprocessError, ValueError, IndexError) as e:
        return check("speaker_consistency", "NOT_CHECKED", f"failed: {e}", required=True)
    (project / "evidence").mkdir(exist_ok=True)
    (project / "evidence" / "speaker-check.json").write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                                                             encoding="utf-8")
    if d.get("status") not in ("PASS", "FAIL"):
        return check("speaker_consistency", "NOT_CHECKED", str(d.get("detail") or d), required=True)
    lo = min(d["lines"].items(), key=lambda kv: kv[1])
    detail = (f"{d['model']}: {len(ids)} lines, min line→centroid {lo[1]:.3f} ({lo[0]}) vs ≥{d['minSim']}, "
              f"pair min {d['pairMin']:.3f} vs ≥{d['minPair']}, pair mean {d['pairMean']:.3f}")
    if d["status"] == "FAIL":
        detail = f"severity=high: narration is not one consistent voice — below: {d['belowMin']}; " + detail
    return check("speaker_consistency", d["status"], detail, required=True)


def run_pacing_gate(project: Path, media: Path | None, *, enforce: bool = False,
                    skip_visual: bool = False) -> dict[str, Any]:
    """Pacing gate (pacing_check.py). P0 report-only → WARN (never blocks);
    enforce=True (P1) → FAIL-level misses block (required)."""
    if not (project / "timeline.parsed.json").is_file():
        return check("pacing", "NOT_APPLICABLE", "no timeline.parsed.json", required=False)
    try:
        import pacing_check
        rep = pacing_check.run(project, media, visual=not skip_visual)
    except Exception as e:  # report-only gate must never crash quality
        return check("pacing", "NOT_CHECKED", f"pacing_check failed: {e}", required=enforce)
    detail = pacing_check.summary(rep) + " → evidence/pacing-check.json"
    if rep["status"] == "PASS":
        return check("pacing", "PASS", detail, required=enforce)
    if enforce and rep["status"] == "FAIL":
        return check("pacing", "FAIL", detail, required=True)
    return check("pacing", "WARN", ("report-only: " if not enforce else "") + detail, required=False)


def gate(
    project: Path,
    *,
    media: Path | None = None,
    force_fail: list[str] | None = None,
    skip_heavy: bool = False,
    require_vo: bool = False,
    asr_mode: str | None = None,
    delivery: bool = False,
    pacing_enforce: bool = False,
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

    if delivery:
        require_vo = True
    asr_mode = resolve_delivery_asr_mode(plan, asr_mode=asr_mode, delivery=delivery)

    checks.append(_schedule_check(project, plan, require_vo=require_vo))
    checks.append(_dialogue_check(project))
    checks.append(_dialogue_loop_check(project))

    media_path = media.resolve() if media else project / "out.mp4"
    if not media_path.is_file():
        for cand in (f"{project.name}.mp4", "final.mp4", "film.mp4", "mux.mp4", "out/video24.mp4"):
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
            if dur is not None:
                engine_dur = _engine_locked_dur(project, style)
                if engine_dur is not None:
                    # Locked film.js DUR is the mux length; plan target is schedule budget.
                    slack = 1.0
                    if abs(dur - engine_dur) <= slack + 1e-6:
                        detail = (
                            f"style_locked_duration: media {dur:.2f}s ≈ engine DUR "
                            f"{engine_dur:g}s (±{slack:g}s)"
                        )
                        if target is not None:
                            detail += (
                                f"; plan targetDurationSec={target} is schedule "
                                f"budget only (style_locked_duration)"
                            )
                        checks.append(check("media_duration", "PASS", detail))
                    else:
                        checks.append(
                            check(
                                "media_duration",
                                "FAIL",
                                f"style_locked_duration: media {dur:.2f}s ≠ engine "
                                f"DUR {engine_dur:g}s (±{slack:g}s); plan target "
                                f"{target} not used as mux length under engine lock",
                            )
                        )
                elif target is not None:
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
                            check(
                                "media_duration",
                                "PASS",
                                f"{dur:.2f}s vs target {target}",
                            )
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
            checks.append(
                check("speaker_consistency", "NOT_CHECKED", "skipped (--skip-heavy)", required=True)
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
        checks.append(run_speaker_check(project, has_vo))

    checks.append(run_visual_check_gate(project, media, delivery))
    if delivery or pacing_enforce:
        checks.append(run_pacing_gate(project, media_path if media_path.is_file() else None,
                                      enforce=pacing_enforce, skip_visual=skip_heavy))

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
    engine_dur_meta = _engine_locked_dur(project, style)
    report = {
        "schemaVersion": 1,
        "project": str(project),
        "style": style,
        "overall": overall,
        "deliveryAllowed": overall == "PASS",
        "asrMode": asr_mode,
        "delivery": bool(delivery),
        "requireVo": bool(require_vo or has_vo),
        "engineLockedDurSec": engine_dur_meta,
        "checks": checks,
        "blocking": [{"name": b["name"], "status": b["status"]} for b in blocking],
        "standards": {
            "loudness_lufs": {"target": -14.0, "tol": 1.0},
            "true_peak_dbtp_max": -1.0,
            "media_duration": (
                "engine DUR ±1s when content/engine.lock.json protects film.js or main.js "
                "(style_locked_duration from film.js/main.js/edl_runtime|edl.js); else plan targetDurationSec +2.5s"
            ),
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
        choices=("strict", "zh-homophone-tolerant", "auto"),
        default=None,
        help="strict: asr_check FAIL stays FAIL. "
        "zh-homophone-tolerant: lexicon fold for zh finance Whisper drift. "
        "auto: zh* → tolerant, else strict. "
        "Default without --delivery/--asr-mode: strict (English never silently weakened).",
    )
    ap.add_argument(
        "--delivery",
        action="store_true",
        help="recommended delivery gate: imply --require-vo; for plan.language zh/zh-en "
        "use zh-homophone-tolerant unless --asr-mode is set explicitly. "
        "English plans stay strict. Does not silently weaken strict ASR.",
    )
    ap.add_argument(
        "--pacing-enforce",
        action="store_true",
        help="pacing gate FAIL blocks delivery (P1). Default with --delivery: report-only WARN",
    )
    ap.add_argument("-o", "--output", help="quality.json path")
    args = ap.parse_args(argv)

    project = Path(args.project).resolve()
    # None asr_mode → resolve inside gate (delivery+zh → tolerant, else strict)
    report = gate(
        project,
        media=Path(args.media).resolve() if args.media else None,
        force_fail=args.force_fail,
        skip_heavy=args.skip_heavy,
        require_vo=args.require_vo,
        asr_mode=args.asr_mode,  # None | strict | zh-homophone-tolerant | auto
        delivery=args.delivery,
        pacing_enforce=args.pacing_enforce,
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
