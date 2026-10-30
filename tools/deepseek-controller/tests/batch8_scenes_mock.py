#!/usr/bin/env python3
"""finance-v003 batch-8 scenes (no network): volatility / correlation / covariance / linear-regression / hypothesis-test
visuals → 60 distinct drawn scenes, distinct from every delivered film's scenes and from batches 5, 6 + 7, content lint
clean, no formulas or σ on screen (β only as the 「β（贝塔）」 label), no gambling or buy-signals, never 「波动大机会大」,
losses drawn down, and every earlier film (snapshot + Sharpe + batches 6/7) keeps its scenes."""
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
    "volatility-v001": (
        ["一艘小船在浪里大起大落，船上的人坐得稳稳的", "屏幕标题「Volatility」，下方一条上下起伏的线", "线的起伏被上下两条虚线框住，标「晃动幅度」", "一条平均线，各个点到平均线拉出长短不一的竖线", "两条线：甲贴着平线微动，乙上下大幅摆动，角标「假设」", "乙那条线旁的刻度条更长", "一个上下双箭头，上下两端一样长", "往上的点和往下的点都被同一把尺子量", "乙那条线晃得厉害，终点没有往下掉", "前方的路被一团雾盖住，雾的范围随晃动变大", "回到开头的小船，镜头停在船上的人身上"],
        ["vol_boat", "vol_title", "vol_band", "vol_devs", "vol_ab", "vol_scale", "vol_dblarrow", "vol_ruler", "vol_end", "vol_fog", "vol_boat_end"]),
    "correlation-v001": (
        ["两个小人并排同步走路，中间画着一个问号", "屏幕标题「Correlation」，两条线并排起伏", "两条线同时上、同时下", "一根刻度尺，左端「-1」，中间「0」，右端「1」", "指针指向右端，两条线完全同步", "指针指向左端，两条线一上一下像跷跷板", "指针在中间，两条线各走各的", "冰淇淋柜和空调柜台前都排着长队，角标「假设」", "镜头上移，一个大太阳同时照着两个柜台", "两个柜台之间画一条虚线，被打了个叉", "刻度尺上的指针一下子往右端滑", "几只原本各自漂着的小气球，被同一阵下沉气流一起压低", "回到并排走路的两个小人，脚下的路突然变成下坡"],
        ["corr_walkers", "corr_title", "corr_together", "corr_ruler", "corr_plus1", "corr_minus1", "corr_zero", "corr_queues", "corr_sun", "corr_nocause", "corr_slide", "corr_balloons", "corr_downhill"]),
    "covariance-v001": (
        ["一台机器：进口塞进一堆原料，出口吐出一张小卡片", "屏幕标题「Covariance」，机器进口那堆原料亮起来", "两条线同向起伏，被一个括号框住", "左边同向的两条线标「+」，右边反向的标「-」", "同一段数据，一把尺子刻「元」，另一把刻「分」，读出来的数差很多", "两张写着不同大数的卡片，大小差得很远", "两张卡片放上天平，天平乱晃，标「没法比」", "原料进机器，出口吐出一张卡片，写着刻度「-1 到 1」", "几张卡片整齐地排在同一根刻度尺上", "回到那台机器：左边原料，右边成品卡片"],
        ["cov_machine", "cov_title", "cov_bracket", "cov_signs", "cov_units", "cov_cards_big", "cov_wobble", "cov_card_out", "cov_cards_ruler", "cov_machine_end"]),
    "linear-regression-v001": (
        ["满屏散落的小点，一条直线从中间穿过", "屏幕标题「Linear Regression」，直线微微倾斜", "几条候选直线轮流出现，最后留下离点最近的那条", "横轴标「大盘收益」", "竖轴标「这只股票的收益」，不出现真实名称和代码", "小点一个接一个落下，铺满坐标图，负收益的点在下方", "直线旁画出一个小台阶，标「斜率」", "小台阶旁亮起「β（贝塔）」", "大盘那边走一格，股票那边走一格半，角标「假设」", "所有点变成泛黄的旧照片", "直线往右延伸进一团雾里，新落下的点散得很开", "回到满屏小点和那条直线，直线上写「总结」"],
        ["reg_scatter", "reg_title", "reg_candidates", "reg_xaxis", "reg_yaxis", "reg_dots_fill", "reg_slope", "reg_beta", "reg_step15", "reg_oldphoto", "reg_fog", "reg_summary"]),
    "hypothesis-test-v001": (
        ["法庭式的天平，一边放「没效果」，先压着", "屏幕标题「Hypothesis Testing」", "一张纸上写「虚构策略」，旁边一条起起伏伏、有涨有跌的回测线，角标「假设」", "一枚硬币在空中翻转", "一堆随机结果堆成小山，策略的结果落在小山最边上", "屏幕出现「p 值」，不出现公式", "天平上「没效果」那一边亮起", "小山边上那一小块被涂色，标「这么极端的概率」", "两张卡片：左边「看到这种数据的概率」打勾，右边「没效果的概率」打叉", "右边那张打叉的卡片放大，旁边一个警示三角", "天平上「没效果」那一边被抬起", "天平抬起了，另一边写「有效」的盒子仍然是虚线框", "回测线延伸进雾里，有涨有跌，看不清", "回到天平，镜头停在「没效果」那个标签上"],
        ["hyp_scale", "hyp_title", "hyp_backtest", "hyp_coin", "hyp_hill", "hyp_pval", "hyp_scale_glow", "hyp_tail_shade", "hyp_two_cards", "hyp_warn", "hyp_lift", "hyp_dashed", "hyp_fog", "hyp_end"]),
}
sj = (REPO / "styles" / "pictogram-motion" / "versions" / "finance-v003" / "scenes.js").read_text("utf-8")
B8 = []
for fid, (vis, want) in FILMS.items():
    got = [VP.pick_scene(v) for v in vis]
    ok(got == want and len(set(got)) == len(vis), f"{fid}: {len(vis)} visuals → {len(vis)} distinct batch-8 scenes")
    shots = [{"line": f"L{i + 1:02d}", "visual": vis[i], "scene": s, "data": VP.scene_data(s, f"L{i + 1:02d}")} for i, s in enumerate(got)]
    ok(VP.lint(shots, vis) == [], f"{fid}: lint clean (no tickers/fund names/K-lines/gambling/rising-only/dupes)")
    B8 += want
