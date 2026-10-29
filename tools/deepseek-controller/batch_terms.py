#!/usr/bin/env python3
"""FRM per-term template films (templates/finance-term/, see its STEPS.md).

  python3 batch_terms.py init   --csv /workspace/finance/frm_core100.csv --out $WORDFILM_FILMS/frm [--only 1,5-9] [--skip 42]
  python3 batch_terms.py plan   --term $WORDFILM_FILMS/frm/043-es           # after the expert fills + approves lines.json
  python3 batch_terms.py status --out $WORDFILM_FILMS/frm [--json]
  python3 batch_terms.py build  --out $WORDFILM_FILMS/frm [--only 43-50] [--el-backup]   # approved terms, one at a time
  bash templates/finance-term/build_term.sh $WORDFILM_FILMS/frm/043-es       # render + gates + handoffs

$WORDFILM_FILMS stands for the films root (common.films_root: $WORDFILM_FILMS, else <repo>/films, else
/workspace/films); the CSV path is wherever the source list lives.

init writes <out>/<NNN>-<slug>/src/{term.json, lines.json} (lines skeleton; never overwrites an
existing lines.json). plan refuses until lines.json has approvedBy and every cap filled, then writes
src/{plan.json, BRIEF.md, FACTS.md} and validates. No LLM, no network, no TTS here.

Per-term display: eyebrow label (default from the CSV 科目归类, or a CSV column `eyebrow`),
end card `endTitle` / `endLine` (CSV columns or lines.json "brand"), and `glossary`
(caption gloss at first use). Titles are uppercased with common.upper_keep (VaR never becomes VAR).
build --el-backup also renders an ElevenLabs backup narration + <film>-el.mp4 per term
(off by default; EL_VOICE / EL_MODEL env override the voice and model).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CTL = Path(__file__).resolve().parent
TPL = CTL / "templates" / "finance-term"
SHOT_MAX = 40
LINE_MAX = 32  # calm profile single-line advice (WARN only); finance-term default pacing=calm / speed 1.0
sys.path.insert(0, str(CTL))
from common import upper_keep  # noqa: E402

# GARP area (CSV 科目归类) → intro eyebrow label; a CSV `eyebrow` column or lines.json brand wins.
AREA_EYEBROW = {
    "估值与风险模型": "VALUATION & RISK MODELS",
    "数量分析": "QUANTITATIVE ANALYSIS",
    "金融市场与产品": "FINANCIAL MARKETS & PRODUCTS",
    "风险管理基础": "FOUNDATIONS OF RISK MANAGEMENT",
    "信用风险": "CREDIT RISK",
    "市场风险": "MARKET RISK",
    "操作风险与韧性": "OPERATIONAL RISK & RESILIENCE",
    "时事专题": "CURRENT ISSUES",
    "流动性与资金风险": "LIQUIDITY & TREASURY RISK",
    "风险管理与投资管理": "RISK & INVESTMENT MANAGEMENT",
}
BRAND_CSV = ("eyebrow", "eyebrowTop", "endTitle", "endLine")


def area_eyebrow(area: str) -> str:
    for k, v in AREA_EYEBROW.items():
        if k in (area or ""):
            return v
    return "FRM CORE 100"


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
    meta = {"seq": f"{int(seq):03d}", "en": en, "zh": zh, "area": area, "short": short or zh, "slug": slug,
            "eyebrow": area_eyebrow(area)}
    for k in BRAND_CSV:  # optional CSV columns
        if str(row.get(k) or "").strip():
            meta[k] = str(row[k]).strip()
    return meta


def _fill(s: str, meta: dict[str, str]) -> str:
    rep = dict(meta)
    rep["EN_UPPER"] = upper_keep(re.sub(r"\s*\([^)]*\)", "", meta["en"]))
    rep["SHORT_UPPER"] = upper_keep(meta["short"])  # VaR stays VaR
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
        joined = " ".join(by_shot.get(sh["id"], []))
        # shot text is the plan-level summary (manifest shotMaxChars 40); VO lines carry the full wording
        sh["text"] = (joined if len(joined) <= SHOT_MAX else by_shot[sh["id"]][0][:SHOT_MAX]) or sh["onScreenText"]
    plan["voice"]["lines"] = []
    for ln in L["lines"]:
        row = {"id": ln["id"], "role": ln["role"], "text": strip_cap(ln["cap"]), "cap": ln["cap"], "shotId": ln["shot"]}
        if ln.get("say"):
            row["say"] = ln["say"]
        plan["voice"]["lines"].append(row)
    plan["brand"] = term_brand(meta, L)
    if L.get("glossary"):
        plan["glossary"] = dict(L["glossary"])
    return plan, warns


def term_brand(meta: dict, L: dict) -> dict:
    """Per-term display strings for pictogram finance-v002: defaults ← CSV columns ← lines.json brand."""
    short = meta.get("short") or meta["zh"]
    b = {
        "eyebrow": meta.get("eyebrow") or area_eyebrow(meta.get("area", "")),
        "titleEn": short if short != meta["zh"] else upper_keep(re.sub(r"\s*\([^)]*\)", "", meta["en"]))[:48],
        "titleZh": meta["zh"],
        "endTitle": f"{meta['zh']} {short}" if short != meta["zh"] else meta["zh"],
        "sloganEn": upper_keep(re.sub(r"\s*\([^)]*\)", "", meta["en"]))[:48],
        "sloganZh": meta["zh"],
        "sloganJp": "",
    }
    for k in BRAND_CSV:
        if meta.get(k):
            b[k] = meta[k]
    for k, v in (L.get("brand") or {}).items():
        if k == "keepCase" or (isinstance(v, str) and v.strip()):
            b[k] = v
    return b


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


def latest_film(d: Path) -> Path:
    films = sorted(d.parent.glob(f"{d.name}-v[0-9][0-9][0-9]"))
    return films[-1] if films else d.parent / f"{d.name}-v001"


def term_state(d: Path) -> str:
    src = d / "src"
    q = latest_film(d) / "quality.json"
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


def cmd_build(a: argparse.Namespace) -> int:
    """Plan + build every approved term in turn (never in parallel: ASR gates share the CPU)."""
    only = parse_ids(a.only)
    env = dict(os.environ, EL_BACKUP="1" if a.el_backup else os.environ.get("EL_BACKUP", "0"))
    bad = 0
    for d in sorted(Path(a.out).iterdir()):
        if not (d / "src" / "term.json").is_file():
            continue
        if only is not None and int(d.name.split("-")[0]) not in only:
            continue
        st = term_state(d)
        if st not in ("approved", "planned", "quality-FAIL"):
            print(f"skip {d.name}: {st}")
            continue
        if not (d / "src" / "plan.json").is_file() and cmd_plan(argparse.Namespace(term=str(d))):
            bad += 1
            continue
        film = a.version and d.parent / f"{d.name}-{a.version}" or latest_film(d)
        r = subprocess.run(["bash", str(TPL / "build_term.sh"), str(d), str(film)], env=env)
        bad += r.returncode != 0
        print(f"{'OK ' if r.returncode == 0 else 'FAIL'} {d.name} → {film}")
    return 1 if bad else 0


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
    b = sub.add_parser("build")
    b.add_argument("--out", required=True)
    b.add_argument("--only")
    b.add_argument("--version", help="film suffix, e.g. v002 (default: latest existing, else v001)")
    b.add_argument("--el-backup", action="store_true",
                   help="also render an ElevenLabs backup narration + <film>-el.mp4 (off by default)")
    a = ap.parse_args(argv)
    return {"init": cmd_init, "plan": cmd_plan, "status": cmd_status, "build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
