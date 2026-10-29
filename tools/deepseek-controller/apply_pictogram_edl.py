#!/usr/bin/env python3
"""Build pictogram edl_runtime.json + timeline.json from edl_content (never edits edl.js/scenes.js).

Locked demo edl.js hardcodes Olympics shots; scenes.js closes over EDL.shots at load.
core/render/page.mjs, after window.READY, fetches edl_runtime.json (if present),
replaces window.EDL / window.DUR, and re-evals scenes.js so card/chapter copy + timing
come from this touchable — protected file hashes stay intact.

Also writes brand_strings.json: literal replacements applied by page.mjs to the
*eval'd* scenes.js source (disk scenes.js hash untouched) so HUD/intro/finale
Olympics labels can track the plan topic. Complex intro animation structure
(rings / 43-sport grid) stays demo-shaped — full rebrand needs a style version.

Also writes timeline.json vo{id→t} + dur for music_bed / mix_vo_only (picture engine ignores it).
Demo music/music.py is Olympics-length / section-asserted; controller E2E uses cli mix / music_bed.py (or mix_vo_only).

Usage:
  python3 tools/deepseek-controller/apply_pictogram_edl.py --project /path/to/film
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from common import acronym_case_violations, dump_json, load_json, mixed_acronyms_in, upper_keep

# Fixture / adapt may emit aliases not present in poses/*. Remap to real POSES keys.
POSE_ALIASES: dict[str, str] = {
    "stand": "golf",
    "point": "fencing",
    "group": "relay",
}

# zh on-screen → uppercase EN title for Inter Tight (card/chapter architecture)
EN_GLOSS: dict[str, str] = {
    "分散投资": "DIVERSIFY",
    "资产": "ASSETS",
    "资产类别": "ASSET CLASSES",
    "股票": "STOCKS",
    "债券": "BONDS",
    "现金": "CASH",
    "黄金": "GOLD",
    "房产": "REAL ESTATE",
    "指数": "INDEX",
    "别押一把": "NO SINGLE BET",
    "组合": "PORTFOLIO",
    "风险": "RISK",
    "波动": "VOLATILITY",
    "长期": "LONG TERM",
    "为何分散": "WHY DIVERSIFY",
    "流动性": "LIQUIDITY",
    "账上": "ON BOOKS",
    "周转": "TURNOVER",
    "随时能用": "READY CASH",
    "留现金": "KEEP CASH",
    "时机": "TIMING",
    "紧张": "STRESS",
}


# Palette keys that exist on G.PAL in engine.js
PAL_OK = {"red", "purple", "green", "gold", "ochre", "ink", "multi"}
PAL_ALIASES: dict[str, str] = {
    "signal": "red",
    "accent": "gold",
    "page": "ink",
    "ink": "ink",
}


def _en_title(zh: str, fallback: str = "") -> str:
    zh = (zh or "").strip()
    if zh in EN_GLOSS:
        return EN_GLOSS[zh]
    # already Latin
    # upper_keep: VaR stays VaR (VAR reads as vector autoregression)
    if zh and re.fullmatch(r"[A-Za-z0-9 .·\-&/,']+", zh):
        return upper_keep(zh)
    if fallback and re.fullmatch(r"[A-Za-z0-9 .·\-&/,']+", fallback):
        return upper_keep(fallback)
    return upper_keep(fallback or zh or "ITEM")[:24]


def _pal(raw: Any) -> str:
    s = str(raw or "red").strip().lower()
    s = PAL_ALIASES.get(s, s)
    return s if s in PAL_OK else "red"


def _pose(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    p = str(raw).strip()
    return POSE_ALIASES.get(p, p)


def _compile_shots(
    content_shots: list[dict[str, Any]],
    *,
    beat: float,
    schedule_shots: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Expand edl_content shots into engine-shaped EDL.shots with t0/dur/title/…"""
    by_id = {s["id"]: s for s in (schedule_shots or []) if isinstance(s, dict) and "id" in s}
    out: list[dict[str, Any]] = []
    card_n = 0
    chap = None
    ci = 0
    b = 0

    for i, raw in enumerate(content_shots):
        if not isinstance(raw, dict):
            continue
        sid = raw.get("id") or f"s{i}"
        kind = str(raw.get("kind") or "card")
        zh = str(raw.get("zh") or raw.get("en") or "")
        en_src = str(raw.get("en") or "")
        # Prefer Latin en when adapt duplicated zh into en
        en = _en_title(zh, en_src if en_src != zh else "")
        jp = str(raw.get("jp") or "")
        beats = int(raw.get("beats") or 4)
        if beats < 1:
            beats = 4
        pal = _pal(raw.get("pal"))
        pose = _pose(raw.get("pose"))

        # Schedule may pad last shot — prefer its duration when present
        sched = by_id.get(sid) or {}
        if sched.get("t1") is not None and sched.get("t0") is not None:
            dur = float(sched["t1"]) - float(sched["t0"])
            if dur > 0:
                beats = max(1, int(round(dur / beat)))
                # keep fractional pad on last shot via explicit dur below
                dur_sec = dur
            else:
                dur_sec = beats * beat
        else:
            dur_sec = beats * beat

        t0 = float(sched["t0"]) if sched.get("t0") is not None else b * beat
        # Keep beat index consistent with t0 when schedule drives times
        if sched.get("t0") is not None:
            b0 = int(round(t0 / beat))
        else:
            b0 = b

        entry: dict[str, Any] = {
            "id": sid,
            "kind": kind,
            "zh": zh,
            "en": en,
            "jp": jp,
            "beats": beats,
            "b0": b0,
            "t0": round(t0, 6),
            "dur": round(dur_sec, 6),
            "i": i,
            "role": raw.get("role"),
            "motionPreset": raw.get("motionPreset"),
            "data": raw.get("data") or {},
        }

        if kind == "chapter":
            chap = entry
            ci = 0
            no = str(raw.get("no") or f"{len([x for x in out if x.get('kind') == 'chapter']) + 1:02d}")
            entry["no"] = no
            entry["pal"] = pal if pal != "signal" else "multi"
            entry["pal"] = _pal(entry["pal"])
            # multi looks best for catalogue chapter; red for risk chapter
            if entry["pal"] not in PAL_OK:
                entry["pal"] = "multi"
            entry["pk"] = "purple" if entry["pal"] == "multi" else entry["pal"]
            entry["cname"] = en
        elif kind == "card":
            card_n += 1
            entry["n"] = int(raw.get("n") or card_n)
            entry["pose"] = pose
            entry["pal"] = chap["pal"] if chap else pal
            entry["chap"] = chap["id"] if chap else None
            entry["ci"] = ci
            ci += 1
            if entry["pal"] == "multi":
                entry["pk"] = ["red", "purple", "green", "gold", "ochre"][entry["ci"] % 5]
            else:
                entry["pk"] = entry["pal"] if entry["pal"] in PAL_OK else "red"
            # display fields (matches edl.js post-process)
            if raw.get("fam") or raw.get("sub"):
                entry["fam"] = True
                entry["sub"] = raw.get("sub") or en
                entry["title"] = entry["sub"]
                entry["family"] = en
            else:
                entry["title"] = en
                if raw.get("sub"):
                    entry["tag"] = raw["sub"]
                entry["family"] = str(raw.get("family") or (chap["en"] if chap else "ITEM"))
        elif kind == "intro":
            entry["id"] = entry.get("id") or "intro"
        elif kind == "finale":
            entry["id"] = entry.get("id") or "finale"

        out.append(entry)
        if sched.get("t1") is not None:
            # next default t0 follows schedule end
            b = int(round(float(sched["t1"]) / beat))
        else:
            b = b0 + beats

    return out



