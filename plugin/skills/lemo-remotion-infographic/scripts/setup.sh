#!/bin/sh
# Remotion infographic: put the template into a film project and install it.
#   sh setup.sh <film-dir> [--no-install]
# Creates <film-dir>/remotion/ (template copy, never overwritten once it exists), refreshes
# public/fonts/ (Inter Tight + Noto Sans SC via fetch_fonts.py, the library display fonts from
# core/fonts/ with their own fonts.css) and runs npm install there. Prints REMOTION=<path>.
# The library is $WORDFILM_HOME (or $LEMO_OPUSCAR_HOME), else the clone this script sits in.
# Refuses any target inside $LIB/styles: Remotion projects live with the film or in ~/lemo-my-styles/.
set -e
die() { echo "setup.sh: $*" >&2; exit 1; }
FILM="$1"; INSTALL=1
[ -n "$FILM" ] || die "usage: sh setup.sh <film-dir> [--no-install]"
[ "${2:-}" = "--no-install" ] && INSTALL=0
HERE=$(cd "$(dirname "$0")" && pwd -P)
is_lib() { [ -f "$1/AGENTS.md" ] && [ -d "$1/core/render" ]; }
LIB=${WORDFILM_HOME:-${LEMO_OPUSCAR_HOME:-}}
[ -n "$LIB" ] || LIB=$(cd "$HERE/../../../.." && pwd -P)
is_lib "$LIB" || die "$LIB is not the WordFilm library; run the lemo-opuscar setup.sh and set WORDFILM_HOME"
LIB=$(cd "$LIB" && pwd -P)

mkdir -p "$FILM"
FILM=$(cd "$FILM" && pwd -P)
case "$FILM/" in "$LIB/styles/"*) die "refusing $FILM: never build inside \$LIB/styles (use films/<id>/ or ~/lemo-my-styles/)";; esac
DEST="$FILM/remotion"
TPL="$HERE/../template"

if [ -f "$DEST/package.json" ]; then
  echo "= $DEST exists; keeping its src/ and props, refreshing fonts"
else
  mkdir -p "$DEST"
  cp "$TPL/package.json" "$TPL/tsconfig.json" "$TPL/remotion.config.ts" "$TPL/props.schema.json" "$DEST/"
  cp -R "$TPL/src" "$DEST/src"
  cp "$TPL/src/sample-props.json" "$DEST/props.json"
  echo "+ template copied to $DEST"
fi

mkdir -p "$DEST/public/fonts/core"
cp "$LIB/core/fonts/fonts.css" "$LIB/core/fonts/OFL.md" "$LIB"/core/fonts/f*.woff2 "$DEST/public/fonts/core/"
python3 "$LIB/tools/deepseek-controller/fetch_fonts.py" --fonts-dir "$DEST/public/fonts" --style remotion-infographic \
  || die "fonts missing (offline? set LEMO_FONT_CACHE to a folder holding InterTightwght.ttf and NotoSansSCwght.ttf)"

if [ "$INSTALL" = 1 ]; then
  command -v npm >/dev/null || die "npm (Node 20+) is needed"
  (cd "$DEST" && npm install --no-audit --no-fund) || die "npm install failed in $DEST"
fi
echo "REMOTION=$DEST"
