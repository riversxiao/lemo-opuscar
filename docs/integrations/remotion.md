# Remotion · second engine for data / caption shorts

**Status:** bridge instructions (2026-10-28). Opus `styles/*/demo` engines stay locked. Remotion is a **parallel** path for information-design shorts (charts, lower-thirds, kinetic captions), not a rewrite of Swiss / Caption demos.

## Role in this fork

| Path | Who fills what | Render |
|---|---|---|
| Opus demo lock (default) | Flash: timeline / copy / palette only | Playwright `still.mjs` / `video.mjs` |
| Remotion infographic (optional) | Flash: props / data JSON only; composition code from a Remotion scaffold | Remotion CLI / Studio |

## How Flash should work

1. User (or strong model) scaffolds a Remotion project once (see Grok Bot / Cursor `remotion-create` + `remotion-render` skills conceptually — **do not** paste third-party skill bodies into this repo).
2. Flash only edits **data**: `public/data/*.json`, `src/props.json`, copy strings, colors, durations — same spirit as lemo content-layer edits.
3. Forbidden for Flash: rewriting Remotion webpack config, `<Player>` internals, or “porting” a locked Opus shader into Remotion mid-job.

## Suggested pilot

One Caption-like Chinese topic (numbers + keyword callouts), 20–30 s, Remotion composition + lemo-style BRIEF stating `engine: remotion-infographic`. Compare against Caption News pure-graphics path on the same facts (Sprint C in `docs/NEXT-ROUND.md`).

## Skill pointer

[`plugin/skills/lemo-remotion-infographic/SKILL.md`](../../plugin/skills/lemo-remotion-infographic/SKILL.md)
