#!/bin/sh
# WordFilm skill (plugin directory edition): put the bundled library in its working folder, then print its path.
#   sh setup.sh                    copy the library that ships with this plugin (when it is new or changed) → LIB=<path>
#   sh setup.sh deps [voice] [music]
#                                  the same, then install packages (see the library's tools/setup.sh)
# The library ships inside the plugin; nothing is cloned or fetched here. It is copied out because the packages
# (node_modules/, .venv/) and the models it downloads later should survive plugin updates.
# WORDFILM_HOME = the working folder (default ~/.wordfilm; an existing ~/.lemo-opuscar folder from before the
#   rename is still used when ~/.wordfilm does not exist). The old name LEMO_OPUSCAR_HOME still works.
set -e
SRC=$(cd "$(dirname "$0")/../library" && pwd -P)
LIB=${WORDFILM_HOME:-${LEMO_OPUSCAR_HOME:-}}
if [ -z "$LIB" ]; then
  if [ ! -e "$HOME/.wordfilm" ] && [ -f "$HOME/.lemo-opuscar/.edition" ]; then LIB=$HOME/.lemo-opuscar
  else LIB=$HOME/.wordfilm; fi
fi
case "$LIB" in /*) ;; *) LIB=$(pwd)/$LIB ;; esac

stamp=$(cat "$SRC/.edition" 2>/dev/null || echo unknown)
if [ "$(cat "$LIB/.edition" 2>/dev/null)" != "$stamp" ]; then
  if [ -e "$LIB" ] && [ -n "$(ls -A "$LIB" 2>/dev/null)" ] && [ ! -f "$LIB/.edition" ]; then
    echo "✗ $LIB exists and is not a WordFilm library folder. Set WORDFILM_HOME to another folder."; exit 1
  fi
  mkdir -p "$LIB"
  # copy over the old files; packages and downloaded models (node_modules/, .venv/, core/tts/*.onnx…) stay
  cp -R "$SRC/." "$LIB/"
  echo "✓ library $stamp ready in $LIB"
fi
LIB=$(cd "$LIB" && pwd -P)
exec sh "$LIB/tools/setup.sh" "$@"
