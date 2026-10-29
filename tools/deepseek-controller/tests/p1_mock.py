#!/usr/bin/env python3
"""Pacing P1 mock tests (local only, no network, no billing):
TP limiter, end-card outro, sub-beats + keyword emphasis, pacing rework (≤2 rounds, WARN untouched),
rhythm checks + critic dimension, per-step token log, ElevenLabs speed."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CTL = Path(__file__).resolve().parents[1]
ROOT = CTL.parents[1]
os.environ.setdefault("DC_QUOTA_LEDGER", "/tmp/dc-test-quota-ledger.jsonl")
sys.path.insert(0, str(CTL))
sys.path.insert(0, str(ROOT / "core" / "tts"))

import pacing_profile as pp  # noqa: E402
import beats  # noqa: E402
import pacing_rework as prw  # noqa: E402
import rhythm_check as rc  # noqa: E402
import dialogue_loop as dl  # noqa: E402
import llm_free as L  # noqa: E402

n = 0


def ok(cond, msg):
    global n
    if not cond:
        print("FAIL:", msg)
        sys.exit(1)
    n += 1
    print("ok", msg)


td = Path(tempfile.mkdtemp(prefix="p1-mock-"))
try:
    # ---------------- end-card outro default (readcheck no-pad end card)
    std = pp.PROFILES["standard"]
    ok(pp.default_outro({"shots": [{"role": "hook"}, {"role": "end"}]}, std) == std["endCardSec"] == 1.0,
       "end-role last shot → endCardSec outro (standard 1.0s)")
    ok(pp.default_outro({"shots": [{"role": "hook"}, {"role": "payoff"}]}, std) == 0.0, "no end card → 0 outro")
    ok(pp.default_outro({"outroSec": 9, "shots": []}, std) == pp.OUTRO_MAX_SEC, "plan outroSec capped at 1.5s")
    src = (ROOT / "core/render/readcheck.mjs").read_text(encoding="utf-8")
    ok("--end-pad" in src and "END_PAD" in src, "readcheck has --end-pad for end-card texts")

    # ---------------- true-peak limiter (mux.sh) on a deliberately hot mix
    if shutil.which("ffmpeg"):
        v, a, o = td / "v.mp4", td / "hot.wav", td / "o.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=160x90:d=4:r=30",
                        "-pix_fmt", "yuv420p", str(v)], check=True)
        # quiet bed + sharp 9 kHz clicks: loudnorm gain-up would push TP well above −1 without the limiter
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "aevalsrc='0.03*sin(2*PI*220*t)+0.95*lt(mod(t,0.25),0.0004)*sin(2*PI*9000*t)':s=48000:d=4",
                        "-ac", "2", str(a)], check=True)
        def mux_tp(out, **env):
            p = subprocess.run(["sh", str(ROOT / "core/render/mux.sh"), str(v), str(a), str(out), "30", "0"],
                               capture_output=True, text=True, env={**os.environ, **env})
            if p.returncode or not out.is_file():
                return None
            e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out), "-af", "ebur128=peak=true",
                                "-f", "null", "-"], capture_output=True, text=True).stderr
            return float(re.findall(r"Peak:\s+(-?[\d.]+)", e)[-1])
        tp = mux_tp(o)
        ok(tp is not None and tp <= -1.0, f"true peak after limiter {tp} dBTP ≤ −1.0")
        tp_off = mux_tp(td / "off.mp4", LEMO_TP_LIMIT="0")
        print(f"   (limiter off: TP {tp_off} dBTP)")

    # ---------------- sub-beats
    ok(beats.split_shot(0, 4.0, [], 4.5) == [], "shot ≤ max → no split (no over-correction)")
    b = beats.split_shot(0, 11.5, [3.1, 6.0, 7.2, 8.9], 4.5)
    edges = [0] + b + [11.5]
    ok(len(b) == 2 and max(y - x for x, y in zip(edges, edges[1:])) <= 4.5, f"11.5s shot → 3 sub-beats ≤4.5s {b}")
    ok(b == [3.1, 7.2], f"boundaries snap to feasible line starts {b}")
    b2 = beats.split_shot(0, 12.0, [], 3.0)
    e2 = [0] + b2 + [12.0]
    ok(max(y - x for x, y in zip(e2, e2[1:])) <= 3.0 + 1e-6, "no cue starts → even split still ≤ max")

    # synthetic project (style-agnostic: only timeline + lines + voices)
    P = td / "proj"
    (P / "content").mkdir(parents=True)
    (P / "voices").mkdir()
    lines = [{"id": "L01", "text": "利率归零了", "cap": "利率|{归零}", "function": "hook"},
             {"id": "L02", "text": "钱却还是不动", "cap": "钱|{不动}"},
             {"id": "L03", "text": "这就叫流动性陷阱", "cap": "有个名字|{流动性陷阱}"}]
    (P / "content/lines.json").write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
    (P / "content/plan.json").write_text(json.dumps({"pacing": "standard"}), encoding="utf-8")
    (P / "voices/dur.json").write_text(json.dumps({"L01": 1.6, "L02": 1.8, "L03": 2.4}), encoding="utf-8")
    (P / "voices/words.json").write_text(json.dumps({"L03": [["这", 0, .2], ["就", .2, .4], ["叫", .4, .6],
        ["流", .6, .8], ["动", .8, 1.0], ["性", 1.0, 1.2], ["陷", 1.2, 1.4], ["阱", 1.4, 1.6]]}), encoding="utf-8")
    tl = {"scheduledDurationSec": 10.0,
          "cues": [{"type": "voice", "id": "L01", "t": 0.15}, {"type": "voice", "id": "L02", "t": 3.0},
                   {"type": "voice", "id": "L03", "t": 6.4}],
          "shots": [{"id": "s1", "t0": 0, "t1": 10.0, "dur": 10.0}]}
    (P / "timeline.parsed.json").write_text(json.dumps(tl), encoding="utf-8")
    rt = beats.build(P, "standard")
    bb = rt["beats"]
    ok(len(bb) == 3 and bb[0]["scale"] == 1.0 and all(x["scale"] < 1 for x in bb[1:]),
       "10s shot → 3 beats; sub-beat 0 identity, later pull-back framings (<1)")
    ok(rt["stats"]["beatMaxSec"] <= 4.5, "beat max ≤ standard maxShotSec")
    kw = {e["keyword"]: e for e in rt["emphasis"]}
    ok("流动性陷阱" in kw and kw["流动性陷阱"]["timing"] == "words" and abs(kw["流动性陷阱"]["t"] - 7.0) < 0.05,
       f"keyword frame at spoken time from words.json ({kw.get('流动性陷阱')})")
    ts = [e["t"] for e in rt["emphasis"]]
    ok(all(y - x >= beats.EMPH["minGap"] for x, y in zip(ts, ts[1:])), "emphasis frames ≥ minGap apart")
    edges_ = [x["t0"] for x in bb]
    ok(all(min(abs(t - e) for e in edges_) >= beats.EMPH["avoidBeat"] for t in ts), "emphasis never on a reframe")
    page = (ROOT / "core/render/page.mjs").read_text(encoding="utf-8")
    ok("beats_runtime.json" in page and "window.TEXTS = t =>" in page and "title-safe" in page,
       "page.mjs bridge: generic render/TEXTS wrap with title-safe clamp")

    # ---------------- pacing rework: ≤2 rounds, WARN untouched, upstream not touched
    def mk(fails, warns=(), extra=None):
        items = [{"metric": m, "level": "FAIL"} for m in fails] + [{"metric": m, "level": "WARN"} for m in warns]
        return {"status": "FAIL" if fails else ("WARN" if warns else "PASS"), "items": items,
                "fails": [i for i in items if i["level"] == "FAIL"],
                "warns": [i for i in items if i["level"] == "WARN"], "metrics": extra or {}}

    act = prw.plan_round(mk(["shotMaxSec", "frozenMaxSec", "speechRatio"], ["interLineGapMax"],
                            {"frozenSpans": [[1.0, 6.0], [8.0, 9.5]], "shotSource": "timeline"}),
                         1, 4.5, 4.5, 4.0)
    ok(act["maxShot"] == 4.5 and len(act["drift"]) == 1 and act["drift"][0]["t0"] == 1.0,
       "FAIL shotMax→sub-beats; drift only on frozen span > FAIL threshold")
    ok(act["needsUpstream"] == ["speechRatio"] and act["warnsIgnored"] == ["interLineGapMax"],
       "audio FAIL → needsUpstream; WARN ignored")
    seq = [mk(["shotMaxSec"], extra={"shotSource": "timeline"}), mk(["shotMaxSec"], extra={"shotSource": "beats_runtime"}),
           mk(["shotMaxSec"], extra={"shotSource": "beats_runtime"}), mk([])]
    renders: list[int] = []
    out = prw.run(P, td / "x.mp4", pacing="standard", render=lambda *a: renders.append(1),
                  measure=lambda: seq.pop(0))
    ok(len(out["rounds"]) == 2 and len(renders) == 2, "rework stops at max 2 rounds")
    ok(out["rounds"][1]["maxShot"] == round(4.5 * 0.85, 3), "round 2 tightens 0.85×")
    seq2 = [mk([], ["frozenMaxSec", "changesPer10s"])]
    renders.clear()
    out2 = prw.run(P, td / "x.mp4", pacing="standard", render=lambda *a: renders.append(1),
                   measure=lambda: seq2.pop(0))
    ok(not out2["rounds"] and not renders and out2["warnsReportOnly"] == ["changesPer10s", "frozenMaxSec"],
       "WARN only → zero rounds, zero renders (no over-correction)")

    # ---------------- rhythm
    r = rc.check([{"id": "L01", "text": "这是一个特别特别长的开场钩子句子啊", "function": "hook", "cap": "开场|钩子"},
                  {"id": "L02", "text": "短句"}], cps=5.3)
    rules = {(x["id"], x["rule"], x["severity"]) for x in r["issues"]}
    ok(("L01", "hook", "medium") in rules, "hook > 12字 → medium")
    ok(("L01", "keyword", "medium") in rules, "cap without {关键词} → medium")
    ok(r["status"] == "FAIL" and "L01" in rc.flagged(r, ["L01", "L02"]), "rhythm medium → flaggable for reviser")
    long = [{"id": f"L{i}", "text": "这一句话写得很长很长足足有十六个字吧"} for i in range(4)]
    r2 = rc.check([{"id": "L00", "text": "钱不动", "function": "hook"}] + long)
    ok(any(x["rule"] == "alternation" for x in r2["issues"]) and r2["counts"]["medium"] == 0,
       "≥3 long lines in a row → low alternation (advisory)")
    r3 = rc.check([{"id": "L01", "text": "央行降息，银行惜贷，企业不借，居民存钱"}])
    ok(any(x["rule"] == "one_point" for x in r3["issues"]), "4 clauses in one line → one_point low")
    ok(rc.check([{"id": "L01", "text": "钱却不动", "function": "hook", "cap": "钱|{不动}"}])["status"] == "PASS",
       "short hook with {keyword} → PASS")
    ok("rhythm" in dl.SCRIPT_DIMS and "rhythm" in dl.LINE_DIMS and "rhythm" in dl.CRITIC_SYS, "critic has rhythm dimension")
    ev = dl.evaluate_critique({"lines": [{"id": "L01", "scores": {}}], "script": {"scores": {
        d: 5 for d in dl.SCRIPT_DIMS if d != "rhythm"}}}, ["L01"])
    ok(ev["pass"], "critic reply without rhythm tolerated (back-compat)")
    ev = dl.evaluate_critique({"lines": [{"id": "L01", "scores": {}}], "script": {"scores": {
        **{d: 5 for d in dl.SCRIPT_DIMS}, "rhythm": 3}}}, ["L01"])
    ok(not ev["pass"] and any("rhythm" in x for x in ev["reasons"]), "script.rhythm < 4 → FAIL")

    # ---------------- per-step token log
    saved = {k: os.environ.get(k) for k in ("TOKENHARBOR_API_KEY", "OPENROUTER_API_KEY", "DC_LLM_CHAIN")}
    os.environ["TOKENHARBOR_API_KEY"] = "test-th"
    os.environ["OPENROUTER_API_KEY"] = "test-or"
    os.environ.pop("DC_LLM_CHAIN", None)
    seen: list[str] = []

    def tr(url, headers, body):
        seen.append(body["model"])
        if len(seen) == 1:   # first: reasoning-only empty content → still logged, ok False
            return {"model": body["model"], "choices": [{"message": {"content": None}}],
                    "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150,
                              "completion_tokens_details": {"reasoning_tokens": 50}}}
        return {"model": body["model"], "choices": [{"message": {"content": '{"a":1}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20}}
    c = L.FreeFirstClient(transport=tr, sleep_fn=lambda s: None)
    c.chat_json("s", "u", retries=0, step="critic r1")
    dl._step(c, "reviser r1")
    c.chat_json("s", "u")
    log = c.call_log
    ok(len(log) == 3 and log[0]["ok"] is False and log[0]["reasoning"] == 50 and log[0]["step"] == "critic r1",
       "failed-parse call still logged with tokens + step")
    ok(log[1]["step"] == "critic r1" and log[1]["ok"] and log[2]["step"] == "reviser r1" and log[2]["total"] == 120,
       "step labels + total tokens per call")
    ok(all(not x["paid"] for x in log) and "test-th" not in json.dumps(log), "free only; no key in call_log")
    for k, val in saved.items():
        if val is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = val

    # ---------------- ElevenLabs speed
    from providers import elevenlabs as EL  # noqa: E402
    import tts_router  # noqa: E402
    ok(EL.voice_settings("eleven_multilingual_v2", 1.08)["speed"] == 1.08, "elevenlabs voice_settings.speed passed")
    ok(EL.voice_settings("eleven_multilingual_v2", 1.5)["speed"] == 1.2 and
       EL.voice_settings("eleven_multilingual_v2", 0.5)["speed"] == 0.7, "speed clamped to docs range 0.7–1.2")
    ok("speed" not in EL.voice_settings("eleven_v4", 1.1), "eleven_v4 → speed omitted (unsupported)")
    ok("speed" not in EL.voice_settings("eleven_multilingual_v2", 1.0), "speed 1.0 → field omitted")
    ok("elevenlabs" in tts_router.SPEED_PROVIDERS, "tts_router passes speed to elevenlabs")
    ok(pp.PROFILES["fast"]["elevenlabsSpeed"] <= 1.2, "profile elevenlabsSpeed within API range")
finally:
    shutil.rmtree(td, ignore_errors=True)


# ---------------- token_measure: per-step aggregation (fake client, no network)
import token_measure as tm  # noqa: E402


class _FakeTM:
    def __init__(self):
        self.step, self.call_log, self.model = None, [], "fake"
        self.usage = {"calls": 0, "prompt": 0, "completion": 0, "reasoning": 0, "cacheHit": 0}

    def balance(self):
        return None

    def chat_json(self, system, user, step=None):
        if step is not None:
            self.step = step
        self.call_log.append({"step": self.step, "provider": "tokenharbor", "model": "m", "servedModel": "m",
                              "paid": False, "prompt": 10, "completion": 5, "reasoning": 1, "total": 15, "ok": True})
        if self.step == "script-gen":
            return {"lines": [{"id": "L01", "speaker": "VO", "function": "hook", "text": "{VaR}能亏多少？", "shotId": "s1"},
                              {"id": "L02", "speaker": "VO", "function": "payoff", "text": "它只说门槛，不说{尾部}。", "shotId": "s2"}]}
        if self.step == "fact-check":
            return {"lines": [{"id": "L01", "verdict": "ok"}, {"id": "L02", "verdict": "risk"}]}
        if system.startswith("[REVISER]"):
            return {"lines": []}
        sc = {"factual": 5, "natural": 5, "asr_safe": 5, "function_fit": 5, "rhythm": 5}
        return {"lines": [{"id": i, "scores": sc, "issues": []} for i in ("L01", "L02")],
                "script": {"scores": {"factual": 5, "consistency": 5, "hook": 5, "flow": 5, "no_jinju": 5,
                                      "natural": 5, "rhythm": 5}, "issues": []}, "summary": "fake"}


tmp_tm = Path(tempfile.mkdtemp(prefix="p1-tm-"))
pass
(tmp_tm / "BRIEF.md").write_text("VaR brief", encoding="utf-8")
o = tm.measure(tmp_tm, tmp_tm / "BRIEF.md", 10.0, 2, 2, False, client=_FakeTM())
ok(o["status"] == "OK" and set(o["steps"]) >= {"script-gen", "fact-check", "critic r1"}, f"token_measure steps {list(o['steps'])}")
ok(o["total"]["total"] == 15 * o["total"]["calls"] and o["paidCalls"] == 0 and o["factCheck"]["risk"] == 1,
   "token_measure totals + fact-check verdicts + no paid")
ok((tmp_tm / "TOKENS.md").is_file() and (tmp_tm / "evidence" / "token-usage.json").is_file(), "TOKENS.md + token-usage.json")

shutil.rmtree(tmp_tm, ignore_errors=True)
print(f"p1 mock: {n} checks passed")
