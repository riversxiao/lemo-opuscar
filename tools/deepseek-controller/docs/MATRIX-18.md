# 18-film comparison matrix (full factorial)

**Epic:** same vocab card × style × path — full factorial 3×3×2 = **18** cells.  
**Library:** this repo (`$LIB` = the WordFilm checkout; the recorded runs used a clone under `/workspace`)  
**Film root:** `/workspace/films/`  
**Canonical dir:** `/workspace/films/matrix-{topic}-{style}-{path}/`  
**Tracker:** [`../fixtures/matrix-18.json`](../fixtures/matrix-18.json) · CLI: `python3 tools/deepseek-controller/cli.py matrix`

Timezone labels below are **Asia/Shanghai (UTC+8)**.

## Dimensions

| Axis | Values | Meaning |
|---|---|---|
| **topic** | `fuli` 复利 · `fensan` 分散投资 · `liudong` 流动性 | One vocab card / 一词一图 |
| **style** | `swiss` · `pictogram` · `caption` | Engine style family |
| **path** | `controller` · `flash` | Baseline deepseek-controller scaffold/adapt/delivery **vs** DeepSeek Flash (OpenCode) agent edit |

Full factorial **3×3×2 = 18**, filled in two epics:

- **M01–M12** (first epic): for each topic, **native style × {controller, flash}** (6) + **two non-native styles × controller** (6)
- **M13–M18** (this epic, 2026-10-29 Asia/Shanghai): **cross-style × flash** — DeepSeek Flash (OpenCode `deepseek/deepseek-flash`, DeepSeek official API only) retargets each topic onto its two non-native styles

`cli.py matrix` refuses a tracker that is not the full factorial (cell count ≠ 18, duplicate topic×style×path, or duplicate id).

Native style per topic (historical showcase diagonal):

| topic | native style |
|---|---|
| fuli | swiss |
| fensan | pictogram |
| liudong | caption |

## Cells (M01–M18)

| ID | topic | style | path | role | status | film / alias |
|---|---|---|---|---|---|---|
| M01 | fuli | swiss | controller | native | **delivery-pass** | `/workspace/films/fuli-controller-e2e` → target `matrix-fuli-swiss-controller` |
| M02 | fuli | swiss | flash | native | **delivery-pass** | `/workspace/films/fuli-swiss-ds-v001` (plan retrofit; audio-only TP loudnorm) |
| M03 | fuli | pictogram | controller | cross | **delivery-pass** | `/workspace/films/matrix-fuli-pictogram-controller` (finance-v001) |
| M04 | fuli | caption | controller | cross | **delivery-pass** | `/workspace/films/matrix-fuli-caption-controller` (compound-v001) |
| M05 | fensan | pictogram | controller | native | **delivery-pass** | `/workspace/films/fensan-controller-e2e` |
| M06 | fensan | pictogram | flash | native | **delivery-pass** | `/workspace/films/fensan-pictogram-ds-v001` (music+SRT; `voice.provider=none`) |
| M07 | fensan | swiss | controller | cross | **delivery-pass** | `/workspace/films/matrix-fensan-swiss-controller` |
| M08 | fensan | caption | controller | cross | **delivery-pass** | `/workspace/films/matrix-fensan-caption-controller` (diversify-v001) |
| M09 | liudong | caption | controller | native | **delivery-pass** | `/workspace/films/liudong-controller-e2e` |
| M10 | liudong | caption | flash | native | **delivery-pass** | `/workspace/films/liudong-caption-ds-v001` (plan retrofit; ASR lexicon) |
| M11 | liudong | swiss | controller | cross | **delivery-pass** | `/workspace/films/matrix-liudong-swiss-controller` |
| M12 | liudong | pictogram | controller | cross | **delivery-pass** | `/workspace/films/matrix-liudong-pictogram-controller` (finance-v001) |
| M13 | fuli | pictogram | flash | cross | **delivery-pass** | `/workspace/films/matrix-fuli-pictogram-flash` (31.20s music+SRT; edl-beats timeline) |
| M14 | fuli | caption | flash | cross | **muxed** | `/workspace/films/matrix-fuli-caption-flash` (30.00s; schedule 32.25s > 30s + ASR 复利→复立) |
| M15 | fensan | swiss | flash | cross | **delivery-pass** | `/workspace/films/matrix-fensan-swiss-flash` (32.00s; plan normalize) |
| M16 | fensan | caption | flash | cross | **muxed** | `/workspace/films/matrix-fensan-caption-flash` (30.00s; schedule 31.25s > 30s; ASR/readcheck PASS) |
| M17 | liudong | swiss | flash | cross | **delivery-pass** | `/workspace/films/matrix-liudong-swiss-flash` (32.00s; plan normalize) |
| M18 | liudong | pictogram | flash | cross | **delivery-pass** | `/workspace/films/matrix-liudong-pictogram-flash` (31.21s music+SRT; edl-beats timeline) |

