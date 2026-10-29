# Remotion · second engine for data / caption shorts

**Status:** working template (2026-10-29). Opus `styles/*/demo` engines stay locked. Remotion is a **parallel** path for information-design shorts (charts, lower-thirds, kinetic captions), not a rewrite of Swiss / Caption demos. Everything lives in [`plugin/skills/lemo-remotion-infographic/`](../../plugin/skills/lemo-remotion-infographic/SKILL.md).

## Role in this fork

| Path | Who fills what | Render |
|---|---|---|
| Opus demo lock (default) | Flash: timeline / copy / palette only | Playwright `still.mjs` / `video.mjs` |
| Remotion infographic (optional) | Flash: `plan.json` or `props.json` only; composition code is the skill's template | `scripts/render.sh` (Remotion CLI) then `core/render/mux.sh` |

## Pipeline

```sh
S=<lib>/plugin/skills/lemo-remotion-infographic/scripts
sh $S/setup.sh films/<id>                                    # films/<id>/remotion/: template, fonts, npm install
python3 tools/deepseek-controller/cli.py validate plan.json
python3 $S/plan_to_props.py plan.json [--timeline films/<id>/content/timeline.json] -o films/<id>/remotion/props.json
sh $S/render.sh films/<id>/remotion --audio films/<id>/mix.wav --out films/<id>/<id>.mp4
```

1. **Template.** Remotion 4.0.539, React 19.2. Compositions `Infographic` (1920x1080) and `InfographicPortrait` (1080x1920), both 24 fps, duration from props; props for the other aspect are refused. Scene kinds: title, chapter, caption (keyword lower-third), bigNumber, compare, chart, end. Fonts are self-hosted in `public/fonts/`: Inter Tight + Noto Sans SC (the controller engines' text pair, `fetch_fonts.py --style remotion-infographic`) and the library display families, registered from a copy of `core/fonts/fonts.css` so the family names match exactly. A font that fails to load cancels the render.
2. **Props.** `template/props.schema.json` is the contract; `plan_to_props.py` (stdlib only) maps aspect, target duration (or the schedule timeline), `onScreenText` markup (`|` new line, `{word}` accent), role and numeric `data` to scenes, and exits non-zero on input it cannot draw honestly (unsupported aspect, mixed series and numbers, negative bars, too many bars, shots under 1 s, non-`unit` strings, unknown display font). `--check props.json` validates without jsonschema.
3. **Into the mux.** Full frame: `out/picture.mp4` (h264) goes to `core/render/mux.sh picture.mp4 mix.wav out.mp4 24 0`. Overlay: props made with `--overlay` (transparent) render to `out/overlay.webm` (VP8 + alpha), which `render.sh --over base.mp4` lays over a same-size style render (decoded with libvpx so the alpha survives) into `out/composite.mp4`, then the same mux. A PNG sequence (`--sequence --image-format=png`) also works; encode it with ffmpeg at 24 fps first.

Verified end to end on the controller fixtures: `plan-caption-news.json` and `plan-caption-news-portrait.json` rendered to 30 s 1920x1080 and 1080x1920 films (720 frames, h264 + AAC, mux at −14.0 LUFS), and the overlay path over a 1920x1080 base. `npm test` covers the converter; set `WORDFILM_REMOTION_DIR=<films/<id>/remotion>` to also render 12 frames in both aspects (the harness never runs `npm install`).

## How Flash should work

1. Run `setup.sh` once per film; do not paste third-party Remotion skill bodies into this repo.
2. Flash only edits **data**: the plan (then re-run `plan_to_props.py`) or `props.json` directly (`--check` before rendering): copy strings, numbers, colours, durations, the same spirit as lemo content-layer edits.
3. Forbidden for Flash: editing `src/*.tsx`, the Remotion config, `<Player>` internals, or "porting" a locked Opus shader into Remotion mid-job.

Remotion is not MIT: free for individuals and small teams, companies check the [Remotion License](https://www.remotion.dev/license).

## Suggested pilot

One Caption-like Chinese topic (numbers + keyword callouts), 20 to 30 s, Remotion composition + lemo-style BRIEF stating `engine: remotion-infographic`. Compare against Caption News pure-graphics path on the same facts (Sprint C in `docs/NEXT-ROUND.md`).

## Skill pointer

[`plugin/skills/lemo-remotion-infographic/SKILL.md`](../../plugin/skills/lemo-remotion-infographic/SKILL.md)
