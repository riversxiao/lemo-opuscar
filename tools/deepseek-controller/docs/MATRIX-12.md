# 12-film comparison matrix

**Epic:** same vocab card × style × path — **do not render all 12 in one night.**  
**Library:** `/workspace/lemo-opuscar-deepseek`  
**Film root:** `/workspace/films/`  
**Canonical dir:** `/workspace/films/matrix-{topic}-{style}-{path}/`  
**Tracker:** [`../fixtures/matrix-12.json`](../fixtures/matrix-12.json) · CLI: `python3 tools/deepseek-controller/cli.py matrix`

Timezone labels below are **Asia/Shanghai (UTC+8)**.

## Dimensions

| Axis | Values | Meaning |
|---|---|---|
| **topic** | `fuli` 复利 · `fensan` 分散投资 · `liudong` 流动性 | One vocab card / 一词一图 |
| **style** | `swiss` · `pictogram` · `caption` | Engine style family |
| **path** | `controller` · `flash` | Baseline deepseek-controller scaffold/adapt/delivery **vs** DeepSeek Flash (OpenCode) agent edit |

Full factorial would be **3×3×2 = 18**. This epic’s **12** is the **native pair + cross-style controller** cut:

- For each topic: **native style × {controller, flash}** (6 cells)
- For each topic: **two non-native styles × controller only** (6 cells)
- Cross-style × flash deferred to a follow-up epic (would complete 18)

Native style per topic (historical showcase diagonal):

| topic | native style |
|---|---|
| fuli | swiss |
| fensan | pictogram |
| liudong | caption |

## Cells (M01–M12)

| ID | topic | style | path | role | status | film / alias |
|---|---|---|---|---|---|---|
| M01 | fuli | swiss | controller | native | **delivery-pass** | `/workspace/films/fuli-controller-e2e` → target `matrix-fuli-swiss-controller` |
| M02 | fuli | swiss | flash | native | **muxed** | `/workspace/films/fuli-swiss-ds-v001` (no `--delivery` gate yet) |
| M03 | fuli | pictogram | controller | cross | **delivery-pass** | `/workspace/films/matrix-fuli-pictogram-controller` (finance-v001) |
| M04 | fuli | caption | controller | cross | **delivery-pass** | `/workspace/films/matrix-fuli-caption-controller` (compound-v001) |
| M05 | fensan | pictogram | controller | native | **delivery-pass** | `/workspace/films/fensan-controller-e2e` |
| M06 | fensan | pictogram | flash | native | **muxed** | `/workspace/films/fensan-pictogram-ds-v001` |
| M07 | fensan | swiss | controller | cross | **delivery-pass** | `/workspace/films/matrix-fensan-swiss-controller` |
| M08 | fensan | caption | controller | cross | empty | `matrix-fensan-caption-controller` |
| M09 | liudong | caption | controller | native | **delivery-pass** | `/workspace/films/liudong-controller-e2e` |
| M10 | liudong | caption | flash | native | **muxed** | `/workspace/films/liudong-caption-ds-v001` |
| M11 | liudong | swiss | controller | cross | empty | `matrix-liudong-swiss-controller` |
| M12 | liudong | pictogram | controller | cross | empty | `matrix-liudong-pictogram-controller` |

**Filled:** M01/M05/M09 + M03/M04/M07 (controller `--delivery` PASS) + M02/M06/M10 (Flash muxed). **9/12.** Remaining cross: **M08 / M11 / M12**.

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
4. For **flash** cells: mp4 + COMPARE/BUILD notes; delivery gate optional until Flash path grows a plan.json
5. No edits to locked engine cores unless the cell is an explicit style-unlock sibling (out of matrix id)

## CLI

```bash
python3 tools/deepseek-controller/cli.py matrix           # table
python3 tools/deepseek-controller/cli.py matrix --json    # raw tracker
python3 tools/deepseek-controller/cli.py matrix --filled   # only non-empty
python3 tools/deepseek-controller/cli.py matrix --id M01   # one cell
```

## Proof slice (2026-10-29 Asia/Shanghai)

Documented existing delivery films into M01 / M05 / M09 rather than re-rendering. Flash natives M02 / M06 / M10 registered as `muxed`. Cross-style controller cells M03–M04, M07–M08, M11–M12 left **empty** on purpose.

## Next knife (exact cells)

Priority order for follow-ups (still no “render all 12”):

1. **M03** `fuli-pictogram-controller` — same 复利 card on Pictogram via controller scaffold + mux + `--delivery`
2. **M04** `fuli-caption-controller` — same 复利 card on Caption
3. **M07** `fensan-swiss-controller` — 分散 on Swiss
4. Promote Flash cells **M02/M06/M10** to `delivery-pass` (add plan.json + evidence) without full remux if media already OK
5. Then M08 / M11 / M12 cross cells
6. Later epic: cross-style × flash (6 more → 18)

## Related

- [E2E-swiss.md](E2E-swiss.md) · [E2E-pictogram.md](E2E-pictogram.md) · [E2E-caption.md](E2E-caption.md)
- [STUDIO.md](STUDIO.md) · [TTS.md](TTS.md) · [MUSIC-BED.md](MUSIC-BED.md) · [nle-handoff.md](nle-handoff.md)
- `/workspace/films/COMPARE-multi-style-ds.md` · `showcase/COMPARE.md`
