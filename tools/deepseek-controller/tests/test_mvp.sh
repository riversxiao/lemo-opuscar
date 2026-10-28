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

# 8) Swiss scaffold: expected files + ease.js hash unchanged vs demo
DEMO_EASE="$ROOT/styles/swiss-motion/demo/ease.js"
DEMO_HASH="$(sha256sum "$DEMO_EASE" | awk '{print $1}')"
rm -rf /tmp/dc-scaffold-swiss
if "${CLI[@]}" scaffold "$FIX/plan-swiss-motion.json" -o /tmp/dc-scaffold-swiss --lib "$ROOT" >/tmp/dc-sc.out 2>/tmp/dc-sc.err \
  && test -f /tmp/dc-scaffold-swiss/content/shots.json \
  && test -f /tmp/dc-scaffold-swiss/content/engine.lock.json \
  && test -f /tmp/dc-scaffold-swiss/lines.json \
  && test -f /tmp/dc-scaffold-swiss/palette.json \
  && test -f /tmp/dc-scaffold-swiss/PROJECT.md \
  && test -f /tmp/dc-scaffold-swiss/ease.js \
  && test -f /tmp/dc-scaffold-swiss/film.js; then
  ok "scaffold swiss creates expected files"
  PROJ_HASH="$(sha256sum /tmp/dc-scaffold-swiss/ease.js | awk '{print $1}')"
  if test "$PROJ_HASH" = "$DEMO_HASH"; then
    ok "scaffold leaves ease.js hash identical to demo"
  else
    bad "ease.js hash changed: demo=$DEMO_HASH proj=$PROJ_HASH"
  fi
  FILM_DEMO="$(sha256sum "$ROOT/styles/swiss-motion/demo/film.js" | awk '{print $1}')"
  FILM_PROJ="$(sha256sum /tmp/dc-scaffold-swiss/film.js | awk '{print $1}')"
  if test "$FILM_DEMO" = "$FILM_PROJ"; then
    ok "scaffold leaves film.js hash identical to demo"
  else
    bad "film.js hash changed"
  fi
  if grep -q '一块钱' /tmp/dc-scaffold-swiss/lines.json; then
    ok "scaffold synced Chinese lines into root lines.json"
  else
    bad "root lines.json missing plan text"
  fi
else
  bad "scaffold swiss files: $(cat /tmp/dc-sc.out) $(cat /tmp/dc-sc.err)"
fi

# 9) pictogram stub scaffold (copy+adapt only)
rm -rf /tmp/dc-scaffold-picto
if "${CLI[@]}" scaffold "$FIX/plan-pictogram-motion.json" -o /tmp/dc-scaffold-picto --lib "$ROOT" --force >/tmp/dc-sc2.out 2>/tmp/dc-sc2.err \
  && test -f /tmp/dc-scaffold-picto/content/edl_content.json \
  && test -f /tmp/dc-scaffold-picto/engine.js; then
  ENG_DEMO="$(sha256sum "$ROOT/styles/pictogram-motion/demo/engine.js" | awk '{print $1}')"
  ENG_PROJ="$(sha256sum /tmp/dc-scaffold-picto/engine.js | awk '{print $1}')"
  if test "$ENG_DEMO" = "$ENG_PROJ"; then
    ok "pictogram stub scaffold keeps engine.js hash"
  else
    bad "pictogram engine.js hash changed"
  fi
else
  bad "pictogram stub scaffold: $(cat /tmp/dc-sc2.out) $(cat /tmp/dc-sc2.err)"
fi

echo
echo "Results: $pass passed, $fail failed"
test "$fail" -eq 0
