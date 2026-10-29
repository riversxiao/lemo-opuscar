#!/usr/bin/env python3
"""Finance token-saving mocks (no network, temp ledgers):
dialogue_loop default 2 rounds → NEEDS_HUMAN with no further calls; compact critic/reviser context
(reviser sees/returns only flagged lines); quota-aware routing TokenHarbor → OpenRouter :free at ≥80 %."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

CTL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CTL))
td = Path(tempfile.mkdtemp(prefix="fin-mock-"))
os.environ["DC_BUDGET_LEDGER"] = str(td / "ledger.jsonl")
os.environ["DC_QUOTA_LEDGER"] = str(td / "quota.jsonl")
import dialogue_loop as D  # noqa: E402
import llm_free as L  # noqa: E402

n = 0


def ok(c, m):
    global n
    if not c:
        print("FAIL:", m)
        sys.exit(1)
    n += 1
    print("ok", m)


FIX = CTL / "fixtures" / "dialogue" / "pass" / "content"
SC = {"factual": 5, "natural": 5, "asr_safe": 5, "function_fit": 5, "rhythm": 5}
SS = {"factual": 5, "consistency": 5, "hook": 5, "flow": 5, "no_jinju": 5, "natural": 5, "rhythm": 5}


class Rec:
    """Recording client: critic always flags L06 (never passes); reviser rewrites L06 + tries L01."""
    def __init__(self):
        self.calls, self.step, self.call_log, self.model = [], None, [], "rec"
        self.usage = {"calls": 0}
        self.k = 0

    def balance(self):
        return None

    def chat_json(self, system, user):
        self.calls.append((self.step, system, user))
        if system.startswith("[REVISER]"):
            self.k += 1
            return {"lines": [{"id": "L06", "text": f"改写第{self.k}版，回到零利率。"}, {"id": "L01", "text": "偷改"}]}
        lines = [{"id": f"L0{i}", "scores": SC, "issues": []} for i in range(1, 7)]
        lines[5] = {"id": "L06", "scores": {**SC, "natural": 2},
                    "issues": [{"type": "awkward", "severity": "high", "detail": "金句腔"}]}
        return {"lines": lines, "script": {"scores": SS, "issues": []}, "summary": "x"}


def proj(name):
    p = td / name
    shutil.copytree(FIX, p / "content")
    (p / "BRIEF.md").write_text("# 流动性陷阱\n\n## FACTS\n- 日本九十年代利率接近零。\n\n## 其他\n很长的背景" + "背景" * 2000,
                                encoding="utf-8")
    return p


# 1) default 2 rounds → NEEDS_HUMAN, exactly critic r1, reviser r1, critic r2 — no more calls
p = proj("cap")
c = Rec()
s = D.run_loop(p, client=c, settle_sec=0, log=lambda *_: None)
ok(D.DEFAULT_MAX_ROUNDS == 2 and s["maxRounds"] == 2, "default max rounds = 2")
ok(s["status"] == "NEEDS_HUMAN" and s["needsHuman"] and s["rounds"] == 2, f"not PASS after 2 → NEEDS_HUMAN ({s['status']})")
ok([x[0] for x in c.calls] == ["critic r1", "reviser r1", "critic r2"], f"exactly 3 LLM calls {[x[0] for x in c.calls]}")
ok(not D.gate_status(p)[0], "NEEDS_HUMAN keeps TTS gate closed")
L1 = json.loads((p / "content" / "lines.json").read_text())
ok(next(x for x in L1 if x["id"] == "L01")["text"] != "偷改", "reviser cannot touch unflagged lines")
c4 = Rec()
s4 = D.run_loop(proj("cap4"), client=c4, max_rounds=4, settle_sec=0, log=lambda *_: None)
ok(s4["rounds"] == 4 and len(c4.calls) == 7 and s4["status"] == "NEEDS_HUMAN", "--max-rounds 4 still configurable")

# 2) compact context
crit_user, rev_user = c.calls[0][2], c.calls[1][2]
ok("台词规则清单" in crit_user and "## 8. 明确不做" not in crit_user and "lemo-dialogue SKILL" not in crit_user,
   "critic gets compact rules, not full DIALOGUE.md/SKILL")
ok("日本九十年代利率接近零" in crit_user and "背景背景背景" not in crit_user, "critic gets the film's FACTS section only")
cf = Rec()
D.run_loop(proj("full"), client=cf, settle_sec=0, log=lambda *_: None, compact=False)
ratio = len(crit_user) / len(cf.calls[0][2])
ok(ratio < 0.35, f"compact critic prompt ≤35% of full ({ratio:.2f})")
sect = rev_user.split("# 要改的句子（只改并只返回这些）\n", 1)[1].split("\n\n#", 1)[0]
ok('"L06"' in sect and '"L01"' not in sect and "L01: " in rev_user, "reviser: only flagged lines editable, others read-only id:text")
ok("只返回 flagged" in D.REVISER_SYS and "low 全片最多 3 条" in D.CRITIC_SYS, "reviser returns only flagged; critic output capped")
ok(len(rev_user) / len(cf.calls[1][2]) < 0.35, "compact reviser prompt ≤35% of full")
ok(s["context"] == "compact", "summary records context=compact")

# 3) quota-aware routing
os.environ["TOKENHARBOR_API_KEY"] = "test-th"
os.environ["OPENROUTER_API_KEY"] = "test-or"
qp = L.quota_ledger_path()
ok(qp == td / "quota.jsonl", "quota ledger honours DC_QUOTA_LEDGER (tests never touch the real one)")
_q = os.environ.pop("DC_QUOTA_LEDGER")
ok(L.quota_ledger_path() == Path.home() / ".cache" / "wordfilm" / "tokenharbor-usage.jsonl", "default = shared real ledger")
os.environ["DC_QUOTA_LEDGER"] = _q
seen = []


def tr(url, headers, body):
    seen.append((url, body["model"]))
    return {"model": body["model"], "choices": [{"message": {"content": "{\"ok\": 1}"}}],
            "usage": {"prompt_tokens": 600, "completion_tokens": 400, "total_tokens": 1000}}


cl = L.FreeFirstClient(transport=tr, sleep_fn=lambda *_: None)
ok(not cl.routing["routed"] and cl.routing["order"][0].startswith("tokenharbor/"), "under 80% → TokenHarbor first")
cl.chat_json("s", "u", step="t")
ok(seen[-1][1] == "deepseek-v4.1-flash:free" and L.quota_usage()["used"] == 1000, "TokenHarbor call recorded in quota ledger")
now = time.time()
with qp.open("a") as f:
    f.write(json.dumps({"ts": now - 8 * 86400, "provider": "tokenharbor", "total": 900000}) + "\n")
    f.write(json.dumps({"ts": now - 3600, "provider": "tokenharbor", "total": 990000}) + "\n")
q = L.quota_usage()
ok(q["used"] == 991000 and abs(q["pct"] - 0.7928) < 1e-3, f"rolling 7-day window ignores old rows ({q['used']})")
ok(not cl.reroute()["routed"], "79% → still TokenHarbor")
with qp.open("a") as f:
    f.write(json.dumps({"ts": now - 60, "provider": "tokenharbor", "total": 10000}) + "\n")
r = cl.reroute()
ok(r["routed"] and r["order"] == ["openrouter/nvidia/nemotron-3.5-lightning:free", "openrouter/recursive/flint-v1.0:free",
                                  "tokenharbor/deepseek-v4.1-flash:free"], f"≥80% → OpenRouter :free first {r['order']}")
cl.chat_json("s", "u", step="t2")
ok(seen[-1][1] == "nvidia/nemotron-3.5-lightning:free" and L.quota_usage()["used"] == 1001000,
   "routed call served by nemotron; OpenRouter calls not counted against TokenHarbor")
c2 = L.FreeFirstClient(transport=tr, sleep_fn=lambda *_: None)
ok(c2.routing["routed"], "new client (next batch) routes at start")
ok(all(not s_["paid"] for s_ in c2._slots) and not any("nvidia" == s_["provider"] for s_ in c2._slots),
   "never paid; no NVIDIA NIM slot")
c3 = L.FreeFirstClient(transport=tr, sleep_fn=lambda *_: None, weekly_budget=10_000_000)
ok(not c3.routing["routed"], "configurable weekly budget")
os.environ["DC_QUOTA_ROUTE"] = "0"
ok(not L.FreeFirstClient(transport=tr).routing["routed"], "DC_QUOTA_ROUTE=0 disables routing")
os.environ.pop("DC_QUOTA_ROUTE")
ok("test-th" not in qp.read_text() and "test-or" not in qp.read_text(), "no keys in quota ledger")
cr = Rec()
cr.reroute = lambda: {"routed": True, "used": 1, "budget": 1, "pct": 1.0, "routePct": 0.8, "order": ["openrouter/x"]}
cr.routing = cr.reroute()
s5 = D.run_loop(proj("rt"), client=cr, settle_sec=0, log=lambda *_: None)
ok(s5["routing"]["routed"], "dialogue_loop records routing in summary")

# 4) header-based quota (primary signal) — x-th-free-used-pct / x-th-free-resets
from datetime import datetime, timedelta, timezone
qh = td / "hq.jsonl"
os.environ["DC_QUOTA_LEDGER"] = str(qh)
hp = L.quota_header_path()
ok(hp == td / "hq.header.json", f"header state beside temp ledger ({hp.name})")
ok(L.parse_th_headers({"X-TH-Free-Used-Pct": "83.5%"})["pct"] == 0.835, "header pct parsed (percent, case-insensitive)")
ok(L.parse_th_headers({"content-type": "application/json"}) is None, "no header → None")
ok(L.parse_th_headers({"x-th-free-used-pct": "n/a"}) is None, "garbage header → None")
ok(L.parse_reset("2026-10-30T00:00:00Z") == datetime(2026, 10, 30, tzinfo=timezone.utc).timestamp(), "ISO Z reset")
ok(L.parse_reset("Fri, 30 Oct 2026 00:00:00 GMT") == datetime(2026, 10, 30, tzinfo=timezone.utc).timestamp(), "RFC1123 reset")
ok(L.parse_reset("2026-10-30T00:00:00") == datetime(2026, 10, 30, tzinfo=timezone.utc).timestamp(), "naive reset = UTC")
fut = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
hdr = {"pct": "12"}
seen.clear()


def trh(url, headers, body):
    seen.append((url, body["model"]))
    r = {"model": body["model"], "choices": [{"message": {"content": "{\"ok\": 1}"}}],
         "usage": {"prompt_tokens": 60, "completion_tokens": 40, "total_tokens": 100}}
    if "tokenharbor" in url and hdr.get("pct") is not None:
        return r, {"x-th-free-used-pct": hdr["pct"], "x-th-free-resets": hdr.get("resets", fut)}
    return r


ch = L.FreeFirstClient(transport=trh, sleep_fn=lambda *_: None)
ok(ch.routing["source"].startswith("local-ledger"), "no header seen yet → ledger fallback")
ch.chat_json("s", "u", step="h1")
st = L.quota_status()
ok(st["source"] == "header x-th-free-used-pct" and st["pct"] == 0.12, f"header recorded & primary ({st['source']})")
ok(not ch.routing["routed"], "header 12% → TokenHarbor stays first")
hdr["pct"] = "81.2"
ch.chat_json("s", "u", step="h2")
ok(seen[-1][1] == "deepseek-v4.1-flash:free", "the call that returned 81% was TokenHarbor")
ok(ch.routing["routed"] and ch.routing.get("trigger") == "mid-batch header" and ch.routing["source"].startswith("header"),
   "header ≥80% → reroutes mid-batch even though ledger is ~0%")
ok(ch.routing["ledgerPct"] < 0.01, "ledger estimate kept alongside header")
ch.chat_json("s", "u", step="h3")
ok(seen[-1][1] == "nvidia/nemotron-3.5-lightning:free", "next call in the same batch → OpenRouter nemotron")
ok(L.FreeFirstClient(transport=trh).routing["routed"], "next batch: persisted header routes at start")
# header lower than ledger wins (primary)
with qh.open("a") as f:
    f.write(json.dumps({"ts": time.time() - 60, "provider": "tokenharbor", "total": 1_200_000}) + "\n")
L.record_header({"pct": 0.3, "resetsAt": L.parse_reset(fut), "resetsRaw": fut, "observedAt": time.time()})
r = L.FreeFirstClient(transport=trh).routing
ok(not r["routed"] and r["pct"] == 0.3 and r["ledgerPct"] > 0.9, "fresh header 30% overrides ledger 96%")
# stale header (reset passed) → ledger fallback
L.record_header({"pct": 0.3, "resetsAt": L.parse_reset(past), "resetsRaw": past, "observedAt": time.time() - 7200})
r = L.FreeFirstClient(transport=trh).routing
ok(r["source"].startswith("local-ledger") and r["routed"], "reset time passed → header ignored, ledger 96% routes")
# no reset header → TTL
L.record_header({"pct": 0.95, "resetsAt": None, "resetsRaw": None, "observedAt": time.time() - 7 * 3600})
ok(L.header_quota() is None, "no reset + older than TTL → ignored")
L.record_header({"pct": 0.95, "resetsAt": None, "resetsRaw": None, "observedAt": time.time()})
ok(L.FreeFirstClient(transport=trh).routing["routed"], "no reset + fresh → used")
# dict-carried headers on HTTP-error-free path; OpenRouter headers ignored
hp.unlink()
L.FreeFirstClient(transport=lambda u, h, b: {"__headers__": {"x-th-free-used-pct": "50"}, "model": b["model"],
                  "choices": [{"message": {"content": "{}"}}], "usage": {}}, quota_route=False).chat_json("s", "u")
ok(L.header_quota()["pct"] == 0.5, "__headers__ dict form accepted")
hp.unlink()
os.environ["TOKENHARBOR_API_KEY"] = ""
L.FreeFirstClient(transport=lambda u, h, b: ({"model": b["model"], "choices": [{"message": {"content": "{}"}}]},
                  {"x-th-free-used-pct": "99"})).chat_json("s", "u")
ok(not hp.exists(), "x-th headers from non-TokenHarbor providers are ignored")
os.environ["TOKENHARBOR_API_KEY"] = "test-th"
# real (non-mock) transport path: headers read from the urlopen response object
import io
import email.message


class _Resp(io.BytesIO):
    def __init__(self, data, hdrs):
        super().__init__(data)
        self.headers = email.message.Message()
        for k, v in hdrs.items():
            self.headers[k] = v

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


_orig = L.urllib.request.urlopen
L.urllib.request.urlopen = lambda req, timeout=None: _Resp(json.dumps(
    {"model": "m", "choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 5}}).encode(),
    {"X-Th-Free-Used-Pct": "88", "X-Th-Free-Resets": fut})
qh.write_text("")  # ledger 0 % → only the header can route
try:
    cu = L.FreeFirstClient(sleep_fn=lambda *_: None)
    cu.chat_json("s", "u")
finally:
    L.urllib.request.urlopen = _orig
ok(cu.call_log[-1]["provider"] == "tokenharbor" and L.header_quota()["pct"] == 0.88 and cu.routing["routed"],
   "urlopen path captures TokenHarbor response headers → routed")
ok("test-th" not in hp.read_text(), "no keys in header state")
ok(all(not s_["paid"] for s_ in ch._slots), "header routing never adds paid slots")
os.environ["DC_QUOTA_LEDGER"] = _q

shutil.rmtree(td, ignore_errors=True)
print(f"finance mock: {n} checks passed")
