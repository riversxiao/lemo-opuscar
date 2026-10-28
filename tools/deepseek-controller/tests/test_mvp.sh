#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CTL="$ROOT/tools/deepseek-controller"
CLI=(python3 "$CTL/cli.py")
FIX="$CTL/fixtures"
pass=0
fail=0

ok() { echo "PASS: $*"; pass=$((pass+1)); }
bad() { echo "FAIL: $*"; fail=$((fail+1)); }

# 1) invalid plan rejected
if "${CLI[@]}" validate "$FIX/plan-invalid.json" >/tmp/dc-val.out 2>/tmp/dc-val.err; then
  bad "invalid plan should exit non-zero"
else
  ok "invalid plan rejected"
fi

# 2) valid plans validate
for p in plan-swiss-motion.json plan-pictogram-motion.json plan-caption-news.json; do
  if "${CLI[@]}" validate "$FIX/$p" >/dev/null; then
    ok "validate $p"
  else
    bad "validate $p"
  fi
done

# 3) adapt writes content
rm -rf /tmp/dc-adapt-swiss
if "${CLI[@]}" adapt "$FIX/plan-swiss-motion.json" -o /tmp/dc-adapt-swiss >/dev/null \
  && test -f /tmp/dc-adapt-swiss/content/shots.json \
  && test -f /tmp/dc-adapt-swiss/content/lines.json; then
  ok "adapt swiss writes content-only files"
else
  bad "adapt swiss"
fi

# ensure adapt did not create engine cores
if test ! -e /tmp/dc-adapt-swiss/ease.js && test ! -e /tmp/dc-adapt-swiss/film.js; then
  ok "adapt does not copy engine cores"
else
  bad "adapt leaked engine files"
fi

# 4) schedule fails when VO too long
if "${CLI[@]}" schedule --project "$FIX/schedule-too-long" --require-vo >/tmp/dc-sch.out 2>/tmp/dc-sch.err; then
  bad "schedule should fail when VO too long"
else
  if grep -q "exceeds target" /tmp/dc-sch.err; then
    ok "schedule fails when VO too long"
  else
    bad "schedule failed but missing exceeds-target message: $(cat /tmp/dc-sch.err)"
  fi
fi

# 5) schedule OK with short durs
if "${CLI[@]}" schedule --project "$FIX/out-swiss-motion" --require-vo >/tmp/dc-sch2.out 2>/tmp/dc-sch2.err; then
  ok "schedule OK with measured short VO"
else
  bad "schedule short VO: $(cat /tmp/dc-sch2.err)"
fi

# 6) quality fails on forced FAIL
if "${CLI[@]}" quality --project "$FIX/out-swiss-motion" --skip-heavy --allow-unchecked \
  --force-fail fixture_forced_fail -o "$FIX/quality-fail/quality.json" \
  >/tmp/dc-q.out 2>/tmp/dc-q.err; then
  bad "quality should fail with --force-fail"
else
  if grep -q 'overall=FAIL' /tmp/dc-q.out; then
    ok "quality fails when forced FAIL"
  else
    bad "quality force-fail output unexpected: $(cat /tmp/dc-q.out) $(cat /tmp/dc-q.err)"
  fi
fi

# 7) quality can PASS content-stage with allow-unchecked (no force)
if "${CLI[@]}" quality --project "$FIX/out-swiss-motion" --skip-heavy --allow-unchecked \
  -o /tmp/dc-quality-pass.json >/tmp/dc-q2.out 2>/tmp/dc-q2.err; then
  ok "quality PASS with --allow-unchecked at content stage"
else
  bad "quality allow-unchecked: $(cat /tmp/dc-q2.out) $(cat /tmp/dc-q2.err)"
fi

# 8–10) Full thin glue for all three styles: files + protected hashes
assert_hash() {
  local demo="$1" proj="$2" label="$3"
  local dh ph
  dh="$(sha256sum "$demo" | awk '{print $1}')"
  ph="$(sha256sum "$proj" | awk '{print $1}')"
  if test "$dh" = "$ph"; then
    ok "$label hash unchanged vs demo"
  else
    bad "$label hash changed"
  fi
}

