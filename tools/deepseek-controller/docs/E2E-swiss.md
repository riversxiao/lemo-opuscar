# E2E dry path — Swiss fixture (2026-10-28)

Fixture: `fixtures/plan-swiss-motion.json` · base `59f62e4` · project: `/workspace/films/fuli-controller-e2e` (box, not in Git).
Scope: scaffold → edge-tts VO → schedule → quality. **No Playwright render, no mux, no MP4 — not a deliverable film.**

## Steps
```bash
P=/workspace/films/fuli-controller-e2e
python3 tools/deepseek-controller/cli.py scaffold tools/deepseek-controller/fixtures/plan-swiss-motion.json -o $P --lib "$PWD"
python3 core/tts/tts_zh.py $P/content/lines.json $P/voices      # writes l*.wav + voices/dur.json
python3 tools/deepseek-controller/cli.py schedule --project $P --require-vo
python3 tools/deepseek-controller/zh_words_rel.py --project $P  # new: zh sentence-level words_rel.json
python3 tools/deepseek-controller/cli.py quality --project $P
```
Deps needed on the box: `soundfile`, `soxr`, `faster-whisper` (pip). Swiss `fonts/*.ttf` are gitignored — fetched Archivo-VF / DMSerifDisplay / UnifrakturMaguntia from google/fonts into the project.

## dur.json contract
`voices/dur.json` = `{lineId: seconds}`; `tts_zh.py` already writes it (fallback: ffprobe of `voices/<id>.wav`). No glue change needed.

## Measured VO (zh-CN-YunxiNeural, edge-tts)
| line | shot | sec |
|---|---|---|
| l1 | s1 | 2.054 |
| l2 | s2 | 2.716 |
| l3 | s3 | 3.101 |
| l4 | s4 | 2.554 |
| l5 | s5 | 2.653 |

## Schedule
- Gate check first (no VO yet): `--require-vo` → **FAIL**, 5× "missing VO duration", exit 1 (correct).
- With VO: **PASS**, 20.75 s ≤ 32 s target, grid 0.25 s. Shots s1 3.25 · s2 3.75 · s3 4.25 · s4 3.75 · s5 3.75 · s6 2.00 (end, no VO). Not over target → **no fixture trimming done**.
- Note: plan targets 32 s but schedule yields 20.75 s; the controller doesn't pad. Decide whether to pad holds/end card or lower `targetDuration`.

## quality.json (content stage) — overall **FAIL**, deliveryAllowed=false
| check | status | note |
|---|---|---|
| plan_present | PASS | |
| schedule_fits_target | PASS | 20.75 ≤ 32 |
| ffprobe_media / loudness_ebur128 / media_duration | NOT_CHECKED (optional) | no mp4, expected |
| readcheck | NOT_CHECKED (blocking) | Swiss demo page has no `window.TEXTS(t)` registry → readcheck can't run. Earlier it FAILed on missing fonts and missing `voices/words_rel.json` (fixed by font fetch + `zh_words_rel.py`) |
| asr_check | FAIL (blocking) | whisper small: l3 "本金"→"本经" sim 0.92 < 0.92 (l5 "复利"→"赋利" passed on similarity). Homophone ASR miss, not bad VO; left as FAIL — not overridden |

## Bugs / follow-ups found
1. `tools/words.py` is English-only (crashes on CJK) → added `zh_words_rel.py` (sentence-level timing). Should be called by scaffold/build for zh.
2. Swiss demo lacks `window.TEXTS(t)` → readcheck is permanently NOT_CHECKED; add text registry in an adapter (engine lock stays).
3. `quality` `schedule_fits_target` reported PASS even when `schedule --require-vo` had failed (it reads the diagnostic timeline). Should check the schedule's own pass flag.
4. `quality --project .` used relative path badly for readcheck ("no index.html in '.'"); absolute path works.
5. ASR for zh finance terms: consider `asr` per-line hint or a homophone-tolerant compare (do not just lower threshold).
6. Swiss fonts not shipped (gitignored) — scaffold should fetch or error clearly.

Evidence copies in the project: `evidence/quality-novo.json`, `evidence/timeline-novo.json`, `evidence/quality-final.json`, `evidence/timeline-final.json`.
