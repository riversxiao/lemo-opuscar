#!/usr/bin/env python3
"""Variable-length finance-term mocks (no network): 5–17 lines with matching cards/shots, tiered ceilings
(≤7→40 · ≤10→55 · ≤14→75 · ≤17→90, override clamped 15..90), plan refusals, init-from-draft (draft read-only,
never writes into dialogue-drafts, wording verbatim, one shot per line), manifest 90 s, and batch-3
scenes: 14 VaR-long visuals → 14 distinct scenes, lint clean, older films' mappings unchanged."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

CTL = Path(__file__).resolve().parents[1]
REPO = CTL.parents[1]
sys.path[:0] = [str(CTL)]
import batch_terms as BT  # noqa: E402
import viz_pick as VP  # noqa: E402

n = 0


def ok(c, m):
    global n
    if not c:
        print("FAIL:", m)
        sys.exit(1)
    n += 1
    print("ok", m)


td = Path(tempfile.mkdtemp(prefix="varlen-mock-"))

# 1) tiers + override clamp
ok([BT.target_for(k) for k in (5, 7, 8, 10, 11, 14, 15, 17)] == [40, 40, 55, 55, 75, 75, 90, 90], "tiered ceilings 40/55/75/90")
ok(BT.target_for(14, 120) == 90 and BT.target_for(14, 85) == 85 and BT.target_for(7, 30) == 30 and BT.target_for(7, 5) == 15,
   "override clamped 15..90")
ok(BT.DURATION_CEIL == 90 and (BT.LINES_MIN, BT.LINES_MAX) == (5, 17), "5..17 lines, 90 s ceiling")
man = json.loads((CTL / "manifests" / "pictogram-motion.json").read_text("utf-8"))
ok(man["durationSec"]["max"] == 90, "manifest pictogram-motion durationSec max 90")

# 2) shots_for: 14 cards → intro, chapter, cards, hard-cut on the turn, finale
ids = [f"p{i}" for i in range(14)]
sh = BT.shots_for(ids, {"p8"})
ok([s["id"] for s in sh] == ids, "14 shots follow the cards")
ok([sh[0]["motionPreset"], sh[1]["motionPreset"], sh[-1]["motionPreset"]] == ["intro", "chapter", "finale"], "intro/chapter/finale ends")
ok(sh[8]["motionPreset"] == "hard-cut" and sum(s["motionPreset"] == "hard-cut" for s in sh) == 1, "turn shot = the one hard-cut")
ok(all(s["motionPreset"] == "card" for s in sh[2:8] + sh[9:13]), "middle shots are cards")
ok(all(s.get("beats") == 4 for s in sh), "4 beats per shot (schedule stretches to VO)")

# 3) skeletons + plan refusal outside 5..17
for k in (5, 14, 17):
    S = BT.skeleton_lines(k)
    ok(len(S["lines"]) == k and len(S["cards"]) == k, f"skeleton --lines {k}")
for bad in (4, 18):
    try:
        BT.skeleton_lines(bad)
        ok(False, f"skeleton {bad} refused")
    except SystemExit:
        ok(True, f"skeleton --lines {bad} refused")

VIS = [
    "大大的「100万」，下面一条线被打上叉，标「上限」",
    "一栋不写名字的银行大楼，楼前立着一张只有一个数字的报告卡，卡角标「VaR」",
    "三个格子依次亮起：钱袋、时钟、百分比刻度",
    "三个格子里填上「一天」「99%」「100万（假设）」",
    "一百个日历方块排成十乘十，九十九个在门槛线下方，一个是红色",
    "那个红色方块越过门槛线，标「超线」",
    "换成一整年的日历条，大约二百五十格，里面零散亮起两三个红格",
    "红格不再零散，而是几个挤在一起连着亮",
    "门槛线下面没有底，一片看不到头的黑，红格往下掉",
    "一本旧账本翻开，数字飘出来拼成那条门槛线",
    "天色骤变，门槛线开始抖动、变虚",
    "预期的两三个红格旁边，实际亮起一大片红格，没有任何机构名",
    "镜头推到最深的几个红格，取平均画出一条更低的线，屏幕标「预期尾部损失 ES」",
    "银行大楼立在门槛线上，低头看线下那片黑，画面停住",
]


def draft(k):
    fn = ["hook"] + ["evidence"] * (k - 3) + ["turn", "payoff"]
    return [{"id": f"L{i + 1:02d}", "cap": f"第{i + 1}句说{{要点{i + 1}}}。", "text": f"第{i + 1}句说要点{i + 1}。",
             "function": fn[i], "voice": "elevenlabs:TKaUqol7GKx4m7enpCpP", "speed": 1.0, "visual": VIS[i % 14]}
            for i in range(k)]


meta = {"seq": "042", "en": "Value at Risk", "zh": "风险价值", "short": "VaR", "area": "风险度量", "slug": "var"}
mp = td / "term.json"
mp.write_text(json.dumps(meta, ensure_ascii=False), "utf-8")
dd = td / "dialogue-drafts"
dd.mkdir()


def init(k, term, extra=()):
    dp = dd / f"d{k}.lines.json"
    dp.write_text(json.dumps(draft(k), ensure_ascii=False), "utf-8")
    return dp, BT.main(["init-from-draft", "--draft", str(dp), "--term", str(term), "--approved-by", "金融专家 mock",
                        "--meta", str(mp), *extra])


# 4) init-from-draft: draft read-only; refuses a term inside dialogue-drafts
dp, rc = init(14, td / "t14")
before = hashlib.sha256(dp.read_bytes()).hexdigest()
L = json.loads((td / "t14" / "src" / "lines.json").read_text("utf-8"))
ok(rc == 0 and len(L["lines"]) == 14 and [c["shot"] for c in L["cards"]] == ids, "init-from-draft: 14 lines, one card/shot each")
ok([x["cap"] for x in L["lines"]] == [x["cap"] for x in draft(14)], "caps verbatim")
ok(all(x.get("visual") == VIS[i] for i, x in enumerate(L["lines"])), "per-line visual copied")
ok(L.get("voice") == "TKaUqol7GKx4m7enpCpP", "voice: elevenlabs: prefix stripped")
try:
    BT.main(["init-from-draft", "--draft", str(dp), "--term", str(dd / "bad"), "--approved-by", "x", "--meta", str(mp)])
    ok(False, "refuses term inside dialogue-drafts")
except SystemExit:
    ok(not (dd / "bad").exists(), "refuses to write into dialogue-drafts")
ok(sorted(p.name for p in dd.iterdir()) == ["d14.lines.json"] and hashlib.sha256(dp.read_bytes()).hexdigest() == before,
   "draft folder untouched")

# 5) plan: 14 lines → 14 shots, ceiling 75, turn hard-cut; 7 → 40; 10 → 55
for k, tgt in ((17, 90), (15, 90), (14, 75), (10, 55), (7, 40), (5, 40)):
    term = td / f"p{k}"
    init(k, term)
    plan, _ = BT.build_plan(term)
    ok(len(plan["shots"]) == k and plan["targetDurationSec"] == tgt and len(plan["voice"]["lines"]) == k,
       f"plan {k} lines → {k} shots, ceiling {tgt}s")
    ok(plan["shots"][k - 2]["motionPreset"] == "hard-cut", f"plan {k}: turn shot hard-cut")
    ok(BT.main(["plan", "--term", str(term)]) == 0, f"plan {k} validates")

# 6) plan refusals: 4 / 15 lines, card without line, line without card, out of order
def refused(mut, msg):
    term = td / ("r" + str(abs(hash(msg)) % 10 ** 6))
    init(7, term)
    lp = term / "src" / "lines.json"
    X = json.loads(lp.read_text("utf-8"))
    mut(X)
    lp.write_text(json.dumps(X, ensure_ascii=False), "utf-8")
    try:
        BT.build_plan(term)
        ok(False, msg)
    except SystemExit:
        ok(True, msg)


refused(lambda X: (X["lines"].__delitem__(slice(4, 7)), X["cards"].__delitem__(slice(4, 7))), "plan refuses 4 lines")
refused(lambda X: (X["lines"].extend(dict(x, id=f"L{20 + i}", shot=f"p{7 + i}") for i, x in enumerate(X["lines"] + X["lines"][:4])),
                   X["cards"].extend({"shot": f"p{7 + i}", "zh": "卡", "en": "C"} for i in range(11))), "plan refuses 18 lines")
refused(lambda X: X["cards"].append({"shot": "p7", "zh": "多", "en": "X"}), "plan refuses a card with no line")
refused(lambda X: X["lines"][3].update(shot="p9"), "plan refuses a line with no card")
refused(lambda X: X["lines"].__setitem__(slice(2, 4), X["lines"][3:1:-1]), "plan refuses lines out of card order")

# 7) batch-3 scenes: 14 VaR-long visuals → 14 distinct scenes; lint clean; old films unchanged
B3 = ["cap_crossed", "bank_report", "three_slots", "slots_filled", "grid_10x10", "square_over", "year_strip",
      "red_cluster", "bottomless", "old_ledger", "sky_change", "expect_actual", "tail_dots_es", "bank_on_line"]
got = [VP.pick_scene(v) for v in VIS]
ok(got == B3, f"VaR long visuals → batch-3 scenes ({len(set(got))} distinct)")
shots = [{"line": f"L{i + 1:02d}", "visual": VIS[i], "scene": s, "data": VP.scene_data(s, f"L{i + 1:02d}")}
         for i, s in enumerate(got)]
ok(VP.lint(shots, VIS) == [], "lint clean (no tickers/K-lines/rising-only/dupes)")
sj = (REPO / "styles" / "pictogram-motion" / "versions" / "finance-v003" / "scenes.js").read_text("utf-8")
ok(all(f"VIZ.{s} " in sj or f"VIZ.{s}=" in sj or f"VIZ.{s} =" in sj for s in B3), "every batch-3 scene drawn in finance-v003 scenes.js")
# regression: earlier finance-v003 films keep their scenes (series index)
OLD = {
    "大大的「100万」数字，旁边一个打叉的「最多」": "big_number_x",
    "一条水平门槛线，线上标「100万」和「风险价值」": "threshold_line",
    "一排日子方块落在门槛线下，安安稳稳": "days_below",
    "100个日历方块，99个绿色在线下，1个红色闪烁": "calendar_100",
    "那一个红色方块冲破门槛线，往下掉得很深": "red_breach",
    "门槛线亮着，线下面一片黑，打一个问号": "dark_below",
    "镜头往下推到最深的那几格红色方块，取平均画一条更低的线": "tail_avg",
}
beta = json.loads((CTL / "templates" / "finance-term" / "examples" / "004-beta-v001.lines.json").read_text("utf-8"))
bl = beta if isinstance(beta, list) else beta["lines"]
OLD.update(zip([x["visual"] for x in bl], ["plunge", "swing_label", "step_blocks", "waves", "boat", "mirror_updown", "coaster"]))
ok(all(VP.pick_scene(v) == sc for v, sc in OLD.items()), "var-plain-v004 + beta scene mappings unchanged")
# 8) batch-4 scenes: 13 CAPM-long visuals → 13 distinct scenes; capm-v001 keeps its scenes
CV = ["一架天平：一边放「风险」，一边放「回报」，天平只翘起一半", "一把尺子：一头刻「风险」，一头刻「该要的回报」，尺子上标「CAPM」",
      "画面一分为二：左边一栋不写名字的小楼冒烟，右边先空着", "一栋冒烟的小楼旁边排出一整排小楼，烟被稀释得几乎看不见",
      "右边整片地面一起下沉，上面所有小楼一起往下走", "小楼再多，地面下沉时全都跟着沉，一栋也没躲开",
      "左边的烟旁边放着一个空的奖励盒，盖子是开的，里面什么都没有", "一根回报柱子分成上下两段，先亮出分界线",
      "柱子底下那段亮起，标「起步价（如国债）」", "柱子上面那段随着一条晃动的曲线变高：晃得越猛，这段越高",
      "柱子变成虚线的「预期」，旁边实际的柱子有的矮一截、有的掉到零线以下", "那把 CAPM 尺子放在桌上，旁边一个水晶球被打叉",
      "画面回到整片下沉的地面，天平这次稳稳地翘向「躲不掉的风险」一侧"]
B4 = ["balance_half", "ruler_capm", "split_smoke", "row_dilute", "ground_sink", "all_sink", "empty_box", "pillar_split",
      "pillar_base", "pillar_wiggle", "expect_dashed", "ruler_crystal", "balance_settle"]
ok([VP.pick_scene(v) for v in CV] == B4 and all(f"VIZ.{s} =" in sj and f" {s}: '" in sj for s in B4), "CAPM long visuals → 13 drawn batch-4 scenes")
ok(VP.pick_scene("一架天平：一边放「冒险」，一边放「回报」，天平只翘起一半") == "scale_half", "capm-v001 天平 still scale_half")
import apply_pictogram_edl as APE  # noqa: E402
ok("'门槛 100万'" not in sj and sj.count("LOSS_TH") >= 3 and "'亏损门槛 ' + brandStr('thresholdAmount', '100万')" in sj
   and {"thresholdLabel", "thresholdAmount"} <= set(APE.BRAND_KEYS), "threshold label 「亏损门槛 <金额>」 (brand thresholdAmount/thresholdLabel)")
print(f"{n} ok")
