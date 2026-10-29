#!/usr/bin/env bash
# Package a finished lemo MP4 as FCP xmeml (Premiere / Resolve import).
# Not a native .prproj. Prefer: bash tools/premiere_handoff.sh <film_dir> [out_name]
set -euo pipefail

usage() {
  echo "usage: bash tools/premiere_handoff.sh <film_dir> [out_name]" >&2
  echo "  writes <film_dir>/premiere-handoff/{premiere.xml,assets/master.mp4,timeline.edl,…}" >&2
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
exec python3 -m tools.handoff.cli premiere "$FILM_DIR" "${NAME_ARG[@]}" "$@"
