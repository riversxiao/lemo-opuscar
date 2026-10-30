#!/usr/bin/env python3
"""finance-v003 batch-11 scenes (no network): put-call parity / basis risk / hedge ratio / contango-backwardation / margin
visuals → 64 distinct drawn scenes, distinct from every delivered film's scenes and from batches 5–10, content lint clean, no
tickers, real contracts, lottery or gambling imagery; parity is European-only with the 「简化：不考虑分红」 note; the hedge-ratio
formula is drawn exactly once (on screen only); hedging shrinks risk but never to zero; contango ≠ bullish, backwardation ≠
bearish; margin calls top back up to the UPPER (initial) line; margin is a deposit, not a down payment or fee; losses drawn
down; and every earlier film (snapshot + Sharpe + batches 6–10) keeps its scenes."""
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
    "put-call-parity-long-v001": (
        ["两个并排的礼盒，打开后里面的东西一样多，角标「简化：不考虑分红」", "屏幕标题「Put-Call Parity」", "三个对勾依次亮起", "一扇门只在日历最后一天打开", "左边礼盒里放进一张绿色门票", "左边礼盒里再放进一个存钱罐，标「到期等于行权价」", "右边礼盒里放进一张橙色门票", "右边礼盒里再放进一个代表标的的方块", "价格线升到一百二，一百处画虚线，角标「假设」", "左边礼盒：存钱罐换成方块，标一百二", "右边礼盒：橙色门票作废，方块标一百二", "价格线上下各走一遍，两个礼盒的数值始终相同", "镜头倒回今天，两个礼盒放上天平", "天平一边略高，很快被拉回水平", "回到两个并排的礼盒，天平保持水平"],
        ["pcp_boxes", "pcp_title", "pcp_checks", "pcp_euro", "pcp_call_in", "pcp_cash_in", "pcp_put_in", "pcp_asset_in", "pcp_120", "pcp_left120", "pcp_right120", "pcp_both", "pcp_today", "pcp_arb", "pcp_end"]),
    "basis-risk-v001": (
        ["一把伞挡住了大部分雨，伞边还是漏进几滴", "屏幕标题「Basis Risk」", "两条价格线之间的距离被标出来，画面写「基差 = 现货价 − 期货价」", "一架虚构航空公司的飞机旁边一个油桶，角标「假设」", "航油桶旁边放上一个原油桶，用一根绳子连着", "两条价格线大致一起往上", "两条线之间的距离时宽时窄", "航油线升得更高，绳子够不着，中间露出一段缺口", "缺口被放大镜放大，标「基差在变」", "同一种商品的两条价格线，走势相近但不重合", "一块大石头被换成一颗小石子", "回到那把伞：雨小了很多，伞边还有几滴"],
        ["bas_umbrella", "bas_title", "bas_gap", "bas_plane", "bas_rope", "bas_together", "bas_width", "bas_short", "bas_magnify", "bas_samegood", "bas_rock", "bas_end"]),
    "hedge-ratio-v001": (
        ["天平左边一个大方块，右边放的砝码不是同样大小", "屏幕标题「Hedge Ratio」", "复用基差风险那两条走势相近但不重合的线", "两条线之间出现一个相关性刻度盘", "刻度盘指针往高处走，伞变得更大", "两条线各自的起伏幅度被框出来", "期货那条线起伏更大，右边砝码变少", "现货那条线起伏更大，右边砝码变多", "画面写出 h = ρ × σ现货 / σ期货（只上画面，不念）", "左边一百吨航油，右边八十吨期货砝码，角标「假设」", "砝码多一点或少一点，天平都会偏一点", "回到天平：两边的线一起起伏，天平基本稳住"],
        ["hr_scale", "hr_title", "hr_reuse", "hr_dial", "hr_dial_up", "hr_boxes", "hr_fut_big", "hr_spot_big", "hr_formula", "hr_80", "hr_tilt", "hr_end"]),
    "contango-backwardation-v001": (
        ["两个价签并排，一个写「现货」，一个写「期货」，数字不同", "期货价签在上，现货在下，屏幕标题「Contango」", "期货价签在下，现货在上，屏幕标题「Backwardation」", "一个仓库里堆着货", "仓库门口一张账单，写着仓储费和利息", "时间轴越往后，价签越高", "货架上只剩最后几件", "一只手握着现货，旁边的期货价签偏低", "两条线随时间越靠越近", "两条线在到期日汇合成一点", "一个写着「看涨」的箭头被划掉", "一个写着「看空」的箭头被划掉", "回到两个价签，旁边是仓库和货架，没有水晶球"],
        ["cb_tags", "cb_contango", "cb_backw", "cb_warehouse", "cb_bill", "cb_timeline", "cb_shelf", "cb_hand", "cb_converge", "cb_meet", "cb_not_bull", "cb_not_bear", "cb_end"]),
    "margin-v001": (
        ["一个账户余额柱，上面画着两条横线，屏幕标题「Margin」", "上方那条线亮起，标「初始保证金」", "下方那条线亮起，标「维持保证金」", "日历翻页，余额柱上下变化", "余额柱往下沉，穿过下方那条线，角标「假设」", "一封信落到账户上，写着「追加保证金」", "箭头越过下线，一直推到上方那条线，小角标「以常见规则为例」", "余额柱回到上方那条线", "另一条分支：账户被一只手合上", "一张写着「首付」的牌子和一张写着「手续费」的收据", "牌子和收据被换成一把押金钥匙", "回到账户和两条线，旁边那把押金钥匙"],
        ["mg_lines", "mg_init", "mg_maint", "mg_daily", "mg_breach", "mg_letter", "mg_topup", "mg_back", "mg_close", "mg_misread", "mg_key", "mg_end"]),
}
sj = (REPO / "styles" / "pictogram-motion" / "versions" / "finance-v003" / "scenes.js").read_text("utf-8")
B11 = []
for fid, (vis, want) in FILMS.items():
    got = [VP.pick_scene(v) for v in vis]
    ok(got == want and len(set(got)) == len(vis), f"{fid}: {len(vis)} visuals → {len(vis)} distinct batch-11 scenes")
    shots = [{"line": f"L{i + 1:02d}", "visual": vis[i], "scene": s, "data": VP.scene_data(s, f"L{i + 1:02d}")} for i, s in enumerate(got)]
    ok(VP.lint(shots, vis) == [], f"{fid}: lint clean (no tickers/fund names/K-lines/gambling/rising-only/dupes)")
    B11 += want
