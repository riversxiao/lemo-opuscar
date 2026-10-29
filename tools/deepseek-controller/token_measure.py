#!/usr/bin/env python3
"""Per-step LLM token measurement for one film's text layer, through the free-first chain.

Steps (each call labelled via FreeFirstClient.step):
  script-gen   — brief → lines.json (台词教父 rules, {keyword} marks)
  fact-check   — claims in the lines vs the brief/FACTS; returns issues (advisory, recorded)
  critic rN / reviser rN — dialogue_loop.run_loop on the generated lines

Writes <project>/evidence/token-usage.json and TOKENS.md. Never prints keys. Free-first only unless
--allow-paid (OFF by default); when every free model fails → status PROVIDER_ERROR, nothing paid.

  python3 token_measure.py --project /workspace/films/var-tokens --brief BRIEF.md --target 45
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dialogue_loop as D  # noqa: E402
from llm_free import FreeFirstClient, ProviderError  # noqa: E402

GEN_SYS = """你是中文金融讲解短片的编剧，遵循台词教父规则：
- 开场钩子 ≤12字，3秒内说完，反常识或具体问题；
- 一句只讲一个点，长短句交替，避免连续长句；
- 每句标 1 个关键词，用 {关键词} 包住（屏幕强调用）；
- 口语、可朗读，不用金句腔（"这就是…""说白了…"），数字写成读法友好的形式；
- 只用 BRIEF/FACTS 里的事实。
输出严格 JSON：{"lines":[{"id":"L01","speaker":"VO","want":"…","function":"hook|context|evidence|turn|payoff|sting","text":"…","shotId":"s1"}]}"""

FACT_SYS = """你是金融事实核查员。逐句检查台词里的事实/数字/定义是否与资料一致、是否有误导。
输出严格 JSON：{"lines":[{"id":"L01","verdict":"ok|risk|wrong","detail":"…"}],"summary":"…"}"""


def measure(project: Path, brief: Path, target: float, n_lines: int, max_rounds: int, allow_paid: bool,
            client=None) -> dict:
    project.mkdir(parents=True, exist_ok=True)
    (project / "content").mkdir(exist_ok=True)
    (project / "content" / "plan.json").write_text(json.dumps({"targetDurationSec": target}) + "\n")
    bt = brief.read_text(encoding="utf-8")
    if brief.resolve() != (project / "BRIEF.md").resolve():
        (project / "BRIEF.md").write_text(bt, encoding="utf-8")
    c = client or FreeFirstClient(allow_paid=allow_paid)
    t0 = time.time()
    out: dict[str, Any] = {"project": str(project), "targetSec": target, "allowPaid": allow_paid}
    try:
        g = c.chat_json(GEN_SYS, f"# BRIEF\n{bt}\n\n写 {n_lines} 句，总时长约 {target:.0f} 秒（约 4.2 字/秒）。",
                        step="script-gen")
        lines = g.get("lines") or []
        if not lines:
            raise ProviderError("script-gen returned no lines")
        (project / "content" / "lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=2) + "\n")
        fc = c.chat_json(FACT_SYS, f"# 资料\n{bt}\n\n# 台词\n" + json.dumps(lines, ensure_ascii=False),
                         step="fact-check")
        (project / "evidence").mkdir(exist_ok=True)
        (project / "evidence" / "fact-check.json").write_text(json.dumps(fc, ensure_ascii=False, indent=2) + "\n")
        out["factCheck"] = {k: sum(1 for x in fc.get("lines", []) if x.get("verdict") == k) for k in ("ok", "risk", "wrong")}
        s = D.run_loop(project, max_rounds=max_rounds, client=c, settle_sec=0.0)
        out["dialogueLoop"] = {"status": s["status"], "rounds": s["rounds"], "chosenRound": s.get("chosenRound")}
        out["status"] = "OK"
    except ProviderError as e:
        out["status"] = "PROVIDER_ERROR"
        out["error"] = str(e)[:300]
    out["wallSec"] = round(time.time() - t0, 1)
    calls = c.call_log
    steps: dict[str, dict] = {}
    for r in calls:
        k = r.get("step") or "?"
        st = steps.setdefault(k, {"calls": 0, "failedCalls": 0, "prompt": 0, "completion": 0, "reasoning": 0,
                                  "total": 0, "models": []})
        st["calls"] += 1
        st["failedCalls"] += 0 if r.get("ok") else 1
        for f in ("prompt", "completion", "reasoning", "total"):
            st[f] += int(r.get(f) or 0)
        m = f"{r.get('provider')}/{r.get('servedModel') or r.get('model')}"
        if m not in st["models"]:
            st["models"].append(m)
    tot = {f: sum(s[f] for s in steps.values()) for f in ("calls", "prompt", "completion", "reasoning", "total")}
    out.update(steps=steps, total=tot, paidCalls=sum(1 for r in calls if r.get("paid")), callLog=calls)
    (project / "evidence").mkdir(exist_ok=True)
    (project / "evidence" / "token-usage.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    md = ["# Token usage (free-first)", "", f"status {out['status']} · wall {out['wallSec']}s · paid calls {out['paidCalls']}", "",
          "| step | calls | prompt | completion | reasoning | total | model(s) |", "|---|---|---|---|---|---|---|"]
    for k, s_ in steps.items():
        md.append(f"| {k} | {s_['calls']} | {s_['prompt']} | {s_['completion']} | {s_['reasoning']} | {s_['total']} | {', '.join(s_['models'])} |")
    md.append(f"| **total** | {tot['calls']} | {tot['prompt']} | {tot['completion']} | {tot['reasoning']} | **{tot['total']}** | |")
    (project / "TOKENS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--brief", required=True)
    ap.add_argument("--target", type=float, default=45.0)
    ap.add_argument("--lines", type=int, default=9)
    ap.add_argument("--max-rounds", type=int, default=4)
    ap.add_argument("--allow-paid", action="store_true")
    a = ap.parse_args(argv)
    o = measure(Path(a.project).resolve(), Path(a.brief), a.target, a.lines, a.max_rounds, a.allow_paid)
    print((Path(a.project) / "TOKENS.md").read_text())
    return 0 if o["status"] == "OK" else 3


if __name__ == "__main__":
    raise SystemExit(main())
