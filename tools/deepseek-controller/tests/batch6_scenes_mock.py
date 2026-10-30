#!/usr/bin/env python3
"""finance-v003 batch-6 scenes (risk family; no network): systematic-risk / unsystematic-risk / apt-long /
moral-hazard / adverse-selection visuals → 53 distinct drawn scenes, distinct from every delivered film's scenes and
from batch 5 (Sharpe), content lint clean, no formulas on screen, and every earlier film
(fixtures/viz-scene-snapshot.json + the Sharpe-long visuals) still maps each line's visual to the same scene."""
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
    "systematic-risk-v001": (
        ["一张撑开的大伞，伞面破洞，雨照样漏下来", "屏幕标题「Systematic Risk」，下方一整片海面",
         "海面上一排小船，同一个浪打来，全部一起往下沉", "商店街灯一盏盏暗下去，购物车空着",
         "一个大旋钮被猛拧，旁边所有小齿轮跟着一起转", "几条线有上有下，交错着，总线大致平稳",
         "几条线同时掉头往下，挤成一束", "一张安全网的网眼被撑大，接不住往下掉的东西",
         "左边：一艘船漏水，其他船托住；右边：大浪把所有船一起压下去", "回到开头的破伞，伞下的人抬头看天"],
        ["umbrella_holes", "sea_title", "boats_sink", "street_dim", "gears_dial", "lines_offset", "lines_bundle",
         "net_holes", "boats_split", "umbrella_look"]),
    "unsystematic-risk-v001": (
        ["一大块石头被敲成许多小碎块，散到很多篮子里", "屏幕标题「Unsystematic Risk」，下方一条街上的几家小店",
         "一家奶茶店招牌歪了，门口排队的人散开，其他店照常营业", "那家店门口拉下卷帘门，旁边的店灯还亮着",
         "一个人只提一个篮子，篮子破了，东西全掉到地上（往下落）", "一个人提十个小篮子，其中一个漏了，只掉一点",
         "十个篮子用不同颜色、挂在不同的钩子上，不是串在同一根绳上", "一阵大风把十个篮子同时吹得往下晃",
         "回到碎石块：一块大坑被填平成许多浅浅的小坑"],
        ["rock_split", "shop_street", "tea_sign", "shutter_down", "basket_break", "ten_baskets", "hooks_colors",
         "wind_baskets", "pits_fill"]),
    "apt-long-v001": (
        ["一个仪表盘上只有一根指针「大盘」，旁边又亮起几根新指针", "屏幕标题「APT」，下方一块多旋钮的调音台",
         "一个调音台只有一个推子「大盘」", "调音台上多出几个推子，标「通胀」「利率」「增长」",
         "购物小票越拉越长，一个存钱罐的分量往下掉", "一根借款绳越绷越紧，绳上挂的箱子往下坠",
         "几辆小车在同一条路上，路速变化时有的快有的慢", "一个组合连着几根弹簧，每根弹簧粗细不同",
         "几根推子的读数汇成一个总数，标「该要的回报（假设）」", "同样一个苹果，两个摊位标价不同，有人在中间搬运",
         "两个摊位的价签慢慢靠拢到同一个数", "搬运的人脚下一滑，箱子往下掉", "一把尺子放在调音台上，旁边一团雾",
         "回到仪表盘，几根指针一起亮着"],
        ["dial_needles", "mixer_title", "mixer_one", "mixer_faders", "receipt_jar", "rope_strain", "cars_road",
         "springs", "faders_sum", "apple_stalls", "tags_converge", "mover_slip", "ruler_fog", "dial_all"]),
    "moral-hazard-v001": (
        ["一个人站在高处，身后多了一张大网，他往前迈了一步", "屏幕标题「Moral Hazard」，下方一张保单",
         "一辆小车贴着车道线开，司机单手扶方向盘，角标「假设」", "司机身边的「小心」进度条一点点往下降",
         "一座无名小楼下面垫着一个大气垫，楼越盖越歪", "一个人抱走金币，另一群人在下面接住掉下来的砖",
         "保单上一格写「自己先出一部分」，司机重新双手握方向盘", "一条时间线：先签字，之后才出现行为变化的标记",
         "回到开头：网在身后，人的脚印越走越靠边"],
        ["net_step", "policy_title", "car_lane", "care_bar", "airbag_tower", "coins_bricks", "deductible",
         "timeline_after", "footprints_edge"]),
    "adverse-selection-v001": (
        ["一扇门口排队，最前面的人最着急", "屏幕标题「Adverse Selection」，下方一扇半开的门",
         "保险柜台前，咳嗽的人挤在最前面，角标「假设」", "柜台上的价签往上跳", "队伍里健康的人摇头离开，队伍变短",
         "卖家手里拿着两把钥匙，一把亮、一把锈", "买家拿放大镜也看不清，报价牌停在中间",
         "亮车开出市场，场里剩下的锈车越来越多", "桌子一边灯很亮，另一边一片暗",
         "一条时间线：签字之前的位置亮起标记，签字之后那段是灰的", "回到开头的门口队伍，镜头停在最前面那个人身上"],
        ["door_queue", "door_title", "counter_cough", "price_jump", "queue_leave", "two_keys", "magnifier_mid",
         "cars_leave", "table_light", "timeline_before", "queue_front"]),
}
sj = (REPO / "styles" / "pictogram-motion" / "versions" / "finance-v003" / "scenes.js").read_text("utf-8")
B6 = []
for fid, (vis, want) in FILMS.items():
    got = [VP.pick_scene(v) for v in vis]
    ok(got == want and len(set(got)) == len(vis), f"{fid}: {len(vis)} visuals → {len(vis)} distinct batch-6 scenes")
    shots = [{"line": f"L{i + 1:02d}", "visual": vis[i], "scene": s, "data": VP.scene_data(s, f"L{i + 1:02d}")} for i, s in enumerate(got)]
    ok(VP.lint(shots, vis) == [], f"{fid}: lint clean (no tickers/fund names/K-lines/gambling/rising-only/dupes)")
    B6 += want
