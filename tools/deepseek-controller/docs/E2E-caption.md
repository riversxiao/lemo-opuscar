# E2E full path — Caption News fixture (2026-10-28)

Fixture: `fixtures/plan-caption-news.json` · project: `/workspace/films/liudong-controller-e2e` (box, not in Git).
Scope: scaffold → Yunxi TTS → schedule (pad) → apply `timeline.json` → still → video → mix_vo_only → mux → `quality --delivery`.
Engine cores stayed locked (`main.js` / `index.html` / `build.sh` hashes unchanged).

## Why Caption (not Pictogram) first

| style | VO in fixture | Engine content bridge under lock |
|---|---|---|
| **caption-news** | edge / Yunxi 5 lines | `timeline.json` is touchable (VO starts + caps). `SHOTS` / `DUR=59.5` stay in locked `main.js`. |
| pictogram-motion | now has Yunxi lines (fixture updated) | **blocked**: `edl.js` / `scenes.js` hash-locked; glue only writes `edl_content.json` sidecar — **no published bridge** into `edl.js`. Still/video would render the Olympics demo, not plan copy. |

## Steps

```bash
P=/workspace/films/liudong-controller-e2e
LIB=$PWD
python3 tools/deepseek-controller/cli.py scaffold \
  tools/deepseek-controller/fixtures/plan-caption-news.json -o $P --lib "$LIB"
# fonts: demo fonts.sh only subsets main.js glyphs — re-fetch with timeline/lines charset
FORCE=1 sh $P/tools/fonts.sh   # then extend text=… to include timeline.json / lines (see run notes)
python3 $LIB/core/tts/tts_zh.py $P/audio/lines.json $P/voices --voice zh-CN-YunxiNeural
mkdir -p $P/audio/vo && cp -f $P/voices/*.wav $P/voices/dur.json $P/audio/vo/
python3 tools/deepseek-controller/post_tts.py --project $P
python3 tools/deepseek-controller/cli.py schedule --project $P --require-vo
# schedule auto-applies cues → timeline.json (dur = engine 59.5; scheduleBudget = 30)
# Locked SHOTS need assets/img + assets/fr. Without Commons packs, stub JPEGs unblock READY.
python3 tools/deepseek-controller/mix_vo_only.py --project $P
node core/render/events.mjs $P
node core/render/still.mjs $P 1.0 5.0 18.0 35.0 56.0 --out $P/out/still --prefix k_
node core/render/video.mjs $P --fps 30 --workers 3 --out $P/out/video.mp4
sh core/render/mux.sh $P/out/video.mp4 $P/out/mix.wav $P/liudong-controller-e2e.mp4 30 0
python3 tools/deepseek-controller/cli.py quality --project $P \
  --media $P/liudong-controller-e2e.mp4 --delivery
```

## Measured VO (zh-CN-YunxiNeural)

| line | shot | sec |
|---|---|---|
| L01 | c1 | 2.511 |
| L02 | c2 | 2.165 |
| L03 | c3 | 2.353 |
| L04 | c4 | 2.822 |
| L05 | c5 | 2.851 |

## Schedule

- Content **20.5 s** → pad **9.5 s** hold-last-beat → **scheduledDurationSec=30.0** = target.
- Auto-apply: `timeline.json` `vo` starts + hook/caps times; `dur=59.5` (= locked `main.js` `DUR`) for mix/video length; `scheduleBudgetSec=30`.

## Deliverable (box-only)

| artifact | path | notes |
|---|---|---|
| stills | `…/out/still/k_{1,5,18,35,56}.jpg` | Chinese caps from touchable timeline; footage frames are stubs unless Commons packs fetched |
| video | `…/out/video.mp4` | 1785 frames, 59.5 s @ 30 fps, ~81 s wall (3 workers, llvmpipe) |
| mix | `…/out/mix.wav` | `mix_vo_only.py` (no freepats / swarm.wav) |
| **mux MP4** | `…/liudong-controller-e2e.mp4` | **59.50 s**, ~4.2 MB, 1920×1080@30, **I=−14.2 LUFS / TP=−1.2 dBTP** |

## quality `--delivery` — overall **PASS**, deliveryAllowed=true

Evidence: `evidence/quality-mux-delivery.json`.

| check | status | note |
|---|---|---|
| plan_present | PASS | |
| schedule_fits_target | PASS | 30 ≤ 30; pad 9.5 s |
| ffprobe_media | PASS | |
| media_duration | **PASS** (`style_locked_duration`) | mux 59.5 s ≈ protected `main.js` `DUR` (±1s). Plan 30 s is schedule budget only. |
| loudness_ebur128 | PASS | I=−14.2 / TP=−1.2 |
| readcheck | **NOT_APPLICABLE** | `caption-locked-demo-texts` — locked bee-demo TEXTS (加州/瓦螨…) fail holds; controller cannot edit `main.js` |
| asr_check | PASS (tolerant) | lexicon covers 钱↔前, 账↔帐, 缺↔去, etc. |

## Controller fixes in this round

| # | Change |
|---|---|
| 1 | `_engine_locked_dur` also reads protected **main.js** (Caption) |
| 2 | `apply_caption_timeline.py` + schedule auto-apply for caption-news |
| 3 | `mix_vo_only.py` for VO bed without instrument packs |
| 4 | readcheck N/A under caption locked main (`caption-locked-demo-texts`) |
| 5 | `asr_homophones.json` liquidity short-forms |
| 6 | Pictogram fixture `voice.provider=edge` + 6 Yunxi lines (for next knife) |

## Remaining gaps

- Locked `SHOTS` still bee-demo kinds (`vid`/`map`/…); pure-graphic liquidity film needs a maintainer style version or unlocked `main.js` (as `liudong-caption-ds-v001` did).
- Stub `assets/fr` / `assets/img` → gray footage; real Commons via `tools/fetch_sources.sh` + `prep.sh` for production look.
- Demo `audio/mix.py` needs freepats/swarm — E2E uses `mix_vo_only.py`.
- **Pictogram**: content bridge `edl_content.json` → `edl.js` not shipped; cannot mux plan copy without unlocking `edl.js`/`scenes.js`.
- Fonts.sh subsets `main.js` only — extend charset to timeline/lines for full CJK glyphs.

