#!/usr/bin/env python3
"""Deterministic 台词教父 rhythm checks on lines.json (pacing P1, feeds dialogue_loop's critic).

  python3 rhythm_check.py --project P [--pacing standard] [--json]

Rules (lemo-dialogue SKILL / 台词教父):
  hook        first line ≤ 12 字 and finished within 3 s (measured voices/dur.json, else 字/cps)   medium
  keyword     a line that carries a `cap` must mark its keyword with {…}                         medium
  alternation ≥ 3 consecutive long lines (≥ 16 字) — no breather                                    low
              ≥ 4 consecutive lines within ±2 字 of each other — monotone                           low
  one_point   one line packs ≥ 3 clauses (，；) or a list connective (而且/并且/同时/另外/以及)      low
medium = the critic must address it (script.rhythm gates the loop); low = advisory.
All findings go into the critic prompt and evidence/dialogue-loop/round-N.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HOOK_MAX_CHARS = 12
HOOK_MAX_SEC = 3.0
LONG_CHARS = 16
MONO_RUN, MONO_SPREAD = 4, 2
LONG_RUN = 3
_PUNCT = re.compile(r"[\s，。、！？；：,.!?;:“”\"'（）()《》【】\-—…·|{}]")
_CONNECT = ("而且", "并且", "同时", "另外", "以及")


def nchars(s: str) -> int:
    return len(_PUNCT.sub("", s or ""))


def check(lines: list[dict[str, Any]], *, cps: float = 5.3, durs: dict[str, float] | None = None,
          first_vo: float = 0.15) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    ids = [str(l.get("id")) for l in lines]
    texts = [str(l.get("text") or l.get("say") or "") for l in lines]
    ns = [nchars(t) for t in texts]
    if lines:
        hi = next((i for i, l in enumerate(lines) if l.get("function") == "hook"), 0)
        n = ns[hi]
        sec = float((durs or {}).get(ids[hi]) or 0.0) or (n / cps if cps else 0.0)
        end = round(first_vo + sec, 2)
        if n > HOOK_MAX_CHARS:
            issues.append({"id": ids[hi], "rule": "hook", "severity": "medium",
                           "detail": f"hook {n}字 > {HOOK_MAX_CHARS}字"})
        if end > HOOK_MAX_SEC:
            issues.append({"id": ids[hi], "rule": "hook", "severity": "medium",
                           "detail": f"hook ends at {end}s > {HOOK_MAX_SEC}s"})
    for l, i in zip(lines, ids):
        cap = l.get("cap")
        if isinstance(cap, str) and cap.strip() and not re.search(r"\{[^}]+\}", cap):
            issues.append({"id": i, "rule": "keyword", "severity": "medium",
                           "detail": f"cap {cap!r} has no {{关键词}} mark"})
    run: list[int] = []
    for k, n in enumerate(ns + [0]):
        if n >= LONG_CHARS:
            run.append(k)
            continue
        if len(run) >= LONG_RUN:
            issues.append({"id": ids[run[-1]], "lines": [ids[j] for j in run], "rule": "alternation",
                           "severity": "low", "detail": f"{len(run)} long lines in a row (≥{LONG_CHARS}字) — add a short beat"})
        run = []
    k = 0
    while k <= len(ns) - MONO_RUN:
        j = k + 1
        while j < len(ns) and max(ns[k:j + 1]) - min(ns[k:j + 1]) <= MONO_SPREAD:
            j += 1
        if j - k >= MONO_RUN:
            issues.append({"id": ids[j - 1], "lines": ids[k:j], "rule": "alternation", "severity": "low",
                           "detail": f"{j - k} lines of ≈{ns[k]}字 in a row — monotone, alternate short/long"})
            k = j
        else:
            k += 1
    for t, i in zip(texts, ids):
        clauses = len([c for c in re.split(r"[，,；;]", t) if c.strip()])
        if clauses >= 3 or any(c in t for c in _CONNECT):
            issues.append({"id": i, "rule": "one_point", "severity": "low",
                           "detail": f"{clauses} clauses / list connective — one point per line"})
    med = [x for x in issues if x["severity"] == "medium"]
    return {"status": "FAIL" if med else ("WARN" if issues else "PASS"), "issues": issues,
            "counts": {"medium": len(med), "low": len(issues) - len(med)},
            "stats": {"lines": len(lines), "charsPerLine": ns,
                      "shortLines": sum(1 for n in ns if n <= 10), "longLines": sum(1 for n in ns if n >= LONG_CHARS),
                      "keywordLines": sum(1 for l in lines if re.search(r"\{[^}]+\}", str(l.get("cap") or "")))}}


def flagged(rep: dict[str, Any], ids: list[str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for x in rep.get("issues") or []:
        if x["severity"] == "medium" and x["id"] in ids:
            out.setdefault(x["id"], []).append({"type": "rhythm", "severity": "medium",
                                                "detail": f"{x['rule']}: {x['detail']}"})
    return out


def main(argv: list[str] | None = None) -> int:
    import dialogue_check as dc
    import pacing_profile as pp
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--lines")
    ap.add_argument("--pacing")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    p = Path(a.project).resolve()
    lp = dc.find_lines(p, Path(a.lines) if a.lines else None)
    lines = json.loads(lp.read_text(encoding="utf-8"))
    if isinstance(lines, dict):
        lines = lines.get("lines") or []
    prof = pp.profile(p, a.pacing)
    durs = {}
    if (p / "voices" / "dur.json").is_file():
        durs = json.loads((p / "voices" / "dur.json").read_text(encoding="utf-8"))
    rep = check(lines, cps=float(prof["cps"]), durs=durs)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print(f"rhythm {rep['status']}: medium {rep['counts']['medium']}, low {rep['counts']['low']}")
        for x in rep["issues"]:
            print(f"  {x['severity']:6} {x['id']:5} {x['rule']:11} {x['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