ok(len(B6) == 53 and len(set(B6)) == 53, "53 batch-6 scenes, unique across the 5 films")
ok(all(f"VIZ.{s} =" in sj and re.search(rf"\b{s}: '", sj) for s in B6), "every batch-6 scene drawn + palette in finance-v003 scenes.js")
b6 = sj[sj.index("batch 6 (risk family"):sj.index("finance-v003 scene library, batch 8")]
ok(not re.search(r"基金|ETF|筹码|赌|骰|σ|β|Σ|÷|公式|值得买|稳赚", b6), "batch-6 scene text: no formulas, funds, gambling or buy-signals")
ok(re.search(r"'APT'", b6) and "b6title(ctx, 'Systematic Risk'" in b6, "screen titles: 'APT' kept upper, terms via b6title")
r = subprocess.run(["node", "-e", f"new Function(require('fs').readFileSync({json.dumps(str(REPO / 'styles/pictogram-motion/versions/finance-v003/scenes.js'))},'utf8'))"], capture_output=True)
ok(r.returncode == 0, "finance-v003 scenes.js parses")
helpers = re.findall(r"^  (?:function|const) ([A-Za-z0-9_]+)", sj, re.M)
ok(len(helpers) == len(set(helpers)), "no duplicate helper names in scenes.js")

snap = json.loads((CTL / "fixtures" / "viz-scene-snapshot.json").read_text("utf-8"))["films"]
old_scenes = {x["scene"] for rows in snap.values() for x in rows}
B5 = ["twin_q", "score_sharpe", "baskets_8", "calm_wild", "pillars_cut", "remain_six", "swing_box", "sandbags",
      "coin_stack", "score_fill", "card_fog", "ruler_chair", "bag_pillars"]
ok(not (set(B6) & (old_scenes | set(B5))), f"batch-6 scenes distinct from {len(snap)} delivered films + batch 5")
bad = [(f, x["line"], x["scene"], VP.pick_scene(x["visual"])) for f, rows in snap.items() for x in rows
       if VP.pick_scene(x["visual"]) != x["scene"]]
ok(not bad, f"all {sum(len(r) for r in snap.values())} older film lines keep their scenes {bad[:3]}")
r = subprocess.run([sys.executable, str(CTL / "tests" / "sharpe_scenes_mock.py")], capture_output=True, text=True)
ok(r.returncode == 0, "batch-5 Sharpe test still passes (Sharpe visuals keep their scenes)")
print(f"{n} ok")
