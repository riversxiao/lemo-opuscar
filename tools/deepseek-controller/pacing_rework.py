#!/usr/bin/env python3
"""Pacing gate FAIL → visual rework, max 2 rounds (pacing P1).

  python3 pacing_rework.py --project P --media P/film.mp4 [--mix P/out/mix.wav] [--pacing standard]
                           [--max-rounds 2] [--dry-run]

Only FAIL items that a re-render can fix are touched; WARN is report-only, never reworked
(no over-correction). Audio/dialogue FAILs (cps, gaps, pauses, pad, hook) are listed as
`needsUpstream` (dialogue-loop / TTS / schedule) and left alone.

  shotMaxSec FAIL      → (re)build beats_runtime.json sub-beats at profile maxShotSec
                         (2nd round: 0.85× tighter)
  frozenMaxSec FAIL    → add slow pull-out `drift` windows over each frozen span longer than the
                         FAIL threshold (only those spans)
  changesPer10s FAIL   → rebuild sub-beats 0.8× tighter (more reframes)

Each round: beats → video.mjs → mux.sh (existing mix, limiter on) → pacing_check. Stops as soon
as no visual FAIL remains. Writes evidence/pacing-rework.json.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import beats as beats_mod
import pacing_check
import pacing_profile as pp

VISUAL = {"shotMaxSec", "frozenMaxSec", "changesPer10s"}
ROOT = Path(__file__).resolve().parents[2]


def plan_round(rep: dict[str, Any], rnd: int, base_max: float, cur_max: float,
               frozen_fail: float) -> dict[str, Any]:
    """Pure: which fixes a FAIL report asks for this round."""
    fails = {i["metric"]: i for i in rep.get("fails") or []}
    acts: dict[str, Any] = {"maxShot": None, "drift": [], "fixes": [],
                            "needsUpstream": sorted(k for k in fails if k not in VISUAL),
                            "warnsIgnored": sorted(i["metric"] for i in rep.get("warns") or [])}
    m = rep.get("metrics") or {}
    if "shotMaxSec" in fails:
        acts["maxShot"] = base_max if (m.get("shotSource") != "beats_runtime") else round(cur_max * 0.85, 3)
        acts["fixes"].append("shotMaxSec→sub-beats")
    if "changesPer10s" in fails:
        mx = round(min(cur_max, acts["maxShot"] or cur_max) * 0.8, 3)
        acts["maxShot"] = mx
        acts["fixes"].append("changesPer10s→tighter sub-beats")
    if "frozenMaxSec" in fails:
        for a, b in m.get("frozenSpans") or []:
            if b - a > frozen_fail:
                acts["drift"].append({"t0": round(a, 2), "t1": round(b, 2), "amount": -0.015, "dx": 6.0,
                                      "round": rnd})
        acts["fixes"].append(f"frozenMaxSec→drift×{len(acts['drift'])}")
    return acts


def _render(project: Path, media: Path, mix: Path) -> None:
    vid = project / "out" / "video.mp4"
    vid.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["node", str(ROOT / "core/render/video.mjs"), str(project), "--fps", "30", "--workers", "4",
                    "--out", str(vid)], check=True)
    subprocess.run(["bash", str(ROOT / "core/render/mux.sh"), str(vid), str(mix), str(media), "30", "1"], check=True)


def run(project: Path, media: Path, *, mix: Path | None = None, pacing: str | None = None,
        max_rounds: int = 2, dry_run: bool = False,
        render: Callable[[Path, Path, Path], None] | None = None,
        measure: Callable[..., dict[str, Any]] | None = None) -> dict[str, Any]:
    project = project.resolve()
    prof = pp.profile(project, pacing)
    th = pp.gate_thresholds(prof["name"])
    frozen_fail = float(th["frozen_max_max"][1])
    base_max = float(prof["maxShotSec"])
    mix = mix or project / "out" / "mix.wav"
    render = render or _render
    measure = measure or (lambda: pacing_check.run(project, media, pacing=prof["name"]))
    rep = measure()
    rounds: list[dict[str, Any]] = []
    cur_max = base_max
    drift: list[dict[str, Any]] = []
    old = beats_mod._load(project / "beats_runtime.json", {}) or {}
    drift = list(old.get("drift") or [])
    if old.get("maxShotSec"):
        cur_max = float(old["maxShotSec"])
    for rnd in range(1, max_rounds + 1):
        vfails = [i["metric"] for i in rep.get("fails") or [] if i["metric"] in VISUAL]
        if not vfails:
            break
        acts = plan_round(rep, rnd, base_max, cur_max, frozen_fail)
        cur_max = acts["maxShot"] or cur_max
        drift += acts["drift"]
        entry = {"round": rnd, "before": rep["status"], "visualFails": vfails, **acts}
        if dry_run:
            entry["dryRun"] = True
            rounds.append(entry)
            break
        rt = beats_mod.build(project, prof["name"], drift=drift, max_shot=cur_max)
        beats_mod.write(project, rt)
        render(project, media, mix)
        rep = measure()
        entry["after"] = rep["status"]
        entry["afterFails"] = [i["metric"] for i in rep.get("fails") or []]
        rounds.append(entry)
    left = [i["metric"] for i in rep.get("fails") or [] if i["metric"] in VISUAL]
    out = {"schemaVersion": 1, "project": str(project), "media": str(media), "pacing": prof["name"],
           "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "maxRounds": max_rounds, "rounds": rounds, "finalStatus": rep["status"],
           "visualFailsLeft": left,
           "needsUpstream": sorted({i["metric"] for i in rep.get("fails") or []} - VISUAL),
           "warnsReportOnly": sorted(i["metric"] for i in rep.get("warns") or [])}
    d = project / "evidence"
    d.mkdir(parents=True, exist_ok=True)
    (d / "pacing-rework.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--media", required=True)
    ap.add_argument("--mix")
    ap.add_argument("--pacing")
    ap.add_argument("--max-rounds", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    out = run(Path(a.project), Path(a.media), mix=Path(a.mix) if a.mix else None, pacing=a.pacing,
              max_rounds=max(0, min(2, a.max_rounds)), dry_run=a.dry_run)
    for r in out["rounds"]:
        print(f"round {r['round']}: {r['before']} visual FAIL {r['visualFails']} → {r['fixes']}"
              + (f" → {r.get('after')}" if 'after' in r else " (dry-run)"))
    print(f"pacing-rework: final={out['finalStatus']} visualFailsLeft={out['visualFailsLeft']} "
          f"needsUpstream={out['needsUpstream']} warns(report-only)={out['warnsReportOnly']}")
    return 1 if out["visualFailsLeft"] else 0


if __name__ == "__main__":
    sys.exit(main())