# Swiss
rm -rf /tmp/dc-scaffold-swiss
if "${CLI[@]}" scaffold "$FIX/plan-swiss-motion.json" -o /tmp/dc-scaffold-swiss --lib "$ROOT" >/tmp/dc-sc.out 2>/tmp/dc-sc.err \
  && test -f /tmp/dc-scaffold-swiss/content/shots.json \
  && test -f /tmp/dc-scaffold-swiss/content/engine.lock.json \
  && test -f /tmp/dc-scaffold-swiss/lines.json \
  && test -f /tmp/dc-scaffold-swiss/palette.json \
  && test -f /tmp/dc-scaffold-swiss/PROJECT.md \
  && test -f /tmp/dc-scaffold-swiss/ease.js \
  && test -f /tmp/dc-scaffold-swiss/film.js \
  && grep -q '一块钱' /tmp/dc-scaffold-swiss/lines.json; then
  ok "scaffold swiss creates expected files"
  assert_hash "$ROOT/styles/swiss-motion/demo/ease.js" /tmp/dc-scaffold-swiss/ease.js "swiss ease.js"
  assert_hash "$ROOT/styles/swiss-motion/demo/film.js" /tmp/dc-scaffold-swiss/film.js "swiss film.js"
else
  bad "scaffold swiss: $(cat /tmp/dc-sc.out) $(cat /tmp/dc-sc.err)"
fi

# Pictogram
rm -rf /tmp/dc-scaffold-picto
if "${CLI[@]}" scaffold "$FIX/plan-pictogram-motion.json" -o /tmp/dc-scaffold-picto --lib "$ROOT" --force >/tmp/dc-sc2.out 2>/tmp/dc-sc2.err \
  && test -f /tmp/dc-scaffold-picto/content/edl_content.json \
  && test -f /tmp/dc-scaffold-picto/content/engine.lock.json \
  && test -f /tmp/dc-scaffold-picto/edl_content.json \
  && test -f /tmp/dc-scaffold-picto/palette.json \
  && test -f /tmp/dc-scaffold-picto/PROJECT.md \
  && test -f /tmp/dc-scaffold-picto/engine.js \
  && test -f /tmp/dc-scaffold-picto/edl.js \
  && grep -q '分散投资\|股票\|sprint' /tmp/dc-scaffold-picto/edl_content.json; then
  ok "scaffold pictogram creates expected files"
  assert_hash "$ROOT/styles/pictogram-motion/demo/engine.js" /tmp/dc-scaffold-picto/engine.js "pictogram engine.js"
  assert_hash "$ROOT/styles/pictogram-motion/demo/edl.js" /tmp/dc-scaffold-picto/edl.js "pictogram edl.js"
  assert_hash "$ROOT/styles/pictogram-motion/demo/scenes.js" /tmp/dc-scaffold-picto/scenes.js "pictogram scenes.js"
else
  bad "scaffold pictogram: $(cat /tmp/dc-sc2.out) $(cat /tmp/dc-sc2.err)"
fi

# Caption
rm -rf /tmp/dc-scaffold-caption
if "${CLI[@]}" scaffold "$FIX/plan-caption-news.json" -o /tmp/dc-scaffold-caption --lib "$ROOT" --force >/tmp/dc-sc3.out 2>/tmp/dc-sc3.err \
  && test -f /tmp/dc-scaffold-caption/content/timeline_content.json \
  && test -f /tmp/dc-scaffold-caption/content/engine.lock.json \
  && test -f /tmp/dc-scaffold-caption/timeline.json \
  && test -f /tmp/dc-scaffold-caption/lines.json \
  && test -f /tmp/dc-scaffold-caption/audio/lines.json \
  && test -f /tmp/dc-scaffold-caption/palette.json \
  && test -f /tmp/dc-scaffold-caption/FACTS.md \
  && test -f /tmp/dc-scaffold-caption/PROJECT.md \
  && test -f /tmp/dc-scaffold-caption/main.js \
  && grep -q '流动性' /tmp/dc-scaffold-caption/timeline.json; then
  ok "scaffold caption creates expected files"
  assert_hash "$ROOT/styles/caption-news/demo/main.js" /tmp/dc-scaffold-caption/main.js "caption main.js"
  assert_hash "$ROOT/styles/caption-news/demo/index.html" /tmp/dc-scaffold-caption/index.html "caption index.html"
