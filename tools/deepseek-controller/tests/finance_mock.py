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

shutil.rmtree(td, ignore_errors=True)
print(f"finance mock: {n} checks passed")
