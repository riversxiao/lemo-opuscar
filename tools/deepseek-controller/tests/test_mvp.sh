#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CTL="$ROOT/tools/deepseek-controller"
CLI=(python3 "$CTL/cli.py")
FIX="$CTL/fixtures"
pass=0
fail=0
# Headless Chrome for page.mjs readcheck smoke (texts_runtime overlay test).
export PLAYWRIGHT_CHROME="${PLAYWRIGHT_CHROME:-/usr/bin/google-chrome}"

# Never let tests append to the real fixtures/budget-ledger.jsonl (handoff etc. log $0 rows).
export DC_BUDGET_LEDGER="${DC_BUDGET_LEDGER:-/tmp/dc-test-budget-ledger.jsonl}"
rm -f "$DC_BUDGET_LEDGER"

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


# 17b) zh tolerant: Whisper 6% / 0.5 notation == spoken 百分之六 / 零点五; wrong number still fails
if python3 - <<'PY'
import sys
sys.path.insert(0, "tools/deepseek-controller")
import quality
c = quality._load_homophone_classes()
ok, a, b, r = quality._homophone_tolerant_match("官方贴现率从百分之六，降到百分之零点五。", "官方贴线率从6%降到0.5%。", c)
assert ok and a == b, (a, b, r)
bad_ok, *_ = quality._homophone_tolerant_match("官方贴现率从百分之六，降到百分之零点五。", "官方贴现率从9%降到3%。", c)
assert not bad_ok
print("ok")
PY
then
  ok "zh tolerant normalizes 6%/0.5 to 百分之6/0点5; wrong number fails"
else
  bad "zh tolerant percent/decimal normalization"
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
# styleVersion unlocks main.js
dump_json(td / "content" / "engine.lock.json", {
    "style": "caption-news",
    "styleVersion": "liquidity-v001",
    "unlocked": ["main.js"],
    "protectedSha256": {"index.html": "abc"},
    "versionSha256": {"main.js": "def"},
})
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
brand = json.loads((td / "brand_strings.json").read_text())
assert brand["hudTicks"] == 1  # one card in this fixture
assert any(r["from"] == "THE 20TH ASIAN GAMES" for r in brand["replace"])
print("ok")
PY
then
  ok "pictogram edl_runtime apply + locked dur from runtime"
else
  bad "pictogram edl_runtime apply"
fi

# 24) scaffold pictogram + caption fetch/copy fonts (via LEMO_FONT_CACHE)
if python3 - <<'PY'
import os, sys, shutil
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
from fetch_fonts import ensure_fonts

td = Path("/tmp/dc-font-pictogram")
shutil.rmtree(td, ignore_errors=True)
(td / "fonts").mkdir(parents=True)
os.environ["LEMO_FONT_CACHE"] = "/workspace/films/fensan-controller-e2e/fonts"
acts = ensure_fonts(td / "fonts", "pictogram-motion", project=td)
assert (td / "fonts" / "InterTightwght.ttf").is_file()
assert (td / "fonts" / "DMMono-Medium.ttf").is_file()
assert (td / "fonts" / "NotoSansSCwght.ttf").is_file()
assert any(("copied-fallback" in a) or a.startswith("ok ") or a.startswith("fetched ") for a in acts)

td2 = Path("/tmp/dc-font-caption")
shutil.rmtree(td2, ignore_errors=True)
(td2 / "fonts").mkdir(parents=True)
os.environ["LEMO_FONT_CACHE"] = "/workspace/films/liudong-controller-e2e/fonts"
acts2 = ensure_fonts(td2 / "fonts", "caption-news", project=td2)
for name in ("it500.woff2", "it800.woff2", "sc900.woff2"):
    assert (td2 / "fonts" / name).is_file(), name
print("ok")
PY
then
  ok "fetch_fonts pictogram+caption via LEMO_FONT_CACHE"
else
  bad "fetch_fonts pictogram/caption"
fi

# 25) brand_strings builder maps topic + hudTicks from cards
if python3 - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
from apply_pictogram_edl import build_brand_strings
plan = json.loads(Path("tools/deepseek-controller/fixtures/plan-pictogram-motion.json").read_text())
compiled = [
  {"kind": "intro"}, {"kind": "chapter"},
  {"kind": "card"}, {"kind": "card"}, {"kind": "card"}, {"kind": "card"},
  {"kind": "finale"},
]
b = build_brand_strings(plan, compiled)
assert b["titleEn"] == "DIVERSIFY"
assert b["hudTicks"] == 4
assert any(r["to"] == "DIVERSIFY" for r in b["replace"] if r["from"] == "THE 20TH ASIAN GAMES")
assert any(r["from"] == "SET" for r in b["replace"])
print("ok")
PY
then
  ok "brand_strings maps DIVERSIFY + hudTicks=card count"
else
  bad "brand_strings builder"
fi


# 26) style-version finance-v001 unlocks scenes.js only; demo scaffold stays locked
if python3 - <<'PY'
import hashlib, json, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
from apply_pictogram_style_version import apply_style_version, default_lib
from glue_pictogram import glue_pictogram

lib = default_lib()
demo_scenes = lib / "styles/pictogram-motion/demo/scenes.js"
ver_scenes = lib / "styles/pictogram-motion/versions/finance-v001/scenes.js"
assert demo_scenes.is_file() and ver_scenes.is_file()
assert hashlib.sha256(demo_scenes.read_bytes()).digest() != hashlib.sha256(ver_scenes.read_bytes()).digest()

