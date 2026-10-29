#!/bin/sh
# WordFilm skill: same as upstream setup, but defaults to the riversxiao fork
# (DeepSeek edition). Set LEMO_OPUSCAR_REPO / LEMO_OPUSCAR_PIN to override.
#   sh setup.sh                    library ready? (clone on first run, update later) → prints LIB=<path>
#   sh setup.sh deps [voice] [music]
#                                  install packages: core = Node packages, headless browser, Python core tier;
#                                  voice = TTS and speech check (+ the English voice model); music = pluck.py (numba)
#   sh setup.sh demo <slug>        add one style's demo source and poster to the library (reference only)
# The library is a sparse clone of the main branch: guides, core/ tools and every STYLE.md. Big assets: tools/fetch.sh.
# LEMO_OPUSCAR_HOME = where the library lives (default: the clone you stand in, else ~/lemo-opuscar).
#
# DeepSeek overlay is REQUIRED on the returned LIB. Pins that land on pre-overlay
# upstream (e.g. bare 413a6bd) fail. Prefer a full 40-char SHA or tag on this fork.
# Dual pinning: engine/upstream baseline ≠ control-layer (DeepSeek fork) commit — see DEEPSEEK.md.
set -e
REPO=${LEMO_OPUSCAR_REPO:-https://github.com/riversxiao/wordfilm.git}
# Optional: pin to a DeepSeek-era commit/tag (full 40-char SHA preferred)
PIN=${LEMO_OPUSCAR_PIN:-}
RESOLVED_PIN=

# 1. Which library: $LEMO_OPUSCAR_HOME, else the clone we are standing in, else ~/lemo-opuscar
is_lib() { [ -f "$1/AGENTS.md" ] && [ -d "$1/core/render" ]; }
is_deepseek_lib() {
  [ -f "$1/AGENTS.deepseek.md" ] &&
  [ -f "$1/DEEPSEEK.md" ] &&
  [ -f "$1/plugin/skills/lemo-deepseek/SKILL.md" ] &&
  [ -f "$1/plugin/skills/lemo-deepseek/scripts/setup.sh" ]
}
require_deepseek_lib() {
  if ! is_lib "$1"; then
    echo "✗ $1 is not a Lemo-Opuscar library (need AGENTS.md + core/render)."
    exit 1
  fi
  if ! is_deepseek_lib "$1"; then
    echo "✗ $1 is missing the DeepSeek overlay (AGENTS.deepseek.md, DEEPSEEK.md, plugin/skills/lemo-deepseek/)."
    echo "  This path is not a DeepSeek fork, or LEMO_OPUSCAR_PIN landed on a commit without the overlay"
    echo "  (e.g. bare upstream 413a6bd). Set LEMO_OPUSCAR_REPO=https://github.com/riversxiao/wordfilm.git"
    echo "  and pin a DeepSeek-era commit (full 40-char SHA preferred), not the upstream-only baseline."
    exit 1
  fi
}

if [ -n "$LEMO_OPUSCAR_HOME" ]; then LIB=$LEMO_OPUSCAR_HOME
elif top=$(git rev-parse --show-toplevel 2>/dev/null) && is_lib "$top"; then LIB=$top
else LIB=$HOME/lemo-opuscar
fi
case "$LIB" in /*) ;; *) LIB=$(pwd)/$LIB ;; esac

# Our clone skips demo sources, the gallery and big images; what `setup.sh demo` added stays.
# git < 2.35 has no --no-cone: then the whole library is checked out.
apply_sparse() {
  set -- '/*' '!/styles/*/demo/' '!/styleboard/' '!/docs/frames/' '!/docs/cover.jpg' '!/docs/opuscar98.jpg' '!/styles/*/poster.jpg' \
    $(git -C "$LIB" sparse-checkout list 2>/dev/null | grep -E '^/styles/[^/*]+/(demo/|poster\.jpg)$' || true)
  git -C "$LIB" sparse-checkout set --no-cone "$@" 2>/dev/null || git -C "$LIB" sparse-checkout disable || true
}

# Resolve $PIN inside $LIB to a full commit SHA in RESOLVED_PIN. Non-empty PIN that
# cannot be resolved → exit 1 (never soft-warn and continue).
resolve_pin() {
  pin=$1
  RESOLVED_PIN=
  [ -n "$pin" ] || return 0

  # Already available locally (unique abbrev or full SHA / tag)
  if full=$(git -C "$LIB" rev-parse --verify "${pin}^{commit}" 2>/dev/null); then
    RESOLVED_PIN=$full
    return 0
  fi

  # Fetch as ref or object id (GitHub accepts full SHA with --depth 1)
  if git -C "$LIB" fetch --quiet --depth 1 origin "$pin" 2>/dev/null; then
    if full=$(git -C "$LIB" rev-parse --verify "FETCH_HEAD^{commit}" 2>/dev/null); then
      if echo "$pin" | grep -Eq '^[0-9a-fA-F]{4,40}$'; then
        case "$full" in
          "$pin"*) RESOLVED_PIN=$full; return 0 ;;
        esac
        # fetched something whose SHA does not match the requested hex pin
        echo "✗ fetched object $full does not match PIN=$pin"
        exit 1
      fi
      RESOLVED_PIN=$full
      return 0
    fi
  fi

  # Short hex: deepen main history and resolve uniquely
  if echo "$pin" | grep -Eq '^[0-9a-fA-F]{4,39}$'; then
    git -C "$LIB" fetch --quiet --deepen=300 origin main 2>/dev/null || \
      git -C "$LIB" fetch --quiet origin main 2>/dev/null || true
    if full=$(git -C "$LIB" rev-parse --verify "${pin}^{commit}" 2>/dev/null); then
      RESOLVED_PIN=$full
      return 0
    fi
    echo "✗ could not uniquely resolve short PIN=$pin to a commit after fetch."
    echo "  Prefer a full 40-char SHA or an annotated tag on the DeepSeek fork."
    exit 1
  fi

  echo "✗ could not pin $LIB to $PIN (fetch/resolve failed)."
  echo "  Prefer a full 40-char SHA or tag on https://github.com/riversxiao/wordfilm"
  echo "  (DeepSeek-era). Do not use bare upstream 413a6bd as the DeepSeek control-layer pin."
  exit 1
}

# Checkout resolved PIN and verify HEAD. Always fatal when PIN was set.
apply_pin() {
  resolve_pin "$PIN"
  if ! git -C "$LIB" checkout --quiet --detach "$RESOLVED_PIN" 2>/dev/null \
     && ! git -C "$LIB" reset --quiet --hard "$RESOLVED_PIN" 2>/dev/null; then
    echo "✗ failed to check out resolved PIN $RESOLVED_PIN"
    exit 1
  fi
  head=$(git -C "$LIB" rev-parse HEAD)
  case "$head" in
    "$RESOLVED_PIN") ;;
    *)
      echo "✗ HEAD ($head) does not match resolved PIN ($RESOLVED_PIN)"
      exit 1
      ;;
  esac
  # If the user passed a short SHA, also require prefix match on the original PIN
  if echo "$PIN" | grep -Eq '^[0-9a-fA-F]{4,39}$'; then
    case "$head" in
      "$PIN"*) ;;
      *)
        echo "✗ HEAD $head does not start with short PIN $PIN"
        exit 1
        ;;
    esac
  fi
  apply_sparse
}

if [ "$(git -C "$LIB" config --get lemo.managed 2>/dev/null)" = true ]; then
  # our own clone (nothing of the user's lives in it): match main or PIN
  [ "$(git -C "$LIB" remote get-url origin 2>/dev/null)" = "$REPO" ] || git -C "$LIB" remote set-url origin "$REPO"
  if [ -n "$PIN" ]; then
    apply_pin
  elif err=$(git -C "$LIB" fetch --quiet --depth 1 origin main 2>&1 && git -C "$LIB" reset --quiet --hard FETCH_HEAD 2>&1); then
    apply_sparse
  else
    echo "! could not update $LIB (offline?); using the local copy. git: $err" | head -3
  fi
elif ! is_lib "$LIB"; then
  [ -e "$LIB" ] && [ -n "$(ls -A "$LIB" 2>/dev/null)" ] && { echo "✗ $LIB exists but is not the Lemo-Opuscar library. Set LEMO_OPUSCAR_HOME to another folder."; exit 1; }
  command -v git >/dev/null || { echo "✗ git is needed to download the library"; exit 1; }
  echo "↓ downloading the style library into $LIB"
  git clone --quiet --depth 1 --filter=blob:none --sparse --branch main "$REPO" "$LIB" || { rm -rf "$LIB"; echo "✗ download failed (offline?)"; exit 1; }
  apply_sparse
  git -C "$LIB" config lemo.managed true
  if [ -n "$PIN" ]; then
    apply_pin
  fi
else
  # Existing user-owned library (lemo.managed != true).
  # If PIN is set, try to honour it; refuse soft-success when pin cannot be applied.
  if [ -n "$PIN" ]; then
    if ! git -C "$LIB" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      echo "✗ LEMO_OPUSCAR_PIN=$PIN is set, but $LIB is not a git work tree; cannot apply pin safely."
      exit 1
    fi
    [ "$(git -C "$LIB" remote get-url origin 2>/dev/null)" = "$REPO" ] || \
      echo "! $LIB origin differs from LEMO_OPUSCAR_REPO; still attempting pin"
    apply_pin
  fi
fi
LIB=$(cd "$LIB" && pwd -P)

# DeepSeek overlay must be present on every successful path (before LIB=).
require_deepseek_lib "$LIB"

# Installed packages are tracked by content: a marker holds a checksum of the files they came from (and the Python
# version), so a changed package.json or requirements file triggers a reinstall.
sig() { cat "$@" 2>/dev/null | cksum | cut -d' ' -f1; }
pysig() { echo "$(sig "$1")-$("$LIB/.venv/bin/python" -V 2>&1 | cut -d. -f1,2)"; }
req() { [ "$1" = core ] && echo "$LIB/requirements.txt" || echo "$LIB/requirements-$1.txt"; }
node_ok() { [ "$(cat "$LIB/node_modules/.lemo-ok" 2>/dev/null)" = "$(sig "$LIB/package.json" "$LIB/package-lock.json")" ]; }
py_ok() { [ "$(cat "$LIB/.venv/.lemo-$1" 2>/dev/null)" = "$(pysig "$(req "$1")")" ]; }
# a Python 3.11+ for the venv when uv is absent; kokoro-onnx (voice tier) needs < 3.14, so those come first
find_py() {
  for c in python3.12 python3.13 python3.11 python3; do
    "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null && { echo "$c"; return 0; }
  done
  return 1
}

case "$1" in
  deps)
    shift; tiers=core
    for t in "$@"; do case $t in voice|music) tiers="$tiers $t" ;; *) echo "usage: sh setup.sh deps [voice] [music]"; exit 1 ;; esac; done
    cd "$LIB"
    command -v npm >/dev/null || { echo "✗ npm not found: install Node 20+ first"; exit 1; }
    if ! node_ok; then
      npm install --no-audit --no-fund --loglevel=error
      # npm may rewrite package-lock.json; in our own clone put it back, so the checksum stays the same
      [ "$(git config --get lemo.managed 2>/dev/null)" = true ] && git checkout -q -- package.json package-lock.json 2>/dev/null || true
      sig package.json package-lock.json > node_modules/.lemo-ok
    fi
    node node_modules/playwright-core/cli.js install chromium-headless-shell   # the renderer's browser (a no-op when present)
    # a venv whose Python is gone (after a Python upgrade) can't be repaired in place: make it again
    [ ! -e .venv ] || .venv/bin/python -c pass 2>/dev/null || { echo "! $LIB/.venv is broken; making it again"; rm -rf .venv; }
    if [ ! -x .venv/bin/python ]; then
      if command -v uv >/dev/null; then uv venv --quiet --python 3.12 .venv
      else py=$(find_py) || { echo "✗ Python 3.11+ is needed (or install uv, which fetches it)"; exit 1; }; "$py" -m venv .venv; fi
    fi
    for t in $tiers; do
      py_ok "$t" && continue
      if command -v uv >/dev/null; then uv pip install --quiet --python .venv/bin/python -r "$(req "$t")"
      else .venv/bin/python -m pip install --quiet --disable-pip-version-check -r "$(req "$t")"; fi
      pysig "$(req "$t")" > ".venv/.lemo-$t"
    done
    case " $tiers " in *" voice "*) [ -f core/tts/kokoro-v1.0.onnx ] && [ -f core/tts/voices-v1.0.bin ] || sh tools/fetch.sh voice ;; esac
    ;;
  demo)
    [ -n "$2" ] && [ -f "$LIB/styles/$2/STYLE.md" ] || { echo "usage: sh setup.sh demo <slug>  (slugs: $LIB/styles/README.md)"; exit 1; }
    if git -C "$LIB" sparse-checkout list >/dev/null 2>&1 && ! git -C "$LIB" sparse-checkout list | grep -qx "/styles/$2/demo/"; then
      git -C "$LIB" sparse-checkout add "/styles/$2/demo/" "/styles/$2/poster.jpg"
    fi
    echo "demo source: $LIB/styles/$2/demo"
    echo "demo poster: $LIB/styles/$2/poster.jpg"
    ;;
esac

# 2. Tools the pipeline needs (report only; installing them is up to the user)
miss=""
if command -v node >/dev/null; then
  [ "$(node -p 'process.versions.node.split(".")[0]')" -ge 20 ] || miss="$miss node20+(found $(node -v))"
else miss="$miss node20+"; fi
command -v ffmpeg >/dev/null || miss="$miss ffmpeg"
command -v uv >/dev/null || find_py >/dev/null || miss="$miss python3.11+(or uv)"
[ -n "$miss" ] && echo "! missing:$miss"
node_ok && py_ok core || echo "! packages not installed yet: run 'sh setup.sh deps' (a few minutes) before the first render"
echo "LIB=$LIB"
