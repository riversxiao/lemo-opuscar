#!/usr/bin/env bash
# Package a finished lemo MP4 as an OpenFilm project (multi-shot film.html + EDL + ffmpeg rebuild).
# Spec: https://openfilm.dev/docs/manual/
# Prefer: bash tools/openfilm_handoff.sh <film_dir> [out_name]
set -euo pipefail

usage() {
  echo "usage: bash tools/openfilm_handoff.sh <film_dir> [out_name]" >&2
  echo "  film_dir: lemo project containing a muxed .mp4" >&2
  echo "  writes <film_dir>/openfilm-handoff/{film.html,assets/,timeline.edl,manifest.json,…}" >&2
  echo "  flags: EXTRA_ARGS… passed to python (e.g. --extract-shots --json)" >&2
  exit 2
}

if [ $# -lt 1 ]; then usage; fi
FILM_DIR=$1
shift
NAME_ARG=()
# Optional positional out_name (legacy)
if [ $# -ge 1 ] && [[ "${1:-}" != -* ]]; then
  NAME_ARG=(--name "$1")
  shift
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m tools.handoff.cli openfilm "$FILM_DIR" "${NAME_ARG[@]}" "$@"
