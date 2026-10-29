#!/usr/bin/env python3
"""finance-v003 mock: viz_pick scene mapping + 金融专家 content lint, visual_dupe compare,
apply_pictogram_edl viz merge, quality TP ceiling + viz gates. Offline, no keys."""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import viz_pick as V
import visual_dupe as VD
import quality as Q
n = 0
def ok(c, m):
    global n
    assert c, m
    n += 1; print("ok", m)

beta = [("L01", "大盘线轻轻往下一点，个股线猛地下坠一大截"), ("L02", "两条线并排起伏，标出振幅差距"),
        ("L03", "大盘挪一格，个股跳两格"), ("L04", "大浪压过小浪，贝塔>1"), ("L05", "风平浪静的小船"),
        ("L06", "上下对称：涨得高，跌得也深"), ("L07", "一个人坐在过山车上，停在下坡前")]
sc = [V.pick_scene(v) for _, v in beta]
ok(len(set(sc)) == 7 and None not in sc, "beta visuals map to 7 distinct scenes")
shots = [{"line": i, "visual": v, "scene": s, "data": V.scene_data(s, i)} for (i, v), s in zip(beta, sc)]
ok(V.lint(shots, []) == [], "beta lint clean")
bad = [{"line": "X1", "visual": "桌上一堆筹码", "scene": "boat", "data": {}},
       {"line": "X2", "visual": "某某成长基金的K线截图", "scene": "waves", "data": {}},
       {"line": "X3", "visual": "代码 600519 的走势", "scene": "plunge", "data": {}},
       {"line": "X4", "visual": "一条线", "scene": "coaster", "data": {"curves": {"c": list(range(10))}}},
       {"line": "X5", "visual": "又一条", "scene": "coaster", "data": {}}]
rules = {(i["line"], i["rule"]) for i in V.lint(bad, ["赌场之夜"])}
ok(("X1", "gambling imagery") in rules, "chips → gambling imagery FAIL")
ok(("X2", "named fund") in rules and ("X2", "K-line / screenshot") in rules, "named fund + K线截图 FAIL")
ok(("X3", "real ticker / stock code") in rules, "6-digit stock code FAIL")
ok(("X4", "monotonically rising curve implies returns") in rules, "monotonic rising curve FAIL")
ok(any(r.startswith("duplicate scene") for _, r in rules), "same scene twice in a film FAIL")
ok(("-", "gambling imagery (on-screen text)") in rules, "on-screen strings linted")
ok(V.pick_scene("一只猫") is None, "unmapped visual → no scene (FAIL, extend library)")

rng = np.random.default_rng(1)
a = {"bits": rng.random(64) > .5, "lay": (lambda x: x / np.linalg.norm(x))(rng.standard_normal(1296)), "col": rng.random(48) * 255}
ok(VD.compare(a, a)["dup"], "identical keyframes → near-duplicate")
b = {"bits": rng.random(64) > .5, "lay": (lambda x: x / np.linalg.norm(x))(rng.standard_normal(1296)), "col": rng.random(48) * 255}
ok(not VD.compare(a, b)["dup"], "unrelated keyframes → distinct")

import apply_pictogram_edl as A
with tempfile.TemporaryDirectory() as td:
    p = Path(td); (p / "content").mkdir()
    (p / "content" / "viz.json").write_text(json.dumps({"shots": [{"shot": "p6", "scene": "coaster", "data": {}}]}))
    comp = [{"id": "p5", "dur": 3.0}, {"id": "p6", "dur": 5.0}]
    A._merge_viz(p, comp, [{"id": "p6", "outroSec": 1.5}])
    ok(comp[1]["viz"]["scene"] == "coaster" and abs(comp[1]["vizDur"] - 3.5) < 1e-6 and "viz" not in comp[0], "viz merged by shot id; vizDur = dur − outro")
    ok(Q._tp_max(p) == -2.0, "v003 film → TP ≤ −2 dBTP")
    g = {c["name"]: c for c in Q.run_viz_gates(p, None)}
    ok(g["visual_content"]["status"] == "NOT_CHECKED" and g["visual_duplicate"]["required"], "viz gates required once viz.json exists")
    (p / "evidence").mkdir()
    (p / "evidence" / "visual-content.json").write_text(json.dumps({"status": "FAIL", "issues": [{"line": "L1", "rule": "gambling imagery"}], "scenes": {}}))
    (p / "evidence" / "visual-dupe.json").write_text(json.dumps({"status": "FAIL", "duplicates": [{}], "closest": [{"a": "x", "b": "y", "ham": 1, "corr": .97}]}))
    g = {c["name"]: c for c in Q.run_viz_gates(p, None)}
    ok(g["visual_content"]["status"] == "FAIL" and "gambling" in g["visual_content"]["detail"], "content lint FAIL blocks")
    ok(g["visual_duplicate"]["status"] == "FAIL", "near-duplicate FAIL blocks")
with tempfile.TemporaryDirectory() as td:
    ok(Q._tp_max(Path(td)) == -1.0, "legacy film keeps TP ≤ −1")
    g = {c["name"]: c for c in Q.run_viz_gates(Path(td), None)}
    ok(g["visual_content"]["status"] == "NOT_APPLICABLE" and not g["visual_content"]["required"], "pre-v003 film: viz gates not applicable")
print(f"viz mock: {n} checks OK")
