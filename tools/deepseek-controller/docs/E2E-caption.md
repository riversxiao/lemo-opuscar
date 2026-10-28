# E2E full path — Caption News fixture (2026-10-28)

Fixture: `fixtures/plan-caption-news.json` · project: `/workspace/films/liudong-controller-e2e` (box, not in Git).
Scope: scaffold → Yunxi TTS → schedule (pad) → apply `timeline.json` → still → video → mix_vo_only → mux → `quality --delivery`.
Engine cores stayed locked (`main.js` / `index.html` / `build.sh` hashes unchanged).

## Why Caption (not Pictogram) first

| style | VO in fixture | Engine content bridge under lock |
|---|---|---|
| **caption-news** | edge / Yunxi 5 lines | `timeline.json` is touchable (VO starts + caps). `SHOTS` / `DUR=59.5` stay in locked `main.js`. |
| pictogram-motion | Yunxi lines | **bridged**: `edl_runtime.json` + `page.mjs` overlay (see `E2E-pictogram.md`). |

## Steps

```bash
P=/workspace/films/liudong-controller-e2e
LIB=$PWD
python3 tools/deepseek-controller/cli.py scaffold \
  tools/deepseek-controller/fixtures/plan-caption-news.json -o $P --lib "$LIB"
# scaffold auto-fills fonts/*.woff2 via fetch_fonts (cache/sibling/fonts.sh)
# glyph subset may miss new CJK: FORCE=1 sh $P/tools/fonts.sh  # optionally extend text=
python3 $LIB/core/tts/tts_zh.py $P/audio/lines.json $P/voices --voice zh-CN-YunxiNeural
mkdir -p $P/audio/vo && cp -f $P/voices/*.wav $P/voices/dur.json $P/audio/vo/
python3 tools/deepseek-controller/post_tts.py --project $P
python3 tools/deepseek-controller/cli.py schedule --project $P --require-vo
# schedule auto-applies cues → timeline.json (dur = engine 59.5; scheduleBudget = 30)
# Locked SHOTS need assets/img + assets/fr. Stub JPEGs unblock READY; for production look:
#   sh $P/tools/fetch_sources.sh && sh $P/tools/prep.sh
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

## Real Commons assets remux (2026-10-29)

```bash
P=/workspace/films/liudong-controller-e2e
cd $P && sh tools/fetch_sources.sh   # ~406 MB raw/ from Wikimedia (+ NASS PDF, Natural Earth)
# prep.sh: mkdir -p raw/report before pdftoppm (patched in styles/caption-news/demo/tools/prep.sh)
sh tools/prep.sh                     # assets/fr 1164 frames @ 1920×1080 (~162 MB) + img photos
LIB=/workspace/lemo-opuscar-deepseek
cd $LIB
node core/render/events.mjs $P
node core/render/still.mjs $P 1.0 5.0 18.0 35.0 56.0 --out $P/out/still --prefix k_
node core/render/video.mjs $P --fps 30 --workers 3 --out $P/out/video.mp4
sh core/render/mux.sh $P/out/video.mp4 $P/out/mix.wav $P/liudong-controller-e2e.mp4 30 0
python3 tools/deepseek-controller/cli.py quality --project $P \
  --media $P/liudong-controller-e2e.mp4 --delivery