else
  bad "scaffold caption: $(cat /tmp/dc-sc3.out) $(cat /tmp/dc-sc3.err)"
fi

# 11) quality schedule must FAIL when VO required but dur.json empty (fitsTarget alone insufficient)
rm -rf /tmp/dc-q-novo
cp -a "$FIX/out-swiss-motion" /tmp/dc-q-novo
# empty measured durs + write a "fits" timeline that would look OK without require-vo
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/dc-q-novo")
(p / "voices").mkdir(exist_ok=True)
(p / "voices" / "dur.json").write_text("{}\n", encoding="utf-8")
# remove wavs if any
for w in (p / "voices").glob("*.wav"):
    w.unlink()
tl = {
  "targetDurationSec": 32.0,
  "scheduledDurationSec": 12.0,
  "beatGridSec": 0.25,
  "fitsTarget": True,
  "requireVo": True,
  "ok": False,
  "errors": ["missing VO duration for line 'l1'"],
  "warnings": [],
  "shots": [],
  "cues": [],
}
(p / "timeline.parsed.json").write_text(json.dumps(tl, indent=2) + "\n", encoding="utf-8")
PY
if "${CLI[@]}" quality --project /tmp/dc-q-novo --skip-heavy --allow-unchecked \
  -o /tmp/dc-q-novo/quality.json >/tmp/dc-q-novo.out 2>/tmp/dc-q-novo.err; then
  bad "quality should FAIL when timeline.ok=false / missing VO"
else
  if grep -q 'schedule_fits_target' /tmp/dc-q-novo/quality.json \
    && python3 -c 'import json;q=json.load(open("/tmp/dc-q-novo/quality.json"));c={x["name"]:x for x in q["checks"]};assert c["schedule_fits_target"]["status"]=="FAIL";assert q["overall"]=="FAIL"'; then
    ok "quality fails schedule when require-vo would fail (not fooled by fitsTarget)"
  else
    bad "quality novo schedule check: $(cat /tmp/dc-q-novo.out) $(cat /tmp/dc-q-novo.err) $(cat /tmp/dc-q-novo/quality.json)"
  fi
fi

# 12) quality --project . resolves absolute path (no 'index.html in .')
rm -rf /tmp/dc-q-rel
cp -a /tmp/dc-scaffold-swiss /tmp/dc-q-rel 2>/dev/null || true
if test ! -d /tmp/dc-q-rel; then
  "${CLI[@]}" scaffold "$FIX/plan-swiss-motion.json" -o /tmp/dc-q-rel --lib "$ROOT" --force >/dev/null 2>&1 || true
fi
# ensure dur so schedule check can pass under has_vo
python3 - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/dc-q-rel")
plan = json.loads((p/"content"/"plan.json").read_text())
durs = {ln["id"]: 1.0 for ln in (plan.get("voice") or {}).get("lines") or []}
(p/"voices").mkdir(exist_ok=True)
(p/"voices"/"dur.json").write_text(json.dumps(durs)+"\n")
# minimal ok timeline
shots = [{"id":s["id"],"t0":0,"t1":1,"dur":1,"voIds":[],"voDur":0,"readSec":0.5,"text":s.get("text","")} for s in plan["shots"]]
tl={"targetDurationSec":plan["targetDurationSec"],"scheduledDurationSec":1.0,"beatGridSec":0.25,"fitsTarget":True,"requireVo":True,"ok":True,"errors":[],"warnings":[],"shots":shots,"cues":[]}
(p/"timeline.parsed.json").write_text(json.dumps(tl)+"\n")
PY
pushd /tmp/dc-q-rel >/dev/null
if "${CLI[@]}" quality --project . --skip-heavy --allow-unchecked \
  -o /tmp/dc-q-rel-abs.json >/tmp/dc-q-rel.out 2>/tmp/dc-q-rel.err; then
  if python3 -c 'import json;q=json.load(open("/tmp/dc-q-rel-abs.json"));assert q["project"].startswith("/"), q["project"];assert "no index.html in \".\"" not in json.dumps(q)'; then
    ok "quality --project . resolves to absolute path"
  else
    bad "quality relative path still broken: $(cat /tmp/dc-q-rel-abs.json)"
  fi
