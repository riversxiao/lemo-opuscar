"""No-network tests for visual_check.py (+ quality visual_check gate + speaker metric).

Builds a tiny synthetic film (PIL + ffmpeg, Noto CJK) with known defects: a caption with
wrong characters, a single corrupt frame, text running off the right edge, and a subtitle
that keeps showing line 1 while line 2 is spoken. Checks that each is reported as high,
that correct text is not flagged, that the semantic layer refuses non-:free models and
stops on any billing delta (OpenRouter calls are monkeypatched), and the rework helpers.
"""
import json, os, subprocess, sys, tempfile, wave
from pathlib import Path
import importlib.util
import shutil

ROOT = Path(__file__).resolve().parents[3]
SKIP = 77  # test_mvp.sh reports this exit code as SKIP (a prerequisite is missing)

# Optional prerequisites: numpy, Pillow, OpenCV, RapidOCR, ffmpeg and a Noto CJK font
# ($WORDFILM_CJK_FONT, else the Debian/Ubuntu fonts-noto-cjk paths).
_missing = [m for m in ("numpy", "PIL", "cv2", "rapidocr_onnxruntime") if importlib.util.find_spec(m) is None]
_missing += [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
FONT = next((p for p in [os.environ.get("WORDFILM_CJK_FONT") or "",
                         "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                         "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"] if p and os.path.exists(p)), None)
if not FONT:
    _missing.append("Noto CJK font (set WORDFILM_CJK_FONT)")
if _missing:
    print("SKIP: missing " + ", ".join(_missing))
    sys.exit(SKIP)

import numpy as np  # noqa: E402

sys.path.insert(0, str(ROOT / "tools" / "deepseek-controller"))
sys.path.insert(0, str(ROOT / "core" / "tts"))
import visual_check as V  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
tmp = Path(tempfile.mkdtemp())
P = tmp / "film"
(P / "audio" / "vo").mkdir(parents=True)
(P / "content").mkdir()
L1, L2 = "政策利率降到零，钱却还是不动。", "日本和美国先后都撞上过这堵墙。"
for lid, sec in (("L01", 1.2), ("L02", 2.0)):
    with wave.open(str(P / "audio" / "vo" / f"{lid}.wav"), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0\0" * int(16000 * sec))
(P / "audio" / "lines.json").write_text(json.dumps([{"id": "L01", "text": L1}, {"id": "L02", "text": L2}], ensure_ascii=False))
# L02 starts inside the hook while the subtitle still shows L01
tl = {"dur": 6.0, "vo": {"L01": 0.1, "L02": 1.5}, "hook": {"t0": 0.0, "t1": 3.0, "zh": "钱不动", "en": L1},
      "caps": [{"id": "L02", "t0": 3.0, "t1": 6.0, "zh": "降息|{失灵}", "en": L2}]}
(P / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False))
(P / "timeline.parsed.json").write_text(json.dumps({"contentDurationSec": 6.0, "shots": [
    {"id": "s1", "t0": 0.0, "t1": 3.0, "voIds": ["L01"], "role": "hook"},
    {"id": "s2", "t0": 3.0, "t1": 6.0, "voIds": ["L02"], "role": "setup"}]}))
# registry (window.TEXTS) — title on screen all the time, hook subtitle during s1
frames = []
for k in range(61):
    t = round(k * 0.1, 3)
    tx = [{"id": "title", "text": "流动性陷阱", "x0": 180, "y0": 180, "x1": 820, "y1": 320}]
    if t < 3.0:
        tx.append({"id": "hook-say", "text": L1, "x0": 100, "y0": 820, "x1": 1300, "y1": 900})
    frames.append({"t": t, "texts": tx})
TEXTS = {"dur": 6.0, "W": 1920, "H": 1080, "frames": frames}
# render 960x540 @ 30 fps: s2 caption drawn WRONG ("降息生效"), edge text off the right side, frame 120 corrupt
f_big, f_sub = ImageFont.truetype(FONT, 56), ImageFont.truetype(FONT, 22)
fps, n = 30, 180
ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "960x540", "-r", str(fps), "-i", "-",
                       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", str(P / "film.mp4")], stdin=subprocess.PIPE)
rng = np.random.default_rng(1)
for i in range(n):
    t = i / fps
    im = Image.new("RGB", (960, 540), (20, 20, 18)); d = ImageDraw.Draw(im)
    for y in range(0, 540, 45):
        d.line([(0, y + int(4 * np.sin(t * 3 + y))), (960, y + 20)], fill=(40, 40, 36), width=2)
    d.text((100, 95), "流动性陷阱", font=f_big, fill=(245, 245, 240))
    d.text((780, 250), "边缘文字", font=f_big, fill=(245, 245, 240))
    if t < 3.0:
        d.text((60, 420), L1, font=f_sub, fill=(245, 245, 240))
    else:
        d.text((60, 400), "降息生效", font=f_big, fill=(245, 245, 240))
        d.text((60, 480), L2, font=f_sub, fill=(245, 245, 240))
    a = np.asarray(im)
    if i == 120:
        a = rng.integers(0, 255, a.shape, dtype=np.uint8)
    ff.stdin.write(a.tobytes())
ff.stdin.close(); assert ff.wait() == 0

rep = V.run_check(P, P / "film.mp4", semantic=False, texts=TEXTS)
kinds_hi = {(i["kind"], i.get("src", "")) for i in rep["issues"] if i["severity"] == "high"}
hk = {k for k, _ in kinds_hi}
print("high:", sorted(kinds_hi))
assert ("ocr_mismatch", "cap:L02:zh") in kinds_hi, "wrong caption chars not caught"
assert "corrupt_frame" in hk, "corrupt frame not caught"
assert "text_clipped" in hk, "edge-clipped text not caught"
assert "subtitle_vo_mismatch" in hk, "subtitle ≠ narration not caught"
assert not any(i["kind"] == "ocr_mismatch" and i.get("src") in ("tx:title", "cap:L02:sub", "tx:hook-say") for i in rep["issues"]), \
    "correct text flagged (false positive)"
assert rep["status"] == "FAIL" and rep["contactSheets"].get("s1") and Path(rep["contactSheets"]["s1"]).exists()
V.mark_evidence(rep["issues"], tmp / "ev")
assert any(i.get("screenshot") for i in rep["issues"] if i["severity"] == "high")

# --- semantic layer: free-only, billing verified, never paid
sch = V.Schedule(P, TEXTS)
sheets = rep["contactSheets"]
os.environ.pop("OPENROUTER_API_KEY", None)
assert V.semantic_layer(sch, sheets, V.FREE_DEFAULT, True)["status"] == "NOT_AVAILABLE"
os.environ["OPENROUTER_API_KEY"] = "sk-or-mock"
assert V.semantic_layer(sch, sheets, ["openai/gpt-4o"], True)["status"] == "NOT_AVAILABLE", "paid model not refused"
try:
    V._or_chat("k", "openai/gpt-4o", "x", "y"); raise SystemExit("paid model call not refused")
except AssertionError:
    pass
calls = []
V._or_usage = lambda key: 1.0
def fake_chat(key, model, prompt, img, timeout=180):
    calls.append(model)
    if "s2" in str(len(calls)) or len(calls) == 2:
        return json.dumps({"topic_match": True, "contradiction": "画面说美国，旁白说日本", "overcrowded": False,
                           "visual_errors": [], "garbled_glyphs": None, "confidence": 0.9}), {"cost": 0}
    return '{"topic_match": true, "contradiction": null, "overcrowded": false, "visual_errors": [], "garbled_glyphs": null, "confidence": 0.9}', {"cost": 0}
V._or_chat = fake_chat
sem = V.semantic_layer(sch, sheets, ["a/free-model:free"], True)
assert sem["status"] == "PASS" and sem["billing"]["verified"] and sem["model"] == "a/free-model:free", sem
assert any(i["kind"] == "semantic_contradiction" and i["severity"] == "high" for i in sem["issues"])
seq = iter([1.0, 1.25, 1.25])
V._or_usage = lambda key: next(seq)
calls.clear()
sem = V.semantic_layer(sch, sheets, ["a/free-model:free"], True)
assert sem["status"] == "FAIL" and len(calls) == 1 and sem["billing"]["deltaUsd"] == 0.25, sem  # stops after the first charged call

# --- rework helpers: hook subtitle switching (only when main.js is unlocked)
(P / "main.js").write_text("let HOOK_CUE=[];\nfunction shotHook(s,t){ const ke = 1; text(HOOK_CUE[3] || '默认', 1);\n  TX.push({ id: 'hook-a', text: 'x' });\n  if (ke > 0) TX.push({ id: 'hook-say', text: HOOK_CUE[3] || '默认', x0: 1 });\n}\n")
(P / "content" / "engine.lock.json").write_text(json.dumps({"unlocked": []}))
(P / "audio" / "cues.json").write_text(json.dumps([{"t0": 0.0, "t1": 3.0, "text": "钱不动\n" + L1}, {"t0": 3.0, "t1": 6.0, "text": L2}], ensure_ascii=False))
tl["hook"]["t1"] = 6.0; tl["vo"]["L02"] = 3.2; (P / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False))
ok, why, _ = V.fix_hook_subs(P, V.Schedule(P, None))
assert not ok and "locked" in why, why
(P / "content" / "engine.lock.json").write_text(json.dumps({"unlocked": ["main.js"]}))
ok, why, rg = V.fix_hook_subs(P, V.Schedule(P, None))
js = (P / "main.js").read_text()
assert ok and js.count("hookSay(t)") == 1 and "const hookSay" in js and "id: 'hook-say'" not in js and "id: 'hook-a'" in js and rg == [(0.0, 6.0)], (why, js)
subs = json.loads((P / "timeline.json").read_text())["hook"]["subs"]
assert [s["id"] for s in subs] == ["L01", "L02"] and subs[1]["en"] == L2 and subs[0]["t1"] == subs[1]["t0"], subs
cues = json.loads((P / "audio" / "cues.json").read_text())
assert cues[1]["text"] == L2 and cues[0]["t1"] < cues[1]["t1"], cues
tl2 = json.loads((P / "timeline.json").read_text())
tl2["caps"] = [{"id": "C1", "t0": 3.0, "t1": 3.6, "zh": "很长很长的一句大字幕标题", "en": ""}]
(P / "timeline.json").write_text(json.dumps(tl2, ensure_ascii=False))
ri = V.readtime_issues(V.Schedule(P, None))
assert ri and ri[0]["severity"] == "high", ri
ok, why, rg = V.fix_caption(P, V.Schedule(P, None), ri[0])
assert ok and json.loads((P / "timeline.json").read_text())["caps"][0]["t1"] > 3.6, why

# --- quality gate reads evidence/visual-check.json
import quality as Q  # noqa: E402
m = P / "film.mp4"
ev = P / "evidence"; ev.mkdir(exist_ok=True)
(ev / "visual-check.json").unlink(missing_ok=True)
assert Q.run_visual_check_gate(P, m, True)["status"] == "NOT_CHECKED"
assert Q.run_visual_check_gate(P, m, False)["required"] is False
(ev / "visual-check.json").write_text(json.dumps({"media": str(m), "finalStatus": "PASS", "issues": [], "medium": 2, "semantic": {"status": "NOT_AVAILABLE"}}))
g = Q.run_visual_check_gate(P, m, True); assert g["status"] == "PASS" and g["required"], g
(ev / "visual-check.json").write_text(json.dumps({"media": str(m), "finalStatus": "BEST_EFFORT", "issues": [{"severity": "high", "kind": "subtitle_vo_mismatch"}]}))
g = Q.run_visual_check_gate(P, m, True); assert g["status"] == "FAIL" and "severity=high" in g["detail"], g
(ev / "visual-check.json").write_text(json.dumps({"media": str(tmp / "other.mp4"), "finalStatus": "PASS", "issues": []}))
assert Q.run_visual_check_gate(P, m, True)["status"] == "NOT_CHECKED", "report for another file accepted"
(ev / "visual-check.json").write_text(json.dumps({"media": str(m), "finalStatus": "PASS", "issues": []}))
os.utime(m, (os.path.getmtime(ev / "visual-check.json") + 60,) * 2)
assert Q.run_visual_check_gate(P, m, True)["status"] == "NOT_CHECKED", "stale report accepted"

# --- speaker metric (pure): one voice passes, an off-voice line fails
import speaker_check as SC  # noqa: E402
r = np.random.default_rng(0); base = r.normal(size=256)
E = np.stack([base + 0.25 * r.normal(size=256) for _ in range(5)])
assert SC.score([f"L{i}" for i in range(5)], E)["status"] == "PASS"
E[2] = r.normal(size=256)
d = SC.score([f"L{i}" for i in range(5)], E); assert d["status"] == "FAIL" and d["belowMin"] == ["L2"], d
print("visual_check mock OK")