**Filled:** all **18/18** · **delivery-pass 16/18** · **muxed 2/18** (M14, M16) (2026-10-29 Asia/Shanghai).

## Cross-style × flash (M13–M18)

Each cell: fresh dir seeded from the **native Flash film of the target style** (engine files byte-identical, outputs removed) → `BRIEF.md` (topic card, allowed/forbidden edits, no reading other film dirs, no websearch, no video models) → one OpenCode run (`--title "AIGC教父-2026-10-29"`, `-s ses_matrix18_<cell>_20261029`) → mux → `content/plan.json` → `cli.py quality --delivery` → `evidence/quality-mux-delivery.json`.

| Seed (target style) | Seed dir | Locked / verified identical |
|---|---|---|
| pictogram | `fensan-pictogram-ds-v001` | `engine.js`, `poses/*` (scenes.js copy/counts only) |
| swiss | `fuli-swiss-ds-v001` (DUR=32) | `ease.js`, `main.js`, `index.html` |
| caption | `liudong-caption-ds-v001` (DUR=30) | ease + draw infra in `main.js` (eo/ei/eio/back/ledger/veil/num/camPush/capCard), `tools/*` |

Cost = DeepSeek `/user/balance` delta (CNY, billed) per run; tokens + OpenCode USD estimate from `opencode.db`. Ledger rows in `fixtures/budget-ledger.jsonl` (`--cny`, `meta.sessionId`).

| ID | mp4 | dur | gate | ¥ (balance Δ) | tokens in/out |
|---|---|---|---|---|---|
| M13 | `matrix-fuli-pictogram-flash.mp4` | 31.20s | `--delivery` PASS (−13.8 LUFS / −2.4 dBTP; readcheck/ASR N/A, no VO) | ¥0.50 | 86,629 / 23,598 |
| M14 | `matrix-fuli-caption-flash.mp4` | 30.00s | **FAIL**: schedule_fits_target (32.25s > 30s), asr_check (L05 复利→复立 residual); loudness/readcheck PASS | ¥0.81 | 86,186 / 22,592 |
| M15 | `matrix-fensan-swiss-flash.mp4` | 32.00s | `--delivery` PASS (−14.4 / −1.0; ASR 0 mismatches) | ¥1.18 | 88,622 / 32,365 |
| M16 | `matrix-fensan-caption-flash.mp4` | 30.00s | **FAIL**: schedule_fits_target only (31.25s > 30s); loudness/readcheck/ASR PASS | ¥0.86 | 90,751 / 24,637 |
| M17 | `matrix-liudong-swiss-flash.mp4` | 32.00s | `--delivery` PASS (−14.1 / −1.1; ASR 0 mismatches) | ¥0.67 | 81,011 / 26,691 |
| M18 | `matrix-liudong-pictogram-flash.mp4` | 31.21s | `--delivery` PASS (−14.4 / −4.3; readcheck/ASR N/A, no VO) | ¥0.45 | 114,408 / 23,247 |

**Total:** balance ¥14.94 → ¥10.33 = **¥4.61** (per-cell deltas sum ¥4.47; ¥0.14 late-billed between runs, not attributed per cell). Cap was ¥10.

