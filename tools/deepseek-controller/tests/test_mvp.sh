#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CTL="$ROOT/tools/deepseek-controller"
CLI=(python3 "$CTL/cli.py")
FIX="$CTL/fixtures"
pass=0
fail=0
skipped=0
cd "$ROOT"
# Headless Chrome for page.mjs readcheck smoke (texts_runtime overlay test): keep the
# caller's PLAYWRIGHT_CHROME, else a system Chrome when there is one, else leave it unset
# so playwright-core finds its own chromium-headless-shell (core/render/browser.mjs).
if [ -z "${PLAYWRIGHT_CHROME:-}" ] && [ -x /usr/bin/google-chrome ]; then
  export PLAYWRIGHT_CHROME=/usr/bin/google-chrome
fi

ok() { echo "PASS: $*"; pass=$((pass+1)); }
bad() { echo "FAIL: $*"; fail=$((fail+1)); }
# skip <what> <why>: a prerequisite of this machine is missing (not a code failure)
skip() { echo "SKIP: $1 ($2)"; skipped=$((skipped+1)); }

# Everything the harness writes goes to a scratch dir, never into tracked fixtures.
WORK="$(mktemp -d "${TMPDIR:-/tmp}/dc-mvp.XXXXXX")"
export WORK   # python snippets in quoted heredocs read it from the environment
trap 'rm -rf "$WORK"' EXIT
# Never let tests append to the real fixtures/budget-ledger.jsonl (handoff etc. log $0 rows).
export WORDFILM_BUDGET_LEDGER="$WORK/budget-ledger.jsonl"
export DC_QUOTA_LEDGER="$WORK/quota-ledger.jsonl"   # TokenHarbor quota estimate: never the real one
unset DC_BUDGET_LEDGER
SWISS_PROJ="$WORK/out-swiss-motion"
cp -a "$FIX/out-swiss-motion" "$SWISS_PROJ"

# Prerequisites of the environmental checks (each check SKIPs with a reason when absent).
FILMS="$(PYTHONPATH="$CTL" python3 -c 'from common import films_root; print(films_root())')"
have_films() { test -d "$FILMS"; }
have_py() { python3 -c "import $1" >/dev/null 2>&1; }
have_ffmpeg() { command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; }
have_net() {
  python3 -c "import urllib.request; urllib.request.urlopen('https://raw.githubusercontent.com/google/fonts/main/ofl/intertight/OFL.txt', timeout=8).read(64)" >/dev/null 2>&1
}
have_chromium() {
  test -d "$ROOT/node_modules/playwright-core" || return 1
  command -v node >/dev/null 2>&1 || return 1
  node --input-type=module -e "
import { chromium } from 'playwright-core';
const b = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROME || undefined }).catch(() => null);
if (!b) process.exit(1); await b.close();" >/dev/null 2>&1
}
NET=0; have_net && NET=1
# Offline without a font cache: scaffold still needs font files to exist, so give it
# stand-ins (right names and sizes, not real fonts). Font checks then SKIP.
FONTS_STANDIN=0
if [ "$NET" = 0 ] && [ -z "${LEMO_FONT_CACHE:-}" ]; then
  export LEMO_FONT_CACHE="$WORK/font-standins"
  PYTHONPATH="$CTL" python3 -c "
import sys
from pathlib import Path
from fetch_fonts import STYLE_FONTS
d = Path(sys.argv[1]); d.mkdir(parents=True, exist_ok=True)
for pack in STYLE_FONTS.values():
    for name, _url, mn in pack:
        (d / name).write_bytes(b'0' * mn)
" "$LEMO_FONT_CACHE"
  FONTS_STANDIN=1
  echo "NOTE: offline and no LEMO_FONT_CACHE: scaffold checks use stand-in font files"
fi
FIX_STATUS_BEFORE="$(git -C "$ROOT" status --porcelain -- tools/deepseek-controller/fixtures 2>/dev/null || true)"

# 1) invalid plan rejected
if "${CLI[@]}" validate "$FIX/plan-invalid.json" >$WORK/dc-val.out 2>$WORK/dc-val.err; then
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
rm -rf $WORK/dc-adapt-swiss
if "${CLI[@]}" adapt "$FIX/plan-swiss-motion.json" -o $WORK/dc-adapt-swiss >/dev/null \
  && test -f $WORK/dc-adapt-swiss/content/shots.json \
  && test -f $WORK/dc-adapt-swiss/content/lines.json; then
  ok "adapt swiss writes content-only files"
else
  bad "adapt swiss"
fi

# ensure adapt did not create engine cores
if test ! -e $WORK/dc-adapt-swiss/ease.js && test ! -e $WORK/dc-adapt-swiss/film.js; then
  ok "adapt does not copy engine cores"
else
  bad "adapt leaked engine files"
fi

# 4) schedule fails when VO too long
cp -a "$FIX/schedule-too-long" "$WORK/schedule-too-long"
if "${CLI[@]}" schedule --project "$WORK/schedule-too-long" --require-vo >$WORK/dc-sch.out 2>$WORK/dc-sch.err; then
  bad "schedule should fail when VO too long"
else
  if grep -q "exceeds target" $WORK/dc-sch.err; then
    ok "schedule fails when VO too long"
  else
    bad "schedule failed but missing exceeds-target message: $(cat $WORK/dc-sch.err)"
  fi
fi

# 5) schedule OK with short durs
if "${CLI[@]}" schedule --project "$SWISS_PROJ" --require-vo >$WORK/dc-sch2.out 2>$WORK/dc-sch2.err; then
  ok "schedule OK with measured short VO"
else
  bad "schedule short VO: $(cat $WORK/dc-sch2.err)"
fi

# 6) quality fails on forced FAIL
if "${CLI[@]}" quality --project "$SWISS_PROJ" --skip-heavy --allow-unchecked \
  --force-fail fixture_forced_fail -o "$WORK/quality-fail/quality.json" \
  >$WORK/dc-q.out 2>$WORK/dc-q.err; then
  bad "quality should fail with --force-fail"
else
  if grep -q 'overall=FAIL' $WORK/dc-q.out; then
    ok "quality fails when forced FAIL"
  else
    bad "quality force-fail output unexpected: $(cat $WORK/dc-q.out) $(cat $WORK/dc-q.err)"
  fi
fi

# 7) quality can PASS content-stage with allow-unchecked (no force)
if "${CLI[@]}" quality --project "$SWISS_PROJ" --skip-heavy --allow-unchecked \
  -o $WORK/dc-quality-pass.json >$WORK/dc-q2.out 2>$WORK/dc-q2.err; then
  ok "quality PASS with --allow-unchecked at content stage"
else
  bad "quality allow-unchecked: $(cat $WORK/dc-q2.out) $(cat $WORK/dc-q2.err)"
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
rm -rf $WORK/dc-scaffold-swiss
if "${CLI[@]}" scaffold "$FIX/plan-swiss-motion.json" -o $WORK/dc-scaffold-swiss --lib "$ROOT" >$WORK/dc-sc.out 2>$WORK/dc-sc.err \
  && test -f $WORK/dc-scaffold-swiss/content/shots.json \
  && test -f $WORK/dc-scaffold-swiss/content/engine.lock.json \
  && test -f $WORK/dc-scaffold-swiss/lines.json \
  && test -f $WORK/dc-scaffold-swiss/palette.json \
  && test -f $WORK/dc-scaffold-swiss/PROJECT.md \
  && test -f $WORK/dc-scaffold-swiss/ease.js \
  && test -f $WORK/dc-scaffold-swiss/film.js \
  && grep -q '一块钱' $WORK/dc-scaffold-swiss/lines.json; then
  ok "scaffold swiss creates expected files"
  assert_hash "$ROOT/styles/swiss-motion/demo/ease.js" $WORK/dc-scaffold-swiss/ease.js "swiss ease.js"
  assert_hash "$ROOT/styles/swiss-motion/demo/film.js" $WORK/dc-scaffold-swiss/film.js "swiss film.js"
else
  bad "scaffold swiss: $(cat $WORK/dc-sc.out) $(cat $WORK/dc-sc.err)"
fi

# Pictogram
rm -rf $WORK/dc-scaffold-picto
if "${CLI[@]}" scaffold "$FIX/plan-pictogram-motion.json" -o $WORK/dc-scaffold-picto --lib "$ROOT" --force >$WORK/dc-sc2.out 2>$WORK/dc-sc2.err \
  && test -f $WORK/dc-scaffold-picto/content/edl_content.json \
  && test -f $WORK/dc-scaffold-picto/content/engine.lock.json \
  && test -f $WORK/dc-scaffold-picto/edl_content.json \
  && test -f $WORK/dc-scaffold-picto/palette.json \
  && test -f $WORK/dc-scaffold-picto/PROJECT.md \
  && test -f $WORK/dc-scaffold-picto/engine.js \
  && test -f $WORK/dc-scaffold-picto/edl.js \
  && grep -q '分散投资\|股票\|sprint' $WORK/dc-scaffold-picto/edl_content.json; then
  ok "scaffold pictogram creates expected files"
  assert_hash "$ROOT/styles/pictogram-motion/demo/engine.js" $WORK/dc-scaffold-picto/engine.js "pictogram engine.js"
  assert_hash "$ROOT/styles/pictogram-motion/demo/edl.js" $WORK/dc-scaffold-picto/edl.js "pictogram edl.js"
  assert_hash "$ROOT/styles/pictogram-motion/demo/scenes.js" $WORK/dc-scaffold-picto/scenes.js "pictogram scenes.js"
else
  bad "scaffold pictogram: $(cat $WORK/dc-sc2.out) $(cat $WORK/dc-sc2.err)"
fi

# Caption
rm -rf $WORK/dc-scaffold-caption
if "${CLI[@]}" scaffold "$FIX/plan-caption-news.json" -o $WORK/dc-scaffold-caption --lib "$ROOT" --force >$WORK/dc-sc3.out 2>$WORK/dc-sc3.err \
  && test -f $WORK/dc-scaffold-caption/content/timeline_content.json \
  && test -f $WORK/dc-scaffold-caption/content/engine.lock.json \
  && test -f $WORK/dc-scaffold-caption/timeline.json \
  && test -f $WORK/dc-scaffold-caption/lines.json \
  && test -f $WORK/dc-scaffold-caption/audio/lines.json \
  && test -f $WORK/dc-scaffold-caption/palette.json \
  && test -f $WORK/dc-scaffold-caption/FACTS.md \
  && test -f $WORK/dc-scaffold-caption/PROJECT.md \
  && test -f $WORK/dc-scaffold-caption/main.js \
  && grep -q '流动性' $WORK/dc-scaffold-caption/timeline.json; then
  ok "scaffold caption creates expected files"
  assert_hash "$ROOT/styles/caption-news/demo/main.js" $WORK/dc-scaffold-caption/main.js "caption main.js"
  assert_hash "$ROOT/styles/caption-news/demo/index.html" $WORK/dc-scaffold-caption/index.html "caption index.html"
else
  bad "scaffold caption: $(cat $WORK/dc-sc3.out) $(cat $WORK/dc-sc3.err)"
fi

# 11) quality schedule must FAIL when VO required but dur.json empty (fitsTarget alone insufficient)
rm -rf $WORK/dc-q-novo
cp -a "$FIX/out-swiss-motion" $WORK/dc-q-novo
# empty measured durs + write a "fits" timeline that would look OK without require-vo
python3 - <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ["WORK"]) / "dc-q-novo"
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
if "${CLI[@]}" quality --project $WORK/dc-q-novo --skip-heavy --allow-unchecked \
  -o $WORK/dc-q-novo/quality.json >$WORK/dc-q-novo.out 2>$WORK/dc-q-novo.err; then
  bad "quality should FAIL when timeline.ok=false / missing VO"
else
  if grep -q 'schedule_fits_target' $WORK/dc-q-novo/quality.json \
    && python3 -c 'import json,os;q=json.load(open(os.environ["WORK"]+"/dc-q-novo/quality.json"));c={x["name"]:x for x in q["checks"]};assert c["schedule_fits_target"]["status"]=="FAIL";assert q["overall"]=="FAIL"'; then
    ok "quality fails schedule when require-vo would fail (not fooled by fitsTarget)"
  else
    bad "quality novo schedule check: $(cat $WORK/dc-q-novo.out) $(cat $WORK/dc-q-novo.err) $(cat $WORK/dc-q-novo/quality.json)"
  fi
fi

# 12) quality --project . resolves absolute path (no 'index.html in .')
rm -rf $WORK/dc-q-rel
cp -a $WORK/dc-scaffold-swiss $WORK/dc-q-rel 2>/dev/null || true
if test ! -d $WORK/dc-q-rel; then
  "${CLI[@]}" scaffold "$FIX/plan-swiss-motion.json" -o $WORK/dc-q-rel --lib "$ROOT" --force >/dev/null 2>&1 || true
