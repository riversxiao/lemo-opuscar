#!/usr/bin/env bash
# Render one approved FRM term film end to end (local render only, free paths only).
#   bash tools/deepseek-controller/templates/finance-term/build_term.sh <term-dir> [film-dir]
# <term-dir>/src must hold plan.json (batch_terms.py plan), lines.json (approvedBy), BRIEF.md, FACTS.md.
# Film dir default: <term-dir>-v001. Stops on any FAIL; WARN is report-only. Rework (≤2 rounds,
# only on FAIL) is manual — see STEPS.md §Rework. Never prints keys.
#
# env: STYLE_VERSION (default finance-v002: per-term eyebrow/end card, acronym-safe uppercase)
#      EL_BACKUP=1  also build an ElevenLabs backup narration of the same lines into
#                   <film>/backup-el/ and mux <film>/<name>-el.mp4 (+ -el.srt), quality --delivery.
#                   EL_VOICE (default Skylar uDnTdfbGbx3cHHFnY83O, bilingual zh/en male),
#                   EL_MODEL (default eleven_v4). Off by default (uses ElevenLabs characters).
set -euo pipefail
TERM_DIR=$(cd "$1" && pwd); P=${2:-${TERM_DIR}-v001}
REPO=$(cd "$(dirname "$0")/../../../.." && pwd); CTL="$REPO/tools/deepseek-controller"
NAME=$(basename "$P"); SRC="$TERM_DIR/src"
STYLE_VERSION=${STYLE_VERSION:-finance-v002}
APPROVED=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['approvedBy'])" "$SRC/lines.json")
cd "$REPO"

build_one() {  # plan project name provider [handoffs:1|0]
  local PLAN=$1 PJ=$2 NM=$3 PROV=$4 HO=${5:-1} OUT=${6:-$2/$3.mp4}
  python3 "$CTL/cli.py" validate "$PLAN"
  if [ ! -f "$PJ/voices/dur.json" ] || [ "${FORCE_SCAFFOLD:-0}" = 1 ]; then
    python3 "$CTL/cli.py" scaffold "$PLAN" -o "$PJ" --lib "$REPO" --force
    python3 "$CTL/apply_pictogram_style_version.py" --project "$PJ" --version "$STYLE_VERSION"
  fi
  cp "$SRC/BRIEF.md" "$SRC/FACTS.md" "$PJ/"
  # 1) critic as evidence only — locked wording; FLAGGED + approval passes the gate, nothing rewritten
  # (skipped when evidence already matches the current lines sha — saves the free-tier tokens)
  if PYTHONPATH="$CTL" python3 -c "import sys,dialogue_loop as D;from pathlib import Path;sys.exit(0 if D.gate_status(Path(sys.argv[1]))[0] else 1)" "$PJ" 2>/dev/null; then
    echo "dialogue-loop: evidence current (linesSha256 match) — not re-run"
  else
    python3 "$CTL/cli.py" dialogue-loop --project "$PJ" --check-only --approved-by "$APPROVED" --item "$NM check-only" || true
  fi
  # 2) TTS: StepAudio free preview (one session take, reused if scripts unchanged) or ElevenLabs backup
  python3 "$CTL/cli.py" tts --project "$PJ" --provider "$PROV" --fallback "" --pacing standard
  # 3) schedule (ceiling only) + P1 beats/keywords + pictogram edl_runtime
  python3 "$CTL/cli.py" schedule --project "$PJ" --require-vo --pacing standard
  node core/render/events.mjs "$PJ" >/dev/null
  python3 "$CTL/cli.py" mix --project "$PJ" --preset soft-pulse
  node core/render/video.mjs "$PJ" --fps 30 --workers 4 --out "$PJ/out/video.mp4"
  bash core/render/mux.sh "$PJ/out/video.mp4" "$PJ/out/mix.wav" "$OUT" 30 1
  python3 "$CTL/vo_srt.py" --project "$PJ" --out "${OUT%.mp4}.srt"
  # 4) gates — one film at a time (parallel whisper runs gave hallucinated ASR)
  python3 "$CTL/cli.py" visual-check --project "$PJ" --media "$OUT" --no-semantic
  python3 "$CTL/pacing_check.py" --project "$PJ" --media "$OUT" --pacing standard || echo "pacing FAIL → STEPS.md §Rework"
  python3 "$CTL/cli.py" quality --project "$PJ" --media "$OUT" --delivery --asr-mode auto
  # 5) handoffs: OpenFilm + HyperFrames + Premiere xmeml (timebase probed from the master)
  if [ "$HO" = 1 ]; then
    python3 "$CTL/cli.py" handoff --project "$PJ" --target all --name "$NM" --extract-shots --lint --no-budget
  fi
  echo "OK $NM → $OUT ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")s)"
}

build_one "$SRC/plan.json" "$P" "$NAME" stepaudio 1

if [ "${EL_BACKUP:-0}" = 1 ]; then
  # Same approved lines, ElevenLabs voice. say-fields stay as approved; the provider spells numbers
  # in Chinese words (97.5% → 百分之九十七点五) and joins letter spellings (E-S → ES) for eleven_v4.
  python3 - "$SRC/plan.json" "$SRC/plan.el.json" "${EL_VOICE:-uDnTdfbGbx3cHHFnY83O}" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
p["voice"]["provider"], p["voice"]["voiceId"] = "elevenlabs", sys.argv[3]
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(p, ensure_ascii=False, indent=2) + "\n")
PY
  LEMO_TTS_ELEVENLABS_MODEL=${EL_MODEL:-eleven_v4} build_one "$SRC/plan.el.json" "$P/backup-el" "$NAME-el" elevenlabs 0 "$P/$NAME-el.mp4"
fi
