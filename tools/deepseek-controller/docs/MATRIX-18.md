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

1. **M14** fuli×caption×flash: cut VO/copy to fit 30s (schedule 32.25s) + ASR lexicon 复立→复利, re-render, re-gate
2. **M16** fensan×caption×flash: trim copy to fit 30s (schedule 31.25s), re-render, re-gate
3. Optional polish: Caption Commons packs for diversify/compound cells; Swiss German-poster literal rebrand
4. See [BUDGET.md](BUDGET.md) · [EXPERTS.md](EXPERTS.md)

## Related

- [E2E-swiss.md](E2E-swiss.md) · [E2E-pictogram.md](E2E-pictogram.md) · [E2E-caption.md](E2E-caption.md)
- [STUDIO.md](STUDIO.md) · [TTS.md](TTS.md) · [MUSIC-BED.md](MUSIC-BED.md) · [nle-handoff.md](nle-handoff.md)
- [BUDGET.md](BUDGET.md) · [EXPERTS.md](EXPERTS.md)
- `/workspace/films/COMPARE-multi-style-ds.md` · `showcase/COMPARE.md`