else
  if python3 -c 'import json;q=json.load(open("/tmp/dc-q-rel-abs.json"));assert q["project"].startswith("/");print(q["project"])' 2>/dev/null; then
    ok "quality --project . resolves to absolute path (overall may fail)"
  else
    bad "quality --project . : $(cat /tmp/dc-q-rel.out) $(cat /tmp/dc-q-rel.err)"
  fi
fi
popd >/dev/null

# 13) scaffold swiss writes words_rel.json for zh + fetches fonts
if test -f /tmp/dc-scaffold-swiss/voices/words_rel.json \
  && python3 -c 'import json;d=json.load(open("/tmp/dc-scaffold-swiss/voices/words_rel.json"));assert d, d'; then
  ok "scaffold swiss writes zh words_rel.json"
else
  # re-scaffold if earlier run was before fix
  rm -rf /tmp/dc-scaffold-swiss2
  export LEMO_FONT_CACHE="/workspace/films/fuli-controller-e2e/fonts"
  if "${CLI[@]}" scaffold "$FIX/plan-swiss-motion.json" -o /tmp/dc-scaffold-swiss2 --lib "$ROOT" --force >/tmp/dc-sc-zh.out 2>/tmp/dc-sc-zh.err \
    && test -f /tmp/dc-scaffold-swiss2/voices/words_rel.json; then
    ok "scaffold swiss writes zh words_rel.json"
  else
    bad "scaffold zh words_rel: $(cat /tmp/dc-sc-zh.out 2>/dev/null) $(cat /tmp/dc-sc-zh.err 2>/dev/null)"
  fi
fi

# 14) scaffold swiss fonts present (Archivo-VF etc.)
FONT_PROJ=/tmp/dc-scaffold-swiss2
test -d "$FONT_PROJ" || FONT_PROJ=/tmp/dc-scaffold-swiss
if test -f "$FONT_PROJ/fonts/Archivo-VF.ttf" \
  && test -f "$FONT_PROJ/fonts/DMSerifDisplay-Regular.ttf" \
  && test -f "$FONT_PROJ/fonts/UnifrakturMaguntia-Regular.ttf"; then
  ok "scaffold swiss fetches/copies required .ttf fonts"
else
  export LEMO_FONT_CACHE="/workspace/films/fuli-controller-e2e/fonts"
  rm -rf /tmp/dc-scaffold-fonts
  if "${CLI[@]}" scaffold "$FIX/plan-swiss-motion.json" -o /tmp/dc-scaffold-fonts --lib "$ROOT" --force >/tmp/dc-sc-f.out 2>/tmp/dc-sc-f.err \
    && test -f /tmp/dc-scaffold-fonts/fonts/Archivo-VF.ttf; then
    ok "scaffold swiss fetches/copies required .ttf fonts"
  else
    bad "scaffold fonts: $(cat /tmp/dc-sc-f.out) $(cat /tmp/dc-sc-f.err); ls $(ls /tmp/dc-scaffold-fonts/fonts 2>/dev/null)"
  fi
fi

# 15) ebur128 parser ignores early framelog I:-70, prefers Summary
if python3 - <<'PY'
import sys
from pathlib import Path
import subprocess
sys.path.insert(0, "tools/deepseek-controller")
import quality
fake = """
[Parsed_ebur128_0] t: 0.1  I: -70.0 LUFS  TPK: -38.5 -38.5 dBFS
Summary:

  Integrated loudness:
    I:         -14.0 LUFS

  True peak:
    Peak:       -1.0 dBFS
"""
class R:
    stderr = fake
    stdout = ""
