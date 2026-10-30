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
#      TTS_PROVIDER=elevenlabs  main narration on ElevenLabs (series from 贝塔 pilot, wen hao 2026-10-29):
#                   EL_VOICE default = lines.json "voice" (from-draft) else Tex TKaUqol7GKx4m7enpCpP,
#                   EL_MODEL eleven_v4 (speed natural 1.0). Every request sends language_code from the
#                   line `lang` (CJK → zh Mandarin, English → en; mixed = one zh request) — without it v4
#                   drifted into 粤语 (beta-v001 L06). quality gate dialect_mandarin FAILs non-Mandarin.
#                   `say` must spell numbers in Chinese words; chars → voices/spoken.json.
#      STYLE_VERSION=finance-v003  per-line `visual` scenes: viz_pick.py (scene + 金融专家 content lint)
#                   after scaffold, end card as a ${OUTRO_SEC:-1.5}s outro, visual_dupe.py keyframe gate
#                   against the series (FAIL on near-duplicates) before quality; TP ≤ −2 dBTP.
#      REUSE_VOICES=1  re-render with the existing voices/ (no TTS call; use after a picture/gate fix).
#      MUSIC_LIBRARY=<bed dir>  StepAudio bed from <films>/_music-library (reused, no request);
#                   default for finance-v003: _music-library/finance-calm-01. MUSIC_LIBRARY=none → procedural.
#                   <films> = $WORDFILM_FILMS, else <repo>/films when it exists, else /workspace/films.
#      WORDFILM_TP_CEIL / WORDFILM_TP_RETRY_ABOVE (mux.sh true-peak; finance-v003 default -2.8 / -2.0),
#      WORDFILM_TTS_STEPAUDIO_ROLE / _TONE / _INSTRUCTION (series voice prompts). The upstream LEMO_*
#                   spellings of these still work; WORDFILM_* wins. Exported under the WORDFILM_* name.
set -euo pipefail
TERM_DIR=$(cd "$1" && pwd); P=${2:-${TERM_DIR}-v001}
REPO=$(cd "$(dirname "$0")/../../../.." && pwd); CTL="$REPO/tools/deepseek-controller"
NAME=$(basename "$P"); SRC="$TERM_DIR/src"
STYLE_VERSION=${STYLE_VERSION:-finance-v002}
TTS_PROVIDER=${TTS_PROVIDER:-stepaudio}
V3=0; case "$STYLE_VERSION" in finance-v00[3-9]) V3=1;; esac
FILMS=$(PYTHONPATH="$CTL" python3 -c "import common; print(common.films_root())")
if [ "$V3" = 1 ]; then
  MUSIC_LIBRARY=${MUSIC_LIBRARY:-$FILMS/_music-library/finance-calm-01}
  export WORDFILM_TP_CEIL="${WORDFILM_TP_CEIL:-${LEMO_TP_CEIL:--2.8}}"
  export WORDFILM_TP_RETRY_ABOVE="${WORDFILM_TP_RETRY_ABOVE:-${LEMO_TP_RETRY_ABOVE:--2.0}}"
fi
MUSIC_LIBRARY=${MUSIC_LIBRARY:-none}
# Series default (wen hao): narration speed 1.0 — never the standard +10% / brisk StepAudio prompts.
PACING=${PACING:-calm}
FINANCE_TTS_SPEED=${FINANCE_TTS_SPEED:-1.0}
export WORDFILM_TTS_STEPAUDIO_SPEED="$FINANCE_TTS_SPEED"
export WORDFILM_TTS_STEPAUDIO_ROLE="${WORDFILM_TTS_STEPAUDIO_ROLE:-${LEMO_TTS_STEPAUDIO_ROLE:-三十五岁左右的普通话男声，中低音，通俗金融学口播，语速正常、吐字清楚，关键词加重，句尾不拖音，像跟朋友把一件事讲明白；整片始终是同一个人同一个音色}}"
export WORDFILM_TTS_STEPAUDIO_TONE="${WORDFILM_TTS_STEPAUDIO_TONE:-${LEMO_TTS_STEPAUDIO_TONE:-（把一件事讲清楚）}}"
export WORDFILM_TTS_STEPAUDIO_INSTRUCTION="${WORDFILM_TTS_STEPAUDIO_INSTRUCTION:-${LEMO_TTS_STEPAUDIO_INSTRUCTION:-安静录音棚，同一位男声从头到尾讲完整篇口播，语速正常、不赶，句与句之间自然换气；关键词加重；纯人声，无背景音乐，无音效}}"
APPROVED=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['approvedBy'])" "$SRC/lines.json")
# narrator from the draft (batch_terms.py from-draft → lines.json "voice"; `elevenlabs:` prefix accepted)
DRAFT_VOICE=$(python3 -c "import json,sys;v=str(json.load(open(sys.argv[1])).get('voice') or '');print(v.split(':',1)[1] if v.lower().startswith('elevenlabs:') else v)" "$SRC/lines.json")
cd "$REPO"

