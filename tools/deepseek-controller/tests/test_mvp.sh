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

echo
echo "Results: $pass passed, $fail failed"
test "$fail" -eq 0