_real = subprocess.run
subprocess.run = lambda *a, **k: R()
try:
    r = quality.ebur128(Path("/etc/hosts"))
finally:
    subprocess.run = _real
assert r["ok"] and r["integrated_lufs"] == -14.0, r
assert r["true_peak_dbtp"] == -1.0, r
PY
then
  ok "ebur128 prefers Summary I: over early framelog -70"
else
  bad "ebur128 Summary parse"
fi

# 16) style_locked_duration: media ≈ engine DUR passes even when plan target is shorter
if python3 - <<'PY'
import json, sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
import quality

src = Path("tools/deepseek-controller/fixtures/out-swiss-motion")
for cand in (Path("/tmp/dc-scaffold-swiss"), Path("/tmp/dc-scaffold-swiss2"), src):
    if (cand / "film.js").is_file() and (cand / "content" / "engine.lock.json").is_file():
        base = cand
        break
else:
    raise SystemExit("no swiss project with film.js+lock for test 16")

td = Path(tempfile.mkdtemp(prefix="dc-dur-"))
for name in ("film.js", "content"):
    s = base / name
    d = td / name
    if s.is_dir():
        shutil.copytree(s, d)
    else:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
plan_p = td / "content" / "plan.json"
plan = json.loads(plan_p.read_text()) if plan_p.is_file() else {
    "style": "swiss-motion", "targetDurationSec": 32,
    "voice": {"provider": "none", "lines": []}, "shots": [],
}
plan["style"] = "swiss-motion"
plan["targetDurationSec"] = 32
plan["voice"] = {"provider": "none", "lines": []}
plan_p.parent.mkdir(parents=True, exist_ok=True)
plan_p.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")

engine_dur = quality._engine_locked_dur(td, "swiss-motion")
assert engine_dur == 44.0, engine_dur

real_probe = quality.probe_media
real_ebur = quality.ebur128
quality.probe_media = lambda p: {"ok": True, "data": {"format": {"duration": "44.00"}, "streams": []}}
quality.ebur128 = lambda p: {"ok": True, "integrated_lufs": -14.0, "true_peak_dbtp": -1.0}
media = td / "out.mp4"
media.write_bytes(b"0")
tl = {
  "targetDurationSec": 32.0, "scheduledDurationSec": 20.0, "beatGridSec": 0.25,
  "fitsTarget": True, "requireVo": False, "ok": True, "errors": [], "warnings": [],
  "shots": [], "cues": [],
}
(td / "timeline.parsed.json").write_text(json.dumps(tl) + "\n")
try:
    report = quality.gate(td, media=media, skip_heavy=True, require_vo=False)
finally:
    quality.probe_media = real_probe
    quality.ebur128 = real_ebur
checks = {c["name"]: c for c in report["checks"]}
assert checks["media_duration"]["status"] == "PASS", checks["media_duration"]
assert "style_locked_duration" in checks["media_duration"]["detail"], checks["media_duration"]
assert report.get("engineLockedDurSec") == 44.0, report.get("engineLockedDurSec")
quality.probe_media = lambda p: {"ok": True, "data": {"format": {"duration": "50.00"}, "streams": []}}
quality.ebur128 = lambda p: {"ok": True, "integrated_lufs": -14.0, "true_peak_dbtp": -1.0}
try:
    report2 = quality.gate(td, media=media, skip_heavy=True, require_vo=False)
finally:
    quality.probe_media = real_probe
    quality.ebur128 = real_ebur
c2 = {c["name"]: c for c in report2["checks"]}
assert c2["media_duration"]["status"] == "FAIL", c2["media_duration"]
print("ok")
PY
then
  ok "media_duration uses style_locked_duration (engine DUR) for Swiss lock"
else
  bad "style_locked_duration media_duration"
fi