build_one() {  # plan project name provider [handoffs:1|0]
  local PLAN=$1 PJ=$2 NM=$3 PROV=$4 HO=${5:-1} OUT=${6:-$2/$3.mp4}
  python3 "$CTL/cli.py" validate "$PLAN"
  if [ ! -f "$PJ/voices/dur.json" ] || [ "${FORCE_SCAFFOLD:-0}" = 1 ]; then
    python3 "$CTL/cli.py" scaffold "$PLAN" -o "$PJ" --lib "$REPO" --force
    python3 "$CTL/apply_pictogram_style_version.py" --project "$PJ" --version "$STYLE_VERSION"
  fi
  # finance-v003: one distinct vector scene per line from the `visual` field + content-visual lint
  if [ "$V3" = 1 ]; then python3 "$CTL/viz_pick.py" --lines "$SRC/lines.json" --project "$PJ" ${VIZ_OVERRIDES:-}; fi
  cp "$SRC/BRIEF.md" "$SRC/FACTS.md" "$PJ/"
  # 1) critic as evidence only — locked wording; FLAGGED + approval passes the gate, nothing rewritten
  # (skipped when evidence already matches the current lines sha — saves the free-tier tokens)
  if PYTHONPATH="$CTL" python3 -c "import sys,dialogue_loop as D;from pathlib import Path;sys.exit(0 if D.gate_status(Path(sys.argv[1]))[0] else 1)" "$PJ" 2>/dev/null; then
    echo "dialogue-loop: evidence current (linesSha256 match) — not re-run"
  else
    python3 "$CTL/cli.py" dialogue-loop --project "$PJ" --check-only --approved-by "$APPROVED" --item "$NM check-only" || true
  fi
  # 2) TTS: StepAudio free preview (one session take, reused if scripts unchanged) or ElevenLabs backup
  # REUSE_VOICES=1: keep the takes already in voices/ (ElevenLabs has no take cache — a re-run re-bills chars)
  if [ "${REUSE_VOICES:-0}" = 1 ] && [ -f "$PJ/voices/dur.json" ]; then
    echo "tts: REUSE_VOICES=1 — reusing $PJ/voices (no new synthesis)"
  else
    python3 "$CTL/cli.py" tts --project "$PJ" --provider "$PROV" --fallback "" --pacing "$PACING" --speed "$FINANCE_TTS_SPEED"
  fi
  if [ "$PROV" = elevenlabs ] && [ -n "${ELEVENLABS_VOICE_ID:-}" ]; then  # wrong narrator = stop before render
    python3 -c "import json,sys;d=json.load(open(sys.argv[1]));v=d.get('voice');sys.exit(0 if v==sys.argv[2] else 'EL voice mismatch: '+str(v))" "$PJ/voices/spoken.json" "$ELEVENLABS_VOICE_ID"
  fi
  # 3) schedule (ceiling only) + P1 beats/keywords + pictogram edl_runtime
  local OUTRO=(); [ "$V3" = 1 ] && OUTRO=(--outro "${OUTRO_SEC:-1.5}")
  python3 "$CTL/cli.py" schedule --project "$PJ" --require-vo --pacing "$PACING" "${OUTRO[@]}"
  node core/render/events.mjs "$PJ" >/dev/null
  if [ "$MUSIC_LIBRARY" != none ]; then
    python3 "$CTL/cli.py" mix --project "$PJ" --preset soft-pulse --bed-source stepaudio --music-library "$MUSIC_LIBRARY"
  else
    python3 "$CTL/cli.py" mix --project "$PJ" --preset soft-pulse
  fi
  # frame size from the plan aspect (16:9 → 1920x1080, the renderer default; 9:16 → 1080x1920)
  local SIZE; SIZE=$(PYTHONPATH="$CTL" python3 -c "import sys, common; from pathlib import Path; print(common.size_arg(common.project_size(Path(sys.argv[1]))))" "$PJ")
  node core/render/video.mjs "$PJ" --size "$SIZE" --fps 30 --workers 4 --out "$PJ/out/video.mp4"
  bash core/render/mux.sh "$PJ/out/video.mp4" "$PJ/out/mix.wav" "$OUT" 30 1
  python3 "$CTL/vo_srt.py" --project "$PJ" --out "${OUT%.mp4}.srt"
  # 4) gates — one film at a time (parallel whisper runs gave hallucinated ASR)
  python3 "$CTL/cli.py" visual-check --project "$PJ" --media "$OUT" --no-semantic
  python3 "$CTL/pacing_check.py" --project "$PJ" --media "$OUT" --pacing "$PACING" || echo "pacing FAIL → STEPS.md §Rework"
  if [ "$V3" = 1 ]; then python3 "$CTL/visual_dupe.py" --project "$PJ" || echo "visual-dupe FAIL → STEPS.md §Rework"; fi
  python3 "$CTL/cli.py" quality --project "$PJ" --media "$OUT" --delivery --asr-mode auto
  # delivered finance-v003 film joins the series index (next films are checked against it)
  if [ "$V3" = 1 ] && [ "$HO" = 1 ]; then python3 "$CTL/visual_dupe.py" --project "$PJ" --register >/dev/null || true; fi
  # 5) handoffs: OpenFilm + HyperFrames + Premiere xmeml (timebase probed from the master)
  if [ "$HO" = 1 ]; then
    python3 "$CTL/cli.py" handoff --project "$PJ" --target all --name "$NM" --extract-shots --lint --no-budget
  fi
  echo "OK $NM → $OUT ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")s)"
}

