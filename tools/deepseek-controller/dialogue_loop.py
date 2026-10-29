#!/usr/bin/env python3
"""Self-loop dialogue optimizer: deterministic dialogue-check + LLM critic + reviser.

  cli.py dialogue-loop --project P [--lines X] [--brief Y] [--max-rounds 4]

Each round:
  a. deterministic `dialogue_check.check_lines` (DIALOGUE.md §5);
  b. LLM critic (DeepSeek official API, deepseek-flash) grounded in DIALOGUE.md +
     plugin/skills/lemo-dialogue/SKILL.md + the film's BRIEF/FACTS. It returns
     structured JSON (per-line + whole-script scores and issues). PASS/FAIL is
     decided HERE by fixed thresholds, not by the model's own verdict;
  c. if either fails → reviser rewrites ONLY the flagged lines (same ids,
     functions, shotIds; total chars kept inside the ±15 % window); loop.

Every round is written to <project>/evidence/dialogue-loop/round-N.json.
If no round fully passes, the best round is written back and the loop status is
BEST_EFFORT (never PASS). <project>/evidence/dialogue-loop.json records the
status and the sha256 of the lines that were approved; `cli.py tts` refuses to
run unless status == PASS and the current lines still hash to that value.

LLM transport: DeepSeek official only (https://api.deepseek.com, DEEPSEEK_API_KEY).
No fallback provider: any provider error stops the loop (exit 3).
Tests: --mock <json> ({"critic":[...], "reviser":[...]} consumed in order) — no network.
Spend guard: --max-cny (balance delta via /user/balance) and --min-balance floor.
Cost: one ledger row per real run (kind=llm-api; cny = balance delta; tokens summed).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import dialogue_check as dc

ROOT = Path(__file__).resolve().parent
LIB = ROOT.parent.parent
API = os.environ.get("DC_DEEPSEEK_BASE", "https://api.deepseek.com")
MODEL = "deepseek-flash"

LINE_DIMS = ("factual", "natural", "asr_safe", "function_fit")
SCRIPT_DIMS = ("factual", "consistency", "hook", "flow", "no_jinju", "natural")
# Thresholds (scores are 1–5). Decided here, not by the model.
TH = {"line_min": 3, "script_min": 4, "max_high": 0, "max_medium": 2}
EDIT_KEYS = ("text", "say", "cap", "want")


class ProviderError(RuntimeError):
    pass


class BadJSON(ValueError):
    pass


class BudgetStop(RuntimeError):
    pass


# ---------------------------------------------------------------- utils
def lines_sha(lines: list[dict[str, Any]]) -> str:
    """Hash of the spoken content + functions (what TTS and the gate care about)."""
    core = [{k: ln.get(k) for k in ("id", "function", "text", "say", "cap", "voice")} for ln in lines]
    return hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _read(p: Path, limit: int = 12000) -> str:
    try:
        return p.read_text(encoding="utf-8")[:limit]
    except OSError:
        return ""


def load_lines(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("lines") or []
    return data


# ---------------------------------------------------------------- LLM
class DeepSeekClient:
    def __init__(self, model: str = MODEL, effort: str = "high", timeout: int = 300):
        key = os.environ.get("DEEPSEEK_API_KEY")
        if not key:
            raise ProviderError("DEEPSEEK_API_KEY not set")
        self._key = key
        self.model, self.effort, self.timeout = model, effort, timeout
        self.usage = {"calls": 0, "prompt": 0, "completion": 0, "reasoning": 0, "cacheHit": 0}

    def balance(self) -> float | None:
        req = urllib.request.Request(f"{API}/user/balance", headers={"Authorization": f"Bearer {self._key}"})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=30))
            for b in d.get("balance_infos") or []:
                if b.get("currency") == "CNY":
                    return float(b["total_balance"])
        except (urllib.error.URLError, ValueError, KeyError, TimeoutError):
            return None
        return None

    def chat_json(self, system: str, user: str, retries: int = 2) -> dict[str, Any]:
        """Malformed JSON from the model is retried (same provider/model); HTTP/transport errors stop."""
        for attempt in range(retries + 1):
            try:
                return self._chat_once(system, user)
            except BadJSON as e:
                if attempt == retries:
                    raise ProviderError(f"DeepSeek returned non-JSON content {retries + 1}x: {e}") from None
        raise AssertionError

    def _chat_once(self, system: str, user: str) -> dict[str, Any]:
        body = {"model": self.model, "messages": [{"role": "system", "content": system},
                                                  {"role": "user", "content": user}],
                "response_format": {"type": "json_object"}, "temperature": 0.3,
                "max_tokens": 16000, "reasoning_effort": self.effort}
        req = urllib.request.Request(f"{API}/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {self._key}",
                                              "Content-Type": "application/json"})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=self.timeout))
        except urllib.error.HTTPError as e:
            raise ProviderError(f"DeepSeek HTTP {e.code}: {e.read()[:300]!r}") from None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise ProviderError(f"DeepSeek transport error: {e}") from None
        u = r.get("usage") or {}
        self.usage["calls"] += 1
        self.usage["prompt"] += int(u.get("prompt_tokens") or 0)
        self.usage["completion"] += int(u.get("completion_tokens") or 0)
        self.usage["reasoning"] += int((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
        self.usage["cacheHit"] += int(u.get("prompt_cache_hit_tokens") or 0)
        try:
            return json.loads(r["choices"][0]["message"]["content"])
        except (KeyError, IndexError, ValueError, TypeError) as e:
            raise BadJSON(str(e)) from None


class MockClient:
    """Deterministic stand-in for tests: replies consumed in order per role."""

    def __init__(self, path: Path):
        self.script = json.loads(path.read_text(encoding="utf-8"))
        self.idx = {"critic": 0, "reviser": 0}
        self.usage = {"calls": 0, "prompt": 0, "completion": 0, "reasoning": 0, "cacheHit": 0}
        self.model = "mock"

    def balance(self) -> float | None:
        return None

    def chat_json(self, system: str, user: str) -> dict[str, Any]:
        role = "reviser" if system.startswith("[REVISER]") else "critic"
        seq = self.script.get(role) or []
        i = self.idx[role]
        if i >= len(seq):
            raise ProviderError(f"mock: no more {role} replies")
        self.idx[role] += 1
        self.usage["calls"] += 1
        rep = seq[i]
        if isinstance(rep, dict) and rep.get("__error__"):
            raise ProviderError(rep["__error__"])
        return rep


# ---------------------------------------------------------------- prompts
def grounding(brief: Path | None, project: Path) -> str:
    parts = ["# DIALOGUE.md（台词层规则）\n" + _read(LIB / "DIALOGUE.md", 9000),
             "# 台词教父规则（lemo-dialogue SKILL）\n" + _read(LIB / "plugin/skills/lemo-dialogue/SKILL.md", 5000)]
    if brief and brief.is_file():
        parts.append("# BRIEF\n" + _read(brief, 8000))
    for name in ("FACTS.md", "TREATMENT.md"):
        p = project / name
        if p.is_file():
            parts.append(f"# {name}\n" + _read(p, 6000))
    return "\n\n".join(parts)


CRITIC_SYS = """你是严格的中文讲解片台词评审（台词教父标准）。依据下面的规则与片子资料，逐句、整体打分并列出问题。
只评，不改写。输出严格 JSON，结构：
{"lines":[{"id":"L01","scores":{"factual":1-5,"natural":1-5,"asr_safe":1-5,"function_fit":1-5},
  "issues":[{"type":"factual|consistency|awkward|hook|flow|jinju|asr_risk|function","severity":"high|medium|low","detail":"…","suggestion":"…"}]}],
 "script":{"scores":{"factual":1-5,"consistency":1-5,"hook":1-5,"flow":1-5,"no_jinju":1-5,"natural":1-5},
  "issues":[{"type":"…","severity":"high|medium|low","lines":["L20","L21"],"detail":"…","suggestion":"…"}]},
 "summary":"一句话"}
