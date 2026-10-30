#!/usr/bin/env python3
"""finance-v003 batch-10 scenes (no network): kurtosis / forward / futures / swap / option-long visuals → 64 distinct drawn
scenes, distinct from every delivered film's scenes and from batches 5–9, content lint clean, no formulas, tickers, real
contracts, lottery or gambling imagery; 「峰度=3，超额峰度=0」 only as one on-screen note; leverage drawn amplifying BOTH gains
and losses; the option buyer's loss stops at a plate (premium), the seller's has none; losses drawn down; and every earlier
film (snapshot + Sharpe + batches 6–9) keeps its scenes."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

CTL = Path(__file__).resolve().parents[1]
REPO = CTL.parents[1]
sys.path[:0] = [str(CTL)]
import viz_pick as VP  # noqa: E402

n = 0


def ok(c, m):
    global n
    if not c:
        print("FAIL:", m)
        sys.exit(1)
    n += 1
    print("ok", m)


FILMS = {
    "kurtosis-v001": (
        ["两座一样高的小山并排，一座的两侧尾巴明显更粗", "屏幕标题「Kurtosis」", "两条尾巴的最外端各亮起几个小点", "放大镜对准山顶，上面打一个问号", "放大镜从山顶移到两侧尾巴", "一条标准钟形曲线作参照，角标「峰度=3，超额峰度=0」（只上画面）", "参照曲线旁边，另一条曲线的两条尾巴逐渐变粗", "左侧亏损尾巴里的点往下落，右侧尾巴里的点往上冒，都比参照曲线更多", "复用偏度那座歪向一边的小山，一个箭头指向拖长的一侧", "一把卡尺卡住尾巴，量它的粗细", "一个指南针和一把卡尺并排放在小山前", "回到两座一样高的小山，镜头往下移，两条尾巴粗细差别一目了然"],
        ["kurt_twins", "kurt_title", "kurt_dots", "kurt_peak", "kurt_lens", "kurt_base", "kurt_fatten", "kurt_extremes", "kurt_skew", "kurt_caliper", "kurt_tools", "kurt_end"]),
    "forward-v001": (
        ["两个人握手，背后的日历翻到半年后", "屏幕标题「Forward」，一张手写的约定书", "麦田一边站着农民，另一边是面粉厂，角标「假设」", "约定书上写下一个价格数字，旁边一袋麦子", "两人只签字，桌上没有钱", "约定书上的条款像裁缝量身一样被改写", "市场价格线往下沉到约定价下方，农民仍拿到约定价那条线", "市场价格线升到约定价上方，农民手里还是原来那个价", "一把锁同时锁住了往上和往下两个箭头", "约定日到了，面粉厂门口挂出「暂停收购」的牌子", "两人之间空出一块，没有第三方", "回到那把锁：价格被锁住，锁链另一头的人却在走开"],
        ["fwd_shake", "fwd_title", "fwd_field", "fwd_price", "fwd_sign", "fwd_tailor", "fwd_low", "fwd_high", "fwd_lock", "fwd_closed", "fwd_gap", "fwd_lock_end"]),
    "futures-v001": (
        ["上一条那张手写约定书，变成一张张一模一样的印刷单，排进大厅", "屏幕标题「Futures」，不出现任何真实合约名称或代码", "一排完全相同的单子，标着同样的数量和日期", "买卖双方中间站着一个第三方，左右各牵一根线", "一个小保险箱被放进柜台", "日历每翻一页，账户里的数字就更新一次，有加有减", "小保险箱旁边，是一整栋合约价值的大楼轮廓", "一根杠杆，一头往上翘，另一头往下压得一样深", "价格线往不利方向下沉一格，角标「假设」", "小保险箱里的钱一下子见底", "账户亮起提醒，旁边一只手准备合上账户", "回到那根杠杆：上下两个方向的箭头一样长"],
        ["fut_print", "fut_title", "fut_same", "fut_clear", "fut_safe", "fut_daily", "fut_building", "fut_lever", "fut_tenth", "fut_empty", "fut_call", "fut_lever_end"]),
    "swap-v001": (
        ["两栋写字楼之间架起一条传送带", "屏幕标题「Swap」", "传送带上排着一长串小信封，一直延伸到远处", "信封上分别印着「固定」和「浮动」", "甲公司楼前一根上下起伏的利率线，角标「假设」", "甲公司付出的信封一个比一个厚", "乙公司楼前的牌子翻了个面", "从甲到乙的传送带上，信封大小一模一样", "从乙到甲的传送带上，信封忽大忽小", "甲公司楼前那根起伏的线，被拉成一条平线", "两家公司的保险柜都锁着没动，只有信封在传送带上来回", "回到两栋楼之间：信封来回传，保险柜原地不动"],
        ["swap_belt", "swap_title", "swap_envs", "swap_labels", "swap_float", "swap_thick", "swap_flip", "swap_fixed", "swap_floating", "swap_flat", "swap_safes", "swap_end"]),
    "option-long-v001": (
        ["一张门票被递出，上面写着「权利」", "屏幕标题「Option」，不出现任何真实合约名称或代码", "买方把一小袋钱交给卖方，袋子上标「权利金」", "门票上写「可以」，不写「必须」", "一扇门，门口的人可以走进去，也可以转身离开", "一张绿色门票，上面画着「买入」", "一张橙色门票，上面画着「卖出」", "一条价格线升到一百二，约定价一百画一条虚线，角标「假设」", "买方拿着绿色门票，按虚线的价格接过货物", "二十的差价柱子上，被切掉一小段标「权利金」", "价格线沉到八十，买方把门票放回口袋，转身离开", "损失只到那一小袋钱为止，下方有一块挡板", "镜头转到卖方，手里拿着那一小袋钱", "买方递出门票，卖方必须交货", "卖方脚下的亏损线一直往下延伸，看不到挡板", "左右对比：买方下方有挡板，卖方下方没有"],
        ["opt_ticket", "opt_title", "opt_premium", "opt_can", "opt_door", "opt_call", "opt_put", "opt_120", "opt_buyin", "opt_cut", "opt_80", "opt_floor", "opt_seller", "opt_deliver", "opt_noflr", "opt_compare"]),
}
sj = (REPO / "styles" / "pictogram-motion" / "versions" / "finance-v003" / "scenes.js").read_text("utf-8")
B10 = []
for fid, (vis, want) in FILMS.items():
    got = [VP.pick_scene(v) for v in vis]
    ok(got == want and len(set(got)) == len(vis), f"{fid}: {len(vis)} visuals → {len(vis)} distinct batch-10 scenes")
    shots = [{"line": f"L{i + 1:02d}", "visual": vis[i], "scene": s, "data": VP.scene_data(s, f"L{i + 1:02d}")} for i, s in enumerate(got)]
    ok(VP.lint(shots, vis) == [], f"{fid}: lint clean (no tickers/fund names/K-lines/gambling/rising-only/dupes)")
    B10 += want
ok(len(FILMS["option-long-v001"][0]) == 16, "option-long has 16 lines (premium deduction after L09)")
ok(len(B10) == 64 and len(set(B10)) == 64, "64 batch-10 scenes, unique across the 5 films")
ok(all(f"VIZ.{s} =" in sj and re.search(rf"\b{s}: '", sj) for s in B10), "every batch-10 scene drawn + palette in finance-v003 scenes.js")
b10 = sj[sj.index("finance-v003 scene library, batch 10"):sj.index("finance-v003 scene library, batch 4")]
code = "\n".join(l.split("//")[0] for l in b10.split("\n"))  # drawn strings only, not comments
ok(not re.search(r"基金|ETF|筹码|赌|骰|扑克|轮盘|赌场|彩票|中奖|σ|Σ|÷|√|公式|值得买|稳赚|机会大|K线|β|小钱|撬", code), "batch-10 scene text: no formulas, funds, gambling, lottery, K-lines, buy-signals or 小钱撬大钱")
ok(not re.search(r"'[A-Z]{1,4}\d{2,4}'|代码", code), "no contract codes drawn")
ok(code.count("峰度=3") == 1 and "'峰度=3，超额峰度=0'" in code, "峰度=3，超额峰度=0 drawn exactly once, as the reference note")
for t in ("'Kurtosis'", "'Forward'", "'Futures'", "'Swap'", "'Option'"):
    ok(f"b6title(ctx, {t}" in code, f"screen title {t} via b6title")
ok("'盈利放大'" in code and "'亏损也放大'" in code and "'两个方向'" in code, "leverage: gains AND losses amplified, both directions")
ok(code.count("b6upArrow(ctx, 520, 700, 420") == 1 and code.count("b6down(ctx, 520, 820, 1000") == 1, "lever end: up and down arrows of equal length")
ok("b10plate(ctx, 760, 1160" in code and "'买方：有上限'" in code and "'卖方：未必有'" in code, "option: buyer floor plate at the premium, seller has none")
ok("'权利金'" in code and "'可以'" in code and "'必须'" in code, "option = a paid right (权利金), 可以 not 必须")
ok("'面粉厂'" in code and "'通常没人担保'" in code and "'暂停收购'" in code, "forward: fictional mill, counterparty default risk")
ok("'本金一般不交换'" in code, "swap: principal usually not exchanged")
r = subprocess.run(["node", "-e", f"new Function(require('fs').readFileSync({json.dumps(str(REPO / 'styles/pictogram-motion/versions/finance-v003/scenes.js'))},'utf8'))"], capture_output=True)
ok(r.returncode == 0, "finance-v003 scenes.js parses")
helpers = re.findall(r"^  (?:function|const) ([A-Za-z0-9_]+)", sj, re.M)
ok(len(helpers) == len(set(helpers)), "no duplicate helper names in scenes.js")

snap = json.loads((CTL / "fixtures" / "viz-scene-snapshot.json").read_text("utf-8"))["films"]
old_scenes = {x["scene"] for rows in snap.values() for x in rows}
B5 = ["twin_q", "score_sharpe", "baskets_8", "calm_wild", "pillars_cut", "remain_six", "swing_box", "sandbags",
      "coin_stack", "score_fill", "card_fog", "ruler_chair", "bag_pillars"]


def scenes_of(t):
    src = (CTL / "tests" / t).read_text("utf-8")
    xs = re.findall(r'"([a-z0-9_]+)"', src[src.index("FILMS = {"):src.index("sj = (REPO")])
    return [x for x in xs if not x.endswith("-v001")]


B6, B7, B8 = scenes_of("batch6_scenes_mock.py"), scenes_of("batch7_scenes_mock.py"), scenes_of("batch8_scenes_mock.py")
B9 = scenes_of("batch9_scenes_mock.py")
ok(len(set(B6)) == 53 and len(set(B7)) == 57 and len(set(B8)) == 60 and len(set(B9)) == 58, "batch 6–9 scene lists parsed")
ok(not (set(B10) & (old_scenes | set(B5) | set(B6) | set(B7) | set(B8) | set(B9))), f"batch-10 scenes distinct from {len(snap)} delivered films + batches 5–9")
bad = [(f, x["line"], x["scene"], VP.pick_scene(x["visual"])) for f, rows in snap.items() for x in rows
       if VP.pick_scene(x["visual"]) != x["scene"]]
ok(not bad, f"all {sum(len(r) for r in snap.values())} older film lines keep their scenes {bad[:3]}")
for t in ("sharpe_scenes_mock.py", "batch6_scenes_mock.py", "batch7_scenes_mock.py", "batch8_scenes_mock.py", "batch9_scenes_mock.py"):
    r = subprocess.run([sys.executable, str(CTL / "tests" / t)], capture_output=True, text=True)
    ok(r.returncode == 0, f"{t} still passes (earlier visuals keep their scenes) {r.stdout[-200:] if r.returncode else ''}")
print(f"{n} ok")