# 17) zh-homophone-tolerant tokenizes 利息→力 short without breaking 富力/复利
if python3 - <<'PY'
import sys
sys.path.insert(0, "tools/deepseek-controller")
import quality
classes = quality._load_homophone_classes()
assert classes, "no classes loaded"
ok, a, b, r = quality._homophone_tolerant_match(
    "每年多出利息，利息再生利息。",
    "每年多出力,利息再生利息。",
    classes,
)
assert ok and a == b, (ok, a, b, r)
ok2, a2, b2, r2 = quality._homophone_tolerant_match(
    "复利靠的是留下，而不是赌一把。",
    "富力靠的是留下,而不是赌一把。",
    classes,
)
assert ok2 and a2 == b2, (ok2, a2, b2, r2)
ok3, a3, b3, r3 = quality._homophone_tolerant_match(
    "复利靠的是留下，而不是赌一把。",
    "蝙蝠靠的是留下,而不是赌一把。",
    classes,
)
assert not ok3, (ok3, a3, b3, r3)
detail = """OK   l1 | x → y
DIFF l2 | 每年多出利息，利息再生利息。 → 每年多出力,利息再生利息。    (similarity 0.87 < 0.92)
DIFF l3 | 同样本金，时间越长差距越大。 → 同样本经,时间越长,差距越大。    (similarity 0.92 < 0.92)
DIFF l5 | 复利靠的是留下，而不是赌一把。 → 赋利靠的是留下,而不是赌一把。    (similarity 0.93 < 0.92)
mismatches: 3
"""
diffs = quality._parse_asr_diffs(detail)
assert len(diffs) == 3, diffs
still = []
for lid, want, got in diffs:
    okx, _, _, _ = quality._homophone_tolerant_match(want, got, classes)
    if not okx:
        still.append(lid)
assert still == [], still
print("ok")
PY
then
  ok "zh-homophone-tolerant handles 利息→力 short; rejects 蝙蝠"
else
  bad "zh-homophone-tolerant tokenize"
fi


# 18) schedule pads under-target (hold-last-beat); under-target still in metadata
if python3 - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
import schedule as sch

proj = Path("tools/deepseek-controller/fixtures/out-swiss-motion")
lines = json.loads((proj/"content"/"lines.json").read_text())
shots = json.loads((proj/"content"/"shots.json").read_text())["shots"]
durs = json.loads((proj/"voices"/"dur.json").read_text())
tl, errs = sch.schedule(
    lines=lines, shots=shots, target_duration=32.0, beat_grid=0.25,
    durs=durs, require_all_vo=True, pad_under_target=True,
)
assert tl["ok"] and tl["fitsTarget"], tl
assert tl["underTargetBeforePad"] is True, tl
assert tl["padMode"] == "hold-last-beat", tl
assert tl["padSec"] > 0, tl
assert tl["contentDurationSec"] < 32, tl
assert abs(tl["scheduledDurationSec"] - 32.0) < 1e-6, tl
assert abs(tl["contentDurationSec"] + tl["padSec"] - 32.0) < 1e-3, tl
assert tl["shots"][-1].get("padSec") == tl["padSec"], tl["shots"][-1]
tl2, _ = sch.schedule(
    lines=lines, shots=shots, target_duration=32.0, beat_grid=0.25,
    durs=durs, require_all_vo=True, pad_under_target=False,
)
assert tl2["ok"] and tl2["fitsTarget"]
assert tl2["padSec"] == 0 and tl2["padMode"] == "none"
assert tl2["scheduledDurationSec"] == tl2["contentDurationSec"] < 32
assert not tl2["underTargetBeforePad"]
big = {k: 20.0 for k in durs}
tl3, e3 = sch.schedule(
    lines=lines, shots=shots, target_duration=32.0, beat_grid=0.25,
    durs=big, require_all_vo=True, pad_under_target=True,
)
assert not tl3["ok"] and tl3["fitsTarget"] is False
assert any("exceeds target" in x for x in e3)
print("ok")
PY
then
  ok "schedule pads under-target; metadata keeps shortfall; over still fails"
else
  bad "schedule pad under-target"
fi

