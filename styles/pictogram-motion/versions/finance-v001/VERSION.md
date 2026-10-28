# pictogram-motion · style version `finance-v001`

Maintainer overlay for **catalogue / finance / diversify** films that need intro & finale
*structure* beyond literal rewrites.

## What changes vs locked demo

| File | Demo lock path | This version |
|---|---|---|
| `engine.js` / `poses/**` / pattern math | protected | **unchanged** (still demo bytes) |
| `edl.js` | protected | still demo bytes; controller uses `edl_runtime.json` overlay |
| `scenes.js` | protected (Olympics intro/finale) | **replaced**: content-driven intro/finale/HUD |

### Structural deltas in `scenes.js`

1. **Intro scales to the intro shot’s beat budget** (controller intros are often 8–12 beats). Demo assumed ~50 beats, so short intros only showed the dark-rings sting.
2. **Count-up stats** come from `CARDS.length` / chapter count / `EDL.DUR` — not hardcoded `43 / 469 / 16`.
3. **Ready cue** is `READY` / `ALLOCATE` (no race-start “ON YOUR MARKS”).
4. **Finale grid** sizes to the card count (compact wall), with `ALL N` cell — not a 9×5 / 43-sport wall.
5. **Slogan phase** is reachable inside short finale shots (phase split scales to `s.beats`).
6. **HUD / titles** read `window.__BRAND_STRINGS` + EDL intro shot (`titleEn` / `titleZh` / slogans).
7. Optional `window.TEXTS(t)` for readcheck.

Rings + sun disc stay — STYLE.md treats them as generic geometry, not an event emblem.

## How to apply (does not change default scaffold)

Default `cli.py scaffold` still copies `styles/pictogram-motion/demo/` and locks demo
`scenes.js`. To opt into this version on an existing pictogram project:

```bash
LIB=/workspace/lemo-opuscar-deepseek
PROJ=/path/to/pictogram-project   # already scaffolded
cd "$LIB"
python3 tools/deepseek-controller/apply_pictogram_style_version.py \
  --project "$PROJ" --version finance-v001
```

This:

- copies `versions/finance-v001/scenes.js` → `$PROJ/scenes.js`
- rewrites `content/engine.lock.json`: keeps engine/edl/… demo hashes; records
  `styleVersion: finance-v001` and the **version** hash of `scenes.js` under
  `versionSha256` (scenes.js removed from `protectedSha256` so demo-lock tests stay valid)

Locked-demo projects without this step are untouched.

## Reproduce (example film)

See `/workspace/films/fensan-pictogram-finance-v001/` (sibling of controller E2E).