Retrofits (metadata / evidence only, no re-render):

- **plan normalize** (M15, M16, M17): Flash `plan.json` had off-schema keys/roles/motionPresets → mapped to `plan.schema.json`; raw kept as `content/plan.flash-raw.json`, change log `evidence/plan-normalize.json`.
- **pictogram timeline** (M13, M18): read-time scheduler treats catalog-card descriptions as read text (49.2s for M13) → `timeline.parsed.json` from EDL beats × 0.4s, source `edl-beats-retrofit` (M06 precedent); diagnostic kept.
- **caption voices**: `audio/vo/*` copied to `voices/`; `timeline.json` backed up/restored around `schedule` (caption-news writer overwrites it).

Honest misses: Flash wrote longer caption copy than the locked 30s caption timeline allows. No K-scale / no fake pass — M14/M16 stay **muxed** until copy is cut and re-rendered.

Root-cause fixes landed (no re-render yet, status unchanged):

- **Overrun guard.** The schedule already failed (32.25s / 31.25s > 30s), but nothing stopped the pipeline from applying the cues and rendering anyway: the Flash run backed up/restored `timeline.json` around `schedule` and the render went ahead. Now `schedule` for caption-news also checks the copy against the locked `main.js` `DUR` (even when `targetDurationSec` or `--target` would allow more) and names the shots to trim, e.g. `copy overruns the locked caption-news timeline by 2.25s: content 32.25s > locked 30.00s; trim shots: c7 (30.00-32.25s)`. `apply_caption_timeline.py` refuses a failed or overrunning `timeline.parsed.json` unless `--force` (diagnostics only). Covered by `tests/test_mvp.sh` (32.25s plan against a 30s lock).
- **ASR lexicon.** `asr_homophones.json` now lists 复立 in the 复利 class, so `--asr-mode=zh-homophone-tolerant` clears the M14 L05 residual (复利 heard as 复立). Covered by `tests/test_mvp.sh`.
- **Trimmed copy (in-repo).** [`../fixtures/matrix-18/m14-trimmed/`](../fixtures/matrix-18/m14-trimmed/) and [`../fixtures/matrix-18/m16-trimmed/`](../fixtures/matrix-18/m16-trimmed/) hold the cut copy as the controller writes it (`content/plan.json`, `lines.json` with DIALOGUE.md `function`/`want`, `timeline_content.json`, ...) plus `voices/dur.json` measured from edge `zh-CN-YunxiNeural` at +0% (2026-10-29). See **M14 / M16 trimmed copy** below.
- **Still to do:** M14 and M16 need a re-render with the trimmed copy (and a fresh `--delivery` gate) on a machine that has the film files under the films root (`$WORDFILM_FILMS`, `<repo>/films` or `/workspace/films`). Until then they stay **muxed**: the fixtures prove the copy fits, not that the film passes.

### M14 / M16 trimmed copy

Budget: the seed `main.js` locks `DUR = 30`. Under the default `standard` pacing profile (`pacing_profile.py`, docs/PACING.md) each caption shot costs its VO plus 0.40s (enter 0.15 + settle 0.15 + exit 0.10), snapped up to the 0.25s grid; the end card (c6, no VO) takes its reading time on the grid, and the schedule adds the profile's 1.0s end-card outro after it. The target is a ceiling: nothing pads the film up to 30s. The cut copy was written when a shot cost VO + 0.95s (enter 0.35 + settle 0.35 + exit 0.25) and the schedule padded to the target; the "old rule" column keeps those numbers. `dialogue-check` estimates at the profile's 5.3 字/s, so it passes these lines both with `--target 20` and against the whole 30s.

