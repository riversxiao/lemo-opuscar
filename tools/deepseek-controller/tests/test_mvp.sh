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

echo
echo "Results: $pass passed, $fail failed"
test "$fail" -eq 0
