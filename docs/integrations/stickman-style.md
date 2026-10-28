# Stickman / stick-figure style candidate

**Status:** research note for `~/lemo-my-styles/` (medium priority). Not a library style yet.

## Fit for Lemo-DeepSeek

Explainer / 讲解类 topics (finance mechanics, product how-tos) map well to stick figures: consistent characters, low asset cost, readable on mobile. Prefer building a **my-style** under [`MY-STYLES.md`](../../MY-STYLES.md) rather than forking an Opus demo lock.

## Upstream references (pick one technique base later)

| Project | License / notes | How it helps |
|---|---|---|
| [bassimeledath/stix](https://github.com/bassimeledath/stix) | MIT · SVG assets + CSS keyframes → GIF/MP4 | Closest to lemo’s HTML→frames mental model; install via `npx skills add bassimeledath/stix` |
| [dsauce/stickman-kino](https://github.com/dsauce/stickman-kino) | local rig + agent skills + optional Kokoro | Full local film CLI; heavier; good pose library inspiration |
| [kaomei/stickman-video-director](https://github.com/kaomei/stickman-video-director) | director prompts for external clip gen | **Not** a code-render rail — conflicts with “no video LM” unless used only for storyboard text |

For this fork: prefer **stix** or a blank-page my-style with Canvas/SVG stick rigs rendered by Playwright — stay on the code-film path. Do not call Seedance/Kling for stick shots.

## Suggested my-style slug

`stickman-explainer` · 中文名示例：火柴人讲解

Technique base candidates: Pictogram Motion (pose vocabulary) or a blank page with SVG limbs. Document invariants in `STYLE.md` once a styleframe is approved.

## Next steps

1. Approve look with one styleframe (light vs dark canvas).
2. 15–20 s demo on a non-finance explainer topic.
3. Register row in `~/lemo-my-styles/README.md` per MY-STYLES.md.