fi
# ensure dur so schedule check can pass under has_vo
python3 - <<'PY'
import json, os
from pathlib import Path
p = Path(os.environ["WORK"]) / "dc-q-rel"
plan = json.loads((p/"content"/"plan.json").read_text())
durs = {ln["id"]: 1.0 for ln in (plan.get("voice") or {}).get("lines") or []}
(p/"voices").mkdir(exist_ok=True)
(p/"voices"/"dur.json").write_text(json.dumps(durs)+"\n")
# minimal ok timeline
shots = [{"id":s["id"],"t0":0,"t1":1,"dur":1,"voIds":[],"voDur":0,"readSec":0.5,"text":s.get("text","")} for s in plan["shots"]]
tl={"targetDurationSec":plan["targetDurationSec"],"scheduledDurationSec":1.0,"beatGridSec":0.25,"fitsTarget":True,"requireVo":True,"ok":True,"errors":[],"warnings":[],"shots":shots,"cues":[]}
(p/"timeline.parsed.json").write_text(json.dumps(tl)+"\n")
PY
pushd $WORK/dc-q-rel >/dev/null
if "${CLI[@]}" quality --project . --skip-heavy --allow-unchecked \
  -o $WORK/dc-q-rel-abs.json >$WORK/dc-q-rel.out 2>$WORK/dc-q-rel.err; then
  if python3 -c 'import json,os;q=json.load(open(os.environ["WORK"]+"/dc-q-rel-abs.json"));assert q["project"].startswith("/"), q["project"];assert "no index.html in \".\"" not in json.dumps(q)'; then
    ok "quality --project . resolves to absolute path"
  else
    bad "quality relative path still broken: $(cat $WORK/dc-q-rel-abs.json)"
  fi
else
  if python3 -c 'import json,os;q=json.load(open(os.environ["WORK"]+"/dc-q-rel-abs.json"));assert q["project"].startswith("/");print(q["project"])' 2>/dev/null; then
    ok "quality --project . resolves to absolute path (overall may fail)"
  else
    bad "quality --project . : $(cat $WORK/dc-q-rel.out) $(cat $WORK/dc-q-rel.err)"
  fi
fi
popd >/dev/null

# 13) scaffold swiss writes words_rel.json for zh + fetches fonts
if test -f $WORK/dc-scaffold-swiss/voices/words_rel.json \
  && python3 -c 'import json,os;d=json.load(open(os.environ["WORK"]+"/dc-scaffold-swiss/voices/words_rel.json"));assert d, d'; then
  ok "scaffold swiss writes zh words_rel.json"
else
  # re-scaffold if earlier run was before fix
  rm -rf $WORK/dc-scaffold-swiss2
  export LEMO_FONT_CACHE="${LEMO_FONT_CACHE:-$FILMS/fuli-controller-e2e/fonts}"
  if "${CLI[@]}" scaffold "$FIX/plan-swiss-motion.json" -o $WORK/dc-scaffold-swiss2 --lib "$ROOT" --force >$WORK/dc-sc-zh.out 2>$WORK/dc-sc-zh.err \
    && test -f $WORK/dc-scaffold-swiss2/voices/words_rel.json; then
    ok "scaffold swiss writes zh words_rel.json"
  else
    bad "scaffold zh words_rel: $(cat $WORK/dc-sc-zh.out 2>/dev/null) $(cat $WORK/dc-sc-zh.err 2>/dev/null)"
  fi
fi

# 14) scaffold swiss fonts present (Archivo-VF etc.)
FONT_PROJ=$WORK/dc-scaffold-swiss2
test -d "$FONT_PROJ" || FONT_PROJ=$WORK/dc-scaffold-swiss
if [ "$FONTS_STANDIN" = 1 ]; then
  skip "scaffold swiss .ttf fonts" "no network to raw.githubusercontent.com and no font cache (LEMO_FONT_CACHE)"
elif test -f "$FONT_PROJ/fonts/Archivo-VF.ttf" \
  && test -f "$FONT_PROJ/fonts/DMSerifDisplay-Regular.ttf" \
  && test -f "$FONT_PROJ/fonts/UnifrakturMaguntia-Regular.ttf"; then
  ok "scaffold swiss fetches/copies required .ttf fonts"
else
  export LEMO_FONT_CACHE="${LEMO_FONT_CACHE:-$FILMS/fuli-controller-e2e/fonts}"
  rm -rf $WORK/dc-scaffold-fonts
  if "${CLI[@]}" scaffold "$FIX/plan-swiss-motion.json" -o $WORK/dc-scaffold-fonts --lib "$ROOT" --force >$WORK/dc-sc-f.out 2>$WORK/dc-sc-f.err \
    && test -f $WORK/dc-scaffold-fonts/fonts/Archivo-VF.ttf; then
    ok "scaffold swiss fetches/copies required .ttf fonts"
  else
    bad "scaffold fonts: $(cat $WORK/dc-sc-f.out) $(cat $WORK/dc-sc-f.err); ls $(ls $WORK/dc-scaffold-fonts/fonts 2>/dev/null)"
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
_which = quality.shutil.which
subprocess.run = lambda *a, **k: R()
# parser-only test: pretend ffmpeg exists so it runs on machines without it
quality.shutil.which = lambda name: "/bin/" + name
try:
    r = quality.ebur128(Path("/etc/hosts"))
finally:
    subprocess.run = _real
    quality.shutil.which = _which
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
import json, os, sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
import quality

src = Path("tools/deepseek-controller/fixtures/out-swiss-motion")
for cand in (Path(os.environ["WORK"]) / "dc-scaffold-swiss", Path(os.environ["WORK"]) / "dc-scaffold-swiss2", src):
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

# 17b) MATRIX-18 M14: Whisper hears 复利 as 复立; the lexicon entry clears that residual
if python3 - <<'PY'
import json, sys
sys.path.insert(0, "tools/deepseek-controller")
import quality
raw = json.load(open("tools/deepseek-controller/asr_homophones.json", encoding="utf-8"))
fuli = [g for g in raw["classes"] if "复利" in g.get("members", [])]
assert fuli and "复立" in fuli[0]["members"], fuli
classes = quality._load_homophone_classes()
want = "复利靠的是留下，而不是赌一把。"
ok, a, b, _ = quality._homophone_tolerant_match(want, "复立靠的是留下,而不是赌一把。", classes)
assert ok and a == b, (a, b)
detail = "DIFF L05 | 复利靠的是留下，而不是赌一把。 → 复立靠的是留下,而不是赌一把。    (similarity 0.93 < 0.95)\nmismatches: 1\n"
diffs = quality._parse_asr_diffs(detail)
assert [d[0] for d in diffs] == ["L05"], diffs
assert all(quality._homophone_tolerant_match(w, g, classes)[0] for _, w, g in diffs)
# without the entry the same line stays a residual (the M14 failure)
bare = [{"members": c["members"] - {"复立"}, "short": c["short"]} for c in classes]
assert not quality._homophone_tolerant_match(want, "复立靠的是留下,而不是赌一把。", bare)[0]
print("ok")
PY
then
  ok "asr_homophones maps 复立 to 复利 (M14 L05 residual cleared)"
else
  bad "asr_homophones 复立 to 复利"
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

# 21b) MATRIX-18 M14/M16: caption copy that overruns the locked caption-news DUR fails
#      schedule before render, even when the target (plan or --target) would allow it
CAP_OVR="$WORK/caption-overrun"
python3 - "$CAP_OVR" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
(p / "content").mkdir(parents=True)
(p / "voices").mkdir()
(p / "main.js").write_text("const W = innerWidth, H = innerHeight, FPS = 30, DUR = 30;\n", encoding="utf-8")
ids = [f"c{i}" for i in range(1, 8)]
caps = [{"id": c, "zh": "复利", "en": "compound", "k": "cap", "role": "hook" if c == "c1" else "explain"} for c in ids]
(p / "content" / "timeline_content.json").write_text(json.dumps({"caps": caps}, ensure_ascii=False))
(p / "content" / "lines.json").write_text(json.dumps(
    [{"id": f"L0{i}", "shotId": c, "text": "复利"} for i, c in enumerate(ids, 1)], ensure_ascii=False))
# six 5.00s shots + one 2.25s shot = 32.25s against the 30s lock (the M14 numbers);
# standard pacing adds 0.40s per shot, snapped up to the 0.25s grid
durs = {f"L0{i}": (4.5 if i < 7 else 1.75) for i in range(1, 8)}
(p / "voices" / "dur.json").write_text(json.dumps(durs))
(p / "content" / "plan.json").write_text(json.dumps({"style": "caption-news", "targetDurationSec": 30}))
(p / "timeline.json").write_text(json.dumps({"dur": 30, "vo": {}, "caps": []}))
PY
cp "$CAP_OVR/timeline.json" "$WORK/caption-overrun.timeline.before"
if "${CLI[@]}" schedule --project "$CAP_OVR" --require-vo >$WORK/dc-ovr.out 2>$WORK/dc-ovr.err; then
  bad "schedule should fail: caption copy 32.25s > locked 30s"
elif grep -q 'copy overruns the locked caption-news timeline by 2.25s: content 32.25s > locked 30.00s' $WORK/dc-ovr.err \
  && grep -q 'trim shots: c7 (30.00-32.25s)' $WORK/dc-ovr.err \
  && cmp -s "$CAP_OVR/timeline.json" "$WORK/caption-overrun.timeline.before" \
  && python3 -c "
import json;t=json.load(open('$CAP_OVR/timeline.parsed.json'))
assert t['ok'] is False and t['lockedDurationSec']==30 and t['lockOverrunSec']==2.25, t"; then
  ok "schedule rejects 32.25s caption copy against the locked 30s caption-news DUR (names c7)"
else
  bad "caption overrun message: $(cat $WORK/dc-ovr.err)"
fi

if "${CLI[@]}" schedule --project "$CAP_OVR" --require-vo --target 33 >$WORK/dc-ovr2.out 2>$WORK/dc-ovr2.err; then
  bad "schedule --target 33 must still fail against the 30s caption lock"
elif grep -q 'copy overruns the locked caption-news timeline by 2.25s' $WORK/dc-ovr2.err \
  && ! grep -q 'exceeds target' $WORK/dc-ovr2.err \
  && cmp -s "$CAP_OVR/timeline.json" "$WORK/caption-overrun.timeline.before"; then
  ok "caption lock guard holds when the target alone would pass (--target 33)"
else
  bad "caption overrun with --target 33: $(cat $WORK/dc-ovr2.err)"
fi

if PYTHONPATH="$CTL" python3 - "$CAP_OVR" <<'PY'
import sys
from pathlib import Path
from apply_caption_timeline import apply_caption_timeline, main
p = Path(sys.argv[1])
try:
    apply_caption_timeline(p)
except ValueError as e:
    assert "schedule did not pass" in str(e), e
else:
    raise SystemExit("apply accepted a failed schedule")
parsed = {"ok": True, "scheduledDurationSec": 32.25, "contentDurationSec": 32.25, "shots": [], "cues": []}
try:
    apply_caption_timeline(p, parsed=parsed)
except ValueError as e:
    assert "overruns the locked caption-news timeline by 2.25s" in str(e), e
else:
    raise SystemExit("apply accepted an overrunning schedule")
assert main(["--project", str(p)]) == 1
assert apply_caption_timeline(p, parsed=parsed, force=True)["dur"] == 30.0
print("ok")
PY
then
  ok "apply_caption_timeline refuses failed/overrunning schedules unless --force"
else
  bad "apply_caption_timeline overrun refusal"
fi

# trimmed copy (c7 cut) fits the lock and applies
python3 - "$CAP_OVR" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
tc = json.loads((p / "content" / "timeline_content.json").read_text())
tc["caps"] = tc["caps"][:6]
(p / "content" / "timeline_content.json").write_text(json.dumps(tc, ensure_ascii=False))
lines = json.loads((p / "content" / "lines.json").read_text())[:6]
(p / "content" / "lines.json").write_text(json.dumps(lines, ensure_ascii=False))
PY
if "${CLI[@]}" schedule --project "$CAP_OVR" --require-vo >$WORK/dc-ovr3.out 2>$WORK/dc-ovr3.err \
  && grep -q 'OK applied caption timeline.json' $WORK/dc-ovr3.out \
  && python3 -c "
import json;t=json.load(open('$CAP_OVR/timeline.parsed.json'))
assert t['ok'] and t['contentDurationSec']==30.0 and t['lockOverrunSec']==0, t"; then
  ok "trimmed caption copy (30.00s) passes the lock and applies"
else
  bad "trimmed caption copy: $(cat $WORK/dc-ovr3.out $WORK/dc-ovr3.err)"
fi