评分维度：
- factual：与 FACTS/通行事实一致；数字、年份、人名、谁命名的概念；不得有投资建议或政治立场。
- consistency：前后自洽（如说「三招」就必须列出三招，指代清楚）。
- natural：像真人口播的中文，一口气能念完；别扭、生造搭配、语义含混（例如「陷阱不在利率低，钱停在原地…」这种不通顺的句子）要标 awkward。
- hook：前 3 拍是否抓人。flow：逻辑递进 hook→定义→证据→转折→收束是否顺。
- no_jinju：禁止金句升华/万能收尾/口号。
- asr_safe：TTS 念出后语音识别容易混淆的词（同音近音专有名词等）；若有不改变事实的更清晰说法，给出建议；术语本身必要时可保留，只标 low。
- function_fit：function 标签（hook|turn|evidence|payoff|sting）是否符合这句的作用。
结构已锁定：镜头顺序、每句 shotId 与 function 标签由 TREATMENT 决定，本轮只改措辞（DIALOGUE.md §6「不改故事结构，结构问题单列建议」）。
对结构本身的意见（转折太晚、标签分布等）只能用 type=structure、severity=low 单列，不要据此压低 flow/hook 分；
flow 只评在现有结构下句与句的衔接、指代与递进是否顺。
severity：high=事实错/自相矛盾/明显不通；medium=别扭、逻辑跳、标签不符、ASR 高风险；low=可选润色。
每句都要出现在 lines 里（没有问题就 issues: []）。不要编造问题；没有问题就给高分。"""

REVISER_SYS = """[REVISER] 你是中文讲解片台词改写手（台词教父标准）。只改被标记的句子，其余句子不要动。
硬规则：不新增事实（只用 FACTS 里的事实）；每句 ≤35 字（不计标点）；保留每句的 id、function 与镜头归属；
text 与 say 同句（若原句有 say，say 必须与 text 同义同关键字，只可标点不同）；禁止金句升华与投资建议；
口语自然、一口气能念完；若原句有 cap（屏幕短字幕，格式如「降息|{失灵}」，| 分行，{} 为强调），改句后 cap 要与新句一致，长度与原 cap 相近。
总字数不得超过给定上限（不要为凑时长加字；同样意思更短更好）。
输出严格 JSON：{"lines":[{"id":"L22","text":"…","say":"…(可省略)","cap":"…(原有才给)","want":"…"}],"notes":"一句话说明改了什么"}"""


def _issue_lines(critique: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    li = critique.get("lines") or []
    si = (critique.get("script") or {}).get("issues") or []
    return li, si


def evaluate_critique(critique: dict[str, Any], ids: list[str]) -> dict[str, Any]:
    """Apply fixed thresholds. Returns {pass, counts, reasons, flagged{id:[issues]}}."""
    flagged: dict[str, list[dict]] = {}
    counts = {"high": 0, "medium": 0, "low": 0}
    reasons: list[str] = []
    li, si = _issue_lines(critique)
    seen = set()
    for row in li:
        lid = str(row.get("id"))
        seen.add(lid)
        sc = row.get("scores") or {}
        for d in LINE_DIMS:
            v = sc.get(d)
            if isinstance(v, (int, float)) and v < TH["line_min"]:
                reasons.append(f"{lid}.{d}={v} < {TH['line_min']}")
                flagged.setdefault(lid, []).append({"type": d, "severity": "medium", "detail": f"score {v}"})
        for iss in row.get("issues") or []:
            sev = str(iss.get("severity", "low")).lower()
            if str(iss.get("type")) == "structure":
                sev = "low"
            counts[sev if sev in counts else "low"] += 1
            if sev in ("high", "medium"):
                flagged.setdefault(lid, []).append(iss)
    for iss in si:
        sev = str(iss.get("severity", "low")).lower()
        if str(iss.get("type")) == "structure":
            sev = "low"  # structure is locked in this step (DIALOGUE.md §6); advisory only
        counts[sev if sev in counts else "low"] += 1
        if sev in ("high", "medium"):
            for lid in iss.get("lines") or []:
                flagged.setdefault(str(lid), []).append(iss)
    ssc = (critique.get("script") or {}).get("scores") or {}
    for d in SCRIPT_DIMS:
        v = ssc.get(d)
        if not isinstance(v, (int, float)):
            reasons.append(f"script.{d} missing")
        elif v < TH["script_min"]:
            reasons.append(f"script.{d}={v} < {TH['script_min']}")
    missing = [i for i in ids if i not in seen]
    if missing:
        reasons.append(f"critic skipped lines {missing}")
    if counts["high"] > TH["max_high"]:
        reasons.append(f"{counts['high']} high-severity issue(s)")
    if counts["medium"] > TH["max_medium"]:
        reasons.append(f"{counts['medium']} medium issue(s) > {TH['max_medium']}")
    flagged = {k: v for k, v in flagged.items() if k in ids}
    return {"pass": not reasons, "counts": counts, "reasons": reasons, "flagged": flagged,
            "modelVerdict": critique.get("summary")}


def det_flagged(rep: dict[str, Any], ids: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in rep.get("fails") or []:
        lid = f.split(":", 1)[0].strip()
        if lid in ids:
            out.setdefault(lid, []).append({"type": "dialogue-check", "severity": "high", "detail": f})
    return out


def round_score(det: dict, ev: dict | None) -> tuple:
    """Lower is better: (det fails, critic not pass, high, medium, low)."""
    c = (ev or {}).get("counts") or {"high": 99, "medium": 99, "low": 99}
    return (len(det.get("fails") or []), 0 if ev and ev["pass"] else 1, c["high"], c["medium"], c["low"])


def apply_revision(lines: list[dict], rev: dict, allowed: set[str]) -> tuple[list[dict], list[dict]]:
    new = copy.deepcopy(lines)
    by = {str(ln.get("id")): ln for ln in new}
    changes = []
    for r in rev.get("lines") or []:
        lid = str(r.get("id"))
        if lid not in allowed or lid not in by:
            continue  # reviser may only touch flagged lines
        ln = by[lid]
        before = {k: ln.get(k) for k in EDIT_KEYS if k in ln}
        for k in EDIT_KEYS:
            if k in r and isinstance(r[k], str) and r[k].strip():
                if k in ("cap", "say") and k not in ln:
                    continue
                ln[k] = r[k].strip()
        if "say" in ln and "text" in r and "say" not in r:
            ln["say"] = ln["text"]
        after = {k: ln.get(k) for k in EDIT_KEYS if k in ln}
        if after != before:
            changes.append({"id": lid, "before": before, "after": after})
    return new, changes


# ---------------------------------------------------------------- loop
def run_loop(project: Path, *, lines_path: Path | None = None, brief: Path | None = None,
             max_rounds: int = 4, target: float | None = None, client=None,
             max_cny: float | None = None, min_balance: float | None = None,
             write_back: bool = True, settle_sec: float = 30.0, log: Callable[[str], None] = print) -> dict[str, Any]:
    project = project.resolve()
    lp = dc.find_lines(project, lines_path)
    brief = brief or (project / "BRIEF.md")
    tgt = target or dc.plan_target(project)
    prof = dc.pp.profile(project)
    det_kw = {"rate": float(prof["cps"]), "line_warn_chars": int(prof["lineMaxChars"]), "pacing": prof["name"]}
    orig = load_lines(lp)
    ids = [str(ln.get("id")) for ln in orig]
    ev_dir = project / "evidence" / "dialogue-loop"
    ev_dir.mkdir(parents=True, exist_ok=True)
    for old in ev_dir.glob("round-*.json"):
        old.unlink()
    (ev_dir / "original-lines.json").write_text(json.dumps(orig, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ground = grounding(brief, project)
    b0 = client.balance() if client else None
    rounds: list[dict] = []
    lines = orig
    status, stop_reason = "BEST_EFFORT", None

    def guard():
        if b0 is None or (max_cny is None and min_balance is None):
            return
        b = client.balance()
        if b is None:
            return
        if max_cny is not None and b0 - b >= max_cny:
            raise BudgetStop(f"spend cap ¥{max_cny} reached (balance {b0:.2f}→{b:.2f})")
        if min_balance is not None and b <= min_balance:
            raise BudgetStop(f"balance ¥{b:.2f} ≤ floor ¥{min_balance}")

    t_start = time.time()
    try:
        for n in range(1, max_rounds + 1):
            det = dc.check_lines(lines, tgt, **det_kw)
            guard()
            user = (f"{ground}\n\n# 目标时长 {tgt}s；确定性门禁结果\n" + json.dumps(
                {k: det.get(k) for k in ("status", "fails", "warns", "duration")}, ensure_ascii=False)
                + "\n\n# 待评台词 lines.json\n" + json.dumps(lines, ensure_ascii=False, indent=1))
            critique = client.chat_json(CRITIC_SYS, user)
            ev = evaluate_critique(critique, ids)
            rec = {"round": n, "lines": lines, "linesSha256": lines_sha(lines), "deterministic": det,
                   "critique": critique, "criticEval": ev, "thresholds": TH,
                   "pass": det["status"] == "PASS" and ev["pass"]}
            log(f"round {n}: dialogue-check {det['status']}; critic {'PASS' if ev['pass'] else 'FAIL'} "
                f"(high {ev['counts']['high']}, medium {ev['counts']['medium']}, low {ev['counts']['low']})"
                + ("" if ev["pass"] else f" — {'; '.join(ev['reasons'][:4])}"))
            if rec["pass"]:
                rounds.append(rec)
                (ev_dir / f"round-{n}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                status = "PASS"
                break
            flagged = dict(ev["flagged"])
            for k, v in det_flagged(det, ids).items():
                flagged.setdefault(k, []).extend(v)
            if n == max_rounds:
                rounds.append(rec)
                (ev_dir / f"round-{n}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                break
            if not flagged:
                # Whole-script / duration problem with no line ids → let reviser pick lines.
                flagged = {i: [{"type": "script", "severity": "medium",
                                "detail": "; ".join(ev["reasons"] + det.get("fails", []))}] for i in ids}
            guard()
            d = det.get("duration") or {}
            ruser = (f"{ground}\n\n# 全部台词（只改 flagged）\n" + json.dumps(lines, ensure_ascii=False, indent=1)
                     + "\n\n# flagged（id → 问题）\n" + json.dumps(flagged, ensure_ascii=False, indent=1)
                     + f"\n\n# 字数约束：当前总字数 {d.get('totalChars')}；总字数上限 {d.get('maxChars')} 字"
                     f"（目标时长是上限，不要为凑时长加字，更短更紧凑可以）；单句 ≤ {dc.MAX_CHARS} 字，"
                     f"建议 ≤ {prof['lineMaxChars']} 字（节奏 {prof['name']}）。")
            rev = client.chat_json(REVISER_SYS, ruser)
            new, changes = apply_revision(lines, rev, set(flagged))
            rec["flagged"] = flagged
            rec["revision"] = {"notes": rev.get("notes"), "changes": changes}
            rounds.append(rec)
            (ev_dir / f"round-{n}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if not changes:
                log(f"round {n}: reviser changed nothing — stopping")
                stop_reason = "reviser made no changes"
                break
            lines = new
    except ProviderError as e:
        status, stop_reason = "PROVIDER_ERROR", str(e)
        log(f"STOP provider failure: {e}")
    except BudgetStop as e:
        stop_reason = str(e)
        log(f"STOP budget: {e}")

    best = min(rounds, key=lambda r: round_score(r["deterministic"], r["criticEval"])) if rounds else None
    if status == "PASS":
        best = rounds[-1]
    chosen = best["lines"] if best else orig
    det_final = dc.check_lines(chosen, tgt, **det_kw)
    if status != "PASS" and status != "PROVIDER_ERROR":
        status = "BEST_EFFORT"
    if client and b0 is not None and getattr(client, "usage", {}).get("calls"):
        time.sleep(settle_sec)  # /user/balance lags a few seconds behind usage
    b1 = client.balance() if client else None
    summary = {"schemaVersion": 1, "status": status, "stopReason": stop_reason,
               "chosenRound": best["round"] if best else None, "rounds": len(rounds),
               "maxRounds": max_rounds, "linesPath": str(lp), "linesSha256": lines_sha(chosen),
               "deterministicFinal": det_final["status"], "thresholds": TH,
               "model": getattr(client, "model", None), "usage": dict(getattr(client, "usage", {})),
               "balanceBefore": b0, "balanceAfter": b1,
               "cny": round(b0 - b1, 2) if (b0 is not None and b1 is not None) else None,
               "durationSec": round(time.time() - t_start, 1),
               "finishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "honesty": "PASS only when dialogue-check PASS and critic thresholds met in the same round; "
                          "BEST_EFFORT = best round written back, TTS stays blocked."}
    if write_back and best is not None and status != "PROVIDER_ERROR":
        text = json.dumps(chosen, ensure_ascii=False, indent=2) + "\n"
        lp.write_text(text, encoding="utf-8")
        # keep sibling copies (content/lines.json ↔ audio/lines.json) identical
        for sib in (project / "content" / "lines.json", project / "audio" / "lines.json", project / "lines.json"):
            if sib.resolve() != lp.resolve() and sib.is_file():
                try:
                    if [str(x.get("id")) for x in load_lines(sib)] == ids:
                        sib.write_text(text, encoding="utf-8")
                except (ValueError, OSError):
                    pass
    (ev_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (project / "evidence" / "dialogue-loop.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def gate_status(project: Path, lines_path: Path | None = None) -> tuple[bool, str]:
    """TTS gate: loop PASS and current lines unchanged since approval."""
    p = project / "evidence" / "dialogue-loop.json"
    if not p.is_file():
        return False, "no evidence/dialogue-loop.json — run `cli.py dialogue-loop` first"
    s = json.loads(p.read_text(encoding="utf-8"))
    if s.get("status") != "PASS":
        return False, f"dialogue-loop status {s.get('status')} (chosen round {s.get('chosenRound')}) — not PASS"
    lp = dc.find_lines(project, lines_path)
    cur = lines_sha(load_lines(lp))
    if cur != s.get("linesSha256"):
        return False, "lines changed after dialogue-loop PASS — re-run dialogue-loop"
    return True, f"dialogue-loop PASS (round {s.get('chosenRound')}/{s.get('maxRounds')})"


def log_cost(summary: dict[str, Any], project: Path, item: str) -> dict | None:
    from budget import append_entry
    u = summary.get("usage") or {}
    if not u.get("calls") or summary.get("model") == "mock":
        return None
    return append_entry({
        "kind": "llm-api", "item": item, "usd": 0.0, "cny": summary.get("cny"),
        "tokensIn": u.get("prompt"), "tokensOut": u.get("completion"),
        "durationSec": summary.get("durationSec"), "path": "dialogue-loop", "project": str(project),
        "model": summary.get("model"), "source": "deepseek-balance+api-usage",
        "notes": (f"dialogue-loop {summary.get('status')} in {summary.get('rounds')} round(s), {u.get('calls')} calls; "
                  f"billed CNY = DeepSeek /user/balance delta {summary.get('balanceBefore')}→{summary.get('balanceAfter')}; "
                  f"usd not computed (no official USD price table here; see cny); reasoning tokens {u.get('reasoning')}"),
        "meta": {"cacheHitTokens": u.get("cacheHit"), "reasoningTokens": u.get("reasoning")},
    })


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--lines", default=None)
    ap.add_argument("--brief", default=None)
    ap.add_argument("--max-rounds", type=int, default=4)
    ap.add_argument("--target", type=float, default=None)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--effort", default="high", choices=["low", "high", "max"])
    ap.add_argument("--max-cny", type=float, default=2.0, help="stop when DeepSeek balance drops this much")
    ap.add_argument("--min-balance", type=float, default=5.0, help="stop when balance ≤ this")
    ap.add_argument("--mock", default=os.environ.get("DC_DIALOGUE_LLM_MOCK"), help="tests: canned replies JSON")
    ap.add_argument("--item", default=None, help="ledger item label")
    ap.add_argument("--no-ledger", action="store_true")
    a = ap.parse_args(argv)
    project = Path(a.project).resolve()
    try:
        client = MockClient(Path(a.mock)) if a.mock else DeepSeekClient(a.model, a.effort)
    except ProviderError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    s = run_loop(project, lines_path=Path(a.lines) if a.lines else None,
                 brief=Path(a.brief) if a.brief else None, max_rounds=a.max_rounds, target=a.target,
                 client=client, max_cny=a.max_cny, min_balance=a.min_balance)
    if not a.no_ledger:
        row = log_cost(s, project, a.item or f"dialogue-loop {project.name}")
        if row:
            print(f"ledger: cny={row.get('cny')} tokensIn={row['tokensIn']} tokensOut={row['tokensOut']}")
    print(f"dialogue-loop: {s['status']} (round {s['chosenRound']}/{s['maxRounds']}, "
          f"{s['rounds']} round(s); deterministic {s['deterministicFinal']})"
          + (f" — {s['stopReason']}" if s.get("stopReason") else ""))
    return {"PASS": 0, "BEST_EFFORT": 1, "PROVIDER_ERROR": 3}.get(s["status"], 1)


if __name__ == "__main__":
    raise SystemExit(main())
