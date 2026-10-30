#!/usr/bin/env python3
"""finance-v003 batch-9 scenes (no network): Monte Carlo / EWMA / GARCH / stationarity / skewness visuals → 58 distinct
drawn scenes, distinct from every delivered film's scenes and from batches 5–8, content lint clean, no formulas, σ, dice or
casinos on screen (λ = 0.94 only as the EWMA corner note, GARCH named on screen only), losses drawn left / down, and every
earlier film (snapshot + Sharpe + batches 6/7/8) keeps its scenes."""
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
    "monte-carlo-v001": (
        ["一个路口分出成千上万条细细的岔路", "屏幕标题「Monte Carlo Simulation」，下方一张岔路地图", "一台电脑屏幕上，一个小点沿岔路随机前进", "一条岔路被点亮，有上有下，往下的部分往下画", "成千上万条岔路一起亮起，像一把散开的扇子", "所有岔路的终点落进下方的格子，堆成一座小山", "小山最左下角那一小块被标红，标「最坏的 1%」", "整张岔路图缩成一张地图，标「可能性」", "地图旁边一个水晶球被打了个叉", "电脑入口塞进一张纸条，写「假设」", "纸条上的字是错的，出口那座小山整个歪掉", "回到开头的路口，路牌上写「假设？」"],
        ["mc_fork", "mc_title", "mc_screen", "mc_onepath", "mc_fan", "mc_hill", "mc_worst", "mc_map", "mc_crystal", "mc_note", "mc_wrong", "mc_signpost"]),
    "ewma-v001": (
        ["一排脚印，越靠近镜头的越清楚，越远的越淡", "屏幕标题「EWMA」", "一条起伏的收益线，上方一个刻度条在跳", "一排砝码大小完全一样，放在一根横杆上", "砝码从右到左变小，最右边今天的那个最大", "左边的砝码越来越小，最后几乎看不见", "砝码大小按同一个比例缩小，角落小字「λ = 0.94（日数据）」", "最右边的大砝码压得刻度条往上一跳", "一道大浪打来，刻度条立刻拉高", "浪过去，刻度条跟着降下来", "回到那排脚印，镜头停在最近、最清楚的那一个"],
        ["ewma_steps", "ewma_title", "ewma_meter", "ewma_equal", "ewma_grow", "ewma_fade", "ewma_ratio", "ewma_press", "ewma_wave", "ewma_settle", "ewma_steps_end"]),
    "garch-v001": (
        ["一池水里落下一块石头，波纹一圈接一圈", "屏幕标题「GARCH」，不念全称", "上一条的砝码横杆旁边，又多出一个齿轮", "三个格子排开，等着被点亮", "第一个格子亮起：一条水平的长线", "第二个格子亮起：一块石头砸进水里", "第三个格子亮起：一段剧烈起伏的波纹", "波纹从昨天的格子延伸到今天的格子", "一条时间线上，大波纹一簇一簇挤在一起，中间夹着平静段", "波纹逐渐变小，落回那条水平的长线", "三个格子的背面是一本旧账本", "回到水池：先平静，再起波纹，再慢慢平静"],
        ["garch_pond", "garch_title", "garch_gear", "garch_boxes", "garch_box1", "garch_box2", "garch_box3", "garch_carry", "garch_cluster", "garch_revert", "garch_ledger", "garch_pond_end"]),
    "stationarity-v001": (
        ["一张地图上的路线在纸上慢慢漂移", "屏幕标题「Stationarity」", "一条线围着一根水平中线上下晃，中线不动", "线的上下包络是两条平行的虚线", "前半段和后半段的线，形状看起来差不多", "一台计算器的入口写着「请放平稳的数据」", "一条价格线没有中线，有时漂高有时漂低，越走越远", "价格线被转换成一条围着零上下晃的线", "每天一根小柱，向上是涨、向下是跌", "小柱基本落在上下两条虚线之间", "回到漂移的地图，旧路线和新路面对不上"],
        ["stat_map", "stat_title", "stat_mean", "stat_band", "stat_halves", "stat_calc", "stat_price", "stat_convert", "stat_bars", "stat_range", "stat_map_end"]),
    "skewness-v001": (
        ["一座小山的山顶偏向右边，左边拖出长长的斜坡", "屏幕标题「Skewness」", "一座对称的钟形小山，中间一条竖线", "竖线两边的尾巴长度相同", "小山向右歪，左边亏损一侧的尾巴拖得又细又长", "小山右侧那一大堆，标「多数时候小赚」", "左边长尾末端一个红点往下落", "一排小小的向上柱，中间突然一根很长的向下柱，角标「假设」", "一条平均线看着平稳，下方拖着一条长影子", "左边的长尾巴同时也变粗了，旁边小字「Fat Tails」", "一把尺子量的是小山的轮廓，不是钱包", "回到那座歪向一边的小山，镜头顺着左边尾巴往下移"],
        ["skew_hill", "skew_title", "skew_sym", "skew_equal", "skew_left", "skew_bulk", "skew_drop", "skew_bars", "skew_shadow", "skew_fat", "skew_ruler", "skew_end"]),
}
sj = (REPO / "styles" / "pictogram-motion" / "versions" / "finance-v003" / "scenes.js").read_text("utf-8")
B9 = []
for fid, (vis, want) in FILMS.items():
    got = [VP.pick_scene(v) for v in vis]
    ok(got == want and len(set(got)) == len(vis), f"{fid}: {len(vis)} visuals → {len(vis)} distinct batch-9 scenes")
    shots = [{"line": f"L{i + 1:02d}", "visual": vis[i], "scene": s, "data": VP.scene_data(s, f"L{i + 1:02d}")} for i, s in enumerate(got)]
    ok(VP.lint(shots, vis) == [], f"{fid}: lint clean (no tickers/fund names/K-lines/gambling/rising-only/dupes)")
    B9 += want