def build_brand_strings(
    plan: dict[str, Any] | None,
    compiled: list[dict[str, Any]],
) -> dict[str, Any]:
    """Olympics literal → content brand map for page.mjs scenes.js source rewrite."""
    plan = plan or {}
    credits = plan.get("credits") if isinstance(plan.get("credits"), dict) else {}
    topic = str(plan.get("topic") or credits.get("title") or "FILM").strip() or "FILM"
    title = str(credits.get("title") or topic).strip() or topic
    year = str(credits.get("year") or "2026").strip() or "2026"
    author = str(credits.get("author") or "").strip()
    en = _en_title(title, title)
    zh = title if any("\u4e00" <= c <= "\u9fff" for c in title) else topic
    if topic in EN_GLOSS:
        en = EN_GLOSS[topic]
    card_n = sum(1 for s in compiled if s.get("kind") == "card")
    chap_n = sum(1 for s in compiled if s.get("kind") == "chapter")
    ticks = max(card_n, 1)
    hud_line = en[:22]
    tagline_en = "STAY DIVERSIFIED" if ("DIVERS" in en or "\u5206\u6563" in topic) else en[:22]
    tagline_zh = (
        "\u7559\u4f59\u5730\uff0c\u4e0d\u8d4c\u4e00\u628a"
        if ("\u5206\u6563" in topic or "\u5206\u6563" in title)
        else zh[:16]
    )
    credit_line = f"{author} \u00b7 {year}" if author else f"LemoLab \u00b7 {year}"

    pairs = [
        ("THE 20TH ASIAN GAMES", hud_line),
        ("AICHI-NAGOYA 2026", f"{en[:14]} {year}"[:22]),
        ("2026  \u00b7  AICHI \u2013 NAGOYA  \u00b7  JAPAN", f"{year}  \u00b7  {en}  \u00b7  ZH"[:42]),
        ("\u7b2c20\u56de\u30a2\u30b8\u30a2\u7af6\u6280\u5927\u4f1a  \u00b7  \u611b\u77e5\u30fb\u540d\u53e4\u5c4b", f"{zh}  \u00b7  {year}"[:36]),
        ("\u7b2c20\u5c4a\u4e9a\u6d32\u8fd0\u52a8\u4f1a  \u00b7  \u7231\u77e5 \u00b7 \u540d\u53e4\u5c4b", f"{zh}  \u00b7  {year}"[:36]),
        ("\u7b2c20\u56de\u30a2\u30b8\u30a2\u7af6\u6280\u5927\u4f1a\uff082026 / \u611b\u77e5\u30fb\u540d\u53e4\u5c4b\uff09", f"{zh}\uff08{year}\uff09"[:40]),
        ("SEPTEMBER 19 \u2014 OCTOBER 4, 2026", f"CONTROLLER E2E  \u00b7  {year}"),
        ("THE 20TH ASIAN GAMES   \u00b7   2026.9.19 \u2014 10.4", f"{hud_line}   \u00b7   {year}"),
        ("IMAGINE ONE ASIA", tagline_en),
        ("\u3053\u3053\u3067\u3001\u3072\u3068\u3064\u306b\u3002", tagline_zh),
        ("\u5728\u8fd9\u91cc\uff0c\u5408\u800c\u4e3a\u4e00", tagline_zh),
        ("9.19 \u2014 10.4", year),
        ("ON YOUR MARKS", "READY"),
        ("SET", "GO"),
        ("\u5404\u5c31\u5404\u4f4d", "\u51c6\u5907"),
        ("\u9884\u5907", "\u5f00\u59cb"),
        ("\u4f4d\u7f6e\u306b\u3064\u3044\u3066", "\u51c6\u5907"),
        ("\u3088\u30fc\u3044", "\u5f00\u59cb"),
        ("SPORTS", "CARDS" if card_n else "BEATS"),
        ("EVENTS", "CHAPTERS" if chap_n else "SHOTS"),
        ("DAYS", "SECS"),
        ("LemoLab \u00d7 Claude Opus 5.5", credit_line[:36]),
        # Card meta "01 / 43" — scenes.js uses string literal ' / 43'
        (" / 43", f" / {ticks}"),
        ("{ n: 43,", f"{{ n: {ticks},"),
    ]
    # Prefer longer Olympics phrases before short tokens (SET/DAYS)
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    seen: set[str] = set()
    replace: list[dict[str, str]] = []
    for frm, to in pairs:
        if frm in seen:
            continue
        seen.add(frm)
        if to and to != frm:
            replace.append({"from": frm, "to": str(to)})

    out = {
        "note": (
            "Runtime rewrite of Olympics literals inside eval(scenes.js) by "
            "core/render/page.mjs when demo scenes.js is locked. "
            "Also supplies titleEn/titleZh/slogan*/credit for style-version "
            "finance-v001 (content-driven intro/finale). Disk edl.js stays locked."
        ),
        "topic": topic,
        "titleEn": en,
        "titleZh": zh,
        "year": year,
        "sloganEn": tagline_en,
        "sloganZh": (
            "鸡蛋不要放进同一个篮子"
            if ("分散" in topic or "分散" in title)
            else tagline_zh
        ),
        "sloganJp": "分散投資" if ("分散" in topic or "DIVERS" in en) else en[:12],
        "credit": credit_line[:40],
        "hudTicks": ticks,
        "cardCount": card_n,
        "chapterCount": chap_n,
        "replace": replace,
    }
    # Per-term overrides (plan.brand): eyebrow label, end card title/line, titles, slogans.
    # finance-v002 scenes.js reads eyebrow/eyebrowTop/endTitle/endLine; older versions ignore them.
    brand = plan.get("brand") if isinstance(plan.get("brand"), dict) else {}
    for k in BRAND_KEYS:
        if isinstance(brand.get(k), str):
            out[k] = brand[k]
    out["keepCase"] = sorted(set(brand.get("keepCase") or []) | _plan_acronyms(plan))
    return out