| cell | VO | 字 | measured VO | content, old rule | content (standard pacing) | scheduled (with outro) | dialogue-check `--target 20` |
|---|---|---|---|---|---|---|---|
| M14 fuli | 一块钱存着不动，三十年后会变成多少？ / 利息滚回本金，第二年连利息一起生利息。 / 按年利率百分之七算，三十年后接近七块六。 / 中途取出花掉，后面的雪球就滚不动了。 / 复利靠的不是押对一次，是时间不被打断。 | 84 | 22.34s | 29.50s (was 32.25s), padded to 30.00s | **26.25s** | 27.25s | PASS |
| M16 fensan | 分散投资，不是把鸡蛋随手乱撒。 / 股票、债券和现金，涨跌往往不同步。 / 全押一类资产，一次下跌就全部砸中。 / 多配一类走势不同的资产，就少一次同时踩坑。 / 分散省不掉风险，但能给你留下回旋余地。 | 78 | 21.41s | 29.00s (was 31.25s), padded to 30.00s | **25.50s** | 26.50s | PASS |

The measured VO is edge at +0%; a re-render now speaks at the profile's edge rate (+10%), so the real lines come out shorter still.

The 7% figure is arithmetic (1.07^30 ≈ 7.61). `tests/test_mvp.sh` (21c) validates both plans, runs `dialogue-check --target 20` and `schedule --require-vo` against a `DUR = 30` lock and requires content ≤ 29.50s, scheduled ≤ 30s with no pad and no lock overrun.

Re-render on a machine with the films (run from the library root; `F` is the films root):

```bash
LIB=$(git rev-parse --show-toplevel); cd "$LIB"
F=${WORDFILM_FILMS:-$LIB/films}             # or /workspace/films
CTL=tools/deepseek-controller
for cell in m14:fuli m16:fensan; do
  id=${cell%%:*}; topic=${cell#*:}
  P="$F/matrix-$topic-caption-flash"
  mkdir -p "$P/content/flash-overrun" && cp -f "$P"/content/*.json "$P/content/flash-overrun/"   # keep the 32.25s / 31.25s copy as evidence
  cp -f "$CTL/fixtures/matrix-18/$id-trimmed/content/"{plan,lines,timeline_content}.json "$P/content/"
  python3 $CTL/cli.py validate "$P/content/plan.json"
  python3 $CTL/cli.py dialogue-check --project "$P" --target 20
  python3 $CTL/cli.py dialogue-loop --project "$P" --target 20 --item "matrix $id trimmed"   # needs DEEPSEEK_API_KEY; tts refuses lines without a loop PASS
  python3 $CTL/cli.py tts --project "$P" --provider edge --voice zh-CN-YunxiNeural --target 20
  mkdir -p "$P/audio/vo" && cp -f "$P"/voices/*.wav "$P/voices/dur.json" "$P/audio/vo/"
  python3 $CTL/post_tts.py --project "$P"
  python3 $CTL/cli.py schedule --project "$P" --require-vo     # must print OK; content <= 30s, no lock overrun
  python3 $CTL/mix_vo_only.py --project "$P"
  node core/render/still.mjs "$P" 1.0 12.0 24.0 29.0 --out "$P/out/still" --prefix k_
  node core/render/video.mjs "$P" --fps 30 --workers 3 --out "$P/out/video.mp4"
  sh core/render/mux.sh "$P/out/video.mp4" "$P/out/mix.wav" "$P/matrix-$topic-caption-flash.mp4" 30 0
  python3 $CTL/cli.py quality --project "$P" --media "$P/matrix-$topic-caption-flash.mp4" \
    --delivery --asr-mode zh-homophone-tolerant
done
```

Checked here (2026-10-29, no films, no DeepSeek key): `validate`, `dialogue-check --target 20` and `schedule` pass on both fixtures; `cli.py tts` stops at the dialogue-loop gate without a key, as designed. If the loop revises a line, keep it within the same 字 count or `schedule` will fail on the lock. Compare the new `voices/dur.json` with the fixture: a different Edge voice build can move a line by a few tenths of a second, and `schedule` will name the shot to cut if it does. When `quality --delivery` passes, set the cell to `delivery-pass` in [`../fixtures/matrix-18.json`](../fixtures/matrix-18.json) with the evidence path and update the tables above.

### Improved siblings (not separate matrix cells)

