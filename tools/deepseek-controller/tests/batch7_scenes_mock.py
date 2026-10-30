#!/usr/bin/env python3
"""finance-v003 batch-7 scenes (no network): three-lines / barings / ltcm-long / normal-dist / fat-tails visuals →
57 distinct drawn scenes, distinct from every delivered film's scenes and from batches 5 + 6, content lint clean
(a negated 「不出现K线」 drawing note is allowed, a real K-line is not), no formulas or gambling on screen, Barings shows
「88888」 and the quake only as a map, and every earlier film (snapshot + Sharpe + batch 6) keeps its scenes."""
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
    "three-lines-v001": (
        ["一条通道上依次立着三道闸门", "屏幕标题「Three Lines of Defense」，三道闸门编号一二三", "第一道闸门旁，业务员边干活边看风险表", "第二道闸门上方一个独立的观察台，有人拿望远镜",
         "第三道闸门旁，有人翻看前两道的记录本", "三道闸门各自有独立的锁，钥匙在三个人手里", "一张桌子被隔板分成两边：左边下单，右边记账，坐着不同的人", "隔板被拿走，一个人同时坐两边，账本上的红字被盖住",
         "三道闸门亮灯，一个红色小错块在第二道被拦下", "镜头拉远：一栋无名老楼的轮廓，门口只剩一道闸门"],
        ["gates_three", "gates_title", "gate_worker", "gate_tower", "gate_audit", "gate_locks", "desk_split",
         "desk_merge", "gates_catch", "oldbank_gate"]),
    "barings-v001": (
        ["一个人的剪影站在一栋老银行大楼前，大楼出现裂缝", "老楼门牌「巴林银行 1995」，门口落下卷帘门", "交易台前一个背影，屏幕标「Nick Leeson · 新加坡」",
         "屏幕标「日经225 指数期货」，不出现K线", "一本账簿最后一页夹着一个隐藏的小抽屉，红字往里塞", "抽屉标签「88888」", "同一个人左手下单、右手盖章结算", "本该站第二个人的位置是空椅子",
         "地图上日本神户一带震波扩散（不出现伤亡画面）", "红色亏损雪球往下坡滚，越滚越大", "屏幕数字「约 8.27 亿英镑」往下沉", "红色亏损柱往下压，越过了标着「银行资本」的地板线",
         "一枚一英镑硬币放在老楼钥匙旁", "回到三道闸门：三道全开着，没有一盏灯亮"],
        ["bank_crack", "bank_plate", "desk_leeson", "nikkei_board", "ledger_drawer", "drawer_88888", "two_hands",
         "empty_chair", "quake_map", "snowball_down", "pounds_sink", "capital_floor", "coin_keys", "gates_dark"]),
    "ltcm-long-v001": (
        ["一辆精密仪表车在平路上开得很稳，前方出现一个深坑", "屏幕标题「LTCM」，一栋无标识写字楼", "会议桌上放着一枚奖章和厚厚的模型手册，标「1994」", "两条本该并拢的线中间有一道缝，箭头指向合拢",
         "一根小撬棍撬起一块巨石", "天平一边一枚小硬币，另一边二十五枚叠起来的硬币，标「约25倍+」", "一张欠条被撕开，标「1998 俄罗斯违约」", "那两条线不仅没合拢，缝隙越撕越宽",
         "撬棍反弹，巨石往下砸，红色亏损线成倍下坠", "十四个无标识的小方块围成一圈，中间一个协调人", "一只大手接住正在下坠的写字楼，标「约36亿美元」", "模型手册上写「极少发生」，窗外大浪拍来",
         "回到开头：精密仪表车卡在深坑里，撬棍断在旁边"],
        ["gauge_car", "ltcm_title", "medal_manual", "gap_lines", "lever_rock", "coins_25", "iou_torn", "gap_widen",
         "rock_drop", "ring_14", "hand_catch", "manual_wave", "car_stuck"]),
    "normal-dist-v001": (
        ["一堆小球从上方落下，大多数堆在中间", "小球堆成钟形，屏幕标题「Normal Distribution」", "小球的轮廓变成一条平滑的钟形曲线", "钟形中间高耸处标「普通的一天」",
         "两边尾巴越来越细；左尾标「大亏」，右尾标「大赚」", "一台计算器上贴着这条钟形曲线", "计算器一按就出结果，屏幕打勾", "真实数据点散落在钟形曲线旁，几个点落在左边很远处",
         "钟形左侧尾巴被一层阴影加厚，留个悬念"],
        ["balls_pile", "normal_title", "bell_outline", "bell_peak", "bell_tails", "calc_bell", "calc_tick",
         "dots_outliers", "tail_shadow"]),
    "fat-tails-v001": (
        ["日历上标着「极少发生」的那一天，被圈了好几次", "屏幕标题「Fat Tails」，一条钟形曲线的尾巴明显变粗", "细尾巴的钟形曲线，两端几乎贴着地面", "真实数据小球不断落在两端，越堆越高",
         "两条曲线叠在一起：细尾虚线、粗尾实线", "左侧亏损尾巴朝左下方拖长、加粗，标「大跌」", "一条门槛竖线，线外左侧粗尾区域被打上问号", "镜头推进到门槛线外那块粗尾区域，颜色加深",
         "一面写着「LTCM」的墙被一只从尾部伸出的手推倒", "计算器上「安全」两个字被一道裂缝划开", "回到日历：圈了好几次的那一天，旁边并排两条曲线，细尾和粗尾"],
        ["calendar_circled", "fat_title", "thin_bell", "balls_ends", "tails_overlay", "left_tail_drag",
         "threshold_q", "tail_zoom", "wall_push", "calc_crack", "calendar_two"]),
}
sj = (REPO / "styles" / "pictogram-motion" / "versions" / "finance-v003" / "scenes.js").read_text("utf-8")
B7 = []
for fid, (vis, want) in FILMS.items():
    got = [VP.pick_scene(v) for v in vis]
    ok(got == want and len(set(got)) == len(vis), f"{fid}: {len(vis)} visuals → {len(vis)} distinct batch-7 scenes")
    shots = [{"line": f"L{i + 1:02d}", "visual": vis[i], "scene": s, "data": VP.scene_data(s, f"L{i + 1:02d}")} for i, s in enumerate(got)]
    ok(VP.lint(shots, vis) == [], f"{fid}: lint clean (no tickers/fund names/K-lines/gambling/rising-only/dupes)")
    B7 += want
