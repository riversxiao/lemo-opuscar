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
