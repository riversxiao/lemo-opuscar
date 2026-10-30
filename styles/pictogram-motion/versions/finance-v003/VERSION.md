# pictogram-motion · finance-v003

v002 plus a **per-line visual scene library** (2026-10-29, 贝塔 pilot).

- Each dialogue line carries a `visual` brief (台词教父 drafts). `tools/deepseek-controller/viz_pick.py`
  maps it to a scene id + deterministic data (curves / steps) → `content/viz.json`, and runs the
  金融专家 content-visual lint → `evidence/visual-content.json` (no tickers / fund names / K线截图,
  no monotonically rising return curves, no chips / casino / 赌桌, no duplicate scene in a film).
- `apply_pictogram_edl.py` merges `viz` by shot id; shots with `s.viz` skip the sport-pose card and
  draw `G.VIZ[scene]` (plunge, swing_label, step_blocks, waves, boat, mirror_updown, coaster).
  Each scene has its own palette, layout and motion (draw-on + shake, scrolling swing, block hops,
  filled-wave swell, bobbing boat, symmetric up/down bands, coaster push-in).
- Finale = last line's scene for `vizDur`, then an iris into the end card (endTitle / endLine) for
  the outro (`schedule --outro 1.5`).
- Minimal HUD: eyebrow + term top, shot ticks bottom. Viz→viz transitions rotate by shot index.
- New scene: add a rule in viz_pick.py RULES + `VIZ.<id>` here. Local canvas only; no image models.
- Duplicate gate: `visual_dupe.py` (keyframe dHash + layout correlation vs. the series index).
- Batch 3 (2026-10-30, VaR long, up to 14 shots): cap_crossed, bank_report, three_slots, slots_filled,
  grid_10x10, square_over, year_strip, red_cluster, bottomless, old_ledger, sky_change, expect_actual,
  tail_dots_es, bank_on_line. Helpers clockIcon/gauge/tile/goldLine. Same metaphor as var-plain
  (0 line on top, losses downward, gold = threshold, no drawn bottom); no tickers, no K-lines, no dice.
- Threshold label (金融专家 2026-10-30): square_over / tail_dots_es read 「亏损门槛 <金额>」 via `LOSS_TH`
  (brand `thresholdAmount`, default 100万; `thresholdLabel` overrides the whole text). tail_dots_es label
  moved inward (x 270→360) so the 1.35× push-in keeps it title-safe. var-long-v001 not re-rendered.
