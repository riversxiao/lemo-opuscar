"""Offline checks for the Cantonese-drift fix (no network, no EL characters):
language_code per line (zh Mandarin / en / mixed), `elevenlabs:` voice prefix, split runs,
dialect_check.classify rule, batch_terms from-draft wording lock."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "core" / "tts")); sys.path.insert(0, str(ROOT / "tools" / "deepseek-controller"))
import numpy as np
from providers import elevenlabs as E
import dialect_check as D
import batch_terms as B
n = 0
def ok(c, m):
    global n
    assert c, m; n += 1
calls = []
def fake(text, **kw):
    calls.append(dict(kw, text=text)); return (np.ones(4800, "<i2") * 1000).tobytes(), "audio/pcm"
E._post_tts = fake; E.http_speech._trim = lambda a, sr: a
os.environ["ELEVENLABS_API_KEY"] = "x"; os.environ.pop("LEMO_TTS_ELEVENLABS_LANGUAGE", None)
with tempfile.TemporaryDirectory() as d:
    E.synthesize([{"id": "L01", "text": "大盘跌一点。", "voice": "elevenlabs:TKaUqol7GKx4m7enpCpP"},
                  {"id": "L02", "text": "Beta is how hard it swings."},
                  {"id": "L03", "text": "叫贝塔，Beta。", "lang": "mixed"}], d, voice="elevenlabs:TKaUqol7GKx4m7enpCpP")
    sp = json.load(open(d + "/spoken.json"))
ok([c["language"] for c in calls] == ["zh", "en", "zh"], f"language per line {calls}")
ok(all(c["voice"] == "TKaUqol7GKx4m7enpCpP" for c in calls), "prefix stripped")
ok(sp["voice"] == "TKaUqol7GKx4m7enpCpP" and sp["langs"] == {"L01": "zh", "L02": "en", "L03": "mixed"}, "spoken.json langs")
ok(calls[1]["previous_text"] == "大盘跌一点。" and calls[0]["next_text"] == "Beta is how hard it swings.", "context")
calls.clear(); os.environ["LEMO_TTS_ELEVENLABS_MIXED"] = "split"
with tempfile.TemporaryDirectory() as d:
    E.synthesize([{"id": "L03", "text": "叫贝塔，Beta。", "lang": "mixed"}], d, voice="TKaUqol7GKx4m7enpCpP")
    sp = json.load(open(d + "/spoken.json"))
ok([(c["language"], c["text"]) for c in calls] == [("zh", "叫贝塔，"), ("en", "Beta。")], f"split {calls}")
ok([s["lang"] for s in sp["segments"]["L03"]] == ["zh", "en"], "segments")
os.environ.pop("LEMO_TTS_ELEVENLABS_MIXED")
ok(E.split_lang("贝塔大于一。") == [("zh", "贝塔大于一。")], "no latin → one zh run")
ok(E._post_tts is fake and E.norm_voice("TKa") == "TKa", "bare id")
# dialect rule
ok(D.classify({"yue": .997, "cmn": .002}, "zh", .5, .2)[0] == "FAIL", "yue fails")
ok(D.classify({"cmn": .999}, "zh", .5, .2)[0] == "PASS", "cmn passes")
ok(D.classify({"eng": .997}, "en", .5, .2)[0] == "PASS", "intended English passes")
ok(D.classify({"cmn": .868, "mya": .047, "yue": .033}, "mixed", .5, .2)[0] == "PASS", "mixed Beta line passes")
ok(D.classify({"eng": .7, "cmn": .3}, "mixed", .5, .2)[0] == "PASS", "mixed heard as eng allowed")
ok(D.classify({"eng": .7, "cmn": .3}, "zh", .5, .2)[0] == "WARN", "zh heard as eng → WARN only")
ok(D.classify({"yue": .4, "cmn": .6}, "zh", .5, .2)[0] == "WARN", "weak yue → WARN, no over-correction")
ok(D.classify({"cmn": .9, "yue": .1}, "en", .5, .2)[0] == "WARN", "en line never FAILs")
# from-draft
with tempfile.TemporaryDirectory() as d:
    t = Path(d) / "t"; (t / "src").mkdir(parents=True)
    (t / "src" / "lines.json").write_text(json.dumps({"approvedBy": "x", "lines": [
        {"id": "L01", "cap": "叫{贝塔}（Beta）。", "say": "叫贝塔。", "shot": "p1", "role": "hook"}]}, ensure_ascii=False), "utf-8")
    dr = Path(d) / "d.json"
    dr.write_text(json.dumps([{"id": "L01", "text": "叫贝塔（Beta）。", "say": "叫贝塔。", "visual": "两条线",
                               "voice": "elevenlabs:TKaUqol7GKx4m7enpCpP"}], ensure_ascii=False), "utf-8")
    before = dr.read_bytes()
    ok(B.main(["from-draft", "--draft", str(dr), "--term", str(t)]) == 0, "from-draft ok")
    L = json.loads((t / "src" / "lines.json").read_text("utf-8"))
    ok(L["voice"] == "TKaUqol7GKx4m7enpCpP" and L["lines"][0]["visual"] == "两条线", "copied visual/voice")
    ok(dr.read_bytes() == before, "draft untouched")
    dr.write_text(json.dumps([{"id": "L01", "text": "叫贝塔。", "visual": "x"}], ensure_ascii=False), "utf-8")
    ok(B.main(["from-draft", "--draft", str(dr), "--term", str(t)]) == 1, "paraphrase refused")
print(f"elevenlabs language mock OK ({n} checks)")
