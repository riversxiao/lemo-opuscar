#!/usr/bin/env python3
"""Per-line `visual` → pictogram scene spec (style version finance-v003) + content-visual lint.

Reads the term's approved lines.json (each line carries `visual`, copied from 台词教父's draft —
the drafts folder itself is read-only), picks one scene from the local vector library per line
(SCENES below; drawn by styles/pictogram-motion/versions/finance-v003/scenes.js), generates the
deterministic data the scene draws (line series, bars, …) and writes:

  <project>/content/viz.json            {shots:[{shot, line, visual, scene, params, data}]}
  <project>/evidence/visual-content.json  content-visual lint (金融专家 rules)

Lint (FAIL):
  · real tickers / fund names / K-line screenshots (股票代码, 6-digit codes, $TICK, XX基金, K线, 截图…)
  · a monotonically rising curve that implies returns (every drawn curve must also go down)
  · gambling imagery (筹码/赌场/赌桌/骰子/老虎机/casino/chips/poker…)
  · a visual no scene can draw, or two lines of one film on the same scene id

Usage:
  python3 viz_pick.py --lines <term>/src/lines.json --project <film> [--override L01='…']
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

# ───────── scene library (keyword rules, first match wins; most specific first) ─────────
# Each rule: (scene id, all-of keyword groups). A group matches when any of its words occurs.
RULES: list[tuple[str, list[list[str]]]] = [
    # batch 5 (Sharpe long, 13 lines, 2026-10-30): before batch 4 (柱子/尺子) and batch 2 (篮子/账本/问号/尺子)
    ("bag_pillars",    [["柱子"], ["沙袋"]]),
    ("sandbags",       [["小沙袋", "大沙袋"], ["手里", "拿着"]]),
    ("coin_stack",     [["一份晃动"], ["硬币"]]),
    ("score_fill",     [["记分卡"], ["分数格"]]),
    ("card_fog",       [["记分卡"], ["雾"]]),
    ("score_sharpe",   [["记分卡"], ["卡头"]]),
    ("twin_q",         [["两根一样高"], ["问号"]]),
    ("baskets_8",      [["两个篮子"], ["甲"], ["+8%"]]),
    ("calm_wild",      [["两条收益线"], ["大起大落"]]),
    ("pillars_cut",    [["柱子"], ["切下", "切掉一小段"], ["国债"]]),
    ("remain_six",     [["切掉底部", "剩下的两段"], ["+6%"]]),
    ("swing_box",      [["双箭头"], ["晃动"]]),
    ("ruler_chair",    [["尺子"], ["椅子"]]),
    # batch 4 (CAPM long, 13 lines, 2026-10-30): before batch 3 (预期/实际) and batch 2 (天平/尺子/冒烟)
    ("balance_settle", [["天平"], ["稳稳", "躲不掉"]]),
    ("balance_half",   [["天平"], ["翘起一半", "只翘起"], ["「风险」"]]),  # capm-v001 says 「冒险」 → scale_half
    ("ruler_crystal",  [["尺子"], ["水晶球"]]),
    ("ruler_capm",     [["尺子"], ["一头刻"]]),
    ("split_smoke",    [["一分为二"], ["冒烟"]]),
    ("row_dilute",     [["一整排", "一排小楼"], ["稀释"]]),
    ("all_sink",       [["小楼再多", "全都跟着沉", "一栋也没躲开"]]),
    ("ground_sink",    [["整片地面", "地面一起下沉"], ["下沉"]]),
    ("empty_box",      [["奖励盒", "空的盒"]]),
    ("expect_dashed",  [["柱子"], ["虚线"]]),
    ("pillar_wiggle",  [["柱子"], ["晃动的曲线", "晃得越猛"]]),
    ("pillar_base",    [["柱子"], ["底下那段", "起步价"]]),
    ("pillar_split",   [["柱子"], ["上下两段", "分界线"]]),
    # batch 3 (VaR long, 14 lines, 2026-10-30): most specific first — before 账本/门槛线/格子/平均 below
    ("bank_on_line",   [["银行大楼"], ["门槛线"]]),
    ("bank_report",    [["银行大楼", "银行"], ["报告卡", "报告"]]),
    ("cap_crossed",    [["上限"], ["叉"]]),
    ("slots_filled",   [["三个格子", "三格"], ["填上", "填入"]]),
    ("three_slots",    [["三个格子", "三格"], ["亮起", "依次"]]),
    ("grid_10x10",     [["十乘十", "10×10", "10x10"]]),
    ("square_over",    [["红色方块", "红方块"], ["越过", "超过", "冲过"]]),
    ("year_strip",     [["一整年", "二百五十格", "两百五十格", "250格"]]),
    ("red_cluster",    [["挤在一起", "扎堆", "连着亮"]]),
    ("bottomless",     [["没有底", "看不到头", "无底"]]),
    ("old_ledger",     [["旧账本"]]),
    ("sky_change",     [["天色", "变天"], ["门槛线", "线"]]),
    ("expect_actual",  [["预期"], ["实际"]]),
    ("tail_dots_es",   [["预期尾部损失", "ES"], ["平均"]]),
    # batch 2 (CAPM / ERM / VaR plain / 风险偏好): specific nouns first so 「部门小格子」 ≠ step_blocks
    ("beam_hold",      [["秤杆"]]),
    ("scale_half",     [["天平"], ["一半", "翘起"]]),
    ("ruler",          [["尺子"]]),
    ("rain_wind",      [["小雨"], ["大风"]]),
    ("one_egg",        [["只有一个鸡蛋"]]),
    ("many_eggs",      [["很多鸡蛋"]]),
    ("basket_wave",    [["篮子"], ["打翻"]]),
    ("wave_tag",       [["该多要回报"]]),
    ("dept_smoke",     [["冒烟"]]),
    ("frame_gather",   [["收拢", "大框"]]),
    ("ledgers_merge",  [["账本"]]),
    ("bag_shield",     [["盾"]]),
    ("car_pedals",     [["油门"], ["手刹"]]),
    ("round_table",    [["圆桌"]]),
    ("big_number_x",   [["打叉"]]),
    ("dark_below",     [["问号"]]),
    ("tail_avg",       [["平均"]]),
    ("red_breach",     [["冲破"]]),
    ("calendar_100",   [["日历"]]),
    ("days_below",     [["日子方块"]]),
    ("threshold_line", [["门槛线"]]),
    ("platform_rope",  [["高台"]]),
    ("knob",           [["旋钮"]]),
    ("hand_line",      [["举手"]]),
    ("bag_split",      [["钱袋"], ["分成", "两堆"]]),
    ("ground_shake",   [["地面"], ["晃"]]),
    ("carry_pole",     [["扁担"]]),
    ("bed_awake",      [["床"]]),
    ("coaster",       [["过山车"]]),
    ("boat",          [["小船"]]),
    ("waves",         [["大浪", "小浪"], ["压过", ">1", "＞1"]]),
    ("mirror_updown", [["对称"], ["涨", "冲"], ["跌", "砸"]]),
    ("step_blocks",   [["格子", "一格", "两格"]]),
    ("swing_label",   [["振幅"], ["标出", "标"]]),
    ("plunge",        [["下坠", "猛地", "一大截"]]),
    # add rules + a draw function in finance-v003/scenes.js (G.VIZ) for each new scene id
]

# On-screen-free, content-visual lint (金融专家)
BANNED: list[tuple[str, str]] = [
    (r"股票代码|代码\s*\d|\b\d{6}\b|\$[A-Z]{1,5}\b|\b[A-Z]{1,5}\.(?:US|HK|SH|SZ)\b", "real ticker / stock code"),
    (r"[\u4e00-\u9fff]{2,8}(?:基金|ETF)(?!经理)", "named fund"),
    (r"[Kk]\s*线|蜡烛图|截图|行情软件|行情截图", "K-line / screenshot"),
    (r"筹码|赌场|赌桌|赌博|骰子|老虎机|轮盘|扑克|casino|chips?\b|poker|roulette|slot machine", "gambling imagery"),
    (r"一路上涨|持续上涨|只涨不跌|必涨|稳赚|稳赢|翻倍", "return-implying rise"),
]
# allowed: generic "基金" alone (not a fund name)


def pick_scene(visual: str) -> str | None:
    v = visual or ""
    for sid, groups in RULES:
        if all(any(w in v for w in g) for g in groups):
            return sid
    return None


def _wiggle(n: int, seed: int, amp: float) -> list[float]:
    return [amp * (0.55 * math.sin(i * 0.9 + seed) + 0.45 * math.sin(i * 2.3 + seed * 1.7)) for i in range(n)]


def scene_data(scene: str, line_id: str) -> dict[str, Any]:
    """Deterministic data for line/bar scenes. y up = positive; units are 'grid cells'."""
    N = 48
    if scene == "plunge":
        base = _wiggle(N, 3, 0.25)
        k0 = 30
        mkt = [b * 0.6 - (0 if i < k0 else 0.9 * min(1, (i - k0) / 6)) for i, b in enumerate(base)]
        stk = [b * 1.1 - (0 if i < k0 else 3.6 * min(1, (i - k0) / 5)) for i, b in enumerate(base)]
        return {"curves": {"market": mkt, "stock": stk}, "dropAt": k0 / (N - 1)}
    if scene == "swing_label":
        mkt = [0.9 * math.sin(i / (N - 1) * 2 * math.pi * 2.5) for i in range(N)]
        stk = [2.4 * math.sin(i / (N - 1) * 2 * math.pi * 2.5) for i in range(N)]
        return {"curves": {"market": mkt, "stock": stk}}
    if scene == "step_blocks":
        # market moves one cell, the stock two — shown up AND down (beta works both ways)
        return {"market": [1, -1], "stock": [2, -2]}
    if scene == "waves":
        return {"curves": {"small": [0.8 * math.sin(i / (N - 1) * 2 * math.pi * 2) for i in range(N)],
                           "big": [2.2 * math.sin(i / (N - 1) * 2 * math.pi * 2 - 0.4) for i in range(N)]}}
    if scene == "boat":
        return {"curves": {"water": [0.35 * math.sin(i / (N - 1) * 2 * math.pi * 3) for i in range(N)]}}
    if scene == "mirror_updown":
        half = N // 2
        up = [2.6 * math.sin(i / (half - 1) * math.pi / 2) for i in range(half)]
        stk = up + [up[-1] - 5.2 * math.sin(i / (N - half - 1) * math.pi / 2) for i in range(N - half)]
        mkt = [v * 0.4 for v in stk]
        return {"curves": {"market": mkt, "stock": stk}, "peakAt": (half - 1) / (N - 1)}
    if scene == "coaster":
        trk = [0.4 * math.sin(i * 0.5) for i in range(18)] + [0.4 * math.sin(17 * 0.5) + 2.4 * math.sin((i + 1) / 14 * math.pi / 2) for i in range(14)]
        top = trk[-1]
        trk += [top - 5.0 * (1 - math.cos((i + 1) / 16 * math.pi)) / 2 for i in range(16)]
        return {"curves": {"track": trk}, "stopAt": 31 / (len(trk) - 1)}
    return {}


def rising_only(curve: list[float]) -> bool:
    """True when a curve never goes meaningfully down (implies 'it only goes up')."""
    if len(curve) < 2:
        return False
    rng = (max(curve) - min(curve)) or 1e-9
    drop = 0.0
    peak = curve[0]
    for v in curve:
        peak = max(peak, v)
        drop = max(drop, peak - v)
    return curve[-1] > curve[0] and drop < 0.1 * rng


def lint(shots: list[dict[str, Any]], strings: list[str]) -> list[dict[str, str]]:
    issues = []
    for sh in shots:
        for rx, why in BANNED:
            if re.search(rx, sh.get("visual") or "", flags=re.I):
                issues.append({"line": sh["line"], "rule": why, "text": sh["visual"]})
        if not sh.get("scene"):
            issues.append({"line": sh["line"], "rule": "no scene in library", "text": sh.get("visual") or ""})
        for name, c in ((sh.get("data") or {}).get("curves") or {}).items():
            if rising_only(c):
                issues.append({"line": sh["line"], "rule": "monotonically rising curve implies returns", "text": name})
    seen: dict[str, str] = {}
    for sh in shots:
        s = sh.get("scene")
        if s and s in seen:
            issues.append({"line": sh["line"], "rule": f"duplicate scene in film (same as {seen[s]})", "text": s})
        elif s:
            seen[s] = sh["line"]
    for t in strings:
        for rx, why in BANNED:
            if re.search(rx, t or "", flags=re.I):
                issues.append({"line": "-", "rule": why + " (on-screen text)", "text": t})
    return issues


def build(lines_p: Path, project: Path | None, overrides: dict[str, str]) -> dict[str, Any]:
    L = json.loads(lines_p.read_text("utf-8"))
    lines = L["lines"] if isinstance(L, dict) else L
    shots = []
    for i, ln in enumerate(lines):
        vis = overrides.get(ln["id"], ln.get("visual") or "")
        scene = ln.get("scene") or pick_scene(vis)
        shots.append({"shot": ln.get("shot") or f"p{i}", "line": ln["id"], "visual": vis,
                      "overridden": ln["id"] in overrides, "scene": scene,
                      "data": scene_data(scene, ln["id"]) if scene else {}})
    strings = []
    if isinstance(L, dict):
        strings += [str(v) for v in (L.get("brand") or {}).values() if isinstance(v, str)]
        strings += [str(c.get(k) or "") for c in L.get("cards") or [] for k in ("zh", "en")]
    issues = lint(shots, strings)
    rep = {"status": "FAIL" if issues else "PASS", "styleVersion": "finance-v003", "issues": issues,
           "scenes": {s["line"]: s["scene"] for s in shots}, "source": str(lines_p)}
    if project:
        (project / "content").mkdir(parents=True, exist_ok=True)
        (project / "evidence").mkdir(parents=True, exist_ok=True)
        (project / "content" / "viz.json").write_text(json.dumps({"styleVersion": "finance-v003", "shots": shots},
                                                                 ensure_ascii=False, indent=1) + "\n", "utf-8")
        (project / "evidence" / "visual-content.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", "utf-8")
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lines", required=True)
    ap.add_argument("--project")
    ap.add_argument("--override", action="append", default=[], help="L01='new visual' (term-copy override)")
    a = ap.parse_args(argv)
    ov = dict(x.split("=", 1) for x in a.override)
    rep = build(Path(a.lines), Path(a.project).resolve() if a.project else None, ov)
    print(f"visual-content {rep['status']}: " + ", ".join(f"{k}→{v}" for k, v in rep["scenes"].items()))
    for i in rep["issues"]:
        print(f"  FAIL {i['line']}: {i['rule']} — {i['text']}")
    return 0 if rep["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
