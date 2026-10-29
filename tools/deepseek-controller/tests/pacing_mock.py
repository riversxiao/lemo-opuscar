#!/usr/bin/env python3
"""Pacing P0 mock tests (local only, no network, no billing)."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

CTL = Path(__file__).resolve().parents[1]
ROOT = CTL.parents[1]
sys.path.insert(0, str(CTL))
sys.path.insert(0, str(ROOT / "core" / "tts"))

import pacing_profile as pp  # noqa: E402
import dialogue_check as dc  # noqa: E402
import schedule as sch  # noqa: E402
import pause_trim  # noqa: E402
import pacing_check  # noqa: E402
import quality  # noqa: E402

n = 0


def ok(cond, msg):
    global n
    if not cond:
        print("FAIL:", msg)
        sys.exit(1)
    n += 1
    print("ok", msg)


os.environ.pop("LEMO_PACING", None)
td = Path(tempfile.mkdtemp(prefix="pacing-mock-"))
try:
    # ---- 1 profile resolution
    def proj(plan):
        d = td / f"p{abs(hash(json.dumps(plan, sort_keys=True))) % 10**8}"
        (d / "content").mkdir(parents=True, exist_ok=True)
        (d / "content" / "plan.json").write_text(json.dumps(plan, ensure_ascii=False))
        return d
    ok(pp.resolve(proj({}))[0] == "standard", "no plan fields → standard")
    ok(pp.resolve(proj({"content_type": "market"})) == ("fast", "content_type=market"), "market → fast")
    for ct in ("concept", "personal", "english", "bogus"):
        ok(pp.resolve(proj({"content_type": ct}))[0] == "standard", f"{ct} → standard")
    ok(pp.resolve(proj({"content_type": "宏观"}))[0] == "fast", "alias 宏观 → market → fast")
    ok(pp.resolve(proj({"content_type": "market", "pacing": "calm"})) == ("calm", "plan.pacing"), "plan pacing beats content_type")
    ok(pp.resolve(proj({"pacing": "calm"}), "fast") == ("fast", "explicit"), "explicit beats plan")
    os.environ["LEMO_PACING"] = "calm"
    ok(pp.resolve(proj({"content_type": "market"}))[0] == "calm", "env beats content_type")
    os.environ.pop("LEMO_PACING")
    try:
        pp.resolve(None, "turbo")
        ok(False, "unknown explicit profile raises")
    except ValueError:
        ok(True, "unknown explicit profile raises")
    ok(pp.shot_overhead(pp.PROFILES["standard"]) < 0.95 / 2, "standard shot overhead < half of legacy 0.95s")

    # ---- 2 dialogue_check: profile rate, ceiling only, line WARN
    L = [{"id": f"L{i}", "function": f, "text": t} for i, (f, t) in enumerate([
        ("hook", "利率降到零，钱却不动。"), ("evidence", "日本把贴现率从六降到零点五。"),
        ("turn", "可借钱的人还是没变多。"), ("payoff", "这就叫流动性陷阱。")])]
    r = dc.check_lines(L, 30.0, rate=5.3)
    ok(r["status"] == "PASS" and r["duration"]["minChars"] == 0, "short script under a 30s ceiling PASSes (no lower fill)")
    ok(r["duration"]["underTarget"] is True, "underTarget flagged as info only")
    r = dc.check_lines(L * 12, 10.0, rate=5.3)
    ok(any("over ceiling" in f for f in r["fails"]), "over ceiling FAILs")
    longline = [dict(L[0], text="利率已经低到几乎为零可是家家户户还是宁愿攥着现金。")] + L[1:]
    r = dc.check_lines(longline, 30.0, rate=5.8, line_warn_chars=20, pacing="fast")
    ok(r["status"] == "PASS" and any("line max" in w for w in r["warns"]), "line > profile max is WARN, not FAIL")
    p = proj({"content_type": "market", "targetDurationSec": 30})
    (p / "content" / "lines.json").write_text(json.dumps(L, ensure_ascii=False))
    r = dc.run(p, write=False)
    ok(r["pacing"] == "fast" and r["duration"]["rate"] == 5.8, "dc.run takes rate from content_type profile")

    # ---- 3 schedule
    lines = [{"id": "a", "shotId": "s1"}, {"id": "b", "shotId": "s1", "beat": True}, {"id": "c", "shotId": "s2"}]
    shots = [{"id": "s1", "text": ""}, {"id": "s2", "text": ""}]
    durs = {"a": 2.0, "b": 2.0, "c": 2.0}
    std = pp.profile(None, "standard")
    tl, _ = sch.schedule(lines=lines, shots=shots, target_duration=30, beat_grid=0.25, durs=durs,
                         require_all_vo=True, pacing=std)
    ok(tl["padSec"] == 0 and tl["scheduledDurationSec"] < 12 and tl["durationPolicy"] == "ceiling",
       "default: no pad, duration follows content")
    ok(tl["shotOverheadSec"] == 0.4 and tl["pacing"] == "standard", "standard overhead 0.4s recorded")
    s1 = tl["shots"][0]
    ok(abs(s1["voDur"] - (2 + 0.25 + 2 + 0.6)) < 1e-6, "line gap 0.25 + beat pause 0.6 after beat line")
    tl2, _ = sch.schedule(lines=lines, shots=shots, target_duration=30, beat_grid=0.25, durs=durs,
                          require_all_vo=True, pacing=std, outro_sec=5.0)
    ok(abs(tl2["outroSec"] - 1.5) < 1e-6 and tl2["padSec"] == 0, "outro capped at 1.5s, not counted as pad")
    tl3, _ = sch.schedule(lines=lines, shots=shots, target_duration=30, beat_grid=0.25, durs=durs,
                          require_all_vo=True, pad_under_target=True)
    ok(tl3["padMode"] == "hold-last-beat" and tl3["scheduledDurationSec"] == 30, "legacy pad still available explicitly")
    old, _ = sch.schedule(lines=lines, shots=shots, target_duration=30, beat_grid=0.25, durs=durs, require_all_vo=True)
    ok(tl["cues"][-1]["t"] < old["cues"][-1]["t"], "profile timeline starts last line earlier than legacy overhead")

    # ---- 4 pause_trim
    sr = 24000
    tone = lambda s: (0.3 * np.sin(2 * np.pi * 220 * np.arange(int(s * sr)) / sr)).astype(np.float32)
    sil = lambda s: np.zeros(int(s * sr), np.float32)
    pt = td / "trim"
    (pt / "voices").mkdir(parents=True)
    (pt / "content").mkdir()
    (pt / "content" / "plan.json").write_text("{}")
    (pt / "content" / "lines.json").write_text(json.dumps([{"id": "x", "text": "甲乙"}, {"id": "y", "text": "丙丁", "beat": True}]))
    for lid in ("x", "y"):
        sf.write(pt / "voices" / f"{lid}.wav", np.concatenate([sil(0.4), tone(1.0), sil(0.8), tone(1.0), sil(0.5)]), sr)
    (pt / "voices" / "dur.json").write_text(json.dumps({"x": 3.7, "y": 3.7}))
    (pt / "voices" / "words.json").write_text(json.dumps({"x": [["甲", 0.4, 1.4], ["乙", 2.2, 3.2]]}, ensure_ascii=False))
    rep = pause_trim.trim_project(pt)
    d = json.loads((pt / "voices" / "dur.json").read_text())
    ok(abs(d["x"] - (0.03 + 1.0 + 0.18 + 1.0 + 0.06)) < 0.05, f"intra pause 0.8→0.18, lead/tail trimmed (x={d['x']})")
    ok(abs(d["y"] - (0.03 + 1.0 + 0.8 + 1.0 + 0.06)) < 0.05, f"beat line keeps its pause (y={d['y']})")
    w = json.loads((pt / "voices" / "words.json").read_text())["x"]
    ok(abs(w[1][1] - (0.03 + 1.0 + 0.18)) < 0.05 and w[0][1] < 0.06, f"words.json remapped ({w})")
    ok((pt / "voices" / "_pretrim" / "x.wav").is_file() and (pt / "voices" / "pause_trim.json").is_file(), "backup + report")
    ok(rep["lines"]["x"]["cuts"][1]["between"] == "甲|乙", "cut labelled with surrounding words")
    rep2 = pause_trim.trim_project(pt)
    ok(rep2["removedSec"] < 0.02, "idempotent second pass")

    # ---- 5 run_tts: profile rate/speed → router; trims
    import run_tts
    seen = {}

    def fake(lines_, out_dir, **kw):
        seen.update(kw)
        for L_ in lines_:
            sf.write(Path(out_dir) / f"{L_['id']}.wav", np.concatenate([sil(0.5), tone(1.0), sil(0.9), tone(0.5)]), sr)
        dd = {L_["id"]: 2.9 for L_ in lines_}
        (Path(out_dir) / "dur.json").write_text(json.dumps(dd))
        return "edge", dd
    run_tts.router_synthesize = fake
    rt = proj({"content_type": "market"})
    (rt / "content" / "lines.json").write_text(json.dumps([{"id": "L1", "text": "hello"}]))
    (rt / "voices").mkdir()
    (rt / "voices" / "words.json").write_text("{}")
    os.environ.pop("LEMO_TTS_STEPAUDIO_SPEED", None)
    meta = run_tts.run_tts(rt, post_words=False)
    ok(seen["rate"] == "+20%" and abs(seen["speed"]["stepaudio"] - 1.18) < 1e-9
       and abs(seen["speed"]["elevenlabs"] - pp.PROFILES["fast"]["elevenlabsSpeed"]) < 1e-9,
       "market → fast: edge +20%, stepaudio 1.18, elevenlabs profile speed")
    ok(meta["pacing"] == "fast" and meta["pauseTrim"]["removedSec"] > 0.9, "run_tts trims pauses after synth")
    ok(not (rt / "voices" / "words.json").exists(), "stale words.json removed on new take")
    run_tts.run_tts(rt, post_words=False, rate="-5%", speed=0.9)
    ok(seen["rate"] == "-5%" and seen["speed"] == {"stepaudio": 0.9, "elevenlabs": 0.9}, "explicit rate/speed win")

    # ---- 6 router speed plumbing + StepAudio prompt
    import tts_router
    got = {}
    tts_router.PROBES = {k: (lambda: type("S", (), {"state": "ready", "detail": ""})()) for k in tts_router.SYNTH}
    for prov in ("stepaudio", "edge"):
        tts_router.SYNTH[prov] = lambda lines_, out, _p=prov, **o: (got.__setitem__(_p, o), {L_["id"]: 1.0 for L_ in lines_})[1]
        tts_router._run_one(prov, [{"id": "a", "text": "x"}], str(td), None, "+10%", "+0Hz", None, 1.1)
    ok(got["stepaudio"].get("speed") == 1.1 and "speed" not in got["edge"], "speed only to stepaudio; edge gets rate")
    from providers import stepaudio
    allp = stepaudio.DEFAULT_ROLE + stepaudio.SESSION_INSTRUCTION + stepaudio.DEFAULT_TONE + stepaudio.DEFAULT_INSTRUCTION
    ok(not any(x in allp for x in ("语速中等", "停顿约半秒", "音高平稳", "不夸张")), "old flat StepAudio phrasing removed")
    ok("同一个音色" in stepaudio.DEFAULT_ROLE and "语速偏快" in stepaudio.DEFAULT_ROLE, "brisk + single consistent voice")

    # ---- 7 quality: pad FAIL; pacing gate report-only
    q = td / "q"
    (q / "content").mkdir(parents=True)
    (q / "content" / "plan.json").write_text(json.dumps({"targetDurationSec": 30}))
    base = {"ok": True, "fitsTarget": True, "scheduledDurationSec": 30, "targetDurationSec": 30,
            "contentDurationSec": 26, "padSec": 4.0, "padMode": "hold-last-beat", "shots": [], "cues": []}
    (q / "timeline.parsed.json").write_text(json.dumps(base))
    c = quality._schedule_check(q, {}, require_vo=False)
    ok(c["status"] == "FAIL" and "outro allowance" in c["detail"], "padding 4s → schedule FAIL")
    (q / "timeline.parsed.json").write_text(json.dumps(dict(base, padSec=1.0, scheduledDurationSec=27)))
    ok(quality._schedule_check(q, {}, require_vo=False)["status"] == "PASS", "padding ≤1.5s outro → PASS")

    fake_rep = {"status": "FAIL", "pacing": "standard", "fails": [{"level": "FAIL", "metric": "padSec", "value": 4,
                "warn": 1, "fail": 2, "dir": "max"}], "warns": [], "items": []}
    pacing_check.run = lambda *a, **k: fake_rep
    c = quality.run_pacing_gate(q, None)
    ok(c["status"] == "WARN" and not c["required"] and "report-only" in c["detail"], "P0 pacing gate is report-only WARN")
    c = quality.run_pacing_gate(q, None, enforce=True)
    ok(c["status"] == "FAIL" and c["required"], "enforce → FAIL required")

    # ---- 8 pacing_check.evaluate
    m = {"articulationCps": 5.4, "overallCps": 4.6, "speechRatio": 0.9, "interLineGapMax": 0.5, "intraPauseMax": 0.3,
         "tailSilenceSec": 1.0, "padSec": 0, "shotMaxSec": 4.0, "frozenMaxSec": 1.0, "changesPer10s": 3,
         "firstVoSec": 0.2, "hookEndSec": 2.5}
    ok(pacing_check.evaluate(m, "standard")["status"] == "PASS", "good metrics PASS")
    ok(pacing_check.evaluate(dict(m, speechRatio=0.8), "standard")["status"] == "WARN", "minor miss → WARN only")
    e = pacing_check.evaluate(dict(m, shotMaxSec=14.5), "standard")
    ok(e["status"] == "FAIL" and e["fails"][0]["metric"] == "shotMaxSec", "major miss → FAIL")
    ok(pacing_check.evaluate(dict(m, articulationCps=5.4), "fast")["status"] == "WARN", "fast profile is stricter")
finally:
    shutil.rmtree(td, ignore_errors=True)
print(f"pacing_mock: {n} checks OK")