BRAND_KEYS = ("eyebrow", "eyebrowTop", "endTitle", "endLine", "titleEn", "titleZh",
              "sloganEn", "sloganZh", "sloganJp", "credit")


def _plan_texts(plan: dict[str, Any]) -> list[str]:
    t: list[str] = []
    for sh in plan.get("shots") or []:
        if isinstance(sh, dict):
            t += [str(sh.get(k) or "") for k in ("text", "onScreenText", "onScreenTextEn")]
    for ln in ((plan.get("voice") or {}).get("lines") or []):
        if isinstance(ln, dict):
            t += [str(ln.get("text") or ""), str(ln.get("cap") or "")]
    t += [str((plan.get("credits") or {}).get("title") or "")]
    return t


def _plan_acronyms(plan: dict[str, Any]) -> set[str]:
    return mixed_acronyms_in(_plan_texts(plan))


def display_strings(runtime: dict[str, Any], brand: dict[str, Any]) -> list[str]:
    """Every string the renderer can draw (EDL shot fields + brand strings + replacement targets)."""
    t: list[str] = []
    for s in runtime.get("shots") or []:
        t += [str(s.get(k)) for k in ("zh", "en", "jp", "title", "sub", "family", "tag", "cname") if s.get(k)]
    t += [str(brand.get(k)) for k in BRAND_KEYS if brand.get(k)]
    t += [str(r.get("to") or "") for r in brand.get("replace") or []]
    return t