# 21c) MATRIX-18 M14/M16 trimmed copy (fixtures/matrix-18/m1{4,6}-trimmed: controller-written
#      content/ + measured edge zh-CN-YunxiNeural durations): the plan validates, the lines pass the
#      dialogue gate against the VO budget of the 30s lock (--target 20: 77-103 zi at 4.5 zi/s, the
#      same gate cli tts runs), and schedule fits the locked 30s DUR
#      of the seed main.js (liudong-caption-ds-v001) with no overrun.
for cell in m14 m16; do
  TRIM="$WORK/matrix-$cell-trimmed"
  rm -rf "$TRIM"
  cp -a "$FIX/matrix-18/$cell-trimmed" "$TRIM"
  printf 'const W = innerWidth, H = innerHeight, FPS = 30, DUR = 30;\n' >"$TRIM/main.js"
  if ! "${CLI[@]}" validate "$TRIM/content/plan.json" >$WORK/dc-trim-$cell.val 2>&1; then
    bad "$cell trimmed plan validate: $(cat $WORK/dc-trim-$cell.val)"
  elif ! "${CLI[@]}" dialogue-check --project "$TRIM" --target 20 >$WORK/dc-trim-$cell.dlg 2>&1; then
    bad "$cell trimmed dialogue-check: $(cat $WORK/dc-trim-$cell.dlg)"
  elif ! "${CLI[@]}" schedule --project "$TRIM" --require-vo >$WORK/dc-trim-$cell.out 2>$WORK/dc-trim-$cell.err; then
    bad "$cell trimmed schedule: $(cat $WORK/dc-trim-$cell.err)"
  elif python3 - "$TRIM/timeline.parsed.json" <<'PY' >$WORK/dc-trim-$cell.chk 2>&1
import json, sys
t = json.load(open(sys.argv[1], encoding="utf-8"))
assert t["ok"] and t["lockedDurationSec"] == 30 and t["lockOverrunSec"] == 0, t
# ceiling-only duration (pacing P0): no hold-last-beat pad; only the end-card outro follows
assert t["contentDurationSec"] <= 29.5 and t["scheduledDurationSec"] <= 30.0 and t["padSec"] == 0, t
assert len(t["shots"]) == 6 and all(s["voIds"] for s in t["shots"][:5]), t["shots"]
print(t["contentDurationSec"])
PY
  then
    ok "MATRIX-18 $cell trimmed caption copy: validate + dialogue-check + schedule $(cat $WORK/dc-trim-$cell.chk)s within the locked 30s"
  else
    bad "$cell trimmed timeline: $(cat $WORK/dc-trim-$cell.chk)"
  fi
done

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

# 24) fetch_fonts: pictogram downloads (or copies from a cache); caption woff2 subsets have
#     no raw URL, so they come from LEMO_FONT_CACHE / sibling films (synthetic cache when absent)
PICTO_CACHE="${LEMO_FONT_CACHE:-$FILMS/fensan-controller-e2e/fonts}"
if [ "$FONTS_STANDIN" = 1 ] || { [ "$NET" = 0 ] && ! test -f "$PICTO_CACHE/InterTightwght.ttf"; }; then
  skip "fetch_fonts pictogram" "no network to raw.githubusercontent.com and no real font cache (LEMO_FONT_CACHE)"
elif LEMO_FONT_CACHE="$PICTO_CACHE" python3 - "$WORK/font-pictogram" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
from fetch_fonts import ensure_fonts

td = Path(sys.argv[1])
(td / "fonts").mkdir(parents=True)
acts = ensure_fonts(td / "fonts", "pictogram-motion", project=td)
assert (td / "fonts" / "InterTightwght.ttf").is_file()
assert (td / "fonts" / "DMMono-Medium.ttf").is_file()
assert (td / "fonts" / "NotoSansSCwght.ttf").is_file()
assert any(("copied-fallback" in a) or a.startswith("ok ") or a.startswith("fetched ") for a in acts)
print("ok")
PY
then
  ok "fetch_fonts pictogram (download or LEMO_FONT_CACHE)"
else
  bad "fetch_fonts pictogram"
fi

CAP_CACHE="${LEMO_FONT_CACHE:-$FILMS/liudong-controller-e2e/fonts}"
CAP_KIND="real cache $CAP_CACHE"
if [ "$FONTS_STANDIN" = 1 ] || ! test -f "$CAP_CACHE/it500.woff2"; then
  # No rendered caption film here: prove the cache copy path with stand-in subsets.
  CAP_CACHE="$WORK/font-cache-caption"; CAP_KIND="synthetic cache"
  mkdir -p "$CAP_CACHE"
  for n in it500 it600i it800 sc500 sc900; do head -c 4096 /dev/zero >"$CAP_CACHE/$n.woff2"; done
fi
if LEMO_FONT_CACHE="$CAP_CACHE" python3 - "$WORK/font-caption" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, "tools/deepseek-controller")
from fetch_fonts import ensure_fonts

td = Path(sys.argv[1])
(td / "fonts").mkdir(parents=True)
acts = ensure_fonts(td / "fonts", "caption-news", project=td)
for name in ("it500.woff2", "it600i.woff2", "it800.woff2", "sc500.woff2", "sc900.woff2"):
    assert (td / "fonts" / name).is_file(), name
    assert f"copied-fallback {name}" in acts or f"ok {name}" in acts, acts
print("ok")
PY
then
  ok "fetch_fonts caption woff2 subsets via LEMO_FONT_CACHE ($CAP_KIND)"
else
  bad "fetch_fonts caption ($CAP_KIND)"
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
if ! have_py numpy || ! have_py soundfile; then
  skip "music_bed / cli mix" "numpy + soundfile not installed (pip install -r requirements.txt)"
elif python3 - <<'PY'
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
if ! have_chromium; then
  skip "swiss texts_runtime overlay + quality N/A gate" "no playwright-core in node_modules (npm ci) or no launchable Chromium (node node_modules/playwright-core/cli.js install chromium-headless-shell, or PLAYWRIGHT_CHROME)"
elif python3 - <<'PY'
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
if ! have_py edge_tts; then
  skip "tts router list + kokoro/qwen3 honesty" "edge-tts not installed (pip install edge-tts)"
elif python3 - <<'PY'
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
HO_OUT=$WORK/dc-handoff-of
rm -rf "$HO_OUT" $WORK/dc-handoff-hf
if PYTHONPATH="$ROOT" python3 -m tools.handoff.cli openfilm "$HO_FIX" -o "$HO_OUT" >$WORK/dc-ho.out 2>$WORK/dc-ho.err \
  && test -f "$HO_OUT/film.html" \
  && test -f "$HO_OUT/manifest.json" \
  && test -f "$HO_OUT/timeline.edl" \
  && test -f "$HO_OUT/rebuild_shots.sh" \
  && grep -q 'id="a"' "$HO_OUT/film.html" \
  && grep -q 'id="b"' "$HO_OUT/film.html"; then
  ok "openfilm handoff writes multi-shot film.html+edl+manifest"
else
  bad "openfilm handoff: $(cat $WORK/dc-ho.err $WORK/dc-ho.out)"
fi

SHOTS=$(python3 -c "import json;print(json.load(open('$HO_OUT/manifest.json'))['shotCount'])")
if [ "$SHOTS" = "2" ]; then
  ok "openfilm handoff shotCount=2"
else
  bad "openfilm handoff shotCount=$SHOTS"
fi

if "${CLI[@]}" handoff --project "$HO_FIX" --target openfilm -o $WORK/dc-handoff-cli >$WORK/dc-ho2.out 2>$WORK/dc-ho2.err \
  && test -f $WORK/dc-handoff-cli/film.html; then
  ok "cli handoff openfilm"
else
  bad "cli handoff: $(cat $WORK/dc-ho2.err $WORK/dc-ho2.out)"
fi

# HyperFrames export (skip live lint in CI-ish path — network already proven separately)
if PYTHONPATH="$ROOT" python3 -m tools.handoff.cli hyperframes "$HO_FIX" -o $WORK/dc-handoff-hf >$WORK/dc-hf.out 2>$WORK/dc-hf.err \
  && test -f $WORK/dc-handoff-hf/index.html \
  && test -f $WORK/dc-handoff-hf/lemo-manifest.json \
  && test -f $WORK/dc-handoff-hf/hyperframes.json \
  && grep -q 'data-composition-id="main"' $WORK/dc-handoff-hf/index.html; then
  ok "hyperframes export writes composition + lemo-manifest"
else
  bad "hyperframes export: $(cat $WORK/dc-hf.err $WORK/dc-hf.out)"
fi

if grep -q 'needsUser' $WORK/dc-handoff-hf/lemo-manifest.json; then
  ok "hyperframes manifest marks needsUser blockers"
else
  bad "hyperframes missing needsUser"
fi

# --- matrix tracker (18-film full factorial; no remux) ---
if "${CLI[@]}" matrix >$WORK/dc-matrix.out 2>$WORK/dc-matrix.err \
  && grep -q 'filled 18/18' $WORK/dc-matrix.out \
  && grep -q 'M01' $WORK/dc-matrix.out \
  && grep -q 'M08' $WORK/dc-matrix.out \
  && grep -q 'M12' $WORK/dc-matrix.out \
  && grep -q 'M18' $WORK/dc-matrix.out \
  && grep -q 'delivery-pass' $WORK/dc-matrix.out; then
  ok "matrix lists 18/18 with delivery-pass"
else
  bad "matrix list: $(cat $WORK/dc-matrix.err $WORK/dc-matrix.out)"
fi

# M01 + flash natives promoted to delivery-pass. The rendered films live under the films
# root (WORDFILM_FILMS, <repo>/films or /workspace/films); without it only the status is checked.
for mid in M01 M02 M06 M10; do
  if "${CLI[@]}" matrix --id "$mid" --json >$WORK/dc-matrix-$mid.json 2>$WORK/dc-matrix-$mid.err \
    && python3 -c "import json;d=json.load(open('$WORK/dc-matrix-$mid.json')); assert d['id']=='$mid' and d['status']=='delivery-pass'"; then
    ok "matrix --id $mid --json delivery-pass"
  else
    bad "matrix $mid: $(cat $WORK/dc-matrix-$mid.err $WORK/dc-matrix-$mid.json)"
  fi
  if ! have_films; then
    skip "matrix $mid mp4 on disk" "films root $FILMS not present (set WORDFILM_FILMS)"
  elif python3 -c "import json;d=json.load(open('$WORK/dc-matrix-$mid.json')); assert d['mp4Exists'] and d['evidenceExists'], d" 2>$WORK/dc-matrix-$mid.ev; then
    ok "matrix $mid mp4 + evidence on disk"
  else
    bad "matrix $mid mp4/evidence missing under $FILMS: $(tail -1 $WORK/dc-matrix-$mid.ev)"
  fi
done

# Docs: budget + experts
if test -f "$CTL/docs/BUDGET.md" && test -f "$CTL/docs/EXPERTS.md"; then
  ok "BUDGET.md + EXPERTS.md present"
else
  bad "budget/experts docs missing"
fi

# --- Premiere xmeml handoff ---
rm -rf $WORK/dc-handoff-prem
if PYTHONPATH="$ROOT" python3 -m tools.handoff.cli premiere "$HO_FIX" -o $WORK/dc-handoff-prem >$WORK/dc-prem.out 2>$WORK/dc-prem.err \
  && test -f $WORK/dc-handoff-prem/premiere.xml \
  && test -f $WORK/dc-handoff-prem/manifest.json \
  && test -f $WORK/dc-handoff-prem/assets/master.mp4 \
  && grep -q 'xmeml version="5"' $WORK/dc-handoff-prem/premiere.xml \
  && grep -q 'clipitem id="clip-1"' $WORK/dc-handoff-prem/premiere.xml \
  && grep -q 'clipitem id="clip-2"' $WORK/dc-handoff-prem/premiere.xml; then
  ok "premiere handoff writes xmeml v5 + 2 clipitems"
else
  bad "premiere handoff: $(cat $WORK/dc-prem.err $WORK/dc-prem.out)"
fi

if test -f "$HO_OUT/premiere.xml" || PYTHONPATH="$ROOT" python3 -m tools.handoff.cli openfilm "$HO_FIX" -o $WORK/dc-of-xml >/dev/null 2>&1; then
  # openfilm package must embed premiere.xml (re-export if earlier HO_OUT predates change)
  if test -f "$HO_OUT/premiere.xml"; then OFXML="$HO_OUT/premiere.xml"; else OFXML="$WORK/dc-of-xml/premiere.xml"; fi
  if grep -q 'xmeml' "$OFXML"; then
    ok "openfilm package includes premiere.xml"
  else
    bad "openfilm missing premiere.xml content"
  fi
else
  bad "openfilm premiere.xml missing"
fi

if "${CLI[@]}" handoff --project "$HO_FIX" --target premiere -o $WORK/dc-prem-cli --no-budget >$WORK/dc-prem2.out 2>$WORK/dc-prem2.err \
  && test -f $WORK/dc-prem-cli/premiere.xml; then
  ok "cli handoff premiere"
else
  bad "cli handoff premiere: $(cat $WORK/dc-prem2.err $WORK/dc-prem2.out)"
fi

# --- budget ledger ---
BUD_LEDGER=$WORK/dc-budget-ledger.jsonl
rm -f "$BUD_LEDGER"
if "${CLI[@]}" budget append --ledger "$BUD_LEDGER" --item "test-local" --usd 0 --kind local --path-label controller --duration 1.5 >$WORK/dc-bud.out 2>$WORK/dc-bud.err \
  && "${CLI[@]}" budget append --ledger "$BUD_LEDGER" --item "test-paid" --usd 0.12 --kind manual --tokens-in 10 --tokens-out 2 --path-label flash >$WORK/dc-bud2.out 2>$WORK/dc-bud2.err \
  && "${CLI[@]}" budget summary --ledger "$BUD_LEDGER" --json >$WORK/dc-bud-sum.json 2>$WORK/dc-bud-sum.err \
  && python3 -c "import json;d=json.load(open('$WORK/dc-bud-sum.json')); assert d['entries']==2 and abs(d['totalUsd']-0.12)<1e-9"; then
  ok "budget append + summary"
