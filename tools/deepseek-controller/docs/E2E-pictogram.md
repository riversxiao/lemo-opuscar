# E2E full path — Pictogram Motion fixture (2026-10-28)

Fixture: `fixtures/plan-pictogram-motion.json` · project: `/workspace/films/fensan-controller-e2e` (box, not in Git).
Scope: scaffold → Yunxi TTS → schedule (pad) → `apply_pictogram_edl` → mix_vo_only → still → video → mux → `quality --delivery`.
**Engine cores stayed locked** (`engine.js` / `edl.js` / `scenes.js` / `index.html` / `render.mjs` / `shot.mjs` hashes unchanged).

## Content bridge (no unlock)

| piece | role |
|---|---|
| `content/edl_content.json` | Adapt output (plan shots → pictogram kinds/poses) |
| `apply_pictogram_edl.py` | Compiles schedule → **`edl_runtime.json`** + `timeline.json` (VO bed) |
| `core/render/page.mjs` | After `window.READY`, if `edl_runtime.json` exists: replace `window.EDL` / `window.DUR`, **re-eval `scenes.js`** so `SH`/`CARDS` rebuild; optional `brand_strings.json` rewrites Olympics *literals* in the eval'd source |
| `brand_strings.json` | Touchable map from apply_pictogram_edl (topic → HUD/intro/finale labels + hudTicks) |
| Locked `edl.js` / `scenes.js` | Byte-identical to demo; animation structure (rings / sport-grid) remains Olympics-shaped |

Card/chapter copy and timing come from the plan (e.g. still `k_9.0.jpg` = **STOCKS / 股票**).
`brand_strings.json` rewrites HUD/intro/finale Olympics *literals* at eval time (e.g. AICHI-NAGOYA → DIVERSIFY); hudTicks follows card count. Animation structure stays demo-shaped — readcheck **NOT_APPLICABLE** (`pictogram-locked-demo-texts`).

Pose aliases: `stand→golf`, `point→fencing`, `group→relay` (manifest allowlist names that are not in `poses/*`).

## Steps

```bash
P=/workspace/films/fensan-controller-e2e
LIB=$PWD
python3 tools/deepseek-controller/cli.py scaffold \
  tools/deepseek-controller/fixtures/plan-pictogram-motion.json -o $P --lib "$LIB" --force
# scaffold auto-fetches OFL .ttf (or copies $LEMO_FONT_CACHE / sibling films)
# manual: python3 tools/deepseek-controller/fetch_fonts.py --project $P --style pictogram-motion
python3 core/tts/tts_zh.py $P/lines.json $P/voices --voice zh-CN-YunxiNeural
python3 tools/deepseek-controller/post_tts.py --project $P
python3 tools/deepseek-controller/cli.py schedule --project $P --require-vo
# schedule auto-runs apply_pictogram_edl → edl_runtime.json + timeline.json
python3 tools/deepseek-controller/mix_vo_only.py --project $P
node core/render/still.mjs $P 1.0 9.0 12.5 16.5 20.5 28.0 --out $P/out/still --prefix k_
node core/render/video.mjs $P --fps 24 --workers 3 --out $P/out/video.mp4
sh core/render/mux.sh $P/out/video.mp4 $P/out/mix.wav $P/fensan-controller-e2e.mp4 24 0
python3 tools/deepseek-controller/cli.py quality --project $P \
  --media $P/fensan-controller-e2e.mp4 --delivery
```

## Measured VO (zh-CN-YunxiNeural)

| line | shot | sec |
|---|---|---|
| L01 | p0 | 2.625 |
| L02 | p1 | 3.792 |
| L03 | p2 | 2.157 |
| L04 | p3 | 2.370 |
| L05 | p4 | 2.692 |
| L06 | p5 | 3.210 |

## Schedule

- Content **29.2 s** → pad **2.8 s** hold-last-beat → **scheduledDurationSec=32.0** = target.
- Runtime EDL `DUR=32`; picture length is content-driven under the overlay (locked `edl.js` still encodes Olympics 163.6 s on disk).

## Deliverable (box-only)

| artifact | path | notes |
|---|---|---|
| stills | `…/out/still/k_{1,9,12.5,16.5,20.5,28}.jpg` | Plan cards; **HUD = DIVERSIFY** (brand_strings) |
| brand spot | `…/out/still/k_9.0.jpg` (= `out/still-brand/brand_9.0.jpg`) | Top-left **DIVERSIFY / DIVERSIFY 2026**; ASSETS 01/4; STOCKS/股票 |
| video | `…/out/video.mp4` | 768 frames, 32 s @ 24 fps; brand rewrite on every worker |
| mix | `…/out/mix.wav` | `mix_vo_only.py` (reuse OK) |
| **mux MP4** | `…/fensan-controller-e2e.mp4` | **Remuxed 2026-10-29** with brand HUD · **32.00 s**, 1920×1080@24, **I=−14.3 LUFS / TP=−1.2 dBTP** |

Prior mux (pre-`eb40114` still→video) lacked brand overlay; remux after `brand_strings.json` + `page.mjs` rewrite so deliverable matches spot still.

## quality `--delivery` — overall **PASS**, deliveryAllowed=true

Evidence: `evidence/quality-mux-delivery.json` (refreshed after brand remux).

| check | status | note |
|---|---|---|
| plan_present | PASS | |
| schedule_fits_target | PASS | 32 ≤ 32; pad 2.8 s |
| ffprobe_media | PASS | |
| media_duration | **PASS** (`style_locked_duration`) | mux 32 s ≈ `edl_runtime.json` DUR (±1s) |
| loudness_ebur128 | PASS | I=−14.3 / TP=−1.2 |
| readcheck | **NOT_APPLICABLE** | `pictogram-locked-demo-texts` |
| asr_check | PASS (tolerant) | 押注↔压住, 踩坑↔采坑, … |

## Remaining gaps

- Intro/finale **animation structure** (five rings, 43-sport grid, heartbeat) stays Olympics-shaped; `brand_strings` only rewrites string literals + HUD tick count. Full structural rebrand needs a **maintainer style version** (externalize TEXTS / intro layout) or unlock `scenes.js` in a ds-v00x fork — **not done here** (engine hashes stay locked).
- Demo `music/music.py` is Olympics-length / section-asserted — controller E2E uses **`mix_vo_only.py`** (VO bed + silence; mux loudnorm). Do not expect locked `music.py` to track content EDL.
- Fonts are gitignored; scaffold / `fetch_fonts.py` now auto-fetch or copy from `$LEMO_FONT_CACHE`.