ok(len(B8) == 60 and len(set(B8)) == 60, "60 batch-8 scenes, unique across the 5 films")
ok(all(f"VIZ.{s} =" in sj and re.search(rf"\b{s}: '", sj) for s in B8), "every batch-8 scene drawn + palette in finance-v003 scenes.js")
b8 = sj[sj.index("finance-v003 scene library, batch 8"):sj.index("finance-v003 scene library, batch 4")]
code = "\n".join(l.split("//")[0] for l in b8.split("\n"))  # drawn strings only, not comments
ok(not re.search(r"基金|ETF|筹码|赌|骰|扑克|轮盘|σ|Σ|÷|√|公式|值得买|稳赚|机会大|K线", code), "batch-8 scene text: no formulas, σ, funds, gambling, K-lines or buy-signals")
ok(code.count("β") == 1 and "b8txt(ctx, 'β'" in code, "β drawn exactly once, as the reg_beta label")
for t in ("'Volatility'", "'Correlation'", "'Covariance'", "'Linear Regression'", "'Hypothesis Testing'"):
    ok(f"b6title(ctx, {t}" in code, f"screen title {t} via b6title")
ok("'p', -90" in code and "'值', 90" in code, "「p 值」 drawn as a label, no formula")
ok("'虚构策略'" in code and "'假设'" in code, "fictional backtest labelled 虚构策略 with a 假设 corner badge")
ok("r[n - 1] * i / (n - 1)" in code, "backtest line ends where it started (no profit implied)")
ok("'有效', 46, { dash: o.dash }" in code and "else if (!o.hideR)" in code, "「有效」 stays a dashed box (rejecting ≠ proving)")
ok("'相关 ≠ 因果'" in code and "b6down(ctx" in code, "correlation ≠ causation; crisis balloons pressed DOWN together")
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


B6, B7 = scenes_of("batch6_scenes_mock.py"), scenes_of("batch7_scenes_mock.py")
ok(len(set(B6)) == 53 and len(set(B7)) == 57, "batch 6 + 7 scene lists parsed")
ok(not (set(B8) & (old_scenes | set(B5) | set(B6) | set(B7))), f"batch-8 scenes distinct from {len(snap)} delivered films + batches 5, 6 and 7")
bad = [(f, x["line"], x["scene"], VP.pick_scene(x["visual"])) for f, rows in snap.items() for x in rows
       if VP.pick_scene(x["visual"]) != x["scene"]]
ok(not bad, f"all {sum(len(r) for r in snap.values())} older film lines keep their scenes {bad[:3]}")
for t in ("sharpe_scenes_mock.py", "batch6_scenes_mock.py", "batch7_scenes_mock.py"):
    r = subprocess.run([sys.executable, str(CTL / "tests" / t)], capture_output=True, text=True)
    ok(r.returncode == 0, f"{t} still passes (earlier visuals keep their scenes)")
print(f"{n} ok")
