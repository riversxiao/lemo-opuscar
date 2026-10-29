#!/bin/sh
# Isolated tests for DeepSeek setup.sh PIN + overlay gates (P1-1..P1-3).
# Runs in temp dirs; uses depth-1 fetches against the live fork when online.
set -e
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
SETUP="$SCRIPT_DIR/setup.sh"
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../../.." && pwd)
REPO_URL=${TEST_WORDFILM_REPO:-${TEST_LEMO_REPO:-https://github.com/riversxiao/wordfilm.git}}

# DeepSeek-era tip known on the fork at review time (full SHA).
DS_PIN=${TEST_DS_PIN:-f3d2e1c934be18ac4cb816ecaa5e9d27176afaae}
# Upstream baseline that predates DeepSeek overlay (present as ancestor on the fork).
UP_PIN=${TEST_UP_PIN:-413a6bd6d78ebd3bdd5abaec9538a26867f890df}

PASS=0
FAIL=0
SKIP=0
TMPBASE=$(mktemp -d "${TMPDIR:-/tmp}/wordfilm-ds-setup-test.XXXXXX")
trap 'rm -rf "$TMPBASE"' EXIT

ok() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
bad() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }
skip() { SKIP=$((SKIP + 1)); echo "  SKIP: $1"; }

have_net() {
  git ls-remote --heads "$REPO_URL" main >/dev/null 2>&1
}

run_setup() {
  # Usage: run_setup <home_dir> [env assignments...]
  # Prints stdout+stderr; returns setup exit code.
  home=$1
  shift
  # Clear ambient pins (new and old names) from the parent environment.
  env -u WORDFILM_PIN -u WORDFILM_HOME -u WORDFILM_REPO \
    -u LEMO_OPUSCAR_PIN -u LEMO_OPUSCAR_HOME -u LEMO_OPUSCAR_REPO \
    "$@" WORDFILM_HOME="$home" WORDFILM_REPO="$REPO_URL" \
    sh "$SETUP" 2>&1
}

run_setup_legacy() {
  # Same as run_setup, but only with the pre-rename LEMO_OPUSCAR_* names (fallback path).
  home=$1
  shift
  env -u WORDFILM_PIN -u WORDFILM_HOME -u WORDFILM_REPO \
    -u LEMO_OPUSCAR_PIN -u LEMO_OPUSCAR_HOME -u LEMO_OPUSCAR_REPO \
    "$@" LEMO_OPUSCAR_HOME="$home" LEMO_OPUSCAR_REPO="$REPO_URL" \
    sh "$SETUP" 2>&1
}

echo "== DeepSeek setup.sh pin/overlay tests =="
echo "SETUP=$SETUP"
echo "REPO=$REPO_URL"
echo "TMP=$TMPBASE"

if ! have_net; then
  skip "network unreachable (git ls-remote failed): remaining network cases skipped"
  echo "RESULT pass=$PASS fail=$FAIL skip=$SKIP"
  [ "$FAIL" -eq 0 ]
  exit 0
fi

# --- 1. Fresh clone with full DeepSeek PIN → HEAD matches, overlay present, exit 0 ---
echo "1) fresh clone + DeepSeek PIN"
H1="$TMPBASE/t1"
mkdir -p "$H1"
# setup clones into WORDFILM_HOME when path is empty / not a lib
rmdir "$H1" 2>/dev/null || rm -rf "$H1"
out=$(run_setup "$H1" WORDFILM_PIN="$DS_PIN") && ec=0 || ec=$?
echo "$out" | tail -5
if [ "$ec" -eq 0 ] \
  && echo "$out" | grep -q "^LIB=" \
  && head=$(git -C "$H1" rev-parse HEAD) \
  && [ "$head" = "$DS_PIN" ] \
  && [ -f "$H1/AGENTS.deepseek.md" ] \
  && [ -f "$H1/plugin/skills/lemo-deepseek/SKILL.md" ]; then
  ok "fresh pin $DS_PIN → HEAD+overlay"
else
  bad "fresh pin expected exit0 HEAD=$DS_PIN overlay (ec=$ec head=$(git -C "$H1" rev-parse HEAD 2>/dev/null || echo none))"
fi

# --- 2. PIN to upstream-only commit without overlay → must fail ---
echo "2) pin to pre-overlay upstream commit"
H2="$TMPBASE/t2"
out=$(run_setup "$H2" WORDFILM_PIN="$UP_PIN") && ec=0 || ec=$?
echo "$out" | tail -8
if [ "$ec" -ne 0 ] && echo "$out" | grep -qi "DeepSeek overlay\|missing the DeepSeek"; then
  # Must not pretend success
  if echo "$out" | grep -q "^LIB="; then
    bad "upstream pin failed but still printed LIB="
  else
    ok "upstream pin $UP_PIN refused (no overlay)"
  fi
else
  # Fallback: simulate missing overlay on a managed lib that already exists
  H2b="$TMPBASE/t2b"
  if [ -d "$H1/.git" ]; then
    cp -a "$H1" "$H2b"
    rm -f "$H2b/AGENTS.deepseek.md"
    git -C "$H2b" config lemo.managed true
    out=$(run_setup "$H2b") && ec=0 || ec=$?
    if [ "$ec" -ne 0 ] && ! echo "$out" | grep -q "^LIB="; then
      ok "simulated missing AGENTS.deepseek.md refused"
    else
      bad "missing overlay should fail (ec=$ec)"
    fi
  else
    bad "upstream pin should fail with overlay message (ec=$ec)"
  fi
fi

# --- 3. PIN=nonsense → non-zero, no success LIB ---
echo "3) nonsense PIN (legacy LEMO_OPUSCAR_* names)"
H3="$TMPBASE/t3"
out=$(run_setup_legacy "$H3" LEMO_OPUSCAR_PIN="not-a-real-ref-zzzz-deadbeef") && ec=0 || ec=$?
echo "$out" | tail -6
if [ "$ec" -ne 0 ]; then
  if echo "$out" | grep -q "^LIB="; then
    bad "nonsense PIN printed LIB= on failure"
  else
    ok "nonsense PIN exits non-zero without LIB="
  fi
else
  bad "nonsense PIN should not succeed"
fi

# --- 4. Managed lib + PIN that fails fetch → non-zero ---
echo "4) managed lib + unresolvable PIN"
H4="$TMPBASE/t4"
if [ -d "$H1/.git" ]; then
  cp -a "$H1" "$H4"
  git -C "$H4" config lemo.managed true
  # Point origin at a valid URL but request impossible object
  out=$(run_setup "$H4" WORDFILM_PIN="0000000000000000000000000000000000000001") && ec=0 || ec=$?
  echo "$out" | tail -6
  if [ "$ec" -ne 0 ] && ! echo "$out" | grep -q "^LIB="; then
    ok "managed + bad PIN exits non-zero"
  else
    bad "managed + bad PIN should hard-fail (ec=$ec)"
  fi
else
  skip "no successful clone from test 1 to reuse as managed lib"
fi

# --- 5. User-owned lib missing overlay → fail clearly ---
echo "5) user-owned lib without overlay"
H5="$TMPBASE/t5"
mkdir -p "$H5/core/render" "$H5/plugin/skills/lemo-deepseek/scripts"
printf '# fake\n' > "$H5/AGENTS.md"
# intentionally no AGENTS.deepseek.md / DEEPSEEK.md
out=$(run_setup "$H5") && ec=0 || ec=$?
echo "$out" | tail -6
if [ "$ec" -ne 0 ] && echo "$out" | grep -qi "DeepSeek overlay"; then
  ok "user-owned missing overlay refused"
else
  bad "user-owned missing overlay should fail (ec=$ec)"
fi

# --- 6. Legacy LEMO_OPUSCAR_HOME still resolves an existing library ---
echo "6) legacy LEMO_OPUSCAR_HOME on an existing library"
if [ -d "$H1/.git" ]; then
  out=$(run_setup_legacy "$H1") && ec=0 || ec=$?
  echo "$out" | tail -3
  if [ "$ec" -eq 0 ] && echo "$out" | grep -qx "LIB=$(cd "$H1" && pwd -P)"; then
    ok "LEMO_OPUSCAR_HOME fallback resolves $H1"
  else
    bad "LEMO_OPUSCAR_HOME fallback should resolve $H1 (ec=$ec)"
  fi
else
  skip "no successful clone from test 1 to reuse for the legacy-name check"
fi

# --- 7. WORDFILM_HOME wins over LEMO_OPUSCAR_HOME ---
echo "7) WORDFILM_HOME takes precedence"
H7="$TMPBASE/t7-not-a-lib"
mkdir -p "$H7"; printf 'x\n' > "$H7/stray"
if [ -d "$H1/.git" ]; then
  out=$(run_setup "$H1" LEMO_OPUSCAR_HOME="$H7") && ec=0 || ec=$?
  if [ "$ec" -eq 0 ] && echo "$out" | grep -qx "LIB=$(cd "$H1" && pwd -P)"; then
    ok "WORDFILM_HOME used before LEMO_OPUSCAR_HOME"
  else
    bad "WORDFILM_HOME should win over LEMO_OPUSCAR_HOME (ec=$ec)"
  fi
else
  skip "no successful clone from test 1 to reuse for the precedence check"
fi

echo "RESULT pass=$PASS fail=$FAIL skip=$SKIP"
[ "$FAIL" -eq 0 ]
