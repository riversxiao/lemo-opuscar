# Pacing (节奏) — P0

Central config: `tools/deepseek-controller/pacing_profile.py` (`python3 pacing_profile.py` prints the table).

| profile | cps (字/秒) | edge rate | StepAudio speed | line gap | enter/exit/settle | max intra pause → keep | beat pause | line ≤ | max shot |
|---|---|---|---|---|---|---|---|---|---|
| fast | 5.8 | +20% | 1.18 | 0.15s | 0.12/0.08/0.10 | 0.25 → 0.12s | 0.45s | 20字 | 3.0s |
| standard | 5.3 | +10% | 1.10 | 0.25s | 0.15/0.10/0.15 | 0.35 → 0.18s | 0.6s | 26字 | 4.5s |
| calm | 4.6 | +0% | 1.0 | 0.45s | 0.25/0.15/0.20 | 0.5 → 0.25s | 0.8s | 32字 | 6.0s |

Reference: TV news is about 240–300 字/分 (4–5 字/秒), everyday speech 200–260 字/分. Short-video narration runs faster. 5.3/5.8 are house targets and still need tuning.

## Selection (highest precedence first)
1. CLI `--pacing fast|standard|calm`
2. `plan.json` `"pacing"`
3. env `LEMO_PACING`
4. `plan.json` `content_type`: market → **fast**; concept / personal / english / unknown → **standard**
5. default **standard**

## Duration policy: the target is a ceiling
- `dialogue-check`: FAIL only if the estimate is more than 115% of the target. A short script is fine; don't add words to fill time.
- `schedule`: no hold-last-beat padding by default. `--pad-under-target` restores the legacy behaviour. The only allowed extension is the outro or brand card (`--outro` / plan `outroSec`), capped at **1.5s**.
- `quality`: `padSec` > 1.5s is a **FAIL**.

## TTS
- edge gets `rate` from the profile. StepAudio gets `speed`; precedence is `--speed`, then `LEMO_TTS_STEPAUDIO_SPEED`, then the profile. ElevenLabs is P1.
- StepAudio prompts ask for brisk, crisp narration with keyword stress and no trailing drawl, in one consistent voice. The speaker gate still applies.
- **Pause trim** (`pause_trim.py`) runs after synthesis unless you pass `--no-trim`:
  - An energy-based silence detector finds pauses. Any intra-line pause longer than `maxPauseSec` shrinks to `keepPauseSec`, with an 8ms crossfade.
  - Leading silence is trimmed to 0.03s and trailing silence to 0.06s.
  - Lines with `"beat": true` keep their pauses.
  - `words.json` is remapped. Originals are kept in `voices/_pretrim/` and the report goes to `voices/pause_trim.json`.

## Gate
`pacing_check.py` measures:
- articulation and overall 字/秒, speech ratio
- inter-line gap and intra-line pause
- first-VO and hook-end time
- tail silence, padding
- shot max / sd, frozen-frame max, visual changes per 10s

It writes `evidence/pacing-check.json`. Under `quality --delivery` it is **report-only (WARN, never blocks)** in P0. `--pacing-enforce` makes FAIL-level misses block, which P1 will use for rework.

# P1 — visual rhythm, rework, delivery blockers

## Delivery blockers (generic, every film)
- **True peak**: `core/render/mux.sh` now runs `aresample=192000 → alimiter → aresample=48000` (4× oversampled
  limiter, ceiling `LEMO_TP_CEIL`, default −2.0 dBTP) and re-measures; if TP is still > −1.0 it re-trims.
  `LEMO_TP_LIMIT=0` disables it. Gate stays TP ≤ −1 dBTP.
- **End card without pad**: the scheduler gives the last shot (role end/credits/sting, or the final shot) its own
  outro of `endCardSec` (fast 0.8 / standard 1.0 / calm 1.5 — inside the 1.5 s outro allowance, not counted as pad).
  `readcheck.mjs --end-pad S` (default 0.5) credits text still on the final frame with that hold; such rows are
  marked `*` in the report.

