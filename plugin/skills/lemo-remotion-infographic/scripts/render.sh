#!/bin/sh
# Render the Remotion infographic and hand it to the library mux.
#   sh render.sh <film>/remotion [--props props.json] [--audio mix.wav] [--out film.mp4]
#                [--over base.mp4] [--grain 0] [--frames 0-47]
# Full frame (default): props.json (transparent false) -> out/picture.mp4 (h264)
#   -> core/render/mux.sh picture.mp4 mix.wav film.mp4 24 <grain>.
# Overlay (--over): props made with plan_to_props.py --overlay (transparent true) -> out/overlay.webm
#   (VP8 with alpha) -> laid over a style render of the same size (base.mp4, e.g. from video.mjs)
#   -> out/composite.mp4 -> mux.sh as above.
# Without --audio it stops after the picture (picture.mp4 or composite.mp4), ready for the mux.
# The composition follows props.aspect: 16:9 Infographic 1920x1080, 9:16 InfographicPortrait 1080x1920.
# PLAYWRIGHT_CHROME, when set, is passed to Remotion as the browser (a chrome-headless-shell works).
set -e
die() { echo "render.sh: $*" >&2; exit 1; }
DIR="$1"; [ -n "$DIR" ] && [ -f "$DIR/package.json" ] || die "usage: sh render.sh <film>/remotion [--props p.json] [--audio mix.wav] [--out film.mp4] [--over base.mp4] [--grain 0] [--frames a-b]"
DIR=$(cd "$DIR" && pwd -P); shift
PROPS="$DIR/props.json"; AUDIO=""; OUT=""; OVER=""; GRAIN=0; FRAMES=""
while [ $# -gt 0 ]; do
  case "$1" in
    --props) PROPS="$2"; shift 2;;
    --audio) AUDIO="$2"; shift 2;;
    --out) OUT="$2"; shift 2;;
    --over) OVER="$2"; shift 2;;
    --grain) GRAIN="$2"; shift 2;;
    --frames) FRAMES="$2"; shift 2;;
    *) die "unknown argument: $1";;
  esac
done
abs() { case "$1" in ''|/*) echo "$1";; *) echo "$(pwd -P)/$1";; esac; }
AUDIO=$(abs "$AUDIO"); OUT=$(abs "$OUT"); OVER=$(abs "$OVER")
HERE=$(cd "$(dirname "$0")" && pwd -P)
LIB=${WORDFILM_HOME:-${LEMO_OPUSCAR_HOME:-}}
[ -n "$LIB" ] || LIB=$(cd "$HERE/../../../.." && pwd -P)
[ -f "$LIB/core/render/mux.sh" ] || die "$LIB has no core/render/mux.sh; set WORDFILM_HOME to the library"
[ -f "$PROPS" ] || die "props not found: $PROPS (make them with scripts/plan_to_props.py)"
PROPS=$(cd "$(dirname "$PROPS")" && pwd -P)/$(basename "$PROPS")
[ -d "$DIR/node_modules/remotion" ] || die "no node_modules in $DIR: run scripts/setup.sh first"
command -v ffprobe >/dev/null || die "ffmpeg/ffprobe are needed"

python3 "$HERE/plan_to_props.py" --check "$PROPS" >/dev/null || die "props do not validate (see above)"
read_prop() { python3 -c 'import json,sys; v=json.load(open(sys.argv[1]))[sys.argv[2]]; print(str(v).lower() if isinstance(v,bool) else v)' "$PROPS" "$1"; }
ASPECT=$(read_prop aspect); TRANSPARENT=$(read_prop transparent)
W=$(read_prop width); H=$(read_prop height)
if [ "$ASPECT" = "9:16" ]; then COMP=InfographicPortrait; else COMP=Infographic; fi

set -- --props="$PROPS"
[ -n "${PLAYWRIGHT_CHROME:-}" ] && set -- "$@" --browser-executable="$PLAYWRIGHT_CHROME"
[ -n "$FRAMES" ] && set -- "$@" --frames="$FRAMES"
mkdir -p "$DIR/out"
cd "$DIR"

if [ -n "$OVER" ]; then
  [ "$TRANSPARENT" = true ] || die "overlay needs transparent props: plan_to_props.py --overlay"
  [ -f "$OVER" ] || die "base video not found: $OVER"
  # csv can carry a trailing empty field (side data), so keep only the first two
  BS=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$OVER" | head -1 | cut -d, -f1-2 | tr , x)
  [ "$BS" = "${W}x${H}" ] || die "base video is $BS, the overlay is ${W}x${H}: render the style at --size ${W}x${H}"
  npx --no-install remotion render src/index.ts "$COMP" out/overlay.webm "$@" \
    --codec=vp8 --pixel-format=yuva420p --image-format=png || die "remotion render failed"
  # libvpx decoder keeps the alpha plane; the overlay runs to the end of the base video
  ffmpeg -y -loglevel error -i "$OVER" -c:v libvpx -i out/overlay.webm \
    -filter_complex "[0:v]fps=24[b];[b][1:v]overlay=eof_action=pass:format=auto,format=yuv420p[v]" \
    -map "[v]" -c:v libx264 -preset medium -crf 16 -r 24 out/composite.mp4 || die "overlay compose failed"
  PIC="$DIR/out/composite.mp4"
else
  [ "$TRANSPARENT" = false ] || die "transparent props render as an overlay: pass --over base.mp4"
  npx --no-install remotion render src/index.ts "$COMP" out/picture.mp4 "$@" \
    --codec=h264 --crf=16 || die "remotion render failed"
  PIC="$DIR/out/picture.mp4"
fi
echo "picture: $PIC"

if [ -n "$AUDIO" ]; then
  [ -n "$OUT" ] || OUT="$DIR/out/film.mp4"
  sh "$LIB/core/render/mux.sh" "$PIC" "$AUDIO" "$OUT" 24 "$GRAIN"
fi
