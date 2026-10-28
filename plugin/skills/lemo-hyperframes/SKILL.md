# lemo-hyperframes — optional alternate render rail

Read [`docs/integrations/hyperframes.md`](../../../docs/integrations/hyperframes.md) first.

## When to use

User wants HTML→MP4 via **HeyGen HyperFrames** instead of (or as a bake-off against) lemo Playwright still/video — and the film is **not** bound to a locked Opus `styles/*/demo` engine.

## When not to use

- Any engine-locked DeepSeek Flash job (`AGENTS.deepseek.md`)
- User only asked for Premiere/Resolve handoff → use `lemo-export-nle` / OpenFilm instead

## Agent steps (high level)

1. Confirm Node 22+ and ffmpeg.
2. Install skills: `npx hyperframes skills update` (or `npx skills add heygen-com/hyperframes`).
3. `npx hyperframes init <name>` → write compositions per HyperFrames `/hyperframes` skill.
4. `npx hyperframes preview` → `npx hyperframes render --output ….mp4`.
5. Still run loudness / duration checks the user cares about; do not claim lemo `quality.json` unless that gate exists for this rail.

## Status

Stub only. No lemo adapter, no automatic migration of Opus demos.
