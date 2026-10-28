#!/usr/bin/env bash
# Export a finished lemo MP4 as a HyperFrames composition (lintable via npx).
# Desktop Studio / HeyGen cloud / skills install = needs-user (see README in out dir).
set -euo pipefail

usage() {
  echo "usage: bash tools/hyperframes_export.sh <film_dir> [out_name]" >&2
  echo "  writes <film_dir>/hyperframes-handoff/{index.html,assets/,lemo-manifest.json,…}" >&2
  exit 2
}

if [ $# -lt 1 ]; then usage; fi
FILM_DIR=$1
shift
NAME_ARG=()
if [ $# -ge 1 ] && [[ "${1:-}" != -* ]]; then
  NAME_ARG=(--name "$1")
  shift
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
# Default: run lint so the path is proven on box when network/npm works
exec python3 -m tools.handoff.cli hyperframes "$FILM_DIR" "${NAME_ARG[@]}" --lint "$@"
