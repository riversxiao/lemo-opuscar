# Swiss Motion — files the controller / Flash may touch

- `content/plan.json`
- `content/lines.json`
- `content/shots.json`
- `content/palette.json`
- `content/credits.json`
- `content/TOUCHABLES.md`
- `voices/dur.json`
- `timeline.parsed.json`
- `quality.json`

## Protected (do not edit)

- `ease.js`
- `film.js`
- `main.js`
- `mix.py`
- `index.html`
- `fonts/**`
- `tools/**`

Copy `styles/swiss-motion/demo/` into the project first. Adapter output lives under `content/`. Wire into the engine via thin project glue only — never modify `ease.js` / `film.js` / `mix.py`.