else
  bad "budget: $(cat $WORK/dc-bud.err $WORK/dc-bud2.err $WORK/dc-bud-sum.err $WORK/dc-bud.out $WORK/dc-bud-sum.json 2>/dev/null)"
fi

if "${CLI[@]}" budget append --ledger "$BUD_LEDGER" --item "test-cny" --usd 0.05 --cny 0.5 --kind opencode-session --session-id ses_test --path-label flash >$WORK/dc-bud3.out 2>$WORK/dc-bud3.err \
  && "${CLI[@]}" budget summary --ledger "$BUD_LEDGER" --json >$WORK/dc-bud-sum2.json 2>$WORK/dc-bud-sum2.err \
  && python3 -c "import json;d=json.load(open('$WORK/dc-bud-sum2.json')); assert abs(d['totalCny']-0.5)<1e-9, d"; then
  ok "budget --cny tracked in totalCny"
else
  bad "budget: $(cat $WORK/dc-bud.err $WORK/dc-bud2.err $WORK/dc-bud-sum.err $WORK/dc-bud.out $WORK/dc-bud-sum.json 2>/dev/null)"
fi

if test -f "$CTL/fixtures/budget-ledger.jsonl" && test -f "$CTL/budget.py" \
  && grep -q 'budget-ledger.jsonl' "$CTL/docs/BUDGET.md"; then
  ok "budget.py + ledger fixture + BUDGET.md wire-up"
else
  bad "budget automation files missing"
fi

if "${CLI[@]}" budget import-opencode --ledger $WORK/dc-budget-import.jsonl --min-usd 0.01 --dry-run --json >$WORK/dc-bud-imp.json 2>$WORK/dc-bud-imp.err \
  && python3 -c "import json;d=json.load(open('$WORK/dc-bud-imp.json')); assert d.get('ok') is True and d.get('dryRun') is True"; then
  ok "budget import-opencode --dry-run"
else
  # DB may be absent off-box; still accept honest failure shape
  if grep -q 'opencode db missing' $WORK/dc-bud-imp.json $WORK/dc-bud-imp.err 2>/dev/null; then
    ok "budget import-opencode honest missing-db"
  else
    bad "budget import: $(cat $WORK/dc-bud-imp.err $WORK/dc-bud-imp.json)"
  fi
fi

if "${CLI[@]}" matrix --filled >$WORK/dc-matrix-f.out 2>$WORK/dc-matrix-f.err \
  && grep -q 'M05' $WORK/dc-matrix-f.out \
  && ! grep -E '^M0[0-9].* empty ' $WORK/dc-matrix-f.out \
  && ! grep -E '^M1[0-8].* empty ' $WORK/dc-matrix-f.out; then
  ok "matrix --filled hides empty"
else
  bad "matrix --filled: $(cat $WORK/dc-matrix-f.err $WORK/dc-matrix-f.out)"
fi

if test -f "$CTL/docs/MATRIX-18.md" && test -f "$CTL/fixtures/matrix-18.json"; then
  ok "MATRIX-18.md + matrix-18.json present"
else
  bad "matrix docs/fixture missing"
fi

# Cross-style x flash cells (M13-M18): every cell has a real mp4 + evidence, flash path
"${CLI[@]}" matrix --path flash >$WORK/dc-matrix-flash.out 2>$WORK/dc-matrix-flash.err || true
if python3 -c "
import json
d=json.load(open('$CTL/fixtures/matrix-18.json'))
cells=d['cells']; assert len(cells)==18
keys={(c['topic'],c['style'],c['path']) for c in cells}; assert len(keys)==18
new=[c for c in cells if c['id'] in ('M13','M14','M15','M16','M17','M18')]
assert len(new)==6 and all(c['path']=='flash' and c['role']=='cross' for c in new)
assert all(c['status']!='empty' and c.get('mp4') and c.get('evidence') for c in new)
st={c['id']:c['status'] for c in new}
assert st['M14']=='muxed' and st['M16']=='muxed', st  # not delivered until re-rendered with trimmed copy
" && grep -q 'M13' $WORK/dc-matrix-flash.out && ! grep -q ' controller ' $WORK/dc-matrix-flash.out; then
  ok "matrix-18 full factorial; M13-M18 cross x flash honest status + --path flash"
else
  bad "matrix-18 cross x flash: $(cat $WORK/dc-matrix-flash.err)"
fi
if ! have_films; then
  skip "matrix-18 M13-M18 mp4 + evidence on disk" "films root $FILMS not present (set WORDFILM_FILMS)"
elif PYTHONPATH="$CTL" python3 -c "
import json
from common import film_path
d=json.load(open('$CTL/fixtures/matrix-18.json'))
new=[c for c in d['cells'] if c['id'] in ('M13','M14','M15','M16','M17','M18')]
assert all(film_path(c['mp4']).is_file() and film_path(c['evidence']).is_file() for c in new)
assert all(c['status']!='delivery-pass' or json.load(open(film_path(c['evidence']))).get('deliveryAllowed') for c in new)
" 2>$WORK/dc-matrix-flash.ev; then
  ok "matrix-18 M13-M18 mp4 + evidence on disk; delivery-pass cells allow delivery"
else
  bad "matrix-18 M13-M18 evidence under $FILMS: $(tail -1 $WORK/dc-matrix-flash.ev)"
fi

# Loader rejects a non-factorial tracker
python3 -c "
import json;d=json.load(open('$CTL/fixtures/matrix-18.json'));d['cells']=d['cells'][:12];json.dump(d,open('$WORK/dc-matrix-bad.json','w'))"
if PYTHONPATH="$CTL" python3 -c "
import matrix
try:
    matrix.load_matrix('$WORK/dc-matrix-bad.json')
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
DT=$WORK/dc-dialogue
rm -rf "$DT"; mkdir -p "$DT"
if "${CLI[@]}" dialogue-check --project "$DLG" >$WORK/dc-dlg.out 2>&1 && grep -q 'PASS' $WORK/dc-dlg.out \
  && python3 -c "import json;d=json.load(open('$DLG/evidence/dialogue-check.json'));assert d['status']=='PASS' and d['duration']['totalChars']==92"; then
  ok "dialogue-check PASS fixture (92字 vs 22s ±15%)"
else
  bad "dialogue-check pass fixture: $(cat $WORK/dc-dlg.out)"
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
mk_case toolong "L[:]=L+[dict(x, id=x['id']+'b') for x in L[1:-1]]+[L[-1]]"
mk_case jinju "L[5]['text']='让我们一起记住这个流动性陷阱。'"
mk_case nopayoff "L[4]['function']='evidence'"
mk_case advice "L[5]['text']='别急着抄底，先看懂流动性陷阱。'"
dlg_ok=1
for c in nofn long latehook toolong jinju nopayoff; do
  if "${CLI[@]}" dialogue-check --project "$DT/$c" >"$DT/$c.out" 2>&1; then dlg_ok=0; echo "  case $c unexpectedly PASS"; fi
done
grep -q "function=None" "$DT/nofn.out" || dlg_ok=0
grep -q "> 35字" "$DT/long.out" || dlg_ok=0
grep -q "first 3 VO beats" "$DT/latehook.out" || dlg_ok=0
grep -q "over ceiling" "$DT/toolong.out" || dlg_ok=0
# target is a ceiling: a short script is NOT padded / failed for being short
"${CLI[@]}" dialogue-check --project "$DT/short" >"$DT/short.out" 2>&1 || dlg_ok=0
grep -q "over ceiling\|outside" "$DT/short.out" && dlg_ok=0
grep -q "金句升华" "$DT/jinju.out" || dlg_ok=0
grep -q "coverage" "$DT/nopayoff.out" || dlg_ok=0
if [ "$dlg_ok" = 1 ]; then
  ok "dialogue-check FAILs: missing function / >35字 / late hook / over ceiling (+15%) / 金句 / coverage; short script PASSes (ceiling only)"
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
DLL=$WORK/dc-dialogue-loop; rm -rf "$DLL"; mkdir -p "$DLL"
mkloop() { rm -rf "$DLL/$1"; mkdir -p "$DLL/$1"; cp -r "$DLG/content" "$DLL/$1/"; rm -rf "$DLL/$1/evidence"; }
LEDGER_N0=$( [ -f "$WORDFILM_BUDGET_LEDGER" ] && wc -l <"$WORDFILM_BUDGET_LEDGER" || echo 0 )
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
"${CLI[@]}" dialogue-loop --project "$DLL/n" --mock "$CTL/fixtures/dialogue-loop/mock-never-pass.json" >"$DLL/n.out" 2>&1 && rc=0 || rc=$?
if [ "$rc" = 1 ] && grep -q "NEEDS_HUMAN" "$DLL/n.out" && PYTHONPATH="$CTL" python3 -c "
import json,dialogue_loop as D, quality as Q
from pathlib import Path
P=Path('$DLL/n'); s=json.load(open(P/'evidence/dialogue-loop.json')); assert s['status']=='NEEDS_HUMAN' and s['rounds']==2 and s['maxRounds']==2 and s['needsHuman'], s
assert not D.gate_status(P)[0]
c=Q._dialogue_loop_check(P); assert c['status']=='FAIL' and c['required'], c
" && ! "${CLI[@]}" tts --project "$DLL/n" --provider edge --out "$DLL/n/voices" >/dev/null 2>&1 && [ ! -e "$DLL/n/voices" ]; then
  ok "dialogue-loop never passes → NEEDS_HUMAN after default 2 rounds (exit 1), quality dialogue_loop FAIL, TTS still blocked"
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
LEDGER_N1=$( [ -f "$WORDFILM_BUDGET_LEDGER" ] && wc -l <"$WORDFILM_BUDGET_LEDGER" || echo 0 )
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
if env -u STEP_API_KEY python3 "$CTL/tests/stepaudio_mock.py" >$WORK/dc_stepaudio_mock.log 2>&1; then
  ok "stepaudio: free gen-preview only (paid /audio/speech + non-free models refused), pitch retakes, session mode = 1 request split by ASR timings, 402 stops, music bed cut/fade/RMS + cache"
else
  bad "stepaudio mock (see $WORK/dc_stepaudio_mock.log)"
fi

# elevenlabs provider: local mock API, fake key, no network
if env -u ELEVEN_API_KEY -u ELEVENLABS_API_KEY python3 "$CTL/tests/elevenlabs_mock.py" >$WORK/dc_elevenlabs_mock.log 2>&1; then
  ok "elevenlabs: needs-key without ELEVENLABS_API_KEY; mock TTS writes wav+dur; xi-api-key + multilingual_v2; listed in --list"
else
  bad "elevenlabs mock (see $WORK/dc_elevenlabs_mock.log)"
fi

# elevenlabs-dialogue: local mock Text-to-Dialogue API, fake key, no network
if env -u ELEVEN_API_KEY -u ELEVENLABS_API_KEY python3 "$CTL/tests/elevenlabs_dialogue_mock.py" >$WORK/dc_elevenlabs_dialogue_mock.log 2>&1; then
  ok "elevenlabs-dialogue: needs-key; chunk ≤2000/≤10 voices; mock writes dialogue.wav+manifest; v4→v3 fallback; listed in --list"
else
  bad "elevenlabs-dialogue mock (see $WORK/dc_elevenlabs_dialogue_mock.log)"
fi

# elevenlabs-dialogue guest voice by content type (Tex host; market/concept/personal/english), mock API
if env -u ELEVEN_API_KEY -u ELEVENLABS_API_KEY -u ELEVENLABS_VOICE_HOST -u ELEVENLABS_VOICE_GUEST -u LEMO_TTS_ELEVENLABS_CONTENT_TYPE \
    python3 "$CTL/tests/elevenlabs_content_type_mock.py" >$WORK/dc_elevenlabs_content_type_mock.log 2>&1; then
  ok "elevenlabs-dialogue: content_type → guest (market→Linda, concept→Ladaisy, personal→Shusita, english→Joan; default Linda; VOICE_GUEST overrides; router/run_tts/plan.json)"
else
  bad "elevenlabs content-type mock (see $WORK/dc_elevenlabs_content_type_mock.log)"
fi

# visual-check: synthetic film with known defects (OCR/ffmpeg local), semantic layer mocked, quality gate, speaker metric
env -u OPENROUTER_API_KEY python3 "$CTL/tests/visual_check_mock.py" >"$WORK/visual_check_mock.log" 2>&1 && rc=0 || rc=$?
if [ "$rc" = 0 ]; then
  ok "visual-check: wrong caption chars / corrupt frame / clipped text / subtitle≠VO → high; no false positive on correct text; :free-only + billing-delta stop; hook-subs rework; quality gate; speaker metric"