def case_guard(runtime: dict[str, Any], brand: dict[str, Any]) -> list[str]:
    return acronym_case_violations(display_strings(runtime, brand), set(brand.get("keepCase") or []))


def apply_pictogram_edl(
    project: Path,
    *,
    parsed: dict[str, Any] | None = None,
    bpm: float = 150.0,
    enter: float = 0.35,
) -> dict[str, Any]:
    project = Path(project).resolve()
    content_path = project / "content" / "edl_content.json"
    root_sidecar = project / "edl_content.json"
    if not content_path.is_file() and root_sidecar.is_file():
        content_path = root_sidecar
    if not content_path.is_file():
        raise FileNotFoundError(f"missing edl_content.json under {project}")

    content = load_json(content_path)
    if not isinstance(content, dict):
        raise ValueError("edl_content.json must be an object")
    shots_in = content.get("shots") or []
    if not isinstance(shots_in, list) or not shots_in:
        raise ValueError("edl_content.json shots empty")

    parsed_path = project / "timeline.parsed.json"
    if parsed is None and parsed_path.is_file():
        parsed = load_json(parsed_path)
    if parsed is not None and not isinstance(parsed, dict):
        raise ValueError("timeline.parsed.json must be an object")

    beat = float(content.get("beatSec") or (60.0 / float(content.get("bpm") or bpm)))
    bpm_v = float(content.get("bpm") or bpm)
    bar = beat * 4

    sched_shots = list((parsed or {}).get("shots") or [])
    compiled = _compile_shots(shots_in, beat=beat, schedule_shots=sched_shots)

    if parsed and parsed.get("scheduledDurationSec"):
        dur = float(parsed["scheduledDurationSec"])
    else:
        dur = max((s["t0"] + s["dur"] for s in compiled), default=0.0)
    total_beats = int(round(dur / beat)) if beat > 0 else 0

    runtime = {
        "note": "Controller runtime EDL — applied by core/render/page.mjs after READY; edl.js bytes unchanged.",
        "BPM": bpm_v,
        "BEAT": beat,
        "BAR": bar,
        "shots": compiled,
        "beats": total_beats,
        "DUR": round(dur, 6),
        "bridge": "edl_content→edl_runtime",
    }
    runtime_path = project / "edl_runtime.json"
    dump_json(runtime_path, runtime)

    # Also refresh root edl_content sidecar (times from schedule when available)
    enriched = dict(content)
    enriched["shots"] = []
    # Keep the AUTHORED beat minimum separately: `beats` below is the scheduled length, and
    # schedule.py reads this file back — without beatsAuthored every re-schedule ratcheted
    # shots up to the previous (longer) take's length (stale gaps after a shorter re-take).
    authored = {str(r.get("id")): r.get("beatsAuthored", r.get("beats")) for r in shots_in if isinstance(r, dict)}
    for s in compiled:
        row = {k: s[k] for k in s if k not in ("b0", "i")}
        if authored.get(str(s.get("id"))) is not None:
            row["beatsAuthored"] = authored[str(s.get("id"))]
        enriched["shots"].append(row)
    dump_json(project / "edl_content.json", enriched)
    dump_json(project / "content" / "edl_content.json", enriched)

    # timeline.json for mix_vo_only (and quality VO cues)
    vo: dict[str, float] = {}
    if parsed:
        for c in parsed.get("cues") or []:
            if isinstance(c, dict) and c.get("type") == "voice" and c.get("id"):
                vo[str(c["id"])] = round(float(c.get("t") or 0.0), 4)
        if not vo:
            for s in sched_shots:
                for vid in s.get("voIds") or []:
                    vo[str(vid)] = round(float(s["t0"]) + enter, 4)

    tl = {
        "note": "VO bed for mix_vo_only; pictogram picture timing lives in edl_runtime.json",
        "fps": 24,
        "dur": round(dur, 6),
        "bpm": bpm_v,
        "vo": vo,
        "scheduleBudgetSec": (parsed or {}).get("targetDurationSec"),
        "bridge": "pictogram-edl-runtime",
    }
    dump_json(project / "timeline.json", tl)

    # Align root lines.json t= to cue starts when present
    for lines_rel in ("lines.json", "content/lines.json"):
        lp = project / lines_rel
        if not lp.is_file():
            continue
        raw = load_json(lp)
        if not isinstance(raw, list):
            continue
        changed = False
        for ln in raw:
            if not isinstance(ln, dict):
                continue
            lid = ln.get("id")
            if lid and lid in vo:
                ln["t"] = vo[lid]
                changed = True
        if changed:
            dump_json(lp, raw)

    plan = None
    for plan_rel in ("content/plan.json", "plan.json"):
        pp = project / plan_rel
        if pp.is_file():
            try:
                plan = load_json(pp)
            except (OSError, ValueError):
                plan = None
            break
    brand = build_brand_strings(plan if isinstance(plan, dict) else None, compiled)
    brand["caseViolations"] = case_guard(runtime, brand)
    brand_path = project / "brand_strings.json"
    dump_json(brand_path, brand)

    return {
        "runtimePath": str(runtime_path),
        "brandPath": str(brand_path),
        "hudTicks": brand.get("hudTicks"),
        "shotCount": len(compiled),
        "dur": round(dur, 6),
        "voCount": len(vo),
        "beat": beat,
        "bpm": bpm_v,
        "caseViolations": brand["caseViolations"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Apply pictogram edl_content → edl_runtime (no edl.js edit)")
    ap.add_argument("--project", required=True)
    args = ap.parse_args(argv)
    try:
        info = apply_pictogram_edl(Path(args.project))
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print(
        f"OK edl_runtime shots={info['shotCount']} dur={info['dur']}s "
        f"vo={info['voCount']} → {info['runtimePath']}"
    )
    for v in info["caseViolations"]:
        print(f"WARN acronym case: {v} (quality acronym_case FAILs)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