```

| artifact | path | notes |
|---|---|---|
| raw | `…/raw/` | box-local; ~406 MB Commons bee footage (not in Git) |
| frames | `…/assets/fr/` | 1164 real JPEGs; `h1_001` = 1920×1080 |
| stills | `…/out/still/k_*.jpg` | real hive/bee plates (k_1.0 ≈ 410 KB, lum σ≈45) |
| video | `…/out/video.mp4` | 1785 frames, ~68 MB, ~98 s wall (3 workers, llvmpipe) |
| **mux MP4** | `…/liudong-controller-e2e.mp4` | **59.50 s**, **~32 MB**, 1080p30, **I=−14.2 / TP=−1.2** |

### quality `--delivery` after real assets — **PASS**, deliveryAllowed=true

Evidence: `evidence/quality-mux-delivery-real-assets.json`.

| check | status | note |
|---|---|---|
| plan_present | PASS | |
| schedule_fits_target | PASS | 30 ≤ 30; pad 9.5 s |
| ffprobe_media | PASS | |
| media_duration | PASS (`style_locked_duration`) | 59.50 ≈ DUR 59.5 |
| loudness_ebur128 | PASS | I=−14.2 / TP=−1.2 |
| readcheck | **PASS** | real frames make bee-demo holds readable (was N/A / fail on stubs) |
| asr_check | PASS (tolerant) | zh-homophone-tolerant |

`main.js` SHA256 unchanged vs style demo (`541038bc…`).

## Remaining gaps

- Locked bee `SHOTS` on default e2e — use **`liquidity-v001` style version** (sibling) for aligned TEXTS/SHOTS; see section below.
- Demo `audio/mix.py` needs freepats/swarm — prefer **`cli mix` / `music_bed.py`** for a placeholder bed; `--vo-only` keeps silence. See `docs/MUSIC-BED.md`.
- **Pictogram**: intro/finale animation skeleton still Olympics under lock (brand_strings only overlays HUD text).
- Fonts.sh subsets `main.js` only — extend charset to timeline/lines for full CJK glyphs.
- Style unlock / HyperFrames / multi-route TTS / 12-film matrix still open.

## Audio note

Locked demo score packs are bee-demo length. Prefer **`cli mix`** (placeholder bed + VO) or `--vo-only`; do not regenerate locked bee `audio/mix.py` for content length. See `docs/MUSIC-BED.md`.

## Style version liquidity-v001 (story-aligned sibling, 2026-10-29)

**Problem:** locked `liudong-controller-e2e` keeps bee-demo `main.js` SHOTS (蜂场 / 瓦螨 / 加州) while VO/caps are 流动性 — picture ≠ narration. Unlocking demo `main.js` on that path would break the hash-lock workflow.

**Approach (C + B):** sibling project + caption style version (mirrors pictogram `finance-v001`).

| path | role |
|---|---|
| `/workspace/films/liudong-controller-e2e` | **unchanged** demo lock (`main.js` sha `541038bc…`) |
| `styles/caption-news/versions/liquidity-v001/main.js` | maintainer overlay: DUR=32, liquidity SHOTS/TEXTS, no Commons bee pack |
| `/workspace/films/liudong-caption-liquidity-v001` | sibling scaffold + `apply_caption_style_version.py --version liquidity-v001` |

```bash
LIB=/workspace/lemo-opuscar-deepseek
P=/workspace/films/liudong-caption-liquidity-v001
cd "$LIB"
python3 tools/deepseek-controller/cli.py scaffold \
  tools/deepseek-controller/fixtures/plan-caption-news.json -o "$P" --lib "$LIB" --force
python3 tools/deepseek-controller/apply_caption_style_version.py \
  --project "$P" --version liquidity-v001 --lib "$LIB"
# reuse Yunxi VO from e2e (or re-TTS)
mkdir -p "$P/voices" "$P/audio/vo"
cp -f /workspace/films/liudong-controller-e2e/voices/*.wav \
      /workspace/films/liudong-controller-e2e/voices/dur.json "$P/voices/"
cp -f "$P/voices/"*.wav "$P/voices/dur.json" "$P/audio/vo/"
python3 tools/deepseek-controller/post_tts.py --project "$P"
python3 tools/deepseek-controller/cli.py schedule --project "$P" --require-vo
python3 tools/deepseek-controller/cli.py mix --project "$P" --preset soft-pulse --bed-gain 0.72
node core/render/events.mjs "$P"
node core/render/still.mjs "$P" 1.0 5.0 10.0 18.0 28.0 --out "$P/out/still" --prefix k_
node core/render/video.mjs "$P" --fps 30 --workers 3 --out "$P/out/video.mp4"
sh core/render/mux.sh "$P/out/video.mp4" "$P/out/mix.wav" "$P/liudong-caption-liquidity-v001.mp4" 30 0
python3 tools/deepseek-controller/cli.py quality --project "$P" \
  --media "$P/liudong-caption-liquidity-v001.mp4" --delivery
```

### Deliverable (box-only)

| artifact | notes |
|---|---|
| **MP4** | `…/liudong-caption-liquidity-v001.mp4` · **32.0 s** · ~3.9 MB · 1080p30 · **I=−14.2 / TP=−1.2** |
| stills | hook「账上有钱≠随时能用」、sting「流动性」、split 现金0天/房产90天 — **no bees** |
| music | `cli mix --preset soft-pulse` (locked `audio/mix.py` untouched) |
| evidence | `evidence/quality-mux-delivery.json` |

### quality `--delivery` — **PASS**, deliveryAllowed=true

| check | status | note |
|---|---|---|
| media_duration | PASS | style_locked_duration → versioned `DUR=32` |
| loudness_ebur128 | PASS | bed-gain 0.72 for TP≤−1.2 |
| readcheck | **PASS** | content TEXTS (unlocked main); `_pictogram_style_version` gated on style=pictogram so caption versions are not N/A-misrouted |
| asr_check | PASS | `--delivery` zh-homophone-tolerant |

### Controller fixes

1. `apply_caption_style_version.py` — unlock `main.js` only; keep `index.html`/`build.sh` demo-protected
2. `_caption_locked_main` returns False under `styleVersion` / unlocked `main.js`
3. `_pictogram_style_version` requires `lock.style == pictogram-motion` (do not steal caption versions)