elif [ "$rc" = 77 ]; then
  skip "visual-check mock" "$(grep '^SKIP:' "$WORK/visual_check_mock.log" | head -1 | sed 's/^SKIP: //')"
else
  bad "visual-check mock: $(tail -20 "$WORK/visual_check_mock.log")"
fi

# visual-check geometry follows the film size: 16:9 result unchanged, 9:16 uses portrait regions
python3 "$CTL/tests/visual_check_aspect.py" >"$WORK/visual_check_aspect.log" 2>&1 && rc=0 || rc=$?
if [ "$rc" = 0 ]; then
  ok "visual-check aspect: 16:9 issues unchanged; 9:16 registry scaled from engine.lock.json, no false clip, 90x160 luma scan, 360x640 sheet tiles"
elif [ "$rc" = 77 ]; then
  skip "visual-check aspect" "$(grep '^SKIP:' "$WORK/visual_check_aspect.log" | head -1 | sed 's/^SKIP: //')"
else
  bad "visual-check aspect: $(grep -v '^ok ' "$WORK/visual_check_aspect.log" | tail -20)"
fi

# TTS / speaker env names: WORDFILM_* first, the upstream LEMO_* name as fallback (read at call time)
# spk-*: stand-in interpreters that "import resemblyzer" fine (exit 0), so _spk_python() picks them
for n in spk-legacy spk-new; do printf '#!/bin/sh\nexit 0\n' >"$WORK/$n"; chmod +x "$WORK/$n"; done
if (cd "$ROOT" && env -u WORDFILM_TTS_PYTHON -u LEMO_TTS_PYTHON -u WORDFILM_TTS_QWEN3_BASE -u LEMO_TTS_QWEN3_BASE \
  -u WORDFILM_SPK_PYTHON -u LEMO_SPK_PYTHON -u WORDFILM_OPENCODE_DB -u LEMO_OPENCODE_DB python3 -c "
import os, sys
sys.path.insert(0, 'core/tts'); sys.path.insert(0, 'tools/deepseek-controller')
from providers import env, runtime
E = os.environ
assert env('TTS_X_UNSET', 'd') == 'd'
E['LEMO_TTS_QWEN3_BASE'] = 'http://legacy/v1'
assert env('TTS_QWEN3_BASE') == 'http://legacy/v1'
assert runtime.probe_qwen3().state == 'ready', runtime.probe_qwen3()
E['WORDFILM_TTS_QWEN3_BASE'] = 'http://new/v1'
assert env('TTS_QWEN3_BASE') == 'http://new/v1' and 'http://new/v1' in runtime.probe_qwen3().detail, runtime.probe_qwen3()
E['WORDFILM_TTS_QWEN3_BASE'] = ''   # empty = unset
assert env('TTS_QWEN3_BASE') == 'http://legacy/v1'
E['LEMO_TTS_PYTHON'] = '/bin/sh'
assert runtime.resolve_voice_python() == '/bin/sh'
E['WORDFILM_TTS_PYTHON'] = sys.executable
assert runtime.resolve_voice_python() == sys.executable
import budget, importlib
E['LEMO_OPENCODE_DB'] = '/legacy.db'; importlib.reload(budget); assert str(budget.DEFAULT_OPENCODE_DB) == '/legacy.db'
E['WORDFILM_OPENCODE_DB'] = '/new.db'; importlib.reload(budget); assert str(budget.DEFAULT_OPENCODE_DB) == '/new.db'
import quality
E['LEMO_SPK_PYTHON'] = '$WORK/spk-legacy'
assert quality._spk_python() == '$WORK/spk-legacy', quality._spk_python()
E['WORDFILM_SPK_PYTHON'] = '$WORK/spk-new'
assert quality._spk_python() == '$WORK/spk-new', quality._spk_python()
" >"$WORK/env-names.log" 2>&1); then
  ok "env names: WORDFILM_TTS_* / WORDFILM_SPK_PYTHON / WORDFILM_OPENCODE_DB win, LEMO_* still honoured, empty = unset"
else
  bad "env names: $(tail -5 "$WORK/env-names.log")"
fi

# env names from the upstream merge (pacing / TP / ElevenLabs / StepAudio / quota ledger): same rule
if (cd "$ROOT" && env -u WORDFILM_PACING -u LEMO_PACING -u WORDFILM_TP_MAX_DBTP -u LEMO_TP_MAX_DBTP \
  -u WORDFILM_TTS_ELEVENLABS_ZH_NUMBERS -u LEMO_TTS_ELEVENLABS_ZH_NUMBERS \
  -u WORDFILM_TTS_ELEVENLABS_JOIN_LETTERS -u LEMO_TTS_ELEVENLABS_JOIN_LETTERS \
  -u WORDFILM_TTS_ELEVENLABS_CONTENT_TYPE -u LEMO_TTS_ELEVENLABS_CONTENT_TYPE \
  -u WORDFILM_TTS_STEPAUDIO_SPEED -u LEMO_TTS_STEPAUDIO_SPEED -u WORDFILM_QUOTA_LEDGER -u DC_QUOTA_LEDGER \
  -u WORDFILM_CACHE python3 -c "
import os, sys
from pathlib import Path
sys.path.insert(0, 'core/tts'); sys.path.insert(0, 'tools/deepseek-controller')
E = os.environ
import pacing_profile as pp
plan = {'content_type': 'market'}
assert pp.resolve(None, None, plan) == ('fast', 'content_type=market')
E['LEMO_PACING'] = 'calm'
assert pp.resolve(None, None, plan) == ('calm', 'env LEMO_PACING')
E['WORDFILM_PACING'] = 'standard'
assert pp.resolve(None, None, plan) == ('standard', 'env WORDFILM_PACING')
E['WORDFILM_PACING'] = ''   # empty = unset
assert pp.resolve(None, None, plan) == ('calm', 'env LEMO_PACING')
import quality
p = Path('$WORK/tp-film'); p.mkdir(exist_ok=True)
assert quality._tp_max(p) == -1.0
E['LEMO_TP_MAX_DBTP'] = '-1.5'; assert quality._tp_max(p) == -1.5
E['WORDFILM_TP_MAX_DBTP'] = '-3'; assert quality._tp_max(p) == -3.0
E['WORDFILM_TP_MAX_DBTP'] = ''; assert quality._tp_max(p) == -1.5
from providers import env, elevenlabs as EL, elevenlabs_dialogue as ED
L = {'say': '增长 97.5% 的 E-S'}
assert EL.spoken_text(L) == '增长 百分之九十七点五 的 ES', EL.spoken_text(L)
E['LEMO_TTS_ELEVENLABS_ZH_NUMBERS'] = '0'; assert EL.spoken_text(L) == L['say']
E['WORDFILM_TTS_ELEVENLABS_ZH_NUMBERS'] = '1'; E['LEMO_TTS_ELEVENLABS_JOIN_LETTERS'] = '0'
assert EL.spoken_text(L) == '增长 百分之九十七点五 的 E-S', EL.spoken_text(L)
E['WORDFILM_TTS_ELEVENLABS_JOIN_LETTERS'] = '1'; assert EL.spoken_text(L).endswith(' ES')
E['LEMO_TTS_ELEVENLABS_CONTENT_TYPE'] = 'concept'; assert ED.content_type_from_env() == 'concept'
E['WORDFILM_TTS_ELEVENLABS_CONTENT_TYPE'] = 'personal'; assert ED.content_type_from_env() == 'personal'
E['WORDFILM_TTS_ELEVENLABS_CONTENT_TYPE'] = ''; assert ED.content_type_from_env() == 'concept'
E['LEMO_TTS_STEPAUDIO_SPEED'] = '0.9'; assert env('TTS_STEPAUDIO_SPEED') == '0.9'
E['WORDFILM_TTS_STEPAUDIO_SPEED'] = '1.1'; assert env('TTS_STEPAUDIO_SPEED') == '1.1'
import llm_free as LF
assert LF.quota_ledger_path() == Path.home() / '.cache' / 'wordfilm' / 'tokenharbor-usage.jsonl'
E['WORDFILM_CACHE'] = '$WORK/cache'
assert LF.quota_ledger_path() == Path('$WORK/cache/tokenharbor-usage.jsonl')
E['DC_QUOTA_LEDGER'] = '$WORK/dc-quota.jsonl'; assert LF.quota_ledger_path() == Path('$WORK/dc-quota.jsonl')
E['WORDFILM_QUOTA_LEDGER'] = '$WORK/wf-quota.jsonl'
assert LF.quota_ledger_path() == Path('$WORK/wf-quota.jsonl')
assert LF.quota_header_path() == Path('$WORK/wf-quota.header.json')
" >"$WORK/env-names-upstream.log" 2>&1); then
  ok "upstream env names: WORDFILM_PACING / _TP_MAX_DBTP / _TTS_ELEVENLABS_{ZH_NUMBERS,JOIN_LETTERS,CONTENT_TYPE} / _TTS_STEPAUDIO_SPEED / _QUOTA_LEDGER win, LEMO_* (DC_QUOTA_LEDGER) still honoured, empty = unset"
else
  bad "upstream env names: $(tail -5 "$WORK/env-names-upstream.log")"
fi
# mux.sh true-peak env: WORDFILM_TP_* > LEMO_TP_* > default (a bad value names the one that was read)
if have_ffmpeg; then
  ffmpeg -v error -y -f lavfi -i color=c=gray:s=64x36:d=0.5:r=24 -pix_fmt yuv420p "$WORK/tp-v.mp4" \
    && ffmpeg -v error -y -f lavfi -i sine=f=440:d=0.5 -ar 48000 "$WORK/tp-a.wav"
  MUXT() { env -u WORDFILM_TP_CEIL -u LEMO_TP_CEIL -u WORDFILM_TP_RETRY_ABOVE -u LEMO_TP_RETRY_ABOVE -u WORDFILM_TP_LIMIT -u LEMO_TP_LIMIT \
    "$@" sh "$ROOT/core/render/mux.sh" "$WORK/tp-v.mp4" "$WORK/tp-a.wav" "$WORK/tp-o.mp4" 24 0 >"$WORK/tp.out" 2>&1; }
  if ! MUXT WORDFILM_TP_CEIL=wfbad && grep -q "got 'wfbad'" "$WORK/tp.out" \
    && ! MUXT LEMO_TP_CEIL=lemobad && grep -q "got 'lemobad'" "$WORK/tp.out" \
    && ! MUXT WORDFILM_TP_CEIL= LEMO_TP_CEIL=lemobad2 && grep -q "got 'lemobad2'" "$WORK/tp.out" \
    && ! MUXT WORDFILM_TP_RETRY_ABOVE=rbad LEMO_TP_RETRY_ABOVE=-1.0 && grep -q "got 'rbad'" "$WORK/tp.out" \
    && MUXT WORDFILM_TP_CEIL=-3.0 LEMO_TP_CEIL=lemobad && test -s "$WORK/tp-o.mp4" \
    && ! grep -qE '^ *export LEMO_|[^_]LEMO_TTS_ELEVENLABS_MODEL=' "$CTL/templates/finance-term/build_term.sh" \
    && bash -n "$CTL/templates/finance-term/build_term.sh"; then
    ok "mux.sh WORDFILM_TP_CEIL / _RETRY_ABOVE win over LEMO_TP_*, empty = unset; build_term.sh exports WORDFILM_* names"
  else
    bad "mux.sh TP env names: $(tail -3 "$WORK/tp.out")"
  fi
else
  skip "mux.sh TP env names" "ffmpeg/ffprobe not installed"
fi

# free-first LLM chain (TokenHarbor → OpenRouter :free; no OpenCode; no paid without --allow-paid)
if env -u DEEPSEEK_API_KEY python3 "$CTL/tests/llm_free_mock.py" >$WORK/dc_llm_free_mock.log 2>&1; then
  ok "llm_free: TokenHarbor→nemotron:free→flint:free; 429 retry same; quota advances; no paid without --allow-paid; ledger logs model"
else
  bad "llm_free mock (see $WORK/dc_llm_free_mock.log)"
fi

# pacing P0: profile by content_type, ceiling-only duration, no pad, pause trim, speed, report-only gate
if env -u STEP_API_KEY -u LEMO_PACING python3 "$CTL/tests/pacing_mock.py" >$WORK/dc_pacing_mock.log 2>&1; then
  ok "pacing: market→fast / others→standard + overrides; ceiling-only dialogue; no pad + 1.5s outro; pause trim keeps beat; edge rate + stepaudio speed; pad FAIL; pacing gate report-only"
else
  bad "pacing mock (see $WORK/dc_pacing_mock.log)"
fi

# pacing P1: TP limiter, end-card outro, sub-beats + {keyword} frames, rework ≤2 rounds, rhythm, token steps, ElevenLabs speed
if env -u TOKENHARBOR_API_KEY -u OPENROUTER_API_KEY python3 "$CTL/tests/finance_mock.py" >$WORK/dc_finance_mock.log 2>&1; then
  ok "finance mock: 2-round NEEDS_HUMAN cap, compact critic/reviser context, quota-aware routing ($(tail -1 $WORK/dc_finance_mock.log))"
else
  bad "finance mock (see $WORK/dc_finance_mock.log)"
fi
if env -u STEP_API_KEY -u LEMO_PACING -u ELEVENLABS_API_KEY python3 "$CTL/tests/p1_mock.py" >$WORK/dc_p1_mock.log 2>&1; then
  ok "pacing P1: TP≤−1 limiter; end-card outro; sub-beats ≤ maxShot + keyword frames; rework ≤2 rounds (WARN untouched); rhythm dim; per-step tokens; elevenlabs speed"
else
  bad "pacing P1 mock (see $WORK/dc_p1_mock.log)"
fi
if env -u TOKENHARBOR_API_KEY -u OPENROUTER_API_KEY -u STEP_API_KEY -u ELEVENLABS_API_KEY -u DEEPSEEK_API_KEY python3 "$CTL/tests/term_template_mock.py" >$WORK/dc_term_mock.log 2>&1; then
  ok "finance-term template: check-only approval gate, role/cap/say, zh number folding + number gate, spoken units, beatsAuthored, vo_srt, probe_fps, StepAudio reuse/2nd pass, batch_terms ($(tail -1 $WORK/dc_term_mock.log))"
else
  bad "finance-term template mock (see $WORK/dc_term_mock.log)"
fi

# budget ledger: tests write to \$WORDFILM_BUDGET_LEDGER, never the real fixtures ledger
if PYTHONPATH="$CTL" python3 -c "
import budget,os
assert str(budget.ledger_path())==os.path.realpath('$WORDFILM_BUDGET_LEDGER')
del os.environ['WORDFILM_BUDGET_LEDGER']; os.environ['DC_BUDGET_LEDGER']='$WORK/legacy-ledger.jsonl'
assert str(budget.ledger_path())==os.path.realpath('$WORK/legacy-ledger.jsonl')
os.environ['WORDFILM_BUDGET_LEDGER']='$WORK/new-ledger.jsonl'
assert str(budget.ledger_path())==os.path.realpath('$WORK/new-ledger.jsonl')
" && ! grep -q 'fixtures/handoff-mini' "$CTL/fixtures/budget-ledger.jsonl"; then
  ok "budget ledger honors WORDFILM_BUDGET_LEDGER (upstream DC_BUDGET_LEDGER as fallback); no handoff-mini noise in real ledger"
else
  bad "budget ledger env override / noise"
fi

# --- aspect: 16:9 / 9:16 plan → render size (temp copies only; fixtures stay untouched) ---
if "${CLI[@]}" validate "$FIX/plan-caption-news-portrait.json" >/dev/null 2>$WORK/dc-asp-val.err; then
  ok "validate plan-caption-news-portrait.json (aspect 9:16)"
else
  bad "portrait caption plan: $(cat $WORK/dc-asp-val.err)"
fi

if "${CLI[@]}" validate "$FIX/plan-pictogram-motion-portrait.json" >/dev/null 2>$WORK/dc-asp-picto.err; then
  ok "validate plan-pictogram-motion-portrait.json (pictogram-motion has a native 9:16 layout)"
else
  bad "pictogram 9:16 plan should validate: $(cat $WORK/dc-asp-picto.err)"
fi

rm -rf $WORK/dc-scaffold-picto-portrait
if "${CLI[@]}" scaffold "$FIX/plan-pictogram-motion-portrait.json" -o $WORK/dc-scaffold-picto-portrait --lib "$ROOT" --force >$WORK/dc-spp.out 2>$WORK/dc-spp.err \
  && grep -q 'size=1080x1920 aspect=9:16' $WORK/dc-spp.out \
  && python3 -c "
import json;d=json.load(open('$WORK/dc-scaffold-picto-portrait/content/engine.lock.json'))
assert d['style']=='pictogram-motion' and d['aspect']=='9:16' and d['size']=='1080x1920', d" \
  && grep -q 'core/render/video.mjs .* --size 1080x1920' $WORK/dc-scaffold-picto-portrait/PROJECT.md \
  && ! grep -q '1920x1080' $WORK/dc-scaffold-picto-portrait/PROJECT.md; then
  ok "scaffold pictogram 9:16 records size 1080x1920 in engine.lock + PROJECT.md --size"
else
  bad "scaffold pictogram portrait: $(cat $WORK/dc-spp.out $WORK/dc-spp.err)"
fi

# an aspect that no engine lists is still rejected by the manifest check (schema allows 16:9 / 9:16 only, so patch the manifest copy)
if PYTHONPATH="$CTL" python3 - <<'PY'
import json, validate
plan = json.load(open("tools/deepseek-controller/fixtures/plan-pictogram-motion-portrait.json"))
orig = validate.load_manifest
def only_landscape(slug):
    m = dict(orig(slug)); m["aspects"] = ["16:9"]; return m
validate.load_manifest = only_landscape
msgs = validate.validate_plan(plan)
assert any("pictogram-motion does not support '9:16'" in m for m in msgs), msgs
assert validate.validate_plan(dict(plan, aspect="16:9")) == [], "16:9 must stay valid"
PY
then
  ok "a style whose manifest lacks 9:16 still rejects a 9:16 plan with the aspects message"
else
  bad "manifest aspects rejection"
fi

python3 -c "
import json;d=json.load(open('$FIX/plan-caption-news.json'));d['aspect']='4:3';json.dump(d,open('$WORK/dc-asp-43.json','w'),ensure_ascii=False)"
if "${CLI[@]}" validate $WORK/dc-asp-43.json >/dev/null 2>$WORK/dc-asp-43.err; then
  bad "aspect 4:3 should be rejected"
elif grep -q '\$.aspect: must be one of' $WORK/dc-asp-43.err; then
  ok "unknown aspect 4:3 rejected"
else
  bad "aspect 4:3: $(cat $WORK/dc-asp-43.err)"
fi

# a non-string aspect (LLM-written plan) is reported, not a TypeError crash
python3 -c "
import json;d=json.load(open('$FIX/plan-caption-news-portrait.json'));d['aspect']=['9:16'];json.dump(d,open('$WORK/dc-asp-list.json','w'),ensure_ascii=False)"
"${CLI[@]}" validate $WORK/dc-asp-list.json >/dev/null 2>$WORK/dc-asp-list.err && rc=0 || rc=$?
if [ "$rc" = 1 ] && grep -q '\$.aspect: must be one of' $WORK/dc-asp-list.err && ! grep -q Traceback $WORK/dc-asp-list.err; then
  ok "aspect [\"9:16\"] (list) reported as a validation error"
else
  bad "aspect list: rc=$rc $(cat $WORK/dc-asp-list.err)"
fi

if PYTHONPATH="$CTL" python3 -c "
from common import render_size, project_size, size_arg
assert render_size('16:9') == (1920, 1080) and render_size('9:16') == (1080, 1920)
assert render_size({}) == (1920, 1080) and render_size({'aspect': '9:16'}) == (1080, 1920)
assert size_arg((1080, 1920)) == '1080x1920'
assert project_size('$WORK/dc-no-such-project') == (1920, 1080)
"; then
  ok "render_size maps 16:9→1920x1080, 9:16→1080x1920 (default 16:9)"
else
  bad "render_size helper"
fi

rm -rf $WORK/dc-adapt-portrait
if "${CLI[@]}" adapt "$FIX/plan-caption-news-portrait.json" -o $WORK/dc-adapt-portrait >/dev/null \
  && python3 -c "import json;assert json.load(open('$WORK/dc-adapt-portrait/content/plan.json'))['aspect']=='9:16'"; then
  ok "adapt portrait keeps aspect in content/plan.json"
else
  bad "adapt portrait aspect"
fi

rm -rf $WORK/dc-scaffold-caption-portrait
if "${CLI[@]}" scaffold "$FIX/plan-caption-news-portrait.json" -o $WORK/dc-scaffold-caption-portrait --lib "$ROOT" --force >$WORK/dc-scp.out 2>$WORK/dc-scp.err \
  && grep -q 'size=1080x1920 aspect=9:16' $WORK/dc-scp.out \
  && python3 -c "
import json;d=json.load(open('$WORK/dc-scaffold-caption-portrait/content/engine.lock.json'))
assert d['aspect']=='9:16' and d['size']=='1080x1920', d" \
  && grep -q 'core/render/still.mjs .* --size 1080x1920' $WORK/dc-scaffold-caption-portrait/PROJECT.md \
  && grep -q 'core/render/video.mjs .* --size 1080x1920' $WORK/dc-scaffold-caption-portrait/PROJECT.md \
  && grep -q 'core/render/readcheck.mjs .* --size 1080x1920' $WORK/dc-scaffold-caption-portrait/PROJECT.md \
  && grep -q 'core/render/events.mjs .* --size 1080x1920' $WORK/dc-scaffold-caption-portrait/PROJECT.md \
  && ! grep -q '1920x1080' $WORK/dc-scaffold-caption-portrait/PROJECT.md; then
  ok "scaffold caption 9:16 records size 1080x1920 in engine.lock + PROJECT.md --size"
else
  bad "scaffold caption portrait: $(cat $WORK/dc-scp.out $WORK/dc-scp.err)"
fi

if grep -q -- '--size 1920x1080' $WORK/dc-scaffold-caption/PROJECT.md \
  && python3 -c "
import json;d=json.load(open('$WORK/dc-scaffold-caption/content/engine.lock.json'))
assert d['aspect']=='16:9' and d['size']=='1920x1080', d"; then
  ok "scaffold caption default aspect stays 16:9 / 1920x1080"
else
  bad "scaffold caption landscape size missing"
fi

python3 -c "
import json;d=json.load(open('$FIX/plan-swiss-motion.json'));d['aspect']='9:16';json.dump(d,open('$WORK/dc-plan-swiss-portrait.json','w'),ensure_ascii=False)"
rm -rf $WORK/dc-scaffold-swiss-portrait
if "${CLI[@]}" scaffold $WORK/dc-plan-swiss-portrait.json -o $WORK/dc-scaffold-swiss-portrait --lib "$ROOT" --force >$WORK/dc-ssp.out 2>$WORK/dc-ssp.err \
  && python3 -c "
import json
rt=json.load(open('$WORK/dc-scaffold-swiss-portrait/texts_runtime.json'))
assert rt['aspect']=='9:16' and rt['frame']=={'width':1080,'height':1920}, rt.get('frame')
assert rt['entries']
for e in rt['entries']:
    assert 0<=e['x0']<e['x1']<=1080 and 0<=e['y0']<e['y1']<=1920, e
import sys; sys.path.insert(0, '$CTL')
from apply_swiss_texts import POS_BOX_PORTRAIT
for e in rt['entries']:
    assert (e['x0'], e['y0'], e['x1'], e['y1']) == POS_BOX_PORTRAIT[e['pos']], ('not the portrait box', e)
"; then
  ok "apply_swiss_texts on a 9:16 project clamps TEXTS boxes to 1080x1920"
else
  bad "swiss portrait texts_runtime: $(cat $WORK/dc-ssp.out $WORK/dc-ssp.err)"
fi

if PYTHONPATH="$CTL" python3 -c "
from apply_swiss_texts import build_texts_runtime
lines=[{'id':'l1','t':1.0,'text':'Small. Big statement'},{'id':'l6','t':30.0,'text':'Wall line'}]
land=build_texts_runtime(lines, dur=44)
assert land['frame']=={'width':1920,'height':1080}
assert all(e['x1']<=1920 and e['y1']<=1080 for e in land['entries'])
por=build_texts_runtime(lines, dur=44, aspect='9:16')
assert all(e['x1']<=1080 and e['y1']<=1920 for e in por['entries'])
try:
    build_texts_runtime(lines, aspect='4:3'); raise SystemExit(1)
except ValueError:
    pass
"; then
  ok "build_texts_runtime boxes per aspect (16:9 landscape, 9:16 portrait)"
else
  bad "build_texts_runtime aspect"
fi

if PYTHONPATH="$CTL" python3 -c "
import subprocess, quality
seen = {}
class P:
    returncode = 0; stdout = 'ok'; stderr = ''
def fake(cmd, **kw):
    seen['cmd'] = cmd; return P()
quality.subprocess.run = fake
quality.run_readcheck(__import__('pathlib').Path('$WORK/dc-scaffold-caption-portrait'), style='caption-news')
cmd = seen['cmd']
assert cmd[-2:] == ['--size', '1080x1920'], cmd
"; then
  ok "quality readcheck passes --size from the project aspect"
else
  bad "quality readcheck --size"
fi

# handoff: frame size from --size flag or ffprobe of a portrait master
rm -rf $WORK/dc-handoff-portrait
if PYTHONPATH="$ROOT" python3 -m tools.handoff.cli premiere "$HO_FIX" -o $WORK/dc-handoff-portrait --size 1080x1920 --json >$WORK/dc-hop.json 2>$WORK/dc-hop.err \
  && python3 -c "
import json;d=json.load(open('$WORK/dc-hop.json'))
assert (d['width'],d['height'],d['sizeSource'])==(1080,1920,'flag'), d" \
  && test "$(grep -c '<width>1080</width>' $WORK/dc-handoff-portrait/premiere.xml)" = 2 \
  && test "$(grep -c '<height>1920</height>' $WORK/dc-handoff-portrait/premiere.xml)" = 2; then
  ok "handoff premiere --size 1080x1920 writes portrait xmeml (source=flag)"
else
  bad "handoff premiere portrait: $(cat $WORK/dc-hop.err $WORK/dc-hop.json)"
fi

if PYTHONPATH="$ROOT" python3 -m tools.handoff.cli premiere "$HO_FIX" -o $WORK/dc-handoff-odd --size 1081x1920 >/dev/null 2>$WORK/dc-hoodd.err; then
  bad "handoff --size 1081x1920 should be rejected"
elif grep -q 'even' $WORK/dc-hoodd.err; then
  ok "handoff rejects odd --size"
else
  bad "handoff odd size: $(cat $WORK/dc-hoodd.err)"
fi

if command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; then
  rm -rf $WORK/dc-portrait-film && mkdir -p $WORK/dc-portrait-film/out
  if ffmpeg -y -hide_banner -loglevel error -f lavfi -i color=c=black:s=1080x1920:r=30:d=1 \
       -c:v libx264 -preset ultrafast -pix_fmt yuv420p $WORK/dc-portrait-film/out/final.mp4 \
    && PYTHONPATH="$ROOT" python3 -m tools.handoff.cli both $WORK/dc-portrait-film --with-premiere --json >$WORK/dc-hob.json 2>$WORK/dc-hob.err \
    && python3 -c "
import json;d=json.load(open('$WORK/dc-hob.json'))
for k in ('openfilm','hyperframes','premiere'):
    assert (d[k]['width'],d[k]['height'],d[k]['sizeSource'])==(1080,1920,'probe'), (k,d[k])
assert d['premiere']['fps']==30 and d['premiere']['fpsSource']=='probe'" \
    && grep -q 'data-width="1080"' $WORK/dc-portrait-film/hyperframes-handoff/index.html \
    && grep -q 'width:1080px;height:1920px' $WORK/dc-portrait-film/openfilm-handoff/film.html \
    && ! grep -q '1920px;height:1080px\|width=1920' $WORK/dc-portrait-film/openfilm-handoff/film.html; then
    ok "handoff both: ffprobe of a 1080x1920 master drives all exports"
  else
    bad "handoff probe portrait: $(cat $WORK/dc-hob.err)"
  fi
else
  skip "handoff ffprobe portrait" "ffmpeg/ffprobe not installed"
fi

# release.py: a film uploaded to the fork is recorded in tools/films.json (scratch copy) so the
# gallery links it there; films on the default (upstream) repo are not listed
cp "$ROOT/tools/films.json" "$WORK/films.json"
if python3 -c "
import json, sys; sys.path.insert(0, '$ROOT/tools'); import release
release.FILM_HOSTS = '$WORK/films.json'
release.record_film_host('swiss-motion', 'riversxiao/wordfilm')
release.record_film_host('swiss-motion', 'riversxiao/wordfilm')
release.record_film_host('caption-news', 'lemomo-ai/lemo-opuscar')
d = json.load(open('$WORK/films.json'))
assert d['default'] == 'lemomo-ai/lemo-opuscar', d
assert d['films'] == {'swiss-motion': 'riversxiao/wordfilm'}, d
assert json.load(open('$ROOT/tools/films.json'))['films'] == {}, 'touched the tracked films.json'
" >/dev/null; then
  ok "release.py records fork-hosted films in tools/films.json (upstream films stay on the default)"
else
  bad "release.py record_film_host"
fi

# release.py pages: GitHub Pages on/off and build type, through a fake gh (no network), and pages.yml
# runs it before the build so a fork without Pages fails first with what an admin has to switch on.
FGH="$WORK/fake-gh"; rm -rf "$FGH"; mkdir -p "$FGH"
cat >"$FGH/gh" <<'SH'
#!/bin/sh
# fake gh: `gh api repos/<repo>/pages` answers by $FAKE_PAGES (workflow|legacy|404|403)
[ "$1" = api ] || { echo "fake gh: unexpected $*" >&2; exit 2; }
case "$FAKE_PAGES" in
  workflow) echo '{"html_url":"https://example.github.io/x/","build_type":"workflow","source":{"branch":"main","path":"/"}}' ;;
  legacy) echo '{"html_url":"https://example.github.io/x/","build_type":"legacy","source":{"branch":"gh-pages","path":"/"}}' ;;
  404) echo '{"message":"Not Found"}'; echo 'gh: Not Found (HTTP 404)' >&2; exit 1 ;;
  403) echo '{"message":"Resource not accessible by integration"}'; echo 'gh: Resource not accessible by integration (HTTP 403)' >&2; exit 1 ;;
