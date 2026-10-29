"""Validate a DeepSeek content plan against schema + style manifest."""
from __future__ import annotations

import re

import argparse
import sys
from typing import Any

from common import (
    HEX,
    ID_RE,
    STYLES,
    load_json,
    load_manifest,
    walk_forbidden,
)


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def validate_plan(plan: dict[str, Any], *, strict_manifest: bool = True) -> list[str]:
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["plan must be a JSON object"]

    errors.extend(walk_forbidden(plan))

    allowed_top = {
        "schemaVersion",
        "topic",
        "style",
        "language",
        "targetDurationSec",
        "palette",
        "shots",
        "voice",
        "credits",
        "content_type",
        "pacing",
    }
    for k in plan:
        if k not in allowed_top:
            _err(errors, f"$.{k}: unknown top-level key")

    topic = plan.get("topic")
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 120:
        _err(errors, "$.topic: required string 1..120")

    style = plan.get("style")
    if style not in STYLES:
        _err(errors, f"$.style: must be one of {list(STYLES)}")

    language = plan.get("language")
    if language not in ("zh", "en", "zh-en"):
        _err(errors, "$.language: must be zh|en|zh-en")

    dur = plan.get("targetDurationSec")
    if not isinstance(dur, (int, float)) or not (15 <= float(dur) <= 90):
        _err(errors, "$.targetDurationSec: number in 15..90")

    if "content_type" in plan and plan["content_type"] not in ("market", "concept", "personal", "english"):
        _err(errors, "$.content_type: market|concept|personal|english")
    if "pacing" in plan and plan["pacing"] not in ("fast", "standard", "calm"):
        _err(errors, "$.pacing: fast|standard|calm")

    if "schemaVersion" in plan and plan["schemaVersion"] != 1:
        _err(errors, "$.schemaVersion: must be 1 when present")

    # palette
    if "palette" in plan:
        pal = plan["palette"]
        if not isinstance(pal, dict):
            _err(errors, "$.palette: must be object")
        else:
            for pk, pv in pal.items():
                if pk not in ("page", "ink", "signal", "paper", "accent"):
                    _err(errors, f"$.palette.{pk}: unknown key")
                elif not isinstance(pv, str) or not HEX.match(pv):
                    _err(errors, f"$.palette.{pk}: need #RRGGBB")

    shots = plan.get("shots")
    if not isinstance(shots, list) or not shots:
        _err(errors, "$.shots: non-empty array required")
        shots = []
    elif len(shots) > 40:
        _err(errors, "$.shots: max 40")

    roles = {
        "hook",
        "setup",
        "explain",
        "evidence",
        "contrast",
        "payoff",
        "chapter",
        "card",
        "end",
        "credits",
    }
    shot_ids: set[str] = set()
    for i, sh in enumerate(shots):
        p = f"$.shots[{i}]"
        if not isinstance(sh, dict):
            _err(errors, f"{p}: must be object")
            continue
        for k in sh:
            if k not in (
                "id",
                "role",
                "text",
                "onScreenText",
                "onScreenTextEn",
                "data",
                "motionPreset",
                "pose",
                "beats",
                "allowDarkOpen",
            ):
                _err(errors, f"{p}.{k}: unknown key")
        sid = sh.get("id")
        if not isinstance(sid, str) or not ID_RE.match(sid):
            _err(errors, f"{p}.id: invalid id")
        elif sid in shot_ids:
            _err(errors, f"{p}.id: duplicate '{sid}'")
        else:
            shot_ids.add(sid)
        if sh.get("role") not in roles:
            _err(errors, f"{p}.role: invalid")
        text = sh.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 200:
            _err(errors, f"{p}.text: required string 1..200")
        ost = sh.get("onScreenText")
        if ost is not None and (not isinstance(ost, str) or len(ost) > 120):
            _err(errors, f"{p}.onScreenText: string max 120")
        ose = sh.get("onScreenTextEn")
        if ose is not None and (not isinstance(ose, str) or len(ose) > 40
                                or not re.fullmatch(r"[A-Za-z0-9 .·%&/,'+\-]*", ose)):
            _err(errors, f"{p}.onScreenTextEn: Latin title max 40")
        mp = sh.get("motionPreset")
        if not isinstance(mp, str) or not mp or len(mp) > 40:
            _err(errors, f"{p}.motionPreset: required string")
        if "data" in sh:
            data = sh["data"]
            if not isinstance(data, dict):
                _err(errors, f"{p}.data: object")
            else:
                for dk, dv in data.items():
                    if isinstance(dv, (int, float, bool)):
                        continue
                    if isinstance(dv, str) and len(dv) <= 80:
                        continue
                    if isinstance(dv, list) and len(dv) <= 32 and all(
                        isinstance(x, (int, float)) for x in dv
                    ):
                        continue
                    _err(errors, f"{p}.data.{dk}: only number|bool|short string|number[]")
        if "beats" in sh:
            b = sh["beats"]
            if not isinstance(b, (int, float)) or not (1 <= float(b) <= 64):
                _err(errors, f"{p}.beats: 1..64")

    # voice
    if "voice" in plan:
        voice = plan["voice"]
        if not isinstance(voice, dict):
            _err(errors, "$.voice: object")
        else:
            for k in voice:
                if k not in ("provider", "voiceId", "lines"):
                    _err(errors, f"$.voice.{k}: unknown key")
            prov = voice.get("provider", "none")
            if prov not in ("none", "edge", "kokoro", "qwen3", "omnivoice", "stepaudio", "elevenlabs"):
                _err(errors, "$.voice.provider: invalid")
            if "voiceId" in voice and (
                not isinstance(voice["voiceId"], str) or len(voice["voiceId"]) > 64
            ):
                _err(errors, "$.voice.voiceId: string max 64")
            lines = voice.get("lines", [])
            if lines is None:
                lines = []
            if not isinstance(lines, list) or len(lines) > 40:
                _err(errors, "$.voice.lines: array max 40")
            else:
                lids: set[str] = set()
                for j, ln in enumerate(lines):
                    lp = f"$.voice.lines[{j}]"
                    if not isinstance(ln, dict):
                        _err(errors, f"{lp}: object")
                        continue
                    for k in ln:
                        if k not in ("id", "text", "shotId", "role", "cap", "say"):
                            _err(errors, f"{lp}.{k}: unknown")
                    lid = ln.get("id")
                    if not isinstance(lid, str) or not ID_RE.match(lid):
                        _err(errors, f"{lp}.id: invalid")
                    elif lid in lids:
                        _err(errors, f"{lp}.id: duplicate")
                    else:
                        lids.add(lid)
                    lt = ln.get("text")
                    if not isinstance(lt, str) or not lt.strip() or len(lt) > 200:
                        _err(errors, f"{lp}.text: required 1..200")
                    if "role" in ln and ln["role"] not in ("hook", "turn", "evidence", "payoff", "sting"):
                        _err(errors, f"{lp}.role: hook|turn|evidence|payoff|sting")
                    if "cap" in ln and (not isinstance(ln["cap"], str) or len(ln["cap"]) > 200):
                        _err(errors, f"{lp}.cap: string max 200")
                    if "say" in ln and (not isinstance(ln["say"], str) or not ln["say"].strip() or len(ln["say"]) > 200):
                        _err(errors, f"{lp}.say: string 1..200 (TTS-only pronunciation of text)")
                    sid = ln.get("shotId")
                    if sid is not None:
                        if not isinstance(sid, str) or not ID_RE.match(sid):
                            _err(errors, f"{lp}.shotId: invalid")
                        elif shot_ids and sid not in shot_ids:
                            _err(errors, f"{lp}.shotId: unknown shot '{sid}'")

    if "credits" in plan:
        cr = plan["credits"]
        if not isinstance(cr, dict):
            _err(errors, "$.credits: object")
        else:
            for k, v in cr.items():
                if k not in ("title", "author", "year", "license"):
                    _err(errors, f"$.credits.{k}: unknown")
                elif not isinstance(v, str) or len(v) > 80:
                    _err(errors, f"$.credits.{k}: string")

    # Manifest cross-checks
    if strict_manifest and style in STYLES and not any(
        e.startswith("$.style") for e in errors
    ):
        try:
            man = load_manifest(style)
        except FileNotFoundError as e:
            _err(errors, str(e))
            return errors

        if language not in man.get("languages", []):
            _err(errors, f"$.language: not supported by {style} manifest")

        dmin = man.get("durationSec", {}).get("min", 15)
        dmax = man.get("durationSec", {}).get("max", 90)
        if isinstance(dur, (int, float)) and not (dmin <= float(dur) <= dmax):
            _err(errors, f"$.targetDurationSec: {style} allows {dmin}..{dmax}")

        tmax = man.get("text", {}).get("maxShots", 40)
        if isinstance(shots, list) and len(shots) > tmax:
            _err(errors, f"$.shots: {style} maxShots={tmax}")

        shot_max = man.get("text", {}).get("shotMaxChars", 200)
        on_max = man.get("text", {}).get("onScreenMaxChars", 120)
        presets = set(man.get("motionPresets", []))
        roles_m = set(man.get("shotRoles", []))
        poses = set(man.get("poses", []))
        voice_modes = set(man.get("voiceModes", []))

        for i, sh in enumerate(shots if isinstance(shots, list) else []):
            if not isinstance(sh, dict):
                continue
            p = f"$.shots[{i}]"
            if sh.get("role") not in roles_m:
                _err(errors, f"{p}.role: not in {style} shotRoles")
            if sh.get("motionPreset") not in presets:
                _err(
                    errors,
                    f"{p}.motionPreset: '{sh.get('motionPreset')}' not in {style} allowlist",
                )
            t = sh.get("text") or ""
            if isinstance(t, str) and len(t) > shot_max:
                _err(errors, f"{p}.text: exceeds shotMaxChars={shot_max}")
            ost = sh.get("onScreenText")
            if isinstance(ost, str) and len(ost) > on_max:
                _err(errors, f"{p}.onScreenText: exceeds onScreenMaxChars={on_max}")
            if "pose" in sh:
                if not poses:
                    _err(errors, f"{p}.pose: style has no pose allowlist")
                elif sh["pose"] not in poses:
                    _err(errors, f"{p}.pose: '{sh['pose']}' not allowed")
            elif style == "pictogram-motion" and sh.get("role") == "card":
                _err(errors, f"{p}.pose: required for pictogram card shots")

        if "voice" in plan and isinstance(plan["voice"], dict):
            prov = plan["voice"].get("provider", "none")
            if prov not in voice_modes:
                _err(errors, f"$.voice.provider: not in {style} voiceModes")
            line_max = man.get("text", {}).get("lineMaxChars", 200)
            for j, ln in enumerate(plan["voice"].get("lines") or []):
                if isinstance(ln, dict) and isinstance(ln.get("text"), str):
                    if len(ln["text"]) > line_max:
                        _err(
                            errors,
                            f"$.voice.lines[{j}].text: exceeds lineMaxChars={line_max}",
                        )

    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate DeepSeek content plan JSON")
    ap.add_argument("plan", help="path to plan JSON")
    ap.add_argument("--no-manifest", action="store_true", help="skip style manifest checks")
    args = ap.parse_args(argv)
    plan = load_json(__import__("pathlib").Path(args.plan))
    errors = validate_plan(plan, strict_manifest=not args.no_manifest)
    if errors:
        print(f"INVALID ({len(errors)} error(s)):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
