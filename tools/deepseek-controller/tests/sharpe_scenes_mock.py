#!/usr/bin/env python3
"""finance-v003 batch-5 scenes (Sharpe long, 13 lines; no network): 13 Sharpe-long visuals → 13 distinct drawn scenes,
distinct from every delivered film's scenes, content lint clean, and every earlier film (fixtures/viz-scene-snapshot.json)
still maps each line's visual to the same scene."""
from __future__ import annotations

import json
import re
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


SV = ["两根一样高的收益柱子并排，中间一个问号", "一张记分卡，卡头写「Sharpe」",
      "两个篮子贴「甲」「乙」，头顶各亮「+8%」，角标「假设」", "两条收益线：甲贴着平线微微起伏，乙大起大落，跌的部分往下",
      "两根柱子底部各切下一小段，标「国债回报（起步价）」", "切掉底部后剩下的两段一样高，各标「+6%」",
      "乙那条线的上下摆动被一个上下双箭头框住，标「晃动」", "甲背一个小沙袋、乙背一个大沙袋，各自手里拿着同样大小的「+6%」",
      "记分卡上「Sharpe」下面：一份晃动对应一摞小硬币", "甲的记分卡分数格更满，乙的少一截，不出现任何真实名称",
      "记分卡背面是一本翻旧的账本，前方是一团雾", "一把放在桌上的尺子，旁边空着的椅子，没人替你按按钮",
      "回到开头两根一样高的柱子，这次各背着大小不同的沙袋"]
B5 = ["twin_q", "score_sharpe", "baskets_8", "calm_wild", "pillars_cut", "remain_six", "swing_box", "sandbags",
      "coin_stack", "score_fill", "card_fog", "ruler_chair", "bag_pillars"]

got = [VP.pick_scene(v) for v in SV]
ok(got == B5 and len(set(got)) == 13, "Sharpe long visuals → 13 distinct batch-5 scenes")
sj = (REPO / "styles" / "pictogram-motion" / "versions" / "finance-v003" / "scenes.js").read_text("utf-8")
ok(all(f"VIZ.{s} =" in sj and re.search(rf"\b{s}: '", sj) for s in B5), "every batch-5 scene drawn + palette in finance-v003 scenes.js")
ok("const SHARPE = 'Sharpe'" in sj and "SHARPE'" not in sj.replace("const SHARPE = 'Sharpe'", ""), "screen label is mixed-case 'Sharpe'")
shots = [{"line": f"L{i + 1:02d}", "visual": SV[i], "scene": s, "data": VP.scene_data(s, f"L{i + 1:02d}")} for i, s in enumerate(got)]
ok(VP.lint(shots, SV) == [], "lint clean (no tickers/fund names/K-lines/gambling/rising-only/dupes)")
# batch-5 draw code: no formulas / fund names / gambling words on screen
b5 = sj[sj.index("batch 5 (Sharpe long"):sj.index("function vizScene")]
ok(not re.search(r"基金|ETF|筹码|赌|骰|σ|Rp|Rf|÷|公式|值得买", b5), "batch-5 scene text: no formulas, funds or buy-signals")

snap = json.loads((CTL / "fixtures" / "viz-scene-snapshot.json").read_text("utf-8"))["films"]
old_scenes = {x["scene"] for rows in snap.values() for x in rows}
ok(len(snap) >= 8 and not (set(B5) & old_scenes), f"batch-5 scenes distinct from {len(snap)} delivered films' scenes")
bad = [(f, x["line"], x["scene"], VP.pick_scene(x["visual"])) for f, rows in snap.items() for x in rows
       if VP.pick_scene(x["visual"]) != x["scene"]]
ok(not bad, f"all {sum(len(r) for r in snap.values())} older film lines keep their scenes {bad[:3]}")
print(f"{n} ok")