| Better cut | Related cell | Why |
|---|---|---|
| `fensan-pictogram-finance-v001` | M05 | style-unlock intro; still delivery-pass |
| `liudong-caption-liquidity-v001` | M09 | VO↔picture aligned; 32s; delivery-pass |

Keep e2e paths as the **locked baseline** cell aliases; siblings are notes only.

## Path convention

```
/workspace/films/matrix-{topic}-{style}-{path}/
  README.md          # points at plan + acceptance
  content/plan.json  # when scaffolded
  {name}.mp4         # final mux
  evidence/quality-*-delivery.json
```

Until a cell is scaffolded under `matrix-…`, the tracker may **alias** an existing film dir (absolute path). Aliases count as filled for status; renaming/symlinking is optional polish.

## Status values

| status | meaning |
|---|---|
| `empty` | not started |
| `scaffold` | plan + project dir, no mux |
| `muxed` | mp4 exists; quality gate not run or not pass |
| `delivery-pass` | `cli.py quality --delivery` → `deliveryAllowed=true` |
| `blocked` | known blocker (note required) |

## Acceptance per cell

1. Plan validates (`cli.py validate`)
2. Muxed mp4 under film root (alias OK)
3. For **controller** cells: `quality --delivery` PASS  
4. For **flash** cells: plan.json + `quality --delivery` PASS (same gate; music-only OK when `voice.provider=none`)
5. No edits to locked engine cores unless the cell is an explicit style-unlock sibling (out of matrix id)

## CLI

```bash
python3 tools/deepseek-controller/cli.py matrix           # table
python3 tools/deepseek-controller/cli.py matrix --json    # raw tracker
python3 tools/deepseek-controller/cli.py matrix --filled   # only non-empty
python3 tools/deepseek-controller/cli.py matrix --id M01   # one cell
python3 tools/deepseek-controller/cli.py matrix --path flash  # only flash cells
```

## Proof slice (2026-10-29 Asia/Shanghai)

1. Documented existing delivery films into M01 / M05 / M09; Flash natives M02 / M06 / M10 as `muxed`.
2. Cross-style controller M03/M04/M07 then M08/M11/M12 filled with full still→video→mux + `--delivery` PASS.
3. **Flash promotion:** M02/M06/M10 gained `content/plan.json` + evidence; M02 audio-only loudnorm (TP −0.9 → ≤−1); M06 music+SRT `provider=none`; M10 ASR zh-homophone lexicon for Whisper finance drift. **12/12 delivery-pass.**
4. **Cross × flash** M13–M18 (DeepSeek official, ¥4.61): 4 delivery-pass, 2 muxed (caption 30s overflow).

## Next knife (exact cells)

**Matrix 18/18 filled, 16/18 delivery-pass** (2026-10-29 Asia/Shanghai). Follow-ups:

1. **M14** fuli×caption×flash: copy cut to fit 30s (was 32.25s, now 29.50s under the old shot overhead and 26.25s under standard pacing: `fixtures/matrix-18/m14-trimmed/`); re-render and re-gate per **M14 / M16 trimmed copy** above. ASR lexicon 复立→复利 is in `asr_homophones.json`.
2. **M16** fensan×caption×flash: copy cut to fit 30s (was 31.25s, now 29.00s under the old shot overhead and 25.50s under standard pacing: `fixtures/matrix-18/m16-trimmed/`); re-render and re-gate the same way
3. Optional polish: Caption Commons packs for diversify/compound cells; Swiss German-poster literal rebrand
4. See [BUDGET.md](BUDGET.md) · [EXPERTS.md](EXPERTS.md)

## Related

- [E2E-swiss.md](E2E-swiss.md) · [E2E-pictogram.md](E2E-pictogram.md) · [E2E-caption.md](E2E-caption.md)
- [STUDIO.md](STUDIO.md) · [TTS.md](TTS.md) · [MUSIC-BED.md](MUSIC-BED.md) · [nle-handoff.md](nle-handoff.md)
- [BUDGET.md](BUDGET.md) · [EXPERTS.md](EXPERTS.md)
- `/workspace/films/COMPARE-multi-style-ds.md` · `showcase/COMPARE.md`
