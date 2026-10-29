#!/usr/bin/env python3
"""Narration .srt for VO-driven films (pictogram-motion's demo srt.cjs exports the demo's
title cards, not narration): cue start = timeline.json vo[id], length = voices/dur.json.
Lines longer than --max chars split at sentence/clause punctuation, time shared by chars.

python3 tools/deepseek-controller/vo_srt.py --project P [--out P/<name>.srt] [--cues-out P/out/cues.json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPLIT = re.compile(r"(?<=[。！？；!?;])|(?<=[，,：:])")


def _chunks(text: str, mx: int) -> list[str]:
    text = text.strip()
    if len(text) <= mx:
        return [text]
    parts = [p for p in re.split(r"(?<=[。！？；!?;])", text) if p.strip()]
    out: list[str] = []
    for p in parts:
        if len(p) <= mx:
            out.append(p)
            continue
        cur = ""
        for q in [x for x in re.split(r"(?<=[，,：:])", p) if x]:
            if cur and len(cur) + len(q) > mx:
                out.append(cur)
                cur = q
            else:
                cur += q
        if cur:
            out.append(cur)
    return [o.strip() for o in out if o.strip()]


def build_cues(project: Path, mx: int = 18) -> list[dict]:
    tl = json.loads((project / "timeline.json").read_text("utf-8"))
    dur = json.loads((project / "voices" / "dur.json").read_text("utf-8"))
    raw = json.loads((project / "lines.json").read_text("utf-8"))
    lines = raw["lines"] if isinstance(raw, dict) else raw
    cues = []
    for L in lines:
        lid = L["id"]
        if lid not in tl.get("vo", {}) or lid not in dur:
            continue
        t0, d = float(tl["vo"][lid]), float(dur[lid])
        text = re.sub(r"[{}]", "", str(L.get("cap") or L.get("text") or ""))
        chunks = _chunks(text, mx)
        total = sum(len(c) for c in chunks) or 1
        t = t0
        for c in chunks:
            seg = d * len(c) / total
            cues.append({"t0": round(t, 3), "t1": round(t + seg, 3), "text": c.rstrip("。，,；;："), "lineId": lid})
            t += seg
    return cues


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--out")
    ap.add_argument("--cues-out")
    ap.add_argument("--max", type=int, default=18, help="max chars per cue (default 18)")
    a = ap.parse_args()
    p = Path(a.project).resolve()
    cues = build_cues(p, a.max)
    cj = Path(a.cues_out) if a.cues_out else p / "out" / "cues.json"
    cj.parent.mkdir(parents=True, exist_ok=True)
    cj.write_text(json.dumps(cues, ensure_ascii=False, indent=1), "utf-8")
    out = Path(a.out) if a.out else p / f"{p.name}.srt"
    return subprocess.run([sys.executable, str(ROOT / "core/render/srt.py"), str(cj), str(out)]).returncode


if __name__ == "__main__":
    sys.exit(main())