ok(len(FILMS["put-call-parity-long-v001"][0]) == 15, "put-call parity (long) has 15 lines")
ok(len(B11) == 64 and len(set(B11)) == 64, "64 batch-11 scenes, unique across the 5 films")
ok(all(f"VIZ.{s} =" in sj and re.search(rf"\b{s}: '", sj) for s in B11), "every batch-11 scene drawn + palette in finance-v003 scenes.js")
b11 = sj[sj.index("finance-v003 scene library, batch 11"):sj.index("finance-v003 scene library, batch 4")]
code = "\n".join(l.split("//")[0] for l in b11.split("\n"))  # drawn strings only, not comments
ok(not re.search(r"基金|ETF|筹码|赌|骰|扑克|轮盘|赌场|彩票|中奖|K线|值得买|稳赚|机会大|小钱|撬|√|Σ", code), "batch-11 scene text: no funds, gambling, lottery, K-lines, buy-signals or 小钱撬大钱")
ok(not re.search(r"'[A-Z]{1,4}\d{2,4}'|代码|WTI|Brent|布伦特", code), "no contract codes or real benchmark names drawn")
ok(code.count("σ") == 2 and code.count("ρ") == 1 and "'h = ρ × σ现货 / σ期货'" in code, "hedge-ratio formula drawn exactly once, on screen only")
ok("'简化：不考虑分红'" in code and "'欧式：只在到期日'" in code, "parity: European-only, simplified (no dividends) note")
for t in ("'Put-Call Parity'", "'Basis Risk'", "'Hedge Ratio'", "'Contango'", "'Backwardation'", "'Margin'"):
    ok(f"b6title(ctx, {t}" in code, f"screen title {t} via b6title")
ok("'不是零风险'" in code and "'还剩一点'" in code and "'小风险'" in code, "basis risk: hedging turns big risk small, never zero")
ok("'不代表看涨'" in code and "'也不代表看空'" in code and code.count("b8cross(ctx, 1320, 660, 260") == 2, "contango ≠ bullish, backwardation ≠ bearish (both arrows crossed out)")
ok("'到期基本对上'" in code and "'越靠越近'" in code, "futures converge to spot at expiry")
ok("'以常见规则为例'" in code and "'补回上线'" in code and "'不是补到下线'" in code and "'强制平仓'" in code, "margin call tops back up to the upper line; forced liquidation")
ok("'履约押金'" in code and "'押金，不是首付或手续费'" in code, "margin is a deposit, not a down payment or fee")
ok("b6down(ctx, 1240, 520" in code, "margin loss drawn downward")
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
B9, B10 = scenes_of("batch9_scenes_mock.py"), scenes_of("batch10_scenes_mock.py")
ok(len(set(B6)) == 53 and len(set(B7)) == 57 and len(set(B8)) == 60 and len(set(B9)) == 58 and len(set(B10)) == 64, "batch 6–10 scene lists parsed")
ok(not (set(B11) & (old_scenes | set(B5) | set(B6) | set(B7) | set(B8) | set(B9) | set(B10))), f"batch-11 scenes distinct from {len(snap)} delivered films + batches 5–10")
bad = [(f, x["line"], x["scene"], VP.pick_scene(x["visual"])) for f, rows in snap.items() for x in rows
       if VP.pick_scene(x["visual"]) != x["scene"]]
ok(not bad, f"all {sum(len(r) for r in snap.values())} older film lines keep their scenes {bad[:3]}")
for t in ("sharpe_scenes_mock.py", "batch6_scenes_mock.py", "batch7_scenes_mock.py", "batch8_scenes_mock.py", "batch9_scenes_mock.py", "batch10_scenes_mock.py"):
    r = subprocess.run([sys.executable, str(CTL / "tests" / t)], capture_output=True, text=True)
    ok(r.returncode == 0, f"{t} still passes (earlier visuals keep their scenes) {r.stdout[-200:] if r.returncode else ''}")
print(f"{n} ok")