esac
SH
chmod +x "$FGH/gh"
pg() { PATH="$FGH:$PATH" FAKE_PAGES="$1" python3 "$ROOT/tools/release.py" pages ${2:-} >"$FGH/$1.out" 2>&1; }
pages_ok=1
pg workflow && grep -q '✓ GitHub Pages is on for riversxiao/wordfilm, deployed by GitHub Actions' "$FGH/workflow.out" || { pages_ok=0; echo "  workflow: $(cat "$FGH/workflow.out")"; }
! pg legacy && grep -q 'builds from the branch gh-pages:/' "$FGH/legacy.out" && grep -q 'Source to "GitHub Actions"' "$FGH/legacy.out" || { pages_ok=0; echo "  legacy: $(cat "$FGH/legacy.out")"; }
! pg 404 && grep -q 'GitHub Pages is not enabled for riversxiao/wordfilm' "$FGH/404.out" \
  && grep -q 'https://github.com/riversxiao/wordfilm/settings/pages' "$FGH/404.out" \
  && grep -q 'gh api -X POST repos/riversxiao/wordfilm/pages -f build_type=workflow' "$FGH/404.out" \
  && grep -q 'https://riversxiao.github.io/wordfilm/' "$FGH/404.out" || { pages_ok=0; echo "  404: $(cat "$FGH/404.out")"; }
