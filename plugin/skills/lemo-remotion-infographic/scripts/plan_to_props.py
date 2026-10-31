#!/usr/bin/env python3
"""Controller plan.json -> Remotion infographic props.json (stdlib only).

    python3 plan_to_props.py plan.json -o <film>/remotion/props.json
    python3 plan_to_props.py plan.json --timeline <film>/content/timeline.json -o props.json
    python3 plan_to_props.py plan.json --overlay -o overlay-props.json   # transparent, for WebM overlay
    python3 plan_to_props.py --check props.json                          # validate against props.schema.json

Mapping (plan.schema.json -> template/props.schema.json):
  aspect 16:9 / 9:16      -> width x height 1920x1080 / 1080x1920, composition Infographic / InfographicPortrait
  targetDurationSec       -> durationInFrames at 24 fps (or scheduledDurationSec from --timeline)
  shots[].onScreenText    -> scene lines: '|' starts a new line, {word} is an accent segment
  shots[].text            -> scene lines when onScreenText is empty; always kept as voText
  shots[].role            -> scene kind: chapter -> chapter, end/credits -> end, hook/setup -> title,
                             others -> caption, unless data says otherwise:
  shots[].data            -> one numeric array -> chart (series); one number -> bigNumber;
                             2-4 numbers -> compare (onScreenText pairs label|{tag} label the bars);
                             'unit' string -> unit; booleans are engine flags and are dropped (noted)
  palette page/ink/signal(or accent) -> bg/ink/accent; muted is mixed from ink and bg
  credits                 -> credits (end card line)
Per-shot timing: from --timeline (schedule.py output) when given, else the target duration is split
by reading time (the same estimate schedule.py uses) with beats as a floor.
Anything that cannot be drawn honestly is an error (exit 1), never silently guessed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FPS = 24
HERE = Path(__file__).resolve().parent
SCHEMA = HERE.parent / "template" / "props.schema.json"
LIB_FONTS_CSS = HERE.parents[3] / "core" / "fonts" / "fonts.css"
SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
LANGS = {"zh", "en", "zh-en"}
TEXT_STACK = '"Inter Tight", "Noto Sans SC", sans-serif'
TEXT_FAMILIES = ["Inter Tight", "Noto Sans SC"]
CORE_FALLBACK = ["ZCOOL KuaiLe", "Fredoka", "Lilita One", "IM Fell English"]
KIND_BY_ROLE = {"chapter": "chapter", "end": "end", "credits": "end", "hook": "title", "setup": "title"}


class MapError(Exception):
    pass


def core_families() -> list[str]:
    try:
        css = LIB_FONTS_CSS.read_text(encoding="utf-8")
    except OSError:
        return list(CORE_FALLBACK)
    return sorted(set(re.findall(r"font-family:\s*'([^']+)'", css)))


def cjk_count(s: str) -> int:
    return sum(1 for ch in s if "\u4e00" <= ch <= "\u9fff" or "\u3040" <= ch <= "\u30ff")


def read_time_sec(text: str) -> float:
    """Same estimate as tools/deepseek-controller/schedule.py read_time_sec."""
    cjk = cjk_count(text)
    other = max(0, sum(1 for ch in text if not ch.isspace()) - cjk)
    return max(0.6, cjk / 4.5 + other / 15.0 + 0.4)


def parse_lines(markup: str, sid: str) -> list[list[dict[str, Any]]]:
    lines = []
    for part in markup.split("|"):
        if not part.strip():
            continue
        if part.count("{") != part.count("}"):
            raise MapError(f"shot '{sid}': unbalanced {{}} in onScreenText {markup!r}")
        segs = []
        for m in re.finditer(r"\{([^{}]*)\}|([^{}]+)", part):
            text = (m.group(1) if m.group(1) is not None else m.group(2)).strip()
            if text:
                segs.append({"text": text, "accent": m.group(1) is not None})
        if segs:
            lines.append(segs)
    if len(lines) > 6:
        raise MapError(f"shot '{sid}': {len(lines)} lines on screen, the template draws at most 6")
    return lines


def mix(a: str, b: str, t: float) -> str:
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(pa, pb))


def map_shot(sh: dict[str, Any], notes: list[str]) -> dict[str, Any]:
    sid = sh["id"]
    role = sh["role"]
    markup = (sh.get("onScreenText") or "").strip() or sh["text"]
    lines = parse_lines(markup, sid)
    if not lines:
        raise MapError(f"shot '{sid}': nothing to put on screen (onScreenText and text are empty)")
    scene: dict[str, Any] = {"id": sid, "kind": KIND_BY_ROLE.get(role, "caption"), "role": role, "lines": lines,
                             "voText": sh["text"]}
    data = sh.get("data") or {}
    nums: list[tuple[str, float]] = []
    arrays: list[tuple[str, list[float]]] = []
    for k, v in data.items():
        if isinstance(v, bool):
            notes.append(f"shot '{sid}': data.{k} is an engine flag (boolean), not drawn")
        elif isinstance(v, (int, float)):
            nums.append((k, float(v)))
        elif isinstance(v, list):
            arrays.append((k, [float(x) for x in v]))
        elif k == "unit" and isinstance(v, str):
            if len(v) > 16:
                raise MapError(f"shot '{sid}': data.unit longer than 16 characters")
            scene["unit"] = v
        else:
            raise MapError(f"shot '{sid}': data.{k} is a string; only 'unit' may be a string (labels go in onScreenText)")
    if (nums or arrays) and scene["kind"] in ("chapter", "end"):
        raise MapError(f"shot '{sid}': a {role} shot cannot carry chart data; move the numbers to their own shot")
    if arrays:
        if len(arrays) > 1 or nums:
            keys = [k for k, _ in arrays] + [k for k, _ in nums]
            raise MapError(f"shot '{sid}': data {keys} is ambiguous; one series or 1-4 numbers per shot")
        key, series = arrays[0]
        if not 2 <= len(series) <= 12:
            raise MapError(f"shot '{sid}': data.{key} has {len(series)} values, the chart draws 2-12")
        if any(x < 0 for x in series):
            raise MapError(f"shot '{sid}': data.{key} has negative values; bars start at zero")
        scene.update(kind="chart", series=series)
    elif len(nums) == 1:
        v = nums[0][1]
        if 0 < abs(v) < 1 and "unit" not in scene:
            v, scene["unit"] = round(v * 100, 4), "%"
        scene.update(kind="bigNumber", number=v)
    elif nums:
        if len(nums) > 4:
            raise MapError(f"shot '{sid}': {len(nums)} numbers, the comparison draws 2-4 bars")
        if any(v < 0 for _, v in nums):
            raise MapError(f"shot '{sid}': negative values cannot be compared as bars")
        segs = [s["text"] for line in lines for s in line]
        n = len(nums)
        if len(segs) == 2 * n:
            items = [{"label": segs[2 * i], "tag": segs[2 * i + 1], "value": v} for i, (_, v) in enumerate(nums)]
            scene["lines"] = []
        elif len(segs) == n:
            items = [{"label": segs[i], "value": v} for i, (_, v) in enumerate(nums)]
            scene["lines"] = []
        else:
            items = [{"label": k, "value": v} for k, v in nums]
        for it in items:
            if len(it["label"]) > 40 or len(it.get("tag", "")) > 40:
                raise MapError(f"shot '{sid}': comparison label longer than 40 characters")
        scene.update(kind="compare", items=items)
    return scene


def frames_from_timeline(shots: list[dict[str, Any]], tl: dict[str, Any]) -> tuple[list[tuple[int, int]], int]:
    by_id = {s["id"]: s for s in tl.get("shots", [])}
    missing = [s["id"] for s in shots if s["id"] not in by_id]
    if missing:
        raise MapError(f"timeline has no entry for shots {missing} (re-run schedule after editing the plan)")
    out = []
    for s in shots:
        t = by_id[s["id"]]
        a, b = round(float(t["t0"]) * FPS), round(float(t["t1"]) * FPS)
        if b - a < 12:
            raise MapError(f"shot '{s['id']}': {b - a} frames in the timeline, at least 12 needed")
        out.append((a, b - a))
    total = round(float(tl.get("scheduledDurationSec") or out[-1][0] + out[-1][1] / FPS) * FPS)
    return out, max(total, out[-1][0] + out[-1][1])


def frames_from_target(shots: list[dict[str, Any]], target: float) -> tuple[list[tuple[int, int]], int]:
    total = round(target * FPS)
    weights = []
    for s in shots:
        need = read_time_sec((s.get("onScreenText") or s["text"]).replace("|", "").replace("{", "").replace("}", ""))
        need = max(need + 0.95, read_time_sec(s["text"]))
        if s.get("beats"):
            need = max(need, float(s["beats"]) * 0.25)
        weights.append(need)
    wsum = sum(weights)
    out, t, acc = [], 0, 0.0
    for i, w in enumerate(weights):
        acc += w
        end = total if i == len(weights) - 1 else round(total * acc / wsum)
        if end - t < FPS:
            raise MapError(f"{len(shots)} shots do not fit {target}s: shot '{shots[i]['id']}' would get "
                           f"{end - t} frames (< 1 s); raise targetDurationSec or drop shots")
        out.append((t, end - t))
        t = end
    return out, total


def convert(plan: dict[str, Any], *, timeline: dict[str, Any] | None = None, overlay: bool = False,
            display: str = "Inter Tight") -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    for key in ("topic", "language", "targetDurationSec", "shots"):
        if key not in plan:
            raise MapError(f"plan has no '{key}' (validate it with the controller first)")
    aspect = plan.get("aspect", "16:9")
    if aspect not in SIZES:
        raise MapError(f"aspect {aspect!r} cannot be mapped; the template renders {sorted(SIZES)}")
    if plan["language"] not in LANGS:
        raise MapError(f"language {plan['language']!r} cannot be mapped; expected {sorted(LANGS)}")
    shots = plan["shots"]
    if not isinstance(shots, list) or not shots:
        raise MapError("plan has no shots")
    if len(shots) > 40:
        raise MapError(f"{len(shots)} shots; at most 40")
    for s in shots:
        for key in ("id", "role", "text"):
            if not s.get(key):
                raise MapError(f"shot {s.get('id', '?')!r} has no '{key}'")
    families = TEXT_FAMILIES + core_families()
    if display not in families:
        raise MapError(f"display font {display!r} is not available; choose one of {families}")

    scenes = [map_shot(s, notes) for s in shots]
    if timeline is not None:
        frames, total = frames_from_timeline(shots, timeline)
    else:
        frames, total = frames_from_target(shots, float(plan["targetDurationSec"]))
    for sc, (a, d) in zip(scenes, frames):
        sc["from"], sc["durationInFrames"] = a, d

    pal = plan.get("palette") or {}
    bg = pal.get("page", "#0E0E0C")
    ink = pal.get("ink", "#F7F5EF")
    width, height = SIZES[aspect]
    props: dict[str, Any] = {
        "schemaVersion": 1,
        "fps": FPS,
        "aspect": aspect,
        "width": width,
        "height": height,
        "durationInFrames": total,
        "language": plan["language"],
        "topic": plan["topic"],
        "transparent": bool(overlay),
        "palette": {"bg": bg, "ink": ink, "accent": pal.get("signal") or pal.get("accent") or "#FFC21A",
                    "muted": mix(ink, bg, 0.72)},
        "fonts": {"text": TEXT_STACK, "display": f'"{display}", "Noto Sans SC", sans-serif'},
        "scenes": scenes,
    }
    if plan.get("credits"):
        props["credits"] = dict(plan["credits"])
    return props, notes


# --- minimal JSON Schema check (the subset props.schema.json uses; jsonschema is not a dependency) ---
def check(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$") -> list[str]:
    if "$ref" in schema:
        ref = schema["$ref"].removeprefix("#/").split("/")
        node: Any = root
        for part in ref:
            node = node[part]
        return check(value, node, root, path)
    errs: list[str] = []
    types = {"object": dict, "array": list, "string": str, "boolean": bool}
    t = schema.get("type")
    if t == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif t == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif t:
        ok = isinstance(value, types[t])
    else:
        ok = True
    if not ok:
        return [f"{path}: expected {t}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errs.append(f"{path}: must be {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{path}: {value!r} not in {schema['enum']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append(f"{path}: {value} < {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errs.append(f"{path}: {value} > {schema['maximum']}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 1 << 30):
            errs.append(f"{path}: length {len(value)} out of range")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errs.append(f"{path}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 1 << 30):
            errs.append(f"{path}: {len(value)} items out of range")
        if "items" in schema:
            for i, v in enumerate(value):
                errs += check(v, schema["items"], root, f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                errs.append(f"{path}: missing '{k}'")
        for k, v in value.items():
            if k in props:
                errs += check(v, props[k], root, f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected '{k}'")
    return errs


def validate_props(props: dict[str, Any]) -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = check(props, schema, schema)
    if not errs:
        if SIZES.get(props["aspect"]) != (props["width"], props["height"]):
            errs.append(f"$: {props['aspect']} needs {SIZES[props['aspect']]}, got {props['width']}x{props['height']}")
        end = 0
        for sc in props["scenes"]:
            if sc["from"] < end:
                errs.append(f"$.scenes {sc['id']}: starts at frame {sc['from']}, before the previous scene ends ({end})")
            end = sc["from"] + sc["durationInFrames"]
        if end > props["durationInFrames"]:
            errs.append(f"$: scenes run to frame {end}, past durationInFrames {props['durationInFrames']}")
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", nargs="?", help="controller plan.json")
    ap.add_argument("-o", "--out", help="props.json to write (default: stdout)")
    ap.add_argument("--timeline", help="timeline.json from the controller schedule step (per-shot t0/t1)")
    ap.add_argument("--overlay", action="store_true", help="transparent background, for a WebM overlay")
    ap.add_argument("--display", default="Inter Tight", help="headline font family (text pair or core/fonts)")
    ap.add_argument("--check", metavar="PROPS", help="only validate an existing props.json")
    a = ap.parse_args(argv)
    try:
        if a.check:
            errs = validate_props(json.loads(Path(a.check).read_text(encoding="utf-8")))
            for e in errs:
                print(f"ERROR: {e}", file=sys.stderr)
            if not errs:
                print(f"OK props {a.check}")
            return 1 if errs else 0
        if not a.plan:
            ap.error("need a plan.json (or --check props.json)")
        plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
        tl = json.loads(Path(a.timeline).read_text(encoding="utf-8")) if a.timeline else None
        props, notes = convert(plan, timeline=tl, overlay=a.overlay, display=a.display)
    except (MapError, OSError, ValueError, KeyError, TypeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    errs = validate_props(props)
    if errs:
        for e in errs:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1
    for n in notes:
        print(f"NOTE: {n}", file=sys.stderr)
    text = json.dumps(props, ensure_ascii=False, indent=2) + "\n"
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding="utf-8")
        comp = "InfographicPortrait" if props["aspect"] == "9:16" else "Infographic"
        print(f"OK props {a.out} {props['width']}x{props['height']} {props['durationInFrames']} frames "
              f"@ {FPS} fps, {len(props['scenes'])} scenes, composition {comp}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
