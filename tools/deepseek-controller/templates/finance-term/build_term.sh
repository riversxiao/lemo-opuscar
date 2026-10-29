#!/usr/bin/env bash
# Render one approved FRM term film end to end (local render only, free paths only).
#   bash tools/deepseek-controller/templates/finance-term/build_term.sh <term-dir> [film-dir]
# <term-dir>/src must hold plan.json (batch_terms.py plan), lines.json (approvedBy), BRIEF.md, FACTS.md.
# Film dir default: <term-dir>-v001. Stops on any FAIL; WARN is report-only. Rework (≤2 rounds,
# only on FAIL) is manual — see STEPS.md §Rework. Never prints keys.
set -euo pipefail
TERM_DIR=$(cd "$1" && pwd); P=${2:-${TERM_DIR}-v001}
REPO=$(cd "$(dirname "$0")/../../../.." && pwd); CTL="$REPO/tools/deepseek-controller"
NAME=$(basename "$P"); M="$P/$NAME.mp4"; SRC="$TERM_DIR/src"
APPROVED=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['approvedBy'])" "$SRC/lines.json")
cd "$REPO"
python3 "$CTL/cli.py" validate "$SRC/plan.json"
if [ ! -f "$P/voices/dur.json" ] || [ "${FORCE_SCAFFOLD:-0}" = 1 ]; then
  python3 "$CTL/cli.py" scaffold "$SRC/plan.json" -o "$P" --lib "$REPO" --force
  python3 "$CTL/apply_pictogram_style_version.py" --project "$P" --version finance-v001
fi
cp "$SRC/BRIEF.md" "$SRC/FACTS.md" "$P/"
# 1) critic as evidence only — locked wording; FLAGGED + approval passes the gate, nothing rewritten
# (skipped when evidence already matches the current lines sha — saves the free-tier tokens)
if PYTHONPATH="$CTL" python3 -c "import sys,dialogue_loop as D;from pathlib import Path;sys.exit(0 if D.gate_status(Path(sys.argv[1]))[0] else 1)" "$P" 2>/dev/null; then
  echo "dialogue-loop: evidence current (linesSha256 match) — not re-run"
else
  python3 "$CTL/cli.py" dialogue-loop --project "$P" --check-only --approved-by "$APPROVED" --item "$NAME check-only" || true
fi
# 2) StepAudio free preview, one session take (reused if scripts unchanged)
python3 "$CTL/cli.py" tts --project "$P" --provider stepaudio --fallback "" --pacing standard
# 3) schedule (ceiling only) + P1 beats/keywords + pictogram edl_runtime
python3 "$CTL/cli.py" schedule --project "$P" --require-vo --pacing standard
node core/render/events.mjs "$P" >/dev/null
python3 "$CTL/cli.py" mix --project "$P" --preset soft-pulse
node core/render/video.mjs "$P" --fps 30 --workers 4 --out "$P/out/video.mp4"
bash core/render/mux.sh "$P/out/video.mp4" "$P/out/mix.wav" "$M" 30 1
python3 "$CTL/vo_srt.py" --project "$P" --out "$P/$NAME.srt"
# 4) gates
python3 "$CTL/cli.py" visual-check --project "$P" --media "$M" --no-semantic
python3 "$CTL/pacing_check.py" --project "$P" --media "$M" --pacing standard || echo "pacing FAIL → STEPS.md §Rework"
python3 "$CTL/cli.py" quality --project "$P" --media "$M" --delivery --asr-mode auto
# 5) handoffs: OpenFilm + HyperFrames + Premiere xmeml (timebase probed from the master)
python3 "$CTL/cli.py" handoff --project "$P" --target all --name "$NAME" --extract-shots --lint --no-budget
echo "OK $NAME → $M ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$M")s)"
