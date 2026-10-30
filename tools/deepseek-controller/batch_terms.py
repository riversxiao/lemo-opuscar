#!/usr/bin/env python3
"""FRM per-term template films (templates/finance-term/, see its STEPS.md).

  python3 batch_terms.py init   --csv /workspace/finance/frm_core100.csv --out /workspace/films/frm [--only 1,5-9] [--skip 42] [--lines 12]
  python3 batch_terms.py init-from-draft --draft /workspace/films/dialogue-drafts/<name>.lines.json --term <term-dir> \
                                     --approved-by "金融专家 …" [--meta <earlier term.json>] [--cards overrides.json]
  python3 batch_terms.py from-draft --draft /workspace/films/dialogue-drafts/<name>.lines.json --term <term-dir>
                                     # 台词教父 draft (read-only) → copy visual / voice / lang into <term>/src/lines.json
  python3 batch_terms.py plan   --term /workspace/films/frm/043-es           # after the expert fills + approves lines.json
  python3 batch_terms.py status --out /workspace/films/frm [--json]
  python3 batch_terms.py build  --out /workspace/films/frm [--only 43-50] [--el-backup]   # approved terms, one at a time
  bash templates/finance-term/build_term.sh /workspace/films/frm/043-es       # render + gates + handoffs

init writes <out>/<NNN>-<slug>/src/{term.json, lines.json} (lines skeleton; never overwrites an
existing lines.json). plan refuses until lines.json has approvedBy and every cap filled, then writes
src/{plan.json, BRIEF.md, FACTS.md} and validates. No LLM, no network, no TTS here.

Length (wen hao 2026-10-30): 5–14 lines with one card/shot per line group; plan shots are generated
from the cards and targetDurationSec is a ceiling by line count (≤7 → 40 s, 8–10 → 55 s, 11–14 → 75 s).

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

# Variable film length (wen hao 2026-10-30): line count follows concept difficulty — simple ~7 lines
# (~30 s), hard (VaR, CAPM) 10–14 lines (~45–60 s). targetDurationSec is a CEILING only (never pad);
# still one memory point per film, speed 1.0, pacing calm. lines.json "targetDurationSec" overrides
# the tier (clamped to DURATION_CEIL).
LINES_MIN, LINES_MAX = 5, 14
DURATION_CEIL = 75
DURATION_TIERS = ((7, 40), (10, 55), (LINES_MAX, DURATION_CEIL))  # (max lines, ceiling seconds)
# Card poses for the pictogram fallback (finance-v003 per-line scenes replace them); cycled for long films.
CARD_POSES = ("archery", "shooting", "highjump", "fencing", "rowing", "javelin", "climbing", "sailing",
              "discus", "polevault", "hurdles", "longjump")


def target_for(n_lines: int, override: object = None) -> int:
    """Duration ceiling by line count (tiers above); an explicit lines.json value wins, ≤ DURATION_CEIL."""
    if override not in (None, ""):
        return int(max(15, min(float(override), DURATION_CEIL)))
    for mx, sec in DURATION_TIERS:
        if n_lines <= mx:
            return sec
    return DURATION_CEIL


def shots_for(card_ids: list[str], turn_shots: set[str]) -> list[dict]:
    """One plan shot per card: first = hook/intro, second = chapter, last = payoff/finale,
    the shot holding the `turn` line = explain/hard-cut, all others = card (poses cycle)."""
    out, k = [], 0
    n = len(card_ids)
    for i, sid in enumerate(card_ids):
        if i == 0:
            sh = {"id": sid, "role": "hook", "motionPreset": "intro"}
        elif i == n - 1:
            sh = {"id": sid, "role": "payoff", "motionPreset": "finale", "pose": "relay"}
        elif i == 1:
            sh = {"id": sid, "role": "chapter", "motionPreset": "chapter"}
        elif sid in turn_shots:
            sh = {"id": sid, "role": "explain", "motionPreset": "hard-cut", "pose": "diving"}
        else:
            sh = {"id": sid, "role": "card", "motionPreset": "card", "pose": CARD_POSES[k % len(CARD_POSES)]}
            k += 1
        sh["beats"] = 4
        out.append(sh)
    return out


def skeleton_lines(n: int) -> dict:
    """lines.skeleton.json generalised to n lines/cards (L01 hook · … · turn at ~70 % · last payoff)."""
    if not LINES_MIN <= n <= LINES_MAX:
        raise SystemExit(f"--lines must be {LINES_MIN}..{LINES_MAX}")
    L = json.loads((TPL / "lines.skeleton.json").read_text("utf-8"))
    turn = max(2, round(n * 0.7) - 1)
    L["cards"] = L["cards"][:2] + [{"shot": f"p{i}", "zh": "", "en": ""} for i in range(2, n)]
    L["lines"] = [{"id": f"L{i + 1:02d}", "shot": f"p{i}", "cap": "",
                   "role": "hook" if i == 0 else "payoff" if i == n - 1 else "turn" if i == turn else "evidence"}
                  for i in range(n)]
    return L

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
            sk = (TPL / "lines.skeleton.json").read_text("utf-8") if a.lines == 7 else \
                json.dumps(skeleton_lines(a.lines), ensure_ascii=False, indent=2) + "\n"
            lp.write_text(_fill(sk, meta), "utf-8")
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
    nl = len(L.get("lines") or [])
    if not LINES_MIN <= nl <= LINES_MAX:
        errs.append(f"{nl} lines — finance-term supports {LINES_MIN}..{LINES_MAX} (one memory point per film)")
    card_ids = [str(c.get("shot")) for c in L.get("cards") or []]
    used = [ln.get("shot") for ln in L.get("lines") or []]
    if len(set(card_ids)) != len(card_ids):
        errs.append("cards: duplicate shot id")
    for sid in dict.fromkeys(used):
        if sid not in card_ids:
            errs.append(f"line shot {sid}: no card")
    for sid in card_ids:
        if sid not in used:
            errs.append(f"card {sid}: no line on this shot (every card carries ≥1 line)")
    if used != sorted(used, key=lambda x: card_ids.index(x) if x in card_ids else 0):
        errs.append("lines must follow the card order (shots in sequence)")
    if len(card_ids) < 3:
        errs.append("need ≥3 cards (intro, chapter…, finale)")
    if errs:
        raise SystemExit("plan refused:\n  " + "\n  ".join(errs))
    meta = dict(meta, approvedBy=L["approvedBy"], approvedAt=L.get("approvedAt", ""))
    plan = json.loads(_fill((TPL / "plan.skeleton.json").read_text("utf-8"), meta))
    # shots follow the cards (5–14 lines → matching cards); duration ceiling by line count
    turn_shots = {ln["shot"] for ln in L["lines"] if ln.get("role") == "turn"}
    plan["shots"] = shots_for(card_ids, turn_shots)
    plan["targetDurationSec"] = target_for(nl, L.get("targetDurationSec"))
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
        if ln.get("lang"):
            row["lang"] = ln["lang"]
        plan["voice"]["lines"].append(row)
    if L.get("voice"):   # from-draft: one narrator per film (bare id, `elevenlabs:` prefix stripped)
        plan["voice"]["voiceId"] = norm_voice(L["voice"])
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


LANGS = ("zh", "en", "mixed")


def norm_voice(v: object) -> str:
    """台词教父 drafts write `elevenlabs:<voice-id>`; the pipeline uses the bare id."""
    v = str(v or "").strip()
    if v.lower().startswith("elevenlabs:"):
        v = v.split(":", 1)[1].strip()
    return v


def cmd_from_draft(a: argparse.Namespace) -> int:
    """Copy the per-line `visual`, `voice` (one narrator) and optional `lang` from a 台词教父 draft
    into <term>/src/lines.json. The draft is read-only. Wording is locked: every draft text/say must
    equal the approved term line (cap without braces / say) — any difference refuses (no paraphrase)."""
    draft = json.loads(Path(a.draft).read_text("utf-8"))
    rows = draft if isinstance(draft, list) else draft.get("lines") or []
    lp = Path(a.term) / "src" / "lines.json"
    L = json.loads(lp.read_text("utf-8"))
    by_id = {x["id"]: x for x in L.get("lines") or []}
    errs, voices = [], set()
    for r in rows:
        x = by_id.get(r.get("id"))
        if x is None:
            errs.append(f"{r.get('id')}: not in term lines"); continue
        if strip_cap(x.get("cap") or "") != str(r.get("text") or ""):
            errs.append(f"{r['id']}: draft text ≠ approved cap ({r.get('text')!r} vs {strip_cap(x.get('cap') or '')!r})")
        if (r.get("say") or None) != (x.get("say") or None):
            errs.append(f"{r['id']}: draft say ≠ approved say")
        if r.get("lang") and r["lang"] not in LANGS:
            errs.append(f"{r['id']}: lang must be zh|en|mixed")
        if r.get("voice"):
            voices.add(norm_voice(r["voice"]))
    if len(voices) > 1:
        errs.append(f"more than one narrator voice in the draft: {sorted(voices)} (series = one voice)")
    if len(rows) != len(by_id):
        errs.append(f"draft has {len(rows)} lines, term has {len(by_id)}")
    if errs:
        print("from-draft refused (wording is locked — ask 台词教父/金融专家):\n  " + "\n  ".join(errs))
        return 1
    for r in rows:
        x = by_id[r["id"]]
        for k in ("visual", "lang"):
            if r.get(k):
                x[k] = r[k]
    if voices:
        L["voice"] = voices.pop()
    L["draft"] = str(Path(a.draft).resolve())
    lp.write_text(json.dumps(L, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"OK from-draft → {lp} ({len(rows)} lines, voice {L.get('voice', '-')})")
    return 0


ROLE_OF = {"hook": "hook", "evidence": "evidence", "turn": "turn", "payoff": "payoff"}


def lines_from_draft(draft_rows: list[dict], meta: dict, approved_by: str, approved_at: str,
                     cards: dict[str, dict] | None = None, brand: dict | None = None) -> dict:
    """Term lines.json from an APPROVED 台词教父 draft (list of {id,text,cap,function,say?,visual,voice,lang?}):
    one card/shot per line (p0…), cap/say copied verbatim (no paraphrase), card zh defaults to the {强调词}
    unless --cards overrides it. The draft is only read."""
    if not LINES_MIN <= len(draft_rows) <= LINES_MAX:
        raise SystemExit(f"draft has {len(draft_rows)} lines — finance-term supports {LINES_MIN}..{LINES_MAX}")
    cards = cards or {}
    out_lines, out_cards, voices = [], [], set()
    for i, r in enumerate(draft_rows):
        sid = f"p{i}"
        cap = str(r.get("cap") or r.get("text") or "")
        if strip_cap(cap) != str(r.get("text") or strip_cap(cap)):
            raise SystemExit(f"{r.get('id')}: draft cap ≠ text (fix in the draft, not here)")
        role = ROLE_OF.get(str(r.get("function") or r.get("role") or ""), None)
        if role is None:
            raise SystemExit(f"{r.get('id')}: function must be hook|evidence|turn|payoff")
        ln = {"id": r["id"], "role": role, "shot": sid, "cap": cap}
        for k in ("say", "visual", "lang"):
            if r.get(k):
                ln[k] = r[k]
        if r.get("voice"):
            voices.add(norm_voice(r["voice"]))
        out_lines.append(ln)
        em = re.findall(r"\{([^}]+)\}", cap)
        c = {"shot": sid, "zh": (em[0] if em else strip_cap(cap)[:12]), "en": ""}
        c.update(cards.get(sid) or cards.get(r["id"]) or {})
        out_cards.append(c)
    if len(voices) > 1:
        raise SystemExit(f"more than one narrator voice in the draft: {sorted(voices)}")
    L = {"_doc": "term lines from an approved 台词教父 draft (batch_terms.py init-from-draft); wording locked.",
         "seq": meta.get("seq", ""), "term": meta.get("en", ""), "zh": meta.get("zh", ""),
         "approvedBy": approved_by, "approvedAt": approved_at, "brand": brand or {}, "glossary": {},
         "cards": out_cards, "lines": out_lines}
    if voices:
        L["voice"] = voices.pop()
    return L


def cmd_init_from_draft(a: argparse.Namespace) -> int:
    term = Path(a.term)
    src = term / "src"
    draft_p = Path(a.draft).resolve()
    if "dialogue-drafts" in src.resolve().parts:
        raise SystemExit("refusing to write into the drafts folder")
    rows = json.loads(draft_p.read_text("utf-8"))
    rows = rows if isinstance(rows, list) else rows.get("lines") or []
    meta = json.loads(Path(a.meta).read_text("utf-8")) if a.meta else {}
    for k in ("seq", "en", "zh", "short", "area", "slug", "eyebrow"):
        if getattr(a, k, None):
            meta[k] = getattr(a, k)
    meta.setdefault("short", meta.get("zh", ""))
    meta.setdefault("eyebrow", area_eyebrow(meta.get("area", "")))
    extra = json.loads(Path(a.cards).read_text("utf-8")) if a.cards else {}
    L = lines_from_draft(rows, meta, a.approved_by, a.approved_at or "", extra.get("cards") or {}, extra.get("brand") or {})
    if extra.get("glossary"):
        L["glossary"] = extra["glossary"]
    L["draft"] = str(draft_p)
    src.mkdir(parents=True, exist_ok=True)
    lp = src / "lines.json"
    if lp.exists() and not a.force:
        raise SystemExit(f"{lp} exists (use --force to overwrite the term copy)")
    (src / "term.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", "utf-8")
    lp.write_text(json.dumps(L, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"OK init-from-draft → {lp} ({len(L['lines'])} lines/cards, ceiling {target_for(len(L['lines']))}s, "
          f"voice {L.get('voice', '-')})")
    return 0


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
    i.add_argument("--lines", type=int, default=7, help=f"lines/cards per term ({LINES_MIN}..{LINES_MAX}, default 7)")
    d = sub.add_parser("init-from-draft", help="term src/ from an approved 台词教父 draft (draft read-only)")
    d.add_argument("--draft", required=True)
    d.add_argument("--term", required=True)
    d.add_argument("--approved-by", required=True)
    d.add_argument("--approved-at")
    d.add_argument("--meta", help="term.json to start from (e.g. an earlier take of the same term)")
    d.add_argument("--cards", help="json {cards:{p0:{zh,en}}, brand:{…}, glossary:{…}} display overrides")
    for k in ("seq", "en", "zh", "short", "area", "slug", "eyebrow"):
        d.add_argument(f"--{k}")
    d.add_argument("--force", action="store_true")
    p = sub.add_parser("plan")
    p.add_argument("--term", required=True)
    f = sub.add_parser("from-draft")
    f.add_argument("--draft", required=True)
    f.add_argument("--term", required=True)
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
    return {"init": cmd_init, "init-from-draft": cmd_init_from_draft, "plan": cmd_plan, "from-draft": cmd_from_draft, "status": cmd_status, "build": cmd_build}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
