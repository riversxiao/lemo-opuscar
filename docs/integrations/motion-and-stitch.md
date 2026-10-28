# Motion demos · stitch Release packs

**Status:** short plan (medium). No automatic gallery regen in this sprint.

## Motion demo sources

Use external HTML/CSS/Canvas demos (and OPUSCAR-adjacent open demos the user points at) as **STYLE bases** for my-styles or BRIEF references — not as drop-in replacements for locked `styles/*/demo` engines.

Workflow:

1. Capture a still + 3–5 s loop from the demo (with license noted).
2. Map materials / motion / type to a library technique base (`MY-STYLES.md`).
3. Only then ask Flash to adapt content on a copied engine or a new my-style demo.

## Stitch · multi-spot Release

When several 25–40 s DeepSeek samples share a Release (e.g. `showcase-v001`):

```sh
# sketch — adjust paths; requires ffmpeg
ffmpeg -y -f concat -safe 0 -i list.txt -c copy showcase-reel.mp4
```

`list.txt` lines: `file 'swiss-fuli.mp4'` etc. Prefer re-encode with loudness normalize if peak levels differ across spots.

Optional: chapter markers / title cards between spots (Canvas stills → short clips) so the reel is watchable on X / Bilibili without opening four URLs.

## Out of scope for Sprint A

- Regenerating all 59 gallery frames
- Auto-publishing GitHub Releases