el_plan() {  # src-plan dst-plan voice
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
p["voice"]["provider"], p["voice"]["voiceId"] = "elevenlabs", sys.argv[3]
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(p, ensure_ascii=False, indent=2) + "\n")
PY
}
if [ "$TTS_PROVIDER" = elevenlabs ]; then
  EL_VOICE=${EL_VOICE:-${DRAFT_VOICE:-TKaUqol7GKx4m7enpCpP}}
  el_plan "$SRC/plan.json" "$SRC/plan.el.json" "$EL_VOICE"
  # the provider reads the voice from env (plan voiceId alone is not used → would fall back to Rachel)
  ELEVENLABS_VOICE_ID=$EL_VOICE WORDFILM_TTS_ELEVENLABS_MODEL=${EL_MODEL:-eleven_v4} \
    build_one "$SRC/plan.el.json" "$P" "$NAME" elevenlabs 1
  python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print('ElevenLabs chars this film:',d.get('chars'))" "$P/voices/spoken.json" 2>/dev/null || true
  exit 0
fi
build_one "$SRC/plan.json" "$P" "$NAME" stepaudio 1

if [ "${EL_BACKUP:-0}" = 1 ]; then
  # Same approved lines, ElevenLabs voice. say-fields stay as approved; the provider spells numbers
  # in Chinese words (97.5% → 百分之九十七点五) and joins letter spellings (E-S → ES) for eleven_v4.
  el_plan "$SRC/plan.json" "$SRC/plan.el.json" "${EL_VOICE:-uDnTdfbGbx3cHHFnY83O}"
  ELEVENLABS_VOICE_ID=${EL_VOICE:-uDnTdfbGbx3cHHFnY83O} WORDFILM_TTS_ELEVENLABS_MODEL=${EL_MODEL:-eleven_v4} build_one "$SRC/plan.el.json" "$P/backup-el" "$NAME-el" elevenlabs 0 "$P/$NAME-el.mp4"
fi