# 19) --delivery picks zh-homophone-tolerant for zh plans; en stays strict
if python3 - <<'PY'
import sys
sys.path.insert(0, "tools/deepseek-controller")
import quality
assert quality.resolve_delivery_asr_mode({"language": "zh"}, asr_mode=None, delivery=True) == "zh-homophone-tolerant"
assert quality.resolve_delivery_asr_mode({"language": "zh-en"}, asr_mode=None, delivery=True) == "zh-homophone-tolerant"
assert quality.resolve_delivery_asr_mode({"language": "en"}, asr_mode=None, delivery=True) == "strict"
assert quality.resolve_delivery_asr_mode({"language": "zh"}, asr_mode=None, delivery=False) == "strict"
assert quality.resolve_delivery_asr_mode({"language": "zh"}, asr_mode="strict", delivery=True) == "strict"
assert quality.resolve_delivery_asr_mode({"language": "en"}, asr_mode="auto", delivery=False) == "strict"
assert quality.resolve_delivery_asr_mode({"language": "zh"}, asr_mode="auto", delivery=False) == "zh-homophone-tolerant"
print("ok")
PY
then
  ok "delivery ASR resolve: zh→tolerant, en→strict, explicit wins"
else
  bad "delivery ASR resolve"
fi

# 20) style_locked_duration also reads protected main.js (Caption)
if python3 - <<'PY'
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
import quality
from common import dump_json

td = Path(tempfile.mkdtemp(prefix="dc-cap-dur-"))
(td / "content").mkdir()
(td / "main.js").write_text("const W=1920, H=1080, FPS=30, DUR = 59.5;\nwindow.DUR=DUR;\n", encoding="utf-8")
dump_json(td / "content" / "engine.lock.json", {
    "style": "caption-news",
    "protectedSha256": {"main.js": "x"},
})
assert quality._engine_locked_dur(td, "caption-news") == 59.5
(td / "film.js").write_text("const DUR = 44;\n", encoding="utf-8")
lock = json.loads((td / "content" / "engine.lock.json").read_text())
lock["protectedSha256"]["film.js"] = "y"
dump_json(td / "content" / "engine.lock.json", lock)
assert quality._engine_locked_dur(td, "swiss-motion") == 44.0
print("ok")
PY
then
  ok "style_locked_duration reads main.js (Caption) and prefers film.js"
else
  bad "style_locked_duration main.js"
fi

# 21) caption timeline apply writes vo + engine dur
if python3 - <<'PY'
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
from apply_caption_timeline import apply_caption_timeline
from common import dump_json

td = Path(tempfile.mkdtemp(prefix="dc-cap-tl-"))
(td / "main.js").write_text("const DUR = 59.5;\n", encoding="utf-8")
dump_json(td / "timeline.json", {
    "fps": 30, "dur": 30, "vo": {}, "hook": {"t0": 0, "t1": 1, "zh": "x", "en": "x"}, "caps": [
        {"t0": 0, "t1": 1, "zh": "a", "en": "a"},
        {"t0": 0, "t1": 1, "zh": "b", "en": "b"},
    ],
})
dump_json(td / "timeline.parsed.json", {
    "scheduledDurationSec": 30.0,
    "shots": [
        {"id": "c1", "t0": 0.0, "t1": 3.5, "voIds": ["L01"], "role": "hook", "text": "流动性"},
        {"id": "c2", "t0": 3.5, "t1": 7.0, "voIds": ["L02"], "role": "explain", "text": "现金"},
    ],
    "cues": [
        {"type": "voice", "id": "L01", "shotId": "c1", "t": 0.35},
        {"type": "voice", "id": "L02", "shotId": "c2", "t": 3.85},
    ],
})
info = apply_caption_timeline(td)
assert info["voCount"] == 2 and info["dur"] == 59.5
tl = json.loads((td / "timeline.json").read_text())
assert tl["vo"]["L01"] == 0.35 and tl["dur"] == 59.5
assert tl["hook"]["t1"] == 3.5
print("ok")
PY
then
  ok "apply_caption_timeline sets vo + engine dur"
else
  bad "apply_caption_timeline"
fi