## Visual sub-beats (all styles) — `beats.py` + `core/render/page.mjs`
`cli.py schedule` writes `beats_runtime.json` (opt out `--no-beats`; regenerate with `cli.py beats`).
Shots longer than the profile `maxShotSec` are split into `ceil(dur/max)` sub-beats; boundaries snap to a VO cue start
(±1.2 s) when feasible, else even split, each sub-beat ≥ 0.8 s. page.mjs applies, style-agnostic, a body
`translate+scale` **pull-back** reframe per sub-beat (scale 0.965–0.985, small offsets) — never a push-in, so no text
enters the 5 % title-safe margin (a clamp enforces it), and `window.TEXTS` boxes are remapped so readcheck/OCR stay right.
Honest note: these are reframes of the same composition, not new shots or new on-screen text.
- **Keyword emphasis**: each `{关键词}` in lines.json → a 0.4 s beat (−1.5 % thump + accent-colour border), timed from
  words.json char timing when available, else text ratio; min gap 2.5 s, kept 0.5 s from beat cuts.
- `pacing_check.py` measures `shotMaxSec` on visual beats (`shotSource: beats_runtime`) and reports `editShotMaxSec`.

## Pacing gate → rework (`cli.py pacing-rework`)
FAIL only; WARN is report-only. Max 2 rounds. Per round, visual FAILs only:
shotMax → rebuild beats (0.85× max if beats exist) · changesPer10s → 0.8× max · frozenMaxSec → drift windows only on spans
over the fail threshold. Audio/VO FAILs (speechRatio, gaps…) go to `needsUpstream` (re-TTS / re-schedule), never faked.
Evidence: `evidence/pacing-rework.json`.

## Rhythm dimension (dialogue_loop)
`rhythm_check.py` (deterministic, 台词教父): hook ≤12字 and ends ≤3 s (medium); cap/payoff without `{}` (medium);
≥3 consecutive ≥16字 lines (low, alternation); ≥4 lines within ±2字 (low, monotone); ≥3 clauses or a connective
(而且/并且/同时/另外/以及) (low, one point per line). Findings go into the critic prompt and each round's evidence; the
critic scores `rhythm` per line and per script (gated like other dims when present). Deterministic hits are attached
to lines the critic already flags — no separate hard gate (avoid over-correction).

## ElevenLabs speed
`voice_settings.speed` (ElevenLabs docs: 1.0 normal, recommended 0.7–1.2; not supported on eleven_v4). Clamped to
0.7–1.2, omitted at 1.0 or on eleven_v4*. Per profile `elevenlabsSpeed`, env `LEMO_TTS_ELEVENLABS_SPEED`, or `--speed`.

## Token accounting
`llm_free.FreeFirstClient.call_log` rows carry `step` (script-gen / fact-check / critic rN / reviser rN), provider,
served model, prompt/completion/reasoning/total tokens, latency. `token_measure.py` runs one film's text layer and
writes `evidence/token-usage.json` + `TOKENS.md`.

## Token saving (finance)
- dialogue_loop default **2 rounds** (critic r1 → reviser r1 → critic r2); not PASS → `NEEDS_HUMAN`, no further calls.
  `--max-rounds N` / `DC_DIALOGUE_MAX_ROUNDS`.
- Compact context (default): `RULES_COMPACT` checklist + the film's FACTS + compact lines; reviser gets only flagged
  lines and returns only those; critic output capped (low ≤3, short details). `--full-context` = old behaviour.
- Quota-aware routing (`llm_free.py`): TokenHarbor has no usage API (dashboard only), so every TokenHarbor call's
  tokens go to a local ledger (rolling 7 days; `DC_QUOTA_LEDGER`, else next to `DC_BUDGET_LEDGER`, else
  `~/.cache/wordfilm/tokenharbor-usage.jsonl`). At ≥ `DC_TH_ROUTE_PCT` (0.8) × `DC_TH_WEEKLY_BUDGET` (1,250,000) the
  client puts OpenRouter `nvidia/nemotron-3.5-lightning:free` → `recursive/flint-v1.0:free` first and TokenHarbor last.
  `python3 llm_free.py` prints the current estimate. NVIDIA NIM stays out. Never paid without `--allow-paid`.