! pg 403 Some/Repo && grep -q 'cannot tell whether GitHub Pages is on for Some/Repo (403' "$FGH/403.out" \
  && grep -q 'https://some.github.io/Repo/' "$FGH/403.out" || { pages_ok=0; echo "  403: $(cat "$FGH/403.out")"; }
GITHUB_ACTIONS=true pg 404 owner/site || true; grep -q '^::error title=GitHub Pages::GitHub Pages is not enabled for owner/site' "$FGH/404.out" || { pages_ok=0; echo "  ci: $(cat "$FGH/404.out")"; }
if [ "$pages_ok" = 1 ]; then
  ok "release.py pages: on (workflow) exit 0; branch-built, off (404), unreadable (403) exit 1 with the admin steps; ::error in CI"
else
  bad "release.py pages (fake gh)"
fi
if have_py yaml; then
  if python3 - "$ROOT/.github/workflows/pages.yml" <<'PY' >$WORK/dc-pages-yml.out 2>&1
import sys, yaml
w = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
steps = w["jobs"]["build"]["steps"]
runs = [s.get("run", "") for s in steps]
i = next(i for i, r in enumerate(runs) if "tools/release.py pages" in r)
j = next(i for i, r in enumerate(runs) if "styleboard/build.py" in r)
assert i < j, (i, j)
assert '"$GITHUB_REPOSITORY"' in runs[i] and steps[i]["env"]["GH_TOKEN"] == "${{ github.token }}", steps[i]
assert w["permissions"]["pages"] == "write" and "deploy" in w["jobs"]
PY
  then
    ok "pages.yml parses; the Pages check runs before the build with the workflow token"
  else
    bad "pages.yml: $(cat $WORK/dc-pages-yml.out)"
  fi
else
  skip "pages.yml parse" "PyYAML not installed"
fi

# release.py plan(): each local film is compared against the repo tools/films.json names for it, so
# films the upstream already hosts are not copied to the fork (scratch root, fake releases, no gh calls)
RP="$WORK/release-plan"; rm -rf "$RP"; mkdir -p "$RP/tools" "$RP/.release/web"
for s in up new fork moved; do mkdir -p "$RP/styles/$s"; printf 'film-%s' "$s" >"$RP/styles/$s/$s.mp4"; printf 'web-%s' "$s" >"$RP/.release/web/$s.mp4"; done
printf '{"default": "up/stream", "films": {"fork": "me/fork"}}\n' >"$RP/tools/films.json"
if python3 -c "
import os, sys; sys.path.insert(0, '$ROOT/tools'); import release
release.ROOT, release.OUT, release.REPO = '$RP', '$RP/.release', 'me/fork'
release.style_slugs = lambda: ['fork', 'moved', 'new', 'up']
release.shutil.which = lambda c: '/bin/' + c
size = lambda p: (os.path.getsize('$RP/' + p), None)
rels = {('films', 'up/stream'): {'up.mp4': size('styles/up/up.mp4'), 'moved.mp4': (1, None)},
        ('web', 'up/stream'): {'up.mp4': size('.release/web/up.mp4'), 'moved.mp4': (1, None)},
        ('films', 'me/fork'): {'fork.mp4': size('styles/fork/fork.mp4'), 'moved.mp4': size('styles/moved/moved.mp4')},
        ('web', 'me/fork'): {'fork.mp4': size('.release/web/fork.mp4'), 'moved.mp4': size('.release/web/moved.mp4')}}
release.remote = lambda tag, repo=None: rels.get((tag, repo or release.REPO), {})
got = sorted((t, os.path.basename(p), w) for t, p, w in release.plan())
want = [('films', 'new.mp4', 'missing'), ('films.json', 'moved.mp4', 'on me/fork but tools/films.json names up/stream'), ('web', 'new.mp4', 'missing')]
assert got == want, got
" >$WORK/dc-plan.err 2>&1; then
  ok "release.py plan() leaves upstream-hosted films alone, pushes only what their host lacks"
else
  bad "release.py plan() host selection: $(tail -5 $WORK/dc-plan.err)"
fi

# core/three/post.js: DOF/GTAO targets stay at w*ssaa for pixelRatio 1 and 2 (addPass must not
# resize them) and post.setSize re-targets them for 9:16. Stub renderer, no GPU needed.
if command -v node >/dev/null 2>&1 && test -d "$ROOT/node_modules/three"; then
  if node "$CTL/tests/three_post_size.mjs" >$WORK/dc-three.out 2>&1; then
    ok "core/three/post.js DOF size owned by makePost ($(grep -c '^ok ' $WORK/dc-three.out) checks)"
  else
    bad "core/three/post.js sizing: $(grep -v '^ok ' $WORK/dc-three.out | head -20)"
  fi
else
  skip "core/three/post.js sizing" "node or node_modules/three missing (npm ci)"
fi

# styles/hd-2d and styles/lowpoly-island post copies: targets from w, h x ssaa (3840x2160 at 1920x1080 ssaa 2, as before),
# post.setSize re-targets them for 9:16. Same stub renderer, no GPU needed.
if command -v node >/dev/null 2>&1 && test -d "$ROOT/node_modules/three"; then
  if node "$CTL/tests/style_post_size.mjs" >$WORK/dc-stylepost.out 2>&1; then
    ok "hd-2d / lowpoly-island post copies size from W/H ($(grep -c '^ok ' $WORK/dc-stylepost.out) checks)"
  else
    bad "hd-2d / lowpoly-island post sizing: $(grep -v '^ok ' $WORK/dc-stylepost.out | head -20)"
  fi
else
  skip "hd-2d / lowpoly-island post sizing" "node or node_modules/three missing (npm ci)"
fi

# core/render/reframe.mjs: which portrait renders are reframed, every style.json declares portrait native|reframe,
# and (with ffmpeg) a synthetic 16:9 frame composed into 1080x1920 keeps the whole picture in the centre band over the fill.
if command -v node >/dev/null 2>&1; then
  node "$CTL/tests/reframe.mjs" >$WORK/dc-reframe.out 2>&1; rc=$?
  if [ $rc -eq 0 ]; then
    ok "portrait reframe: plan, style.json lint, ffmpeg compose ($(grep -c '^ok ' $WORK/dc-reframe.out) checks)"
  elif [ $rc -eq 77 ]; then
    ok "portrait reframe: plan + style.json lint ($(grep -c '^ok ' $WORK/dc-reframe.out) checks)"
    skip "portrait reframe ffmpeg compose" "ffmpeg/ffprobe not on PATH"
  else
    bad "portrait reframe: $(grep -v '^ok ' $WORK/dc-reframe.out | head -20)"
  fi
else
  skip "portrait reframe" "node missing"
fi

# swiss-motion 9:16 statements: Chinese copy (no spaces) breaks inside CJK runs and stays within
# the measure on two lines; English and landscape layouts are unchanged. Stub canvas, no fonts needed.
if command -v node >/dev/null 2>&1; then
  if node "$CTL/tests/swiss_fit.mjs" >$WORK/dc-swiss-fit.out 2>&1; then
    ok "swiss-motion 9:16 fit wraps CJK statements ($(grep -c '^ok ' $WORK/dc-swiss-fit.out) checks)"
  else
    bad "swiss-motion 9:16 fit: $(grep -v '^ok ' $WORK/dc-swiss-fit.out | head -20)"
  fi
