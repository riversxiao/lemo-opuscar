# E2E dry path — Swiss fixture (2026-10-28)

Fixture: `fixtures/plan-swiss-motion.json` · project: `/workspace/films/fuli-controller-e2e` (box, not in Git).
Scope: scaffold → edge-tts VO → schedule → quality. **No Playwright render, no mux, no MP4 — not a deliverable film.**

## Steps
```bash
P=/workspace/films/fuli-controller-e2e
python3 tools/deepseek-controller/cli.py scaffold tools/deepseek-controller/fixtures/plan-swiss-motion.json -o $P --lib "$PWD"
# scaffold now: fetches fonts/*.ttf + writes voices/words_rel.json for zh
python3 core/tts/tts_zh.py $P/content/lines.json $P/voices      # writes l*.wav + voices/dur.json
python3 tools/deepseek-controller/post_tts.py --project $P       # refresh zh words_rel after TTS
python3 tools/deepseek-controller/cli.py schedule --project $P --require-vo
python3 tools/deepseek-controller/cli.py quality --project $P --require-vo
# optional finance ASR: --asr-mode=zh-homophone-tolerant
```
Deps needed on the box: `soundfile`, `soxr`, `faster-whisper` (pip). Swiss `fonts/*.ttf` are gitignored — **scaffold / `fetch_fonts.py`** pull Archivo-VF / DMSerifDisplay / UnifrakturMaguntia from google/fonts (or `$LEMO_FONT_CACHE`).

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
- Gate check first (no VO yet): `--require-vo` → **FAIL**, 5× "missing VO duration", exit 1 (correct). Timeline now records `ok: false` + `errors`.
- With VO: **PASS**, 20.75 s ≤ 32 s target, grid 0.25 s. Shots s1 3.25 · s2 3.75 · s3 4.25 · s4 3.75 · s5 3.75 · s6 2.00 (end, no VO). Not over target → **no fixture trimming done**.
- Note: plan targets 32 s but schedule yields 20.75 s; the controller doesn't pad. Decide whether to pad holds/end card or lower `targetDuration`.

## quality.json (content stage) — overall **FAIL**, deliveryAllowed=false (original run)
| check | status | note |
|---|---|---|
| plan_present | PASS | |
| schedule_fits_target | PASS (with VO) | 20.75 ≤ 32 |
| ffprobe_media / loudness_ebur128 / media_duration | NOT_CHECKED (optional) | no mp4, expected |
| readcheck | NOT_CHECKED → **NOT_APPLICABLE** after fix | Swiss demo page has no `window.TEXTS(t)` registry |
| asr_check | FAIL (strict) | whisper small: l3 "本金"→"本经" sim 0.92 < 0.92. Use `--asr-mode=zh-homophone-tolerant` for lexicon fold PASS with detail |

## Bugs / follow-ups found → fixed

| # | Bug | Fix |
|---|---|---|
| 1 | `tools/words.py` English-only on CJK | `zh_words_rel.py` + scaffold/post_tts/quality auto-path for zh |
| 2 | Swiss demo lacks `window.TEXTS(t)` → eternal NOT_CHECKED | quality marks **NOT_APPLICABLE** `swiss-demo-without-registry` (engine lock stays; known gap) |
| 3 | `quality` `schedule_fits_target` PASS when `schedule --require-vo` failed | timeline writes `ok`/`errors`; quality aligns with require-vo when plan has VO or `--require-vo` |
| 4 | `quality --project .` broke readcheck path | resolve project to absolute before checks |
| 5 | ASR zh finance homophones | `--asr-mode=zh-homophone-tolerant` + `asr_homophones.json`; default remains **strict** (no silent override) |
| 6 | Swiss fonts gitignored | `fetch_fonts.py` + swiss scaffold auto-fetch |

Evidence copies in the project: `evidence/quality-novo.json`, `evidence/timeline-novo.json`, `evidence/quality-final.json`, `evidence/timeline-final.json`.

## Remaining known gaps
- No `window.TEXTS(t)` hook without editing protected `film.js`/`main.js`/`index.html` — maintainer style version needed before readcheck can PASS.
- Schedule does not pad under-target duration to `targetDurationSec`.
- Homophone lexicon is a small finance starter set; extend `asr_homophones.json` as needed.
- Full MP4 / mux / Release not part of this dry path.

## Fixed in `e862a01`
See table above; remaining gaps unchanged.