# 22) caption locked-main readcheck helper
if python3 - <<'PY'
import sys, tempfile
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
import quality
from common import dump_json
td = Path(tempfile.mkdtemp(prefix="dc-cap-rc-"))
(td / "content").mkdir()
(td / "main.js").write_text("const DUR=59.5;\n", encoding="utf-8")
dump_json(td / "content" / "engine.lock.json", {
    "style": "caption-news",
    "protectedSha256": {"main.js": "abc"},
})
assert quality._caption_locked_main(td, "caption-news") is True
# style arg ignored when lock.style is caption-news
assert quality._caption_locked_main(td, "swiss-motion") is True
# non-caption lock → False
dump_json(td / "content" / "engine.lock.json", {
    "style": "swiss-motion",
    "protectedSha256": {"film.js": "abc"},
})
assert quality._caption_locked_main(td, "swiss-motion") is False
assert quality._caption_locked_main(td, "caption-news") is False
print("ok")
PY
then
  ok "caption locked-main readcheck helper"
else
  bad "caption locked-main helper"
fi


# 23) pictogram edl_runtime apply + style_locked_duration reads runtime DUR
if python3 - <<'PY'
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
from apply_pictogram_edl import apply_pictogram_edl
import quality
from common import dump_json

td = Path(tempfile.mkdtemp(prefix="dc-picto-edl-"))
(td / "content").mkdir()
dump_json(td / "content" / "edl_content.json", {
    "style": "pictogram-motion", "bpm": 150, "beatSec": 0.4,
    "shots": [
        {"id": "p0", "kind": "intro", "role": "hook", "zh": "分散投资", "en": "DIVERSIFY", "beats": 4, "pal": "red"},
        {"id": "p1", "kind": "chapter", "role": "chapter", "zh": "资产", "en": "ASSETS", "beats": 4, "pal": "multi"},
        {"id": "p2", "kind": "card", "role": "card", "zh": "股票", "en": "STOCKS", "pose": "stand", "beats": 4, "pal": "multi"},
        {"id": "p3", "kind": "finale", "role": "end", "zh": "组合", "en": "PORTFOLIO", "beats": 8, "pal": "red"},
    ],
})
dump_json(td / "timeline.parsed.json", {
    "scheduledDurationSec": 12.0,
    "targetDurationSec": 12.0,
    "shots": [
        {"id": "p0", "t0": 0.0, "t1": 1.6, "voIds": ["L01"]},
        {"id": "p1", "t0": 1.6, "t1": 3.2, "voIds": []},
        {"id": "p2", "t0": 3.2, "t1": 4.8, "voIds": ["L02"]},
        {"id": "p3", "t0": 4.8, "t1": 12.0, "voIds": []},
    ],
    "cues": [
        {"type": "voice", "id": "L01", "shotId": "p0", "t": 0.35},
        {"type": "voice", "id": "L02", "shotId": "p2", "t": 3.55},
    ],
})
info = apply_pictogram_edl(td)
assert info["shotCount"] == 4 and abs(info["dur"] - 12.0) < 1e-6
assert info["voCount"] == 2
rt = json.loads((td / "edl_runtime.json").read_text())
assert rt["DUR"] == 12.0 and rt["shots"][2]["pose"] == "golf"  # stand→golf
assert rt["shots"][2]["title"] == "STOCKS"
tl = json.loads((td / "timeline.json").read_text())
assert tl["vo"]["L01"] == 0.35 and tl["dur"] == 12.0
(td / "edl.js").write_text("const EDL = { DUR: 163.6 };\n", encoding="utf-8")
dump_json(td / "content" / "engine.lock.json", {
    "style": "pictogram-motion",
    "protectedSha256": {"edl.js": "abc", "scenes.js": "def"},
})
assert quality._engine_locked_dur(td, "pictogram-motion") == 12.0
assert quality._pictogram_locked_edl(td, "pictogram-motion") is True
print("ok")
PY
then
  ok "pictogram edl_runtime apply + locked dur from runtime"
else
  bad "pictogram edl_runtime apply"
fi

echo
echo "Results: $pass passed, $fail failed"
test "$fail" -eq 0