td = Path(tempfile.mkdtemp(prefix="dc-picto-sv-"))
try:
    glue_pictogram(
        Path("tools/deepseek-controller/fixtures/plan-pictogram-motion.json"),
        td,
        lib=lib,
        force=True,
    )
    lock = json.loads((td / "content/engine.lock.json").read_text())
    assert "scenes.js" in lock["protectedSha256"]
    assert not lock.get("styleVersion")
    h_demo = hashlib.sha256(demo_scenes.read_bytes()).hexdigest()
    assert lock["protectedSha256"]["scenes.js"] == h_demo
    assert hashlib.sha256((td / "scenes.js").read_bytes()).hexdigest() == h_demo

    apply_style_version(td, "finance-v001", lib=lib)
    lock2 = json.loads((td / "content/engine.lock.json").read_text())
    assert lock2.get("styleVersion") == "finance-v001"
    assert "scenes.js" in lock2.get("unlocked", [])
    assert "scenes.js" not in lock2.get("protectedSha256", {})
    assert "engine.js" in lock2["protectedSha256"]
    assert "edl.js" in lock2["protectedSha256"]
    h_ver = hashlib.sha256(ver_scenes.read_bytes()).hexdigest()
    assert lock2["versionSha256"]["scenes.js"] == h_ver
    assert hashlib.sha256((td / "scenes.js").read_bytes()).hexdigest() == h_ver
    brand = td / "brand_strings.json"
    if brand.is_file():
        b = json.loads(brand.read_text())
        assert b.get("applyLiterals") is False
    assert (td / "content/STYLE_VERSION.md").is_file()
    body = (td / "scenes.js").read_text(encoding="utf-8")
    for bad in ("THE 20TH ASIAN GAMES", "ON YOUR MARKS", "AICHI-NAGOYA", "n: 469"):
        assert bad not in body, bad
    assert "READY" in body and "ALLOCATE" in body
    assert "finaleGrid" in body and "TOTALN" in body
finally:
    shutil.rmtree(td, ignore_errors=True)
print("ok")
PY
then
  ok "pictogram style-version finance-v001 unlocks scenes only"
else
  bad "pictogram style-version finance-v001"
fi


# 27) music_bed synthesizes placeholder + mixes VO; cli mix works
if python3 - <<'PY'
import json, sys, tempfile, shutil, subprocess
from pathlib import Path
import numpy as np, soundfile as sf
sys.path.insert(0, "tools/deepseek-controller")
from music_bed import synthesize_bed, mix_bed_vo, SR

b = synthesize_bed(1.5, preset="soft-pulse", bpm=100, seed=1)
assert b.shape[0] == int(1.5 * SR) and b.shape[1] == 2
assert float(np.max(np.abs(b))) > 0.01
assert float(np.max(np.abs(synthesize_bed(0.5, preset="silence")))) == 0.0

