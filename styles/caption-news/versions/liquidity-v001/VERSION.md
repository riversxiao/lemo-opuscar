# caption-news · style version `liquidity-v001`

Maintainer overlay for **流动性 / liquidity** films whose VO does **not** match the bee-demo SHOTS.

## What changes vs locked demo

| File | Demo lock path | This version |
|---|---|---|
| `index.html` / `build.sh` / `tools/**` | protected | **unchanged** |
| `main.js` | protected (蜜蜂账本 SHOTS/TEXTS) | **replaced**: liquidity SHOTS + graphic cards |

### Structural deltas in `main.js`

1. **DUR = 32 s** (demo 59.5) — closer to plan `targetDurationSec=30` + pad.
2. **SHOTS** tell the liquidity story (hook → sting → cash/house split → stress → timing → live cash → end). No hive / 瓦螨 / 加州 labels.
3. **No Commons bee pack required** — ledger + abstract mesh only (READY does not fetch `assets/states.json` or bee JPEGs).
4. **Channel bug / end card** say 流动性 / LIQUIDITY.
5. `window.TEXTS(t)` still registered for readcheck.

## How to apply (does not change default scaffold)

Default `cli.py scaffold` still copies `styles/caption-news/demo/` and locks demo `main.js`. Opt in on a **sibling** project:

```bash
LIB=/workspace/lemo-opuscar-deepseek
PROJ=/workspace/films/liudong-caption-liquidity-v001
cd "$LIB"
python3 tools/deepseek-controller/cli.py scaffold \
  tools/deepseek-controller/fixtures/plan-caption-news.json -o "$PROJ" --lib "$LIB" --force
python3 tools/deepseek-controller/apply_caption_style_version.py \
  --project "$PROJ" --version liquidity-v001
```

This copies `versions/liquidity-v001/main.js` → `$PROJ/main.js`, records `styleVersion`, moves `main.js` out of `protectedSha256` into `versionSha256`, and leaves `liudong-controller-e2e` demo lock untouched.

## Reproduce

See `/workspace/films/liudong-caption-liquidity-v001/` and `tools/deepseek-controller/docs/E2E-caption.md` (liquidity-v001 section).