else
  skip "swiss-motion 9:16 fit" "node missing"
fi

# tools/portrait_check.py: the reproducible 9:16 check (copies, fonts, footage, stills, sheets, --compare).
# Only the plan is tested here (--dry-run: no network, no files); real renders download fonts/footage.
PCC="$WORK/pc-cache"
if python3 -m py_compile "$ROOT/tools/portrait_check.py" \
  && WORDFILM_CACHE="$PCC" python3 "$ROOT/tools/portrait_check.py" --dry-run >$WORK/dc-pc.out 2>&1 \
  && [ ! -e "$PCC" ] \
  && grep -q "copies in $PCC/portrait-check/styles" $WORK/dc-pc.out \
  && ( for s in caption-news swiss-motion pictogram-motion art-deco hd-2d microgame; do grep -q "^$s: portrait" $WORK/dc-pc.out || exit 1; done ) \
  && grep -q '^caption-news: portrait native, t = 22.3' $WORK/dc-pc.out \
  && grep -q '^art-deco: portrait reframe' $WORK/dc-pc.out \
  && grep -q 'render node core/render/still.mjs .*/styles/hd-2d/demo 55.08 --size 1080x1920' $WORK/dc-pc.out \
  && grep -q 'tools/fonts.sh (demo fetcher), fetch_fonts.ensure_fonts (controller)' $WORK/dc-pc.out \
  && WORDFILM_CACHE="$PCC" python3 "$ROOT/tools/portrait_check.py" --dry-run white-model --t 1 2.5 >$WORK/dc-pc2.out 2>&1 \
  && grep -q 'footage (only with --footage) until data/zshadow.png exists' $WORK/dc-pc2.out \
  && grep -q 'demo 1 2.5 --out' $WORK/dc-pc2.out \
  && ! WORDFILM_CACHE="$PCC" python3 "$ROOT/tools/portrait_check.py" --dry-run no-such-style >/dev/null 2>&1 \
  && ! WORDFILM_CACHE="$PCC" python3 "$ROOT/tools/portrait_check.py" --dry-run --t soon >/dev/null 2>&1 \
  && [ ! -e "$PCC" ]; then
  ok "portrait_check.py --dry-run plans natives + reframe sample under \$WORDFILM_CACHE, writes nothing; bad slug / --t rejected"
else
  bad "portrait_check.py dry run: $(cat $WORK/dc-pc.out $WORK/dc-pc2.out 2>/dev/null | head -30)"
fi
skip "portrait_check.py renders" "downloads fonts and footage; run python3 tools/portrait_check.py [--footage] by hand"

# styleboard/build.py must stay valid on Python 3.10/3.11 (CI builds Pages on 3.12, people run 3.11+):
# no backslashes inside f-string expressions. Compile with every such interpreter on PATH.
SB_PYS=""
for py in python3 python3.10 python3.11; do
  if command -v "$py" >/dev/null 2>&1 && "$py" -c 'pass' >/dev/null 2>&1; then
    v="$("$py" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
    if "$py" -c 'import sys; compile(open(sys.argv[1], encoding="utf-8").read(), sys.argv[1], "exec")' \
        "$ROOT/styleboard/build.py" >$WORK/dc-sb-compile.out 2>&1; then
      SB_PYS="$SB_PYS $v"
    else
      bad "styleboard/build.py does not compile on Python $v: $(tail -3 $WORK/dc-sb-compile.out)"
      SB_PYS="$SB_PYS FAIL"
    fi
  fi
done
case "$SB_PYS" in
  *FAIL*) ;;
  "") skip "styleboard/build.py compile" "no python3 on PATH" ;;
  *) ok "styleboard/build.py compiles on Python$(echo "$SB_PYS" | tr ' ' '\n' | sort -u | tr '\n' ' ' | sed 's/ $//')" ;;
esac

# handoff pytest suite (frame size / fps); one command covers everything
if python3 -c "import pytest" 2>/dev/null; then
  if (cd "$ROOT" && python3 -m pytest tools/handoff/tests -q -p no:cacheprovider >$WORK/dc-pytest.out 2>&1); then
    ok "pytest tools/handoff/tests ($(tail -1 $WORK/dc-pytest.out))"
  else
    bad "pytest tools/handoff/tests: $(tail -20 $WORK/dc-pytest.out)"
  fi
else
  skip "pytest tools/handoff/tests" "pytest not installed (python3 -m pip install -r requirements-dev.txt)"
fi

# Remotion infographic skill: plan -> props converter (stdlib only), then an optional real render.
RMX="$ROOT/plugin/skills/lemo-remotion-infographic"
P2P=(python3 "$RMX/scripts/plan_to_props.py")
rmx_props() {  # $1 fixture, $2 expected WxH, $3 expected frames, $4 out
  "${P2P[@]}" "$FIX/$1" -o "$4" >"$4.out" 2>&1 || { echo "convert failed: $(cat "$4.out")"; return 1; }
  "${P2P[@]}" --check "$4" >/dev/null 2>"$4.err" || { echo "check failed: $(cat "$4.err")"; return 1; }
  python3 - "$4" "$2" "$3" <<'PY' || return 1
import json, sys
p = json.load(open(sys.argv[1]))
size, frames = sys.argv[2], int(sys.argv[3])
assert f"{p['width']}x{p['height']}" == size, (p['width'], p['height'])
assert p['fps'] == 24 and p['durationInFrames'] == frames, p['durationInFrames']
end = p['scenes'][-1]['from'] + p['scenes'][-1]['durationInFrames']
assert end == frames and p['scenes'][0]['from'] == 0, end
assert all(s['durationInFrames'] >= 24 for s in p['scenes'])
PY
  if have_py jsonschema; then
    python3 -c 'import json,sys,jsonschema; jsonschema.validate(json.load(open(sys.argv[1])), json.load(open(sys.argv[2])))' \
      "$4" "$RMX/template/props.schema.json" || { echo "jsonschema rejected $4"; return 1; }
  fi
}
for c in "plan-caption-news.json 1920x1080 720" "plan-caption-news-portrait.json 1080x1920 720" \
         "plan-pictogram-motion-portrait.json 1080x1920 768" "plan-swiss-motion.json 1920x1080 768"; do
  set -- $c
  if msg=$(rmx_props "$1" "$2" "$3" "$WORK/rmx-$1" 2>&1); then
    ok "remotion plan_to_props $1 -> $2, $3 frames @ 24 fps, validates against props.schema.json$(have_py jsonschema && echo ' (+ jsonschema)')"
  else
    bad "remotion plan_to_props $1: $msg"
  fi
done
if python3 - "$WORK/rmx-plan-caption-news.json" <<'PY' >$WORK/rmx-kinds.out 2>&1
import json, sys
p = json.load(open(sys.argv[1]))
k = {s['id']: s for s in p['scenes']}
assert [s['kind'] for s in p['scenes']] == ['title', 'compare', 'chart', 'caption', 'caption', 'end'], [s['kind'] for s in p['scenes']]
assert [(i['label'], i['tag'], i['value']) for i in k['c2']['items']] == [('现金', '快', 0), ('房产', '慢', 90)]
assert k['c3']['series'] == [12, 18, 27, 41]
assert k['c1']['lines'] == [[{'text': '流动性', 'accent': False}], [{'text': '是什么', 'accent': True}]]
assert p['palette']['accent'] == '#FFC21A' and p['transparent'] is False
PY
then ok "remotion plan_to_props scene kinds (title/compare/chart/caption/end), labels and {accent} markup"
else bad "remotion plan_to_props kinds: $(cat $WORK/rmx-kinds.out)"; fi
# --timeline: per-shot frames come from schedule.py's t0/t1
python3 - "$FIX/plan-caption-news.json" "$WORK/rmx-tl.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1])); t, shots = 0.0, []
for s in p['shots']:
    shots.append({'id': s['id'], 't0': t, 't1': t + 4.25}); t += 4.25
json.dump({'scheduledDurationSec': t, 'shots': shots}, open(sys.argv[2], 'w'))
PY
if "${P2P[@]}" "$FIX/plan-caption-news.json" --timeline "$WORK/rmx-tl.json" -o "$WORK/rmx-tl-props.json" >/dev/null 2>&1 \
  && python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); assert p["durationInFrames"]==612 and [s["from"] for s in p["scenes"]]==[0,102,204,306,408,510], p' "$WORK/rmx-tl-props.json"; then
  ok "remotion plan_to_props --timeline maps t0/t1 to frames (6 x 4.25 s = 612 frames)"
else
  bad "remotion plan_to_props --timeline"
fi
# unmappable input exits non-zero with a reason
rmx_reject() {  # $1 label, $2 python mutation of plan P, $3 expected error text
  python3 - "$FIX/plan-caption-news.json" "$WORK/rmx-bad.json" "$2" <<'PY'
import json, sys
P = json.load(open(sys.argv[1])); exec(sys.argv[3]); json.dump(P, open(sys.argv[2], 'w'), ensure_ascii=False)
PY
  if "${P2P[@]}" "$WORK/rmx-bad.json" -o "$WORK/rmx-bad-props.json" >$WORK/rmx-bad.out 2>&1; then
    bad "remotion plan_to_props should reject $1"
  elif grep -q "$3" $WORK/rmx-bad.out; then
    ok "remotion plan_to_props rejects $1"
  else
    bad "remotion plan_to_props $1: unexpected message $(cat $WORK/rmx-bad.out)"
  fi
}
rmx_reject "aspect 4:3" "P['aspect'] = '4:3'" "cannot be mapped"
rmx_reject "a non-unit data string" "P['shots'][1]['data']['note'] = 'x'" "only 'unit' may be a string"
rmx_reject "series plus scalars in one shot" "P['shots'][2]['data']['extra'] = 3" "ambiguous"
rmx_reject "too many shots for the target" "P['shots'] = [dict(P['shots'][3], id='s%d' % i) for i in range(40)]" "do not fit"
if "${P2P[@]}" "$FIX/plan-caption-news.json" --display "Comic Sans" >/dev/null 2>$WORK/rmx-font.err \
   || ! grep -q "not available" $WORK/rmx-font.err; then
  bad "remotion plan_to_props should reject an unknown display font: $(cat $WORK/rmx-font.err)"
else
  ok "remotion plan_to_props rejects a display font that is neither the text pair nor in core/fonts"
fi
python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); p["width"]=1080; json.dump(p, open(sys.argv[2],"w"))' \
  "$WORK/rmx-plan-caption-news.json" "$WORK/rmx-broken.json"
if "${P2P[@]}" --check "$WORK/rmx-broken.json" >/dev/null 2>&1; then
  bad "remotion plan_to_props --check should reject 16:9 props at 1080 wide"
else
  ok "remotion plan_to_props --check rejects props whose size does not match the aspect"
fi
# Real render: only against a project that scripts/setup.sh already installed (the harness never runs
# npm install). Point WORDFILM_REMOTION_DIR at <film>/remotion to run it.
RMXD="${WORDFILM_REMOTION_DIR:-}"
if [ -z "$RMXD" ] || [ ! -d "$RMXD/node_modules/remotion" ]; then
  skip "remotion render 16:9 + 9:16" "no installed template (set WORDFILM_REMOTION_DIR to a dir made by lemo-remotion-infographic/scripts/setup.sh)"
elif ! have_ffmpeg; then
  skip "remotion render 16:9 + 9:16" "ffmpeg/ffprobe missing"
else
  RMXOK=1; RMXMSG=""
  for c in "plan-caption-news.json 1920x1080" "plan-caption-news-portrait.json 1080x1920"; do
    set -- $c
    rm -f "$RMXD/out/picture.mp4"
    if sh "$RMX/scripts/render.sh" "$RMXD" --props "$WORK/rmx-$1" --frames 0-11 >$WORK/rmx-render.out 2>&1; then
      got=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$RMXD/out/picture.mp4" | head -1 | cut -d, -f1-2 | tr , x)
      [ "$got" = "$2" ] || { RMXOK=0; RMXMSG="$RMXMSG $1 is $got (want $2)"; }
    else
      RMXOK=0; RMXMSG="$RMXMSG $1: $(tail -5 $WORK/rmx-render.out)"
    fi
  done
  if [ "$RMXOK" = 1 ]; then ok "remotion render 12 frames at 1920x1080 and 1080x1920"; else bad "remotion render:$RMXMSG"; fi
fi

# The harness must not touch tracked files (fixtures are copied into a scratch dir).
if command -v git >/dev/null 2>&1 && git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  DIRTY="$(git -C "$ROOT" status --porcelain -- tools/deepseek-controller/fixtures)"
  if [ "$DIRTY" = "$FIX_STATUS_BEFORE" ]; then
    ok "harness left tools/deepseek-controller/fixtures untouched"
  else
    bad "harness modified fixtures: before [$FIX_STATUS_BEFORE] after [$DIRTY]"
  fi
else
  skip "fixture cleanliness" "not a git checkout"
fi

echo
echo "Results: $pass passed, $fail failed, $skipped skipped"

test "$fail" -eq 0
