#!/usr/bin/env python3
"""FRM per-term template films (templates/finance-term/, see its STEPS.md).

  python3 batch_terms.py init   --csv /workspace/finance/frm_core100.csv --out /workspace/films/frm [--only 1,5-9] [--skip 42]
  python3 batch_terms.py plan   --term /workspace/films/frm/043-es           # after the expert fills + approves lines.json
  python3 batch_terms.py status --out /workspace/films/frm [--json]
  bash templates/finance-term/build_term.sh /workspace/films/frm/043-es       # render + gates + handoffs

init writes <out>/<NNN>-<slug>/src/{term.json, lines.json} (lines skeleton; never overwrites an
existing lines.json). plan refuses until lines.json has approvedBy and every cap filled, then writes
src/{plan.json, BRIEF.md, FACTS.md} and validates. No LLM, no network, no TTS here.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

CTL = Path(__file__).resolve().parent
TPL = CTL / "templates" / "finance-term"
LINE_MAX = 26  # pacing standard single-line advice (WARN only)


def parse_ids(spec: str | None) -> set[int] | None:
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return out


def term_meta(row: dict[str, str]) -> dict[str, str]:
    keys = list(row)
    seq, en, zh, area = (row[keys[0]].strip(), row[keys[1]].strip(), row[keys[2]].strip(),
                         row[keys[3]].strip() if len(keys) > 3 else "")
    m = re.search(r"\(([^)]+)\)", en)
    short = m.group(1).strip() if m else (en if len(en) <= 12 else "")
    base = short if m else en
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:40] or f"term{seq}"
    return {"seq": f"{int(seq):03d}", "en": en, "zh": zh, "area": area, "short": short or zh, "slug": slug}


def _fill(s: str, meta: dict[str, str]) -> str:
    rep = dict(meta)
    rep["EN_UPPER"] = re.sub(r"\s*\([^)]*\)", "", meta["en"]).upper()
    rep["SHORT_UPPER"] = meta["short"].upper()
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(rep.get(m.group(1), m.group(0))), s)


def cmd_init(a: argparse.Namespace) -> int:
    only, skip = parse_ids(a.only), parse_ids(a.skip) or set()
    out = Path(a.out)
    made = kept = 0
    with open(a.csv, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            meta = term_meta(row)
            n = int(meta["seq"])
            if (only is not None and n not in only) or n in skip:
                continue
            src = out / f"{meta['seq']}-{meta['slug']}" / "src"
            src.mkdir(parents=True, exist_ok=True)
            meta["csv"] = str(Path(a.csv).resolve())
            (src / "term.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", "utf-8")
            lp = src / "lines.json"
            if lp.exists():
                kept += 1
                continue
            lp.write_text(_fill((TPL / "lines.skeleton.json").read_text("utf-8"), meta), "utf-8")
            made += 1
    print(f"OK init {made} new term(s), {kept} kept (lines.json already present) → {out}")
    return 0


def strip_cap(cap: str) -> str:
    return re.sub(r"[{}]", "", cap).strip()


def build_plan(term_dir: Path) -> tuple[dict, list[str]]:
    src = term_dir / "src"
    meta = json.loads((src / "term.json").read_text("utf-8"))
    L = json.loads((src / "lines.json").read_text("utf-8"))
    errs, warns = [], []
    if not str(L.get("approvedBy") or "").strip():
        errs.append("lines.json approvedBy empty — expert approval required before planning")
    for ln in L.get("lines") or []:
        if not str(ln.get("cap") or "").strip():
            errs.append(f"{ln.get('id')}: cap empty")
        elif len(re.sub(r"[\s{}，。、：；！？,.:;!?]", "", ln["cap"])) > LINE_MAX:
            warns.append(f"WARN {ln['id']}: > {LINE_MAX}字 (report only; wording is locked)")
    for c in L.get("cards") or []:
        if not str(c.get("zh") or "").strip():
            errs.append(f"card {c.get('shot')}: zh empty")
    if errs:
        raise SystemExit("plan refused:\n  " + "\n  ".join(errs))
    meta = dict(meta, approvedBy=L["approvedBy"], approvedAt=L.get("approvedAt", ""))
    plan = json.loads(_fill((TPL / "plan.skeleton.json").read_text("utf-8"), meta))
    cards = {c["shot"]: c for c in L["cards"]}
    by_shot: dict[str, list[str]] = {}
    for ln in L["lines"]:
        by_shot.setdefault(ln["shot"], []).append(strip_cap(ln["cap"]))
    for sh in plan["shots"]:
        c = cards.get(sh["id"], {})
        sh["onScreenText"] = c.get("zh") or meta["zh"]
        if c.get("en"):
            sh["onScreenTextEn"] = c["en"][:40]
        sh["text"] = " ".join(by_shot.get(sh["id"], [])) or sh["onScreenText"]
    plan["voice"]["lines"] = []
    for ln in L["lines"]:
        row = {"id": ln["id"], "role": ln["role"], "text": strip_cap(ln["cap"]), "cap": ln["cap"], "shotId": ln["shot"]}
        if ln.get("say"):
            row["say"] = ln["say"]
        plan["voice"]["lines"].append(row)
    return plan, warns


def cmd_plan(a: argparse.Namespace) -> int:
    term = Path(a.term)
    plan, warns = build_plan(term)
    src = term / "src"
    (src / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", "utf-8")
    meta = json.loads((src / "term.json").read_text("utf-8"))
    L = json.loads((src / "lines.json").read_text("utf-8"))
    meta.update(approvedBy=L["approvedBy"], approvedAt=L.get("approvedAt", ""),
                lines_md="\n".join(f"  - {x['id']} ({x['role']}): {x['cap']}" for x in L["lines"]))
    for name in ("BRIEF", "FACTS"):
        (src / f"{name}.md").write_text(_fill((TPL / f"{name}.skeleton.md").read_text("utf-8"), meta), "utf-8")
    import validate  # noqa: PLC0415

    errs = validate.validate_plan(plan) if hasattr(validate, "validate_plan") else []
    for w in warns:
        print(w)
    if errs:
        print("validate FAIL:\n  " + "\n  ".join(map(str, errs)))
        return 1
    print(f"OK plan → {src / 'plan.json'} ({len(plan['voice']['lines'])} lines)")
    return 0


def term_state(d: Path) -> str:
    src = d / "src"
    film = d.parent / f"{d.name}-v001"
    q = film / "quality.json"
    if q.is_file():
        try:
            return "delivered" if json.loads(q.read_text("utf-8")).get("overall") == "PASS" else "quality-FAIL"
        except ValueError:
            return "quality-unreadable"
    if (src / "plan.json").is_file():
        return "planned"
    try:
        L = json.loads((src / "lines.json").read_text("utf-8"))
    except (OSError, ValueError):
        return "missing-lines"
    if str(L.get("approvedBy") or "").strip() and all(str(x.get("cap") or "").strip() for x in L.get("lines") or []):
        return "approved"
    return "awaiting-expert-lines"


def cmd_status(a: argparse.Namespace) -> int:
    rows = [{"term": d.name, "state": term_state(d)} for d in sorted(Path(a.out).iterdir())
            if d.is_dir() and (d / "src" / "term.json").is_file()]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        from collections import Counter

        for r in rows:
            print(f"{r['term']:<40} {r['state']}")
        print(dict(Counter(r["state"] for r in rows)))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("--csv", required=True)
    i.add_argument("--out", required=True)
    i.add_argument("--only")
    i.add_argument("--skip")
    p = sub.add_parser("plan")
    p.add_argument("--term", required=True)
    s = sub.add_parser("status")
    s.add_argument("--out", required=True)
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    return {"init": cmd_init, "plan": cmd_plan, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
