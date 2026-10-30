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
    # batch 8 (quant basics: volatility / correlation / covariance / linear regression / hypothesis test, 2026-10-30): before batch 7;
    # 回到开头的小船 before 小船, 吐出一张卡片+-1 到 1 before 进口塞进, β（贝塔） before 斜率, 虚线框 before 被抬起
    ("vol_boat_end",     [["回到开头的小船"]]),
    ("vol_boat",         [["小船"], ["坐得稳"]]),
    ("vol_title",        [["Volatility"]]),
    ("vol_band",         [["晃动幅度"]]),
    ("vol_devs",         [["平均线"], ["竖线"]]),
    ("vol_ab",           [["甲"], ["乙"], ["大幅摆动"]]),
    ("vol_scale",        [["刻度条更长"]]),
    ("vol_dblarrow",     [["上下双箭头"], ["两端一样长"]]),
    ("vol_ruler",        [["同一把尺子"]]),
    ("vol_end",          [["终点没有往下掉"]]),
    ("vol_fog",          [["前方的路"], ["雾"]]),
    ("corr_walkers",     [["并排同步走路"], ["问号"]]),
    ("corr_title",       [["Correlation"]]),
    ("corr_together",    [["同时上、同时下"]]),
    ("corr_ruler",       [["左端「-1」"]]),
    ("corr_plus1",       [["指针指向右端"]]),
    ("corr_minus1",      [["指针指向左端"]]),
    ("corr_zero",        [["指针在中间"]]),
    ("corr_queues",      [["冰淇淋柜"], ["空调"]]),
    ("corr_sun",         [["大太阳"]]),
    ("corr_nocause",     [["柜台之间"], ["打了个叉"]]),
    ("corr_slide",       [["往右端滑"]]),
    ("corr_balloons",    [["小气球"], ["下沉气流"]]),
    ("corr_downhill",    [["并排走路"], ["下坡"]]),
    ("cov_card_out",     [["吐出一张卡片"], ["-1 到 1"]]),
    ("cov_machine",      [["进口塞进"]]),
    ("cov_title",        [["Covariance"]]),
    ("cov_bracket",      [["括号框住"]]),
    ("cov_signs",        [["标「+」"]]),
    ("cov_units",        [["刻「元」"]]),
    ("cov_cards_big",    [["不同大数"]]),
    ("cov_wobble",       [["天平乱晃"]]),
    ("cov_cards_ruler",  [["整齐地排在同一根刻度尺上"]]),
    ("cov_machine_end",  [["回到那台机器"]]),
    ("reg_scatter",      [["满屏散落的小点"], ["穿过"]]),
    ("reg_title",        [["Linear Regression"]]),
    ("reg_candidates",   [["候选直线"]]),
    ("reg_xaxis",        [["横轴标「大盘收益」"]]),
    ("reg_yaxis",        [["竖轴标"]]),
    ("reg_dots_fill",    [["一个接一个落下"], ["坐标图"]]),
    ("reg_beta",         [["β（贝塔）"]]),
    ("reg_slope",        [["小台阶"], ["斜率"]]),
    ("reg_step15",       [["走一格半"]]),
    ("reg_oldphoto",     [["泛黄的旧照片"]]),
    ("reg_fog",          [["延伸进一团雾"], ["新落下的点"]]),
    ("reg_summary",      [["直线上写「总结」"]]),
    ("hyp_scale",        [["法庭式的天平"]]),
    ("hyp_title",        [["Hypothesis Testing"]]),
    ("hyp_backtest",     [["虚构策略"]]),
    ("hyp_coin",         [["硬币在空中翻转"]]),
    ("hyp_hill",         [["随机结果堆成小山"]]),
    ("hyp_pval",         [["「p 值」"]]),
    ("hyp_scale_glow",   [["那一边亮起"]]),
    ("hyp_tail_shade",   [["小山边上那一小块被涂色"]]),
    ("hyp_two_cards",    [["两张卡片"], ["打勾"], ["打叉"]]),
    ("hyp_warn",         [["警示三角"]]),
    ("hyp_dashed",       [["虚线框"]]),
    ("hyp_lift",         [["「没效果」那一边被抬起"]]),
    ("hyp_fog",          [["回测线延伸进雾里"]]),
    ("hyp_end",          [["回到天平"]]),
    # batch 7 (three lines / Barings / LTCM long / normal distribution / fat tails, 2026-10-30): before batch 5;
    # 卡在深坑 before 深坑, 隔板被拿走 before 隔板, 三道全开着 / 三道闸门亮灯 before 三道闸门, LTCM 墙 before LTCM 标题, 回到日历 before 日历
    ("gates_dark",       [["三道全开着"]]),
    ("gates_catch",      [["三道闸门亮灯"]]),
    ("gates_title",      [["Three Lines"]]),
    ("gate_audit",       [["第三道闸门"], ["记录本"]]),
    ("gates_three",      [["通道"], ["三道闸门"]]),
    ("gate_worker",      [["业务员"], ["风险表"]]),
    ("gate_tower",       [["观察台"], ["望远镜"]]),
    ("gate_locks",       [["独立的锁"], ["钥匙"]]),
    ("desk_merge",       [["隔板被拿走"]]),
    ("desk_split",       [["隔板"], ["分成两边"]]),
    ("oldbank_gate",     [["老楼"], ["只剩一道闸门"]]),
    ("bank_crack",       [["老银行大楼"], ["裂缝"]]),
    ("bank_plate",       [["门牌"], ["巴林银行"]]),
    ("desk_leeson",      [["Nick Leeson"]]),
    ("nikkei_board",     [["日经225"]]),
    ("ledger_drawer",    [["账簿"], ["小抽屉"]]),
    ("drawer_88888",     [["88888"]]),
    ("two_hands",        [["左手下单"], ["盖章"]]),
    ("empty_chair",      [["空椅子"]]),
    ("quake_map",        [["神户"], ["震波"]]),
    ("snowball_down",    [["雪球"], ["下坡"]]),
    ("pounds_sink",      [["亿英镑"]]),
    ("capital_floor",    [["银行资本"], ["地板线"]]),
    ("coin_keys",        [["一英镑硬币"]]),
    ("car_stuck",        [["仪表车"], ["卡在深坑"]]),
    ("gauge_car",        [["仪表车"], ["深坑"]]),
    ("wall_push",        [["LTCM"], ["推倒"]]),
    ("ltcm_title",       [["写字楼"], ["LTCM"]]),
    ("manual_wave",      [["模型手册"], ["大浪"]]),
    ("medal_manual",     [["奖章"], ["模型手册"]]),
    ("gap_lines",        [["并拢的线"]]),
    ("lever_rock",       [["撬棍撬起"]]),
    ("coins_25",         [["二十五枚"]]),
    ("iou_torn",         [["欠条"]]),
    ("gap_widen",        [["缝隙"], ["越撕越宽"]]),
    ("rock_drop",        [["撬棍反弹"]]),
    ("ring_14",          [["十四个"], ["围成一圈"]]),
    ("hand_catch",       [["大手接住"]]),
    ("balls_pile",       [["小球从上方落下"]]),
    ("normal_title",     [["Normal Distribution"]]),
    ("bell_outline",     [["轮廓"], ["钟形曲线"]]),
    ("bell_peak",        [["普通的一天"]]),
    ("bell_tails",       [["左尾"], ["右尾"]]),
    ("calc_bell",        [["计算器上贴着"]]),
    ("calc_tick",        [["计算器"], ["打勾"]]),
    ("calc_crack",       [["计算器"], ["裂缝"]]),
    ("dots_outliers",    [["真实数据点"]]),
    ("tail_shadow",      [["阴影加厚"]]),
    ("calendar_two",     [["回到日历"]]),
    ("calendar_circled", [["日历"], ["圈了好几次"]]),
    ("fat_title",        [["Fat Tails"]]),
    ("thin_bell",        [["细尾巴"], ["贴着地面"]]),
    ("balls_ends",       [["数据小球"], ["两端"]]),
    ("tails_overlay",    [["细尾虚线"]]),
    ("left_tail_drag",   [["左侧亏损尾巴"]]),
    ("threshold_q",      [["门槛竖线"], ["问号"]]),
    ("tail_zoom",        [["粗尾区域"], ["颜色加深"]]),
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
    # batch 6 (risk family: systematic / unsystematic / APT long / moral hazard / adverse selection, 2026-10-30):
    # two-group rules on distinctive nouns, before batch 3 (尺子/格子/账本) and batch 2 (旋钮/小船/篮子/冒烟/问号)
    ("umbrella_look",   [["破伞"], ["抬头"]]),
    ("umbrella_holes",  [["伞面破洞", "大伞"], ["漏下来"]]),
    ("sea_title",       [["标题"], ["一整片海面"]]),
    ("boats_split",     [["船漏水"], ["大浪"]]),
    ("boats_sink",      [["一排小船"], ["往下沉"]]),
    ("street_dim",      [["街灯"], ["购物车"]]),
    ("gears_dial",      [["旋钮"], ["小齿轮"]]),
    ("lines_offset",    [["几条线"], ["总线"]]),
    ("lines_bundle",    [["几条线"], ["挤成一束"]]),
    ("net_holes",       [["安全网"], ["网眼"]]),
    ("pits_fill",       [["碎石块"], ["小坑"]]),
    ("rock_split",      [["石头"], ["碎块"]]),
    ("shop_street",     [["标题"], ["几家小店"]]),
    ("tea_sign",        [["奶茶店"], ["招牌"]]),
    ("shutter_down",    [["卷帘门"]]),
    ("basket_break",    [["只提一个篮子"], ["破了"]]),
    ("ten_baskets",     [["十个小篮子"], ["漏了"]]),
    ("hooks_colors",    [["十个篮子"], ["钩子"]]),
    ("wind_baskets",    [["大风"], ["十个篮子"]]),
    ("dial_all",        [["回到仪表盘"], ["指针"]]),
    ("dial_needles",    [["仪表盘"], ["指针"]]),
    ("mixer_title",     [["标题"], ["调音台"]]),
    ("ruler_fog",       [["尺子"], ["调音台"]]),
    ("mixer_one",       [["调音台"], ["只有一个推子"]]),
    ("mixer_faders",    [["调音台"], ["多出几个推子"]]),
    ("faders_sum",      [["推子的读数"], ["总数"]]),
    ("receipt_jar",     [["购物小票"], ["存钱罐"]]),
    ("rope_strain",     [["借款绳"]]),
    ("cars_road",       [["几辆小车"], ["路速"]]),
    ("springs",         [["弹簧"], ["粗细"]]),
    ("apple_stalls",    [["苹果"], ["摊位"]]),
    ("tags_converge",   [["摊位的价签"], ["靠拢"]]),
    ("mover_slip",      [["搬运的人"], ["脚下一滑"]]),
    ("footprints_edge", [["脚印"], ["靠边"]]),
    ("net_step",        [["大网"], ["迈了一步"]]),
    ("policy_title",    [["标题"], ["保单"]]),
    ("deductible",      [["保单上"], ["双手握"]]),
    ("car_lane",        [["车道线"], ["单手"]]),
    ("care_bar",        [["「小心」"], ["进度条"]]),
    ("airbag_tower",    [["气垫"], ["越盖越歪"]]),
    ("coins_bricks",    [["金币"], ["砖"]]),
    ("timeline_after",  [["时间线"], ["先签字"]]),
    ("timeline_before", [["时间线"], ["签字之前"]]),
    ("queue_front",     [["回到开头的门口队伍"]]),
    ("door_queue",      [["门口排队"], ["最着急"]]),
    ("door_title",      [["标题"], ["半开的门"]]),
    ("counter_cough",   [["保险柜台"], ["咳嗽"]]),
    ("price_jump",      [["价签往上跳"]]),
    ("queue_leave",     [["摇头离开"]]),
    ("two_keys",        [["两把钥匙"]]),
    ("magnifier_mid",   [["放大镜"], ["报价牌"]]),
    ("cars_leave",      [["亮车"], ["锈车"]]),
    ("table_light",     [["桌子"], ["灯很亮"]]),
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
    (r"(?<!不出现)(?<!不画)(?<!没有)[Kk]\s*线|蜡烛图|截图|行情软件|行情截图", "K-line / screenshot"),  # negated mentions (「不出现K线」) are a drawing instruction, not a K-line
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
