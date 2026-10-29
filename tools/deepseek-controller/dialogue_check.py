#!/usr/bin/env python3
"""DIALOGUE.md §4–§5 gate for VO lines — run before TTS.

Checks (FAIL unless noted):
  function   every VO line has function ∈ hook|turn|evidence|payoff|sting
  length     each line's say/text ≤ 35 字 (punctuation/whitespace not counted)
  hook       a `hook` line among the first 3 VO beats
  coverage   hook + (evidence|turn) + payoff present
  duration   Σ字 / 4.5 字/秒 within ±15 % of targetDurationSec
  jinju      strong 金句升华 patterns (「让我们…」「其实…才是…」「归根结底」…)
  same-say   `say` must keep the CJK key chars of `text` (no short paraphrase)
WARN only: weaker cliché words, investment-advice tone, ending-line flourish.

Target: --target, else content/plan.json targetDurationSec.
Writes <project>/evidence/dialogue-check.json (status PASS|FAIL).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FUNCTIONS = ("hook", "turn", "evidence", "payoff", "sting")
MAX_CHARS = 35
DEFAULT_RATE = 4.5
DEFAULT_TOL = 0.15
HOOK_WITHIN = 3

# Strong 金句 / 万能升华 → FAIL
JINJU_FAIL = [
    (r"让我们", "让我们…"),
    (r"其实.{0,16}才是", "其实…才是…"),
    (r"才是真正的", "…才是真正的…"),
    (r"归根结底", "归根结底"),
    (r"说到底", "说到底"),
    (r"一起.{0,8}吧", "一起…吧"),
    (r"未来.{0,6}属于", "未来属于…"),
    (r"唯有.{0,12}才", "唯有…才…"),
    (r"这就是.{0,8}(力量|意义|智慧|真谛|魅力)", "这就是…的力量/意义"),
    (r"记住[，,：:]", "记住："),
    (r"(人生|生活)就像", "人生就像…"),
]
# Weaker → WARN
JINJU_WARN = [
    (r"真正的", "真正的"),
    (r"永远", "永远"),
    (r"智慧", "智慧"),
    (r"本质", "本质"),
    (r"真相", "真相"),
]
ADVICE_WARN = [
    (r"建议(你|大家)", "建议你/大家"),
    (r"(赶紧|赶快|马上)(买|卖|入手|上车)", "赶紧买卖"),
    (r"抄底", "抄底"),
    (r"(一定要|必须)(买|卖|配置|持有)", "一定要买/卖"),
    (r"稳赚|保本|翻倍", "收益承诺"),
]

_PUNCT = re.compile(r"[\s\u3000-\u303f\uff00-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65"
                    r"!-/:-@\[-`{-~·—…“”‘’《》「」『』【】、]")


def count_chars(s: str) -> int:
    """Spoken-length count: every non-punctuation, non-space char counts as one 字."""
    return len(_PUNCT.sub("", s or ""))


def _cjk(s: str) -> str:
    return "".join(ch for ch in (s or "") if "\u4e00" <= ch <= "\u9fff")


def find_lines(project: Path, explicit: Path | None = None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"lines not found: {explicit}")
        return explicit
    for rel in ("content/lines.json", "audio/lines.json", "lines.json"):
        p = project / rel
        if p.is_file():
            return p
    raise FileNotFoundError(f"no lines.json under {project} (tried content/, audio/, root)")


def plan_target(project: Path) -> float | None:
    p = project / "content" / "plan.json"
    if not p.is_file():
        return None
    try:
        v = json.loads(p.read_text(encoding="utf-8")).get("targetDurationSec")
        return float(v) if v else None
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def check_lines(
    lines: list[dict[str, Any]],
    target: float | None,
    *,
    rate: float = DEFAULT_RATE,
    tol: float = DEFAULT_TOL,
    max_chars: int = MAX_CHARS,
) -> dict[str, Any]:
    fails: list[str] = []
    warns: list[str] = []
    vo = [ln for ln in lines if isinstance(ln, dict) and (ln.get("say") or ln.get("text"))
          and str(ln.get("speaker", "VO")).strip() != "" and not ln.get("silent")]
    rows = []
    total = 0
    for i, ln in enumerate(vo):
        lid = str(ln.get("id") or f"#{i + 1}")
        spoken = str(ln.get("say") or ln.get("text") or "")
        n = count_chars(spoken)
        total += n
        fn = ln.get("function")
        if fn not in FUNCTIONS:
            fails.append(f"{lid}: function={fn!r} (need one of {'|'.join(FUNCTIONS)})")
        if n > max_chars:
            fails.append(f"{lid}: {n}字 > {max_chars}字 — split the sentence")
        if ln.get("say") and ln.get("text"):
            a, b = _cjk(str(ln["text"])), _cjk(str(ln["say"]))
            if a and b and len(b) < 0.8 * len(a):
                fails.append(f"{lid}: say ({len(b)}字) shorter than text ({len(a)}字) — no paraphrase")
        for pat, label in JINJU_FAIL:
            if re.search(pat, spoken):
                fails.append(f"{lid}: 金句升华 pattern 「{label}」 in 「{spoken}」")
        for pat, label in JINJU_WARN:
            if re.search(pat, spoken):
                warns.append(f"{lid}: cliché word 「{label}」 in 「{spoken}」")
        for pat, label in ADVICE_WARN:
            if re.search(pat, spoken):
                warns.append(f"{lid}: advice tone 「{label}」 in 「{spoken}」")
        rows.append({"id": lid, "function": fn, "chars": n, "estSec": round(n / rate, 2)})

    if not vo:
        return {"status": "SKIP", "reason": "no VO lines", "fails": [], "warns": [], "lines": []}

    first = [r["function"] for r in rows[:HOOK_WITHIN]]
    if "hook" not in first:
        fails.append(f"no function=hook within the first {HOOK_WITHIN} VO beats (got {first})")
    fset = {r["function"] for r in rows}
    if "hook" not in fset or "payoff" not in fset or not ({"evidence", "turn"} & fset):
        fails.append(f"function coverage needs hook + (evidence|turn) + payoff (got {sorted(x for x in fset if x)})")

    last = str(vo[-1].get("say") or vo[-1].get("text") or "")
    if re.search(r"[！!]$", last.strip()):
        warns.append(f"last line ends with an exclamation (flourish?): 「{last}」")

    est = total / rate
    dur: dict[str, Any] = {"totalChars": total, "rate": rate, "estSec": round(est, 2), "tolerance": tol}
    if target:
        lo, hi = target * (1 - tol), target * (1 + tol)
        dur.update({"targetSec": target, "minSec": round(lo, 2), "maxSec": round(hi, 2),
                    "minChars": int(-(-lo * rate // 1)), "maxChars": int(hi * rate)})
        if not (lo <= est <= hi):
            fails.append(f"VO estimate {est:.1f}s ({total}字 @ {rate}字/s) outside ±{tol:.0%} of target {target:g}s "
                         f"[{lo:.1f}, {hi:.1f}] ≈ {dur['minChars']}–{dur['maxChars']}字")
    else:
        fails.append("no target duration (pass --target or set content/plan.json targetDurationSec)")

    return {"status": "FAIL" if fails else "PASS", "fails": fails, "warns": warns,
            "duration": dur, "lines": rows}


def run(project: Path, *, lines_path: Path | None = None, target: float | None = None,
        rate: float = DEFAULT_RATE, tol: float = DEFAULT_TOL, write: bool = True) -> dict[str, Any]:
    project = project.resolve()
    lp = find_lines(project, lines_path)
    data = json.loads(lp.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("lines") or []
    if not isinstance(data, list):
        raise ValueError(f"{lp}: expected a list of lines")
    tgt = target if target else plan_target(project)
    rep = check_lines(data, tgt, rate=rate, tol=tol)
    rep.update({"schemaVersion": 1, "project": str(project), "linesPath": str(lp),
                "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "spec": "DIALOGUE.md §4–§5"})
    if write:
        ev = project / "evidence"
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "dialogue-check.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return rep


def format_report(rep: dict[str, Any]) -> str:
    out = [f"dialogue-check: {rep['status']}  ({rep.get('linesPath', '')})"]
    d = rep.get("duration") or {}
    if d:
        rng = f" window {d.get('minChars')}–{d.get('maxChars')}字" if "minChars" in d else ""
        out.append(f"  VO {d.get('totalChars')}字 ≈ {d.get('estSec')}s @ {d.get('rate')}字/s; target {d.get('targetSec')}s{rng}")
    for f in rep.get("fails", []):
        out.append(f"  FAIL {f}")
    for w in rep.get("warns", []):
        out.append(f"  WARN {w}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--lines", default=None)
    ap.add_argument("--target", type=float, default=None)
    ap.add_argument("--rate", type=float, default=DEFAULT_RATE)
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOL)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    try:
        rep = run(Path(a.project), lines_path=Path(a.lines) if a.lines else None, target=a.target,
                  rate=a.rate, tol=a.tolerance, write=not a.no_write)
    except (OSError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(json.dumps(rep, ensure_ascii=False, indent=2) if a.json else format_report(rep))
    return 0 if rep["status"] in ("PASS", "SKIP") else 1


if __name__ == "__main__":
    raise SystemExit(main())