ok(len(B9) == 58 and len(set(B9)) == 58, "58 batch-9 scenes, unique across the 5 films")
ok(all(f"VIZ.{s} =" in sj and re.search(rf"\b{s}: '", sj) for s in B9), "every batch-9 scene drawn + palette in finance-v003 scenes.js")
b9 = sj[sj.index("finance-v003 scene library, batch 9"):sj.index("finance-v003 scene library, batch 4")]
code = "\n".join(l.split("//")[0] for l in b9.split("\n"))  # drawn strings only, not comments
ok(not re.search(r"基金|ETF|筹码|赌|骰|扑克|轮盘|赌场|σ|Σ|÷|√|公式|值得买|稳赚|机会大|K线|β", code), "batch-9 scene text: no formulas, σ, funds, gambling, K-lines or buy-signals")
ok(code.count("λ") == 1 and "'λ = 0.94（日数据）'" in code, "λ = 0.94 drawn exactly once, as the EWMA corner note")
for t in ("'Monte Carlo Simulation'", "'EWMA'", "'GARCH'", "'Stationarity'", "'Skewness'"):
    ok(f"b6title(ctx, {t}" in code, f"screen title {t} via b6title")
ok("'最坏的 1%'" in code and "b6down(ctx, wx" in code, "Monte Carlo worst 1% sits on the left and points DOWN")
ok("'不是预测'" in code and "'假设？'" in code, "Monte Carlo = possibilities, not a forecast; ends on 「假设？」")
ok("(1 + b9erf(-4 * u" in code and "'亏', B9X0" in code, "negative skew: long tail on the LEFT, the 亏 side")
ok("一定亏" not in code, "never drawn as 「negative skew = losing money」")
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
ok(len(set(B6)) == 53 and len(set(B7)) == 57 and len(set(B8)) == 60, "batch 6 + 7 + 8 scene lists parsed")
ok(not (set(B9) & (old_scenes | set(B5) | set(B6) | set(B7) | set(B8))), f"batch-9 scenes distinct from {len(snap)} delivered films + batches 5–8")
bad = [(f, x["line"], x["scene"], VP.pick_scene(x["visual"])) for f, rows in snap.items() for x in rows
       if VP.pick_scene(x["visual"]) != x["scene"]]
ok(not bad, f"all {sum(len(r) for r in snap.values())} older film lines keep their scenes {bad[:3]}")
for t in ("sharpe_scenes_mock.py", "batch6_scenes_mock.py", "batch7_scenes_mock.py", "batch8_scenes_mock.py"):
    r = subprocess.run([sys.executable, str(CTL / "tests" / t)], capture_output=True, text=True)
    ok(r.returncode == 0, f"{t} still passes (earlier visuals keep their scenes) {r.stdout[-200:] if r.returncode else ''}")
print(f"{n} ok")