ok(len(B7) == 57 and len(set(B7)) == 57, "57 batch-7 scenes, unique across the 5 films")
ok(all(f"VIZ.{s} =" in sj and re.search(rf"\b{s}: '", sj) for s in B7), "every batch-7 scene drawn + palette in finance-v003 scenes.js")
b7 = sj[sj.index("batch 7 (governance cases"):sj.index("finance-v003 scene library, batch 4")]
ok(not re.search(r"基金|ETF|筹码|赌|骰|扑克|轮盘|σ|β|Σ|÷|公式|值得买|稳赚|伤亡", b7), "batch-7 scene text: no formulas, funds, gambling, casualties or buy-signals")
ok("'88888'" in b7 and "'巴林银行 1995'" in b7 and "'神户 · 1995.1'" in b7, "Barings: 88888 drawer label, door plate, quake as a map label")
ok("ING" not in b7, "no acquirer name or logo drawn")
ok("b6title(ctx, 'Normal Distribution'" in b7 and "b6title(ctx, 'Fat Tails'" in b7 and "b6title(ctx, 'LTCM'" in b7, "screen titles via b6title, LTCM kept upper")
ok("'大亏', B7X0" in b7 and "'大跌', lerp(x0, 320" in b7, "loss tail labelled on the LEFT side of the bell")
K = VP.BANNED[2][0]
ok(re.search(K, "画一根K线") and not re.search(K, "屏幕标「日经225 指数期货」，不出现K线"), "K-line ban: real mention flagged, negated drawing note allowed")
r = subprocess.run(["node", "-e", f"new Function(require('fs').readFileSync({json.dumps(str(REPO / 'styles/pictogram-motion/versions/finance-v003/scenes.js'))},'utf8'))"], capture_output=True)
ok(r.returncode == 0, "finance-v003 scenes.js parses")
helpers = re.findall(r"^  (?:function|const) ([A-Za-z0-9_]+)", sj, re.M)
ok(len(helpers) == len(set(helpers)), "no duplicate helper names in scenes.js")

snap = json.loads((CTL / "fixtures" / "viz-scene-snapshot.json").read_text("utf-8"))["films"]
old_scenes = {x["scene"] for rows in snap.values() for x in rows}
B5 = ["twin_q", "score_sharpe", "baskets_8", "calm_wild", "pillars_cut", "remain_six", "swing_box", "sandbags",
      "coin_stack", "score_fill", "card_fog", "ruler_chair", "bag_pillars"]
b6src = (CTL / "tests" / "batch6_scenes_mock.py").read_text("utf-8")
B6 = re.findall(r'"([a-z0-9_]+)"', b6src[b6src.index("FILMS = {"):b6src.index("sj = (REPO")])
B6 = [x for x in B6 if not x.endswith("-v001")]
ok(len(set(B6)) == 53 and not (set(B7) & (old_scenes | set(B5) | set(B6))), f"batch-7 scenes distinct from {len(snap)} delivered films + batches 5 and 6")
bad = [(f, x["line"], x["scene"], VP.pick_scene(x["visual"])) for f, rows in snap.items() for x in rows
       if VP.pick_scene(x["visual"]) != x["scene"]]
ok(not bad, f"all {sum(len(r) for r in snap.values())} older film lines keep their scenes {bad[:3]}")
for t in ("sharpe_scenes_mock.py", "batch6_scenes_mock.py"):
    r = subprocess.run([sys.executable, str(CTL / "tests" / t)], capture_output=True, text=True)
    ok(r.returncode == 0, f"{t} still passes (earlier visuals keep their scenes)")
print(f"{n} ok")