td = Path(tempfile.mkdtemp(prefix="dc-bed-"))
try:
    (td / "voices").mkdir(); (td / "music").mkdir(); (td / "out").mkdir()
    tt = np.arange(int(0.3 * SR)) / SR
    sf.write(td / "voices" / "L01.wav", (0.25 * np.sin(2 * np.pi * 440 * tt)).astype(np.float32), SR)
    (td / "timeline.json").write_text(json.dumps({"dur": 2.0, "bpm": 100, "vo": {"L01": 0.2}}))
    info = mix_bed_vo(td, preset="soft-pulse", seed=7)
    assert info["mix"].is_file() and info["bed"].is_file()
    meta = json.loads(info["meta"].read_text())
    assert "placeholder" in meta["label"]
    assert meta["preset"] == "soft-pulse"
    info2 = mix_bed_vo(td, bed_path=info["bed"], out=td / "out" / "mix2.wav")
    assert json.loads(info2["meta"].read_text())["preset"] == "external"
    # cli mix + --vo-only
    r = subprocess.run(
        [sys.executable, "tools/deepseek-controller/cli.py", "mix",
         "--project", str(td), "--preset", "pad",
         "--out", str(td / "out" / "cli-mix.wav")],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    assert (td / "out" / "cli-mix.wav").is_file()
    r2 = subprocess.run(
        [sys.executable, "tools/deepseek-controller/cli.py", "mix",
         "--project", str(td), "--vo-only",
         "--out", str(td / "out" / "cli-vo.wav")],
        capture_output=True, text=True,
    )
    assert r2.returncode == 0, r2.stderr
    assert (td / "out" / "cli-vo.wav").is_file()
finally:
    shutil.rmtree(td, ignore_errors=True)
print("ok")
PY
then
  ok "music_bed placeholder + cli mix / --vo-only"
else
  bad "music_bed / cli mix"
fi



# 28) caption style-version liquidity-v001 unlocks main.js only; demo scaffold stays locked
if python3 - <<'PY'
import hashlib, json, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
from apply_caption_style_version import apply_style_version, default_lib
from glue_caption import glue_caption
import quality

lib = default_lib()
demo_main = lib / "styles/caption-news/demo/main.js"
ver_main = lib / "styles/caption-news/versions/liquidity-v001/main.js"
assert demo_main.is_file() and ver_main.is_file()
assert hashlib.sha256(demo_main.read_bytes()).digest() != hashlib.sha256(ver_main.read_bytes()).digest()
body = ver_main.read_text(encoding="utf-8")
for bad in ("蜜蜂账本", "瓦螨", "THE BEE LEDGER", "加州"):
    assert bad not in body, bad
assert "流动性" in body and "LIQUIDITY" in body
assert "DUR = 32" in body

td = Path(tempfile.mkdtemp(prefix="dc-cap-sv-"))
try:
    glue_caption(
        Path("tools/deepseek-controller/fixtures/plan-caption-news.json"),
        td,
        lib=lib,
        force=True,
    )
    lock = json.loads((td / "content/engine.lock.json").read_text())
    assert "main.js" in lock["protectedSha256"]
    assert not lock.get("styleVersion")
    h_demo = hashlib.sha256(demo_main.read_bytes()).hexdigest()
    assert lock["protectedSha256"]["main.js"] == h_demo
    assert quality._caption_locked_main(td, "caption-news") is True

    apply_style_version(td, "liquidity-v001", lib=lib)
    lock2 = json.loads((td / "content/engine.lock.json").read_text())
    assert lock2.get("styleVersion") == "liquidity-v001"
    assert "main.js" in lock2.get("unlocked", [])
    assert "main.js" not in lock2.get("protectedSha256", {})
    assert "index.html" in lock2["protectedSha256"]
    assert "build.sh" in lock2["protectedSha256"]
    h_ver = hashlib.sha256(ver_main.read_bytes()).hexdigest()
    assert lock2["versionSha256"]["main.js"] == h_ver
    assert hashlib.sha256((td / "main.js").read_bytes()).hexdigest() == h_ver
    assert quality._caption_locked_main(td, "caption-news") is False
    assert (td / "content/STYLE_VERSION.md").is_file()
    body2 = (td / "main.js").read_text(encoding="utf-8")
    assert "流动性" in body2 and "蜜蜂账本" not in body2
finally:
    shutil.rmtree(td, ignore_errors=True)
print("ok")
PY
then
  ok "caption style-version liquidity-v001 unlocks main only"
else
  bad "caption style-version liquidity-v001"
fi


# 29) swiss texts_runtime overlay: LAYOUT boxes + holdPad; quality skips N/A when present
if python3 - <<'PY'
import json, sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
from apply_swiss_texts import apply_swiss_texts, build_texts_runtime
import quality
from common import dump_json

lines = [
    {"id": "l1", "t": 4.4, "text": "一块钱. 放着不动会怎样？"},
    {"id": "l5", "t": 22.15, "text": "复利靠的是留下. 而不是赌一把。"},
]
rt = build_texts_runtime(lines, dur=44)
assert len(rt["entries"]) == 2
e1 = rt["entries"][0]
assert e1["id"] == "l1" and e1["pos"] == "page" and "放着不动" in e1["text"]
assert e1["t1"] == 7.8 and e1["x0"] >= 0 and e1["x1"] <= 1920
pads = {p["id"]: p for p in rt["holdPad"]}
assert "l5" in pads and pads["l5"]["padSec"] > 0
e5 = rt["entries"][1]
assert e5["t1"] > e5["t1Visual"]

td = Path(tempfile.mkdtemp(prefix="dc-swiss-texts-"))
try:
    (td / "content").mkdir()
    (td / "lines.json").write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
    (td / "film.js").write_text("export const DUR = 44;\n", encoding="utf-8")
    info = apply_swiss_texts(td)
    assert (td / "texts_runtime.json").is_file()
    assert info["entryCount"] == 2

    td2 = Path(tempfile.mkdtemp(prefix="dc-swiss-na-"))
    try:
        (td2 / "content").mkdir()
        # Minimal READY page (no module) so Playwright returns quickly.
        (td2 / "index.html").write_text(
            "<!doctype html><canvas id=c></canvas><script>"
            "window.DUR=1;window.render=function(){};window.READY=true;</script>",
            encoding="utf-8",
        )
        (td2 / "film.js").write_text("// no TEXTS\n", encoding="utf-8")
        (td2 / "main.js").write_text("// no TEXTS\n", encoding="utf-8")
        dump_json(td2 / "content" / "engine.lock.json", {"style": "swiss-motion", "protectedSha256": {"film.js": "x"}})
        rc = quality.run_readcheck(td2, style="swiss-motion")
        assert rc["status"] == "NOT_APPLICABLE" and "swiss-demo-without-registry" in rc["detail"], rc
        # Overlay present → must not take static N/A. Stub DUR=1 yields no entry hits → NOT_CHECKED.
        dump_json(td2 / "texts_runtime.json", rt)
        rc2 = quality.run_readcheck(td2, style="swiss-motion")
        assert rc2["status"] != "NOT_APPLICABLE", rc2
        assert rc2["status"] in ("NOT_CHECKED", "PASS", "FAIL"), rc2
    finally:
        shutil.rmtree(td2, ignore_errors=True)
finally:
    shutil.rmtree(td, ignore_errors=True)
print("ok")
PY
then
  ok "swiss texts_runtime overlay + quality N/A gate"
else
  bad "swiss texts_runtime overlay"
fi



# 30) tts router --list + kokoro one-line when .venv-voice ready; qwen3 needs-server without BASE
if python3 - <<'PY'
import json, os, subprocess, sys, tempfile
from pathlib import Path
root = Path(".").resolve()
cli = [sys.executable, "tools/deepseek-controller/cli.py"]
r = subprocess.run(cli + ["tts", "--list", "--json"], capture_output=True, text=True)
assert r.returncode == 0, r.stderr
data = json.loads(r.stdout)
by = {p["id"]: p for p in data["providers"]}
assert by["edge"]["state"] == "ready", by["edge"]
assert by["qwen3"]["state"] == "needs-server", by["qwen3"]
assert by["omnivoice"]["state"] == "needs-server", by["omnivoice"]
r2 = subprocess.run([sys.executable, "core/tts/tts_router.py", "--list", "--json"], capture_output=True, text=True)
assert r2.returncode == 0, r2.stderr
td = Path(tempfile.mkdtemp(prefix="dc-tts-qwen-"))
lines = td / "lines.json"
lines.write_text(json.dumps([{"id": "t1", "text": "测试一句。"}], ensure_ascii=False), encoding="utf-8")
env = {k: v for k, v in os.environ.items() if not k.startswith("LEMO_TTS_QWEN3")}
r3 = subprocess.run(
    [sys.executable, "core/tts/tts_router.py", str(lines), str(td / "out"),
     "--provider", "qwen3", "--fallback", ""],
    capture_output=True, text=True, env=env,
)
assert r3.returncode != 0, r3.stdout
blob = r3.stderr + r3.stdout
assert "QWEN3_BASE" in blob or "needs-server" in blob, blob
venv_py = root / ".venv-voice" / "bin" / "python"
if venv_py.is_file() and by["kokoro"]["state"] == "ready":
    out = td / "kokoro"
    r4 = subprocess.run(
        cli + ["tts", "--project", str(td), "--lines", str(lines), "--out", str(out),
               "--provider", "kokoro", "--fallback", "", "--no-post-words",
               "--skip-dialogue-gate"],
        capture_output=True, text=True,
    )
    assert r4.returncode == 0, r4.stderr + r4.stdout
    assert (out / "t1.wav").is_file() and (out / "dur.json").is_file()
    assert json.loads((out / "tts_router.json").read_text())["provider"] == "kokoro"
print("ok")
PY
then
  ok "tts router list + kokoro/qwen3 honesty"
else
  bad "tts router list / kokoro"
fi

# --- handoff: OpenFilm multi-shot + HyperFrames export ---
HO_FIX="$FIX/handoff-mini"
HO_OUT=/tmp/dc-handoff-of
rm -rf "$HO_OUT" /tmp/dc-handoff-hf
if PYTHONPATH="$ROOT" python3 -m tools.handoff.cli openfilm "$HO_FIX" -o "$HO_OUT" >/tmp/dc-ho.out 2>/tmp/dc-ho.err \
  && test -f "$HO_OUT/film.html" \
  && test -f "$HO_OUT/manifest.json" \
  && test -f "$HO_OUT/timeline.edl" \
  && test -f "$HO_OUT/rebuild_shots.sh" \
  && grep -q 'id="a"' "$HO_OUT/film.html" \
  && grep -q 'id="b"' "$HO_OUT/film.html"; then
  ok "openfilm handoff writes multi-shot film.html+edl+manifest"
else
  bad "openfilm handoff: $(cat /tmp/dc-ho.err /tmp/dc-ho.out)"
fi

SHOTS=$(python3 -c "import json;print(json.load(open('$HO_OUT/manifest.json'))['shotCount'])")
if [ "$SHOTS" = "2" ]; then
  ok "openfilm handoff shotCount=2"
else
  bad "openfilm handoff shotCount=$SHOTS"
fi

if "${CLI[@]}" handoff --project "$HO_FIX" --target openfilm -o /tmp/dc-handoff-cli >/tmp/dc-ho2.out 2>/tmp/dc-ho2.err \
  && test -f /tmp/dc-handoff-cli/film.html; then
  ok "cli handoff openfilm"
else
  bad "cli handoff: $(cat /tmp/dc-ho2.err /tmp/dc-ho2.out)"
fi

# HyperFrames export (skip live lint in CI-ish path — network already proven separately)
if PYTHONPATH="$ROOT" python3 -m tools.handoff.cli hyperframes "$HO_FIX" -o /tmp/dc-handoff-hf >/tmp/dc-hf.out 2>/tmp/dc-hf.err \
  && test -f /tmp/dc-handoff-hf/index.html \
  && test -f /tmp/dc-handoff-hf/lemo-manifest.json \
  && test -f /tmp/dc-handoff-hf/hyperframes.json \
  && grep -q 'data-composition-id="main"' /tmp/dc-handoff-hf/index.html; then
  ok "hyperframes export writes composition + lemo-manifest"
else
  bad "hyperframes export: $(cat /tmp/dc-hf.err /tmp/dc-hf.out)"
fi

if grep -q 'needsUser' /tmp/dc-handoff-hf/lemo-manifest.json; then
  ok "hyperframes manifest marks needsUser blockers"
else
  bad "hyperframes missing needsUser"
fi

# --- matrix tracker (18-film full factorial; no remux) ---
if "${CLI[@]}" matrix >/tmp/dc-matrix.out 2>/tmp/dc-matrix.err \
  && grep -q 'filled 18/18' /tmp/dc-matrix.out \
  && grep -q 'M01' /tmp/dc-matrix.out \
  && grep -q 'M08' /tmp/dc-matrix.out \
  && grep -q 'M12' /tmp/dc-matrix.out \
  && grep -q 'M18' /tmp/dc-matrix.out \
  && grep -q 'delivery-pass' /tmp/dc-matrix.out; then
  ok "matrix lists 18/18 with delivery-pass"
else
  bad "matrix list: $(cat /tmp/dc-matrix.err /tmp/dc-matrix.out)"
fi

if "${CLI[@]}" matrix --id M01 --json >/tmp/dc-matrix-m01.json 2>/tmp/dc-matrix-m01.err \
  && python3 -c "import json;d=json.load(open('/tmp/dc-matrix-m01.json')); assert d['id']=='M01' and d['status']=='delivery-pass' and d['mp4Exists']"; then
  ok "matrix --id M01 --json"
else
  bad "matrix M01 json: $(cat /tmp/dc-matrix-m01.err /tmp/dc-matrix-m01.json)"
fi

# Flash natives promoted to delivery-pass
for mid in M02 M06 M10; do
  if "${CLI[@]}" matrix --id "$mid" --json >/tmp/dc-matrix-$mid.json 2>/tmp/dc-matrix-$mid.err \
    && python3 -c "import json;d=json.load(open('/tmp/dc-matrix-$mid.json')); assert d['id']=='$mid' and d['status']=='delivery-pass' and d['mp4Exists']"; then
    ok "matrix --id $mid delivery-pass"
  else
    bad "matrix $mid: $(cat /tmp/dc-matrix-$mid.err /tmp/dc-matrix-$mid.json)"
  fi
done

# Docs: budget + experts
if test -f "$CTL/docs/BUDGET.md" && test -f "$CTL/docs/EXPERTS.md"; then
  ok "BUDGET.md + EXPERTS.md present"
else
  bad "budget/experts docs missing"
fi

# --- Premiere xmeml handoff ---
rm -rf /tmp/dc-handoff-prem
if PYTHONPATH="$ROOT" python3 -m tools.handoff.cli premiere "$HO_FIX" -o /tmp/dc-handoff-prem >/tmp/dc-prem.out 2>/tmp/dc-prem.err \
  && test -f /tmp/dc-handoff-prem/premiere.xml \
  && test -f /tmp/dc-handoff-prem/manifest.json \
  && test -f /tmp/dc-handoff-prem/assets/master.mp4 \
  && grep -q 'xmeml version="5"' /tmp/dc-handoff-prem/premiere.xml \
  && grep -q 'clipitem id="clip-1"' /tmp/dc-handoff-prem/premiere.xml \
  && grep -q 'clipitem id="clip-2"' /tmp/dc-handoff-prem/premiere.xml; then
  ok "premiere handoff writes xmeml v5 + 2 clipitems"
else
  bad "premiere handoff: $(cat /tmp/dc-prem.err /tmp/dc-prem.out)"
fi

if test -f "$HO_OUT/premiere.xml" || PYTHONPATH="$ROOT" python3 -m tools.handoff.cli openfilm "$HO_FIX" -o /tmp/dc-of-xml >/dev/null 2>&1; then
  # openfilm package must embed premiere.xml (re-export if earlier HO_OUT predates change)
  if test -f "$HO_OUT/premiere.xml"; then OFXML="$HO_OUT/premiere.xml"; else OFXML="/tmp/dc-of-xml/premiere.xml"; fi
  if grep -q 'xmeml' "$OFXML"; then
    ok "openfilm package includes premiere.xml"
  else
    bad "openfilm missing premiere.xml content"
  fi
else
  bad "openfilm premiere.xml missing"
fi

if "${CLI[@]}" handoff --project "$HO_FIX" --target premiere -o /tmp/dc-prem-cli --no-budget >/tmp/dc-prem2.out 2>/tmp/dc-prem2.err \
  && test -f /tmp/dc-prem-cli/premiere.xml; then
  ok "cli handoff premiere"
else
  bad "cli handoff premiere: $(cat /tmp/dc-prem2.err /tmp/dc-prem2.out)"
fi

# --- budget ledger ---
BUD_LEDGER=/tmp/dc-budget-ledger.jsonl
rm -f "$BUD_LEDGER"
if "${CLI[@]}" budget append --ledger "$BUD_LEDGER" --item "test-local" --usd 0 --kind local --path-label controller --duration 1.5 >/tmp/dc-bud.out 2>/tmp/dc-bud.err \
  && "${CLI[@]}" budget append --ledger "$BUD_LEDGER" --item "test-paid" --usd 0.12 --kind manual --tokens-in 10 --tokens-out 2 --path-label flash >/tmp/dc-bud2.out 2>/tmp/dc-bud2.err \
  && "${CLI[@]}" budget summary --ledger "$BUD_LEDGER" --json >/tmp/dc-bud-sum.json 2>/tmp/dc-bud-sum.err \
  && python3 -c "import json;d=json.load(open('/tmp/dc-bud-sum.json')); assert d['entries']==2 and abs(d['totalUsd']-0.12)<1e-9"; then
  ok "budget append + summary"
else
  bad "budget: $(cat /tmp/dc-bud.err /tmp/dc-bud2.err /tmp/dc-bud-sum.err /tmp/dc-bud.out /tmp/dc-bud-sum.json 2>/dev/null)"
fi

if "${CLI[@]}" budget append --ledger "$BUD_LEDGER" --item "test-cny" --usd 0.05 --cny 0.5 --kind opencode-session --session-id ses_test --path-label flash >/tmp/dc-bud3.out 2>/tmp/dc-bud3.err \
  && "${CLI[@]}" budget summary --ledger "$BUD_LEDGER" --json >/tmp/dc-bud-sum2.json 2>/tmp/dc-bud-sum2.err \
  && python3 -c "import json;d=json.load(open('/tmp/dc-bud-sum2.json')); assert abs(d['totalCny']-0.5)<1e-9, d"; then
  ok "budget --cny tracked in totalCny"
else
  bad "budget: $(cat /tmp/dc-bud.err /tmp/dc-bud2.err /tmp/dc-bud-sum.err /tmp/dc-bud.out /tmp/dc-bud-sum.json 2>/dev/null)"
fi

if test -f "$CTL/fixtures/budget-ledger.jsonl" && test -f "$CTL/budget.py" \
  && grep -q 'budget-ledger.jsonl' "$CTL/docs/BUDGET.md"; then
  ok "budget.py + ledger fixture + BUDGET.md wire-up"
else
  bad "budget automation files missing"
fi

if "${CLI[@]}" budget import-opencode --ledger /tmp/dc-budget-import.jsonl --min-usd 0.01 --dry-run --json >/tmp/dc-bud-imp.json 2>/tmp/dc-bud-imp.err \
  && python3 -c "import json;d=json.load(open('/tmp/dc-bud-imp.json')); assert d.get('ok') is True and d.get('dryRun') is True"; then
  ok "budget import-opencode --dry-run"
else
  # DB may be absent off-box; still accept honest failure shape
  if grep -q 'opencode db missing' /tmp/dc-bud-imp.json /tmp/dc-bud-imp.err 2>/dev/null; then
    ok "budget import-opencode honest missing-db"
  else
    bad "budget import: $(cat /tmp/dc-bud-imp.err /tmp/dc-bud-imp.json)"
  fi
fi

if "${CLI[@]}" matrix --filled >/tmp/dc-matrix-f.out 2>/tmp/dc-matrix-f.err \
  && grep -q 'M05' /tmp/dc-matrix-f.out \
  && ! grep -E '^M0[0-9].* empty ' /tmp/dc-matrix-f.out \
  && ! grep -E '^M1[0-8].* empty ' /tmp/dc-matrix-f.out; then
  ok "matrix --filled hides empty"
else
  bad "matrix --filled: $(cat /tmp/dc-matrix-f.err /tmp/dc-matrix-f.out)"
fi

if test -f "$CTL/docs/MATRIX-18.md" && test -f "$CTL/fixtures/matrix-18.json"; then
  ok "MATRIX-18.md + matrix-18.json present"
else
  bad "matrix docs/fixture missing"
fi

# Cross-style x flash cells (M13-M18): every cell has a real mp4 + evidence, flash path
"${CLI[@]}" matrix --path flash >/tmp/dc-matrix-flash.out 2>/tmp/dc-matrix-flash.err || true
if python3 -c "
import json,os
d=json.load(open('$CTL/fixtures/matrix-18.json'))
cells=d['cells']; assert len(cells)==18
keys={(c['topic'],c['style'],c['path']) for c in cells}; assert len(keys)==18
new=[c for c in cells if c['id'] in ('M13','M14','M15','M16','M17','M18')]
assert len(new)==6 and all(c['path']=='flash' and c['role']=='cross' for c in new)
assert all(c['status']!='empty' and os.path.exists(c['mp4']) and os.path.exists(c['evidence']) for c in new)
assert all(c['status']!='delivery-pass' or json.load(open(c['evidence'])).get('deliveryAllowed') for c in new)
" && grep -q 'M13' /tmp/dc-matrix-flash.out && ! grep -q ' controller ' /tmp/dc-matrix-flash.out; then
  ok "matrix-18 full factorial; M13-M18 cross x flash honest status + --path flash"
else
  bad "matrix-18 cross x flash: $(cat /tmp/dc-matrix-flash.err)"
fi

# Loader rejects a non-factorial tracker
python3 -c "
import json;d=json.load(open('$CTL/fixtures/matrix-18.json'));d['cells']=d['cells'][:12];json.dump(d,open('/tmp/dc-matrix-bad.json','w'))"
if PYTHONPATH="$CTL" python3 -c "
import matrix
try:
    matrix.load_matrix('/tmp/dc-matrix-bad.json')
except Exception:
    raise SystemExit(0)
raise SystemExit(1)
"; then
  ok "matrix loader rejects 12-cell tracker"
else
  bad "matrix docs/fixture missing"
fi

# ---- DIALOGUE.md gate (dialogue_check.py / cli dialogue-check / TTS block) ----
DLG="$FIX/dialogue/pass"
DT=/tmp/dc-dialogue
rm -rf "$DT"; mkdir -p "$DT"
if "${CLI[@]}" dialogue-check --project "$DLG" >/tmp/dc-dlg.out 2>&1 && grep -q 'PASS' /tmp/dc-dlg.out \
  && python3 -c "import json;d=json.load(open('$DLG/evidence/dialogue-check.json'));assert d['status']=='PASS' and d['duration']['totalChars']==92"; then
  ok "dialogue-check PASS fixture (92字 vs 22s ±15%)"
else
  bad "dialogue-check pass fixture: $(cat /tmp/dc-dlg.out)"
fi
rm -rf "$DLG/evidence"

mk_case() {  # $1 name, $2 python mutation of list L
  mkdir -p "$DT/$1/content"; cp "$DLG/content/plan.json" "$DT/$1/content/"
  python3 -c "
import json; L=json.load(open('$DLG/content/lines.json'))
$2
json.dump(L, open('$DT/$1/content/lines.json','w'), ensure_ascii=False)"
}
mk_case nofn "del L[1]['function']"
mk_case long "L[1]['text']='利率已经低到几乎为零了，可是家家户户还是宁愿把现金攥在手里，既不去花也不去投资更不去借钱。'"
mk_case latehook "L[0]['function']='evidence'; L[4]['function']='hook'"
mk_case short "L[:]=L[:3]+[dict(L[4])]"
mk_case jinju "L[5]['text']='让我们一起记住这个流动性陷阱。'"
mk_case nopayoff "L[4]['function']='evidence'"
mk_case advice "L[5]['text']='别急着抄底，先看懂流动性陷阱。'"
dlg_ok=1
for c in nofn long latehook short jinju nopayoff; do
  if "${CLI[@]}" dialogue-check --project "$DT/$c" >"$DT/$c.out" 2>&1; then dlg_ok=0; echo "  case $c unexpectedly PASS"; fi
done
grep -q "function=None" "$DT/nofn.out" || dlg_ok=0
grep -q "> 35字" "$DT/long.out" || dlg_ok=0
grep -q "first 3 VO beats" "$DT/latehook.out" || dlg_ok=0
grep -q "outside ±15%" "$DT/short.out" || dlg_ok=0
grep -q "金句升华" "$DT/jinju.out" || dlg_ok=0
grep -q "coverage" "$DT/nopayoff.out" || dlg_ok=0
if [ "$dlg_ok" = 1 ]; then
  ok "dialogue-check FAILs: missing function / >35字 / late hook / ±15% / 金句 / coverage"
else
  bad "dialogue-check fail cases: $(cat $DT/*.out)"
fi
if "${CLI[@]}" dialogue-check --project "$DT/advice" >"$DT/advice.out" 2>&1 && grep -q "WARN .*advice tone" "$DT/advice.out"; then
  ok "dialogue-check advice tone is WARN (not FAIL)"
else
  bad "dialogue-check advice warn: $(cat $DT/advice.out)"
fi

# TTS is blocked before any synthesis when the gate fails
if "${CLI[@]}" tts --project "$DT/long" --provider edge --out "$DT/long/voices" >"$DT/tts-block.out" 2>&1; then
  bad "tts should be blocked by dialogue-check FAIL"
elif grep -q "TTS blocked" "$DT/tts-block.out" && [ ! -e "$DT/long/voices" ]; then
  ok "cli tts blocked by dialogue gate (no voices written)"
else
  bad "tts gate: $(cat $DT/tts-block.out)"
fi

# quality: dialogue_gate required for dialogue-layer lines, NOT_APPLICABLE for legacy
if PYTHONPATH="$CTL" python3 -c "
import quality
from pathlib import Path
c=quality._dialogue_check(Path('$DT/long')); assert c['name']=='dialogue_gate' and c['status']=='FAIL' and c['required'], c
c=quality._dialogue_check(Path('$DLG')); assert c['status']=='PASS', c
import json,os; os.makedirs('$DT/legacy/content',exist_ok=True)
json.dump([{'id':'L01','text':'旧片台词。'}],open('$DT/legacy/content/lines.json','w'))
c=quality._dialogue_check(Path('$DT/legacy')); assert c['status']=='NOT_APPLICABLE' and not c['required'], c
"; then
  ok "quality dialogue_gate: FAIL/PASS for function lines, NOT_APPLICABLE legacy"
else
  bad "quality dialogue_gate"
fi
rm -rf "$DLG/evidence"

# schedule: multi-line shots play lines back to back (no stacked VO cues)
if PYTHONPATH="$CTL" python3 -c "
import schedule as S
lines=[{'id':'L01','shotId':'a'},{'id':'L02','shotId':'b'},{'id':'L03','shotId':'b'}]
shots=[{'id':'a','text':'甲'},{'id':'b','text':'乙'}]
tl,err=S.schedule(lines=lines,shots=shots,target_duration=20,beat_grid=0.25,durs={'L01':2.0,'L02':3.0,'L03':2.5},require_all_vo=True)
cue={c['id']:c['t'] for c in tl['cues']}
b=[s for s in tl['shots'] if s['id']=='b'][0]
assert abs(cue['L02']-(b['t0']+0.35))<1e-6 and abs(cue['L03']-(b['t0']+0.35+3.0+0.2))<1e-6, cue
assert abs(b['voDur']-5.7)<1e-6 and cue['L01']==0.35
"; then
  ok "schedule multi-line shot cues sequential (+0.2s gap)"
else
  bad "schedule multi-line cues"
fi

# apply_caption_timeline: capsMode per-line + syncShots only on unlocked style-version main.js
if PYTHONPATH="$CTL" python3 -c "
import json, tempfile
from pathlib import Path
import apply_caption_timeline as A
td=Path(tempfile.mkdtemp()); (td/'content').mkdir()
(td/'main.js').write_text(\"const W = 1920, H = 1080, FPS = 30, DUR = 32;\nconst SHOTS = [\n  { a: 0.0,  b: 4.0,  k: 'hook' },\n  { a: 4.0, b: 9.0, k: 'stress' },\n];\n\",encoding='utf-8')
json.dump({'hook':{'zh':'钩'},'caps':[],'capsMode':'per-line','syncShots':True},open(td/'timeline.json','w'))
json.dump([{'id':'L01','text':'甲。','shotId':'h'},{'id':'L02','text':'乙句。','cap':'{乙}','shotId':'s'},{'id':'L03','text':'丙句。','shotId':'s'}],open(td/'content/lines.json','w'),ensure_ascii=False)
parsed={'scheduledDurationSec':90,'shots':[{'id':'h','t0':0,'t1':3.5,'role':'hook','voIds':['L01']},{'id':'s','t0':3.5,'t1':90,'role':'evidence','voIds':['L02','L03']}],
 'cues':[{'type':'voice','id':'L01','t':0.35},{'type':'voice','id':'L02','t':3.85},{'type':'voice','id':'L03','t':6.0}]}
try:
    A.apply_caption_timeline(td, parsed=parsed); raise SystemExit('locked main.js must refuse')
except ValueError as e:
    assert 'refused' in str(e)
json.dump({'unlocked':['main.js'],'protectedSha256':{'index.html':'x'}},open(td/'content/engine.lock.json','w'))
info=A.apply_caption_timeline(td, parsed=parsed)
src=(td/'main.js').read_text(); tl=json.load(open(td/'timeline.json'))
assert info['shotsSynced'] and 'DUR = 90;' in src and '{ a: 3.50, b: 90.00,' in src and \"k: 'stress'\" in src, src
assert [c['id'] for c in tl['caps']]==['L02','L03'] and tl['caps'][0]['zh']=='{乙}' and tl['caps'][0]['t1']==6.0 and tl['caps'][1]['t1']==90, tl['caps']
assert tl['dur']==90
"; then
  ok "apply_caption_timeline per-line caps + syncShots (refuses locked main.js)"
else
  bad "apply_caption_timeline per-line/syncShots"
fi

# caption-news manifest allows a 90s plan (schema cap 90)
if python3 -c "
import json;m=json.load(open('$CTL/manifests/caption-news.json'));assert m['durationSec']['max']==90 and m['durationSec']['demo']==59.5
s=json.load(open('$CTL/plan.schema.json'));assert s['properties']['targetDurationSec']['maximum']==90"; then
  ok "caption-news durationSec.max=90 (demo still 59.5)"
else
  bad "caption manifest max"
fi

# ---- dialogue-loop (mocked LLM; no network, no real ledger) ----
DLL=/tmp/dc-dialogue-loop; rm -rf "$DLL"; mkdir -p "$DLL"
mkloop() { rm -rf "$DLL/$1"; mkdir -p "$DLL/$1"; cp -r "$DLG/content" "$DLL/$1/"; rm -rf "$DLL/$1/evidence"; }
LEDGER_N0=$( [ -f "$DC_BUDGET_LEDGER" ] && wc -l <"$DC_BUDGET_LEDGER" || echo 0 )
REAL_N0=$(wc -l <"$CTL/fixtures/budget-ledger.jsonl")
mkloop p
if "${CLI[@]}" tts --project "$DLL/p" --provider edge --out "$DLL/p/voices" >"$DLL/p-pre.out" 2>&1; then
  bad "tts should be blocked before dialogue-loop"
elif grep -q "dialogue-loop" "$DLL/p-pre.out" && [ ! -e "$DLL/p/voices" ]; then
  ok "tts blocked when dialogue-check PASS but no dialogue-loop PASS"
else
  bad "tts loop gate: $(cat $DLL/p-pre.out)"
fi
if "${CLI[@]}" dialogue-loop --project "$DLL/p" --max-rounds 4 --mock "$CTL/fixtures/dialogue-loop/mock-pass-after-revise.json" >"$DLL/p.out" 2>&1 \
  && PYTHONPATH="$CTL" python3 -c "
import json,dialogue_loop as D
from pathlib import Path
P=Path('$DLL/p'); s=json.load(open(P/'evidence/dialogue-loop.json'))
assert s['status']=='PASS' and s['chosenRound']==2 and s['rounds']==2, s
L=json.load(open(P/'content/lines.json')); by={x['id']:x for x in L}
assert by['L06']['text'].startswith('凯恩斯早就'), by['L06']
assert by['L01']['text']=='央行把利率降到零，钱却还是不肯动。', 'unflagged line was changed'
assert by['L06']['function']=='sting'
r1=json.load(open(P/'evidence/dialogue-loop/round-1.json')); assert not r1['pass'] and 'L06' in r1['flagged'] and r1['revision']['changes']
assert (P/'evidence/dialogue-loop/round-2.json').is_file()
ok,why=D.gate_status(P); assert ok, why
L[0]['text']='改过一句。'; json.dump(L,open(P/'content/lines.json','w'),ensure_ascii=False)
ok,why=D.gate_status(P); assert not ok and 'changed' in why, why
"; then
  ok "dialogue-loop: critic FAIL → reviser touches only flagged L06 → PASS round 2; gate sha-locks lines"
else
  bad "dialogue-loop pass-after-revise: $(cat $DLL/p.out)"
fi
mkloop n
"${CLI[@]}" dialogue-loop --project "$DLL/n" --max-rounds 2 --mock "$CTL/fixtures/dialogue-loop/mock-never-pass.json" >"$DLL/n.out" 2>&1 && rc=0 || rc=$?
if [ "$rc" = 1 ] && grep -q "BEST_EFFORT" "$DLL/n.out" && PYTHONPATH="$CTL" python3 -c "
import json,dialogue_loop as D, quality as Q
from pathlib import Path
P=Path('$DLL/n'); s=json.load(open(P/'evidence/dialogue-loop.json')); assert s['status']=='BEST_EFFORT' and s['rounds']==2, s
assert not D.gate_status(P)[0]
c=Q._dialogue_loop_check(P); assert c['status']=='FAIL' and c['required'], c
" && ! "${CLI[@]}" tts --project "$DLL/n" --provider edge --out "$DLL/n/voices" >/dev/null 2>&1 && [ ! -e "$DLL/n/voices" ]; then
  ok "dialogue-loop never passes → BEST_EFFORT (exit 1), quality dialogue_loop FAIL, TTS still blocked"
else
  bad "dialogue-loop best-effort: rc=$rc $(cat $DLL/n.out)"
fi
mkloop e
cp "$DLL/e/content/lines.json" "$DLL/e-orig.json"
"${CLI[@]}" dialogue-loop --project "$DLL/e" --mock "$CTL/fixtures/dialogue-loop/mock-provider-error.json" >"$DLL/e.out" 2>&1 && rc=0 || rc=$?
if [ "$rc" = 3 ] && grep -q "provider failure" "$DLL/e.out" && cmp -s "$DLL/e-orig.json" "$DLL/e/content/lines.json"; then
  ok "dialogue-loop provider error → stop (exit 3), lines untouched, no fallback"
else
  bad "dialogue-loop provider error: rc=$rc $(cat $DLL/e.out)"
fi
LEDGER_N1=$( [ -f "$DC_BUDGET_LEDGER" ] && wc -l <"$DC_BUDGET_LEDGER" || echo 0 )
if [ "$LEDGER_N0" = "$LEDGER_N1" ] && [ "$REAL_N0" = "$(wc -l <"$CTL/fixtures/budget-ledger.jsonl")" ] && PYTHONPATH="$CTL" python3 -c "
import dialogue_loop as D
ev=D.evaluate_critique({'lines':[{'id':'L01','scores':{'factual':5,'natural':5,'asr_safe':5,'function_fit':5},'issues':[]}],
  'script':{'scores':{k:5 for k in D.SCRIPT_DIMS},'issues':[{'severity':'high','lines':['L01'],'detail':'三招只列两招'}]}},['L01','L02'])
assert not ev['pass'] and 'L01' in ev['flagged'] and any('skipped' in r for r in ev['reasons']), ev
"; then
  ok "dialogue-loop: mock runs write no ledger rows; thresholds catch script-level high + skipped lines"
else
  bad "dialogue-loop ledger/threshold"
fi

# stepaudio provider + music bed source: local mock StepFun API, fake key, no network
if env -u STEP_API_KEY python3 "$CTL/tests/stepaudio_mock.py" >/tmp/dc_stepaudio_mock.log 2>&1; then
  ok "stepaudio: free gen-preview only (paid /audio/speech + non-free models refused), pitch retakes, session mode = 1 request split by ASR timings, 402 stops, music bed cut/fade/RMS + cache"
else
  bad "stepaudio mock (see /tmp/dc_stepaudio_mock.log)"
fi

# elevenlabs provider: local mock API, fake key, no network
if env -u ELEVEN_API_KEY -u ELEVENLABS_API_KEY python3 "$CTL/tests/elevenlabs_mock.py" >/tmp/dc_elevenlabs_mock.log 2>&1; then
  ok "elevenlabs: needs-key without ELEVENLABS_API_KEY; mock TTS writes wav+dur; xi-api-key + multilingual_v2; listed in --list"
else
  bad "elevenlabs mock (see /tmp/dc_elevenlabs_mock.log)"
fi

# elevenlabs-dialogue: local mock Text-to-Dialogue API, fake key, no network
if env -u ELEVEN_API_KEY -u ELEVENLABS_API_KEY python3 "$CTL/tests/elevenlabs_dialogue_mock.py" >/tmp/dc_elevenlabs_dialogue_mock.log 2>&1; then
  ok "elevenlabs-dialogue: needs-key; chunk ≤2000/≤10 voices; mock writes dialogue.wav+manifest; v4→v3 fallback; listed in --list"
else
  bad "elevenlabs-dialogue mock (see /tmp/dc_elevenlabs_dialogue_mock.log)"
fi

# elevenlabs-dialogue guest voice by content type (Tex host; market/concept/personal/english), mock API
if env -u ELEVEN_API_KEY -u ELEVENLABS_API_KEY -u ELEVENLABS_VOICE_HOST -u ELEVENLABS_VOICE_GUEST -u LEMO_TTS_ELEVENLABS_CONTENT_TYPE \
    python3 "$CTL/tests/elevenlabs_content_type_mock.py" >/tmp/dc_elevenlabs_content_type_mock.log 2>&1; then
  ok "elevenlabs-dialogue: content_type → guest (market→Linda, concept→Ladaisy, personal→Shusita, english→Joan; default Linda; VOICE_GUEST overrides; router/run_tts/plan.json)"
else
  bad "elevenlabs content-type mock (see /tmp/dc_elevenlabs_content_type_mock.log)"
fi

# visual-check: synthetic film with known defects (OCR/ffmpeg local), semantic layer mocked, quality gate, speaker metric
if env -u OPENROUTER_API_KEY python3 "$CTL/tests/visual_check_mock.py" >/tmp/dc_visual_check_mock.log 2>&1; then
  ok "visual-check: wrong caption chars / corrupt frame / clipped text / subtitle≠VO → high; no false positive on correct text; :free-only + billing-delta stop; hook-subs rework; quality gate; speaker metric"
else
  bad "visual-check mock (see /tmp/dc_visual_check_mock.log)"
fi

# budget ledger: tests write to \$DC_BUDGET_LEDGER, never the real fixtures ledger
if PYTHONPATH="$CTL" python3 -c "
import budget,os
assert str(budget.ledger_path())==os.path.realpath('$DC_BUDGET_LEDGER')
" && ! grep -q 'fixtures/handoff-mini' "$CTL/fixtures/budget-ledger.jsonl"; then
  ok "budget ledger honors DC_BUDGET_LEDGER; no handoff-mini noise in real ledger"
else
  bad "budget ledger env override / noise"
fi

echo
echo "Results: $pass passed, $fail failed"

test "$fail" -eq 0
