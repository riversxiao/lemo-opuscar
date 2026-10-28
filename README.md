<div align="center">

# Lemo-DeepSeek · riversxiao

**DeepSeek Flash + locked Opus demo engines → code-made short films (no video models)**

<a href="DEEPSEEK.md"><img alt="DEEPSEEK" src="https://img.shields.io/badge/DEEPSEEK.md-workflow-111?style=for-the-badge"></a>
<a href="AGENTS.deepseek.md"><img alt="AGENTS" src="https://img.shields.io/badge/AGENTS.deepseek-rules-333?style=for-the-badge"></a>
<a href="showcase/README.md"><img alt="Showcase" src="https://img.shields.io/badge/-%E2%96%B6%20Showcase-E8553A?style=for-the-badge"></a>
<a href="https://github.com/riversxiao/lemo-opuscar/releases/tag/showcase-v001"><img alt="Release" src="https://img.shields.io/badge/Release-showcase--v001-2EA44F?style=for-the-badge"></a>
<a href="README.zh-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/README-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-555?style=for-the-badge"></a>

This fork: [github.com/riversxiao/lemo-opuscar](https://github.com/riversxiao/lemo-opuscar)

ℹ️ **This fork defaults to DeepSeek Flash; render engines still come from upstream Opus demos.**  
Upstream is [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar). Here: DeepSeek workflow + my own film showcase.

</div>

## My films

These four are **sample topics** (finance vocab used to demo multiple styles). Swap in any story — product, pets, travel, tutorials. MP4s on the Release; stills in-repo.

| Topic | Style | Stills | Film |
|---|---|---|---|
| Compound interest | Swiss Motion | [stills](showcase/stills/fuli-01.jpg) | [mp4](https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/fuli-swiss-ds-v001.mp4) |
| Diversification | Pictogram Motion | [stills](showcase/stills/fensan-01.jpg) | [mp4](https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/fensan-pictogram-ds-v001.mp4) |
| Liquidity | Caption News | [stills](showcase/stills/liudong-01.jpg) | [mp4](https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/liudong-caption-ds-v001.mp4) |
| What is hedging | Whiteboard | [stills](showcase/stills/duichong-01.jpg) | [mp4](https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/duichong-whiteboard-ds-v001.mp4) |

Details → [`showcase/README.md`](showcase/README.md) · rules → [`AGENTS.deepseek.md`](AGENTS.deepseek.md) · how-to → [`DEEPSEEK.md`](DEEPSEEK.md)

## How to use (this fork · DeepSeek)

Use this path day-to-day. Do **not** install the upstream Claude Code plugin.

### 1. Clone this repo

```sh
git clone https://github.com/riversxiao/lemo-opuscar.git
cd lemo-opuscar

# Optional: pin an audited commit
export LEMO_OPUSCAR_PIN=413a6bd

sh plugin/skills/lemo-deepseek/scripts/setup.sh
sh plugin/skills/lemo-deepseek/scripts/setup.sh deps
# Voice:
# sh plugin/skills/lemo-deepseek/scripts/setup.sh deps voice
# Plucked score:
# sh plugin/skills/lemo-deepseek/scripts/setup.sh deps music
```

### 2. Point your host at the DeepSeek skill

Point OpenCode / Cursor / your agent at:

`plugin/skills/lemo-deepseek/SKILL.md`

Have the agent read first: `AGENTS.deepseek.md` → `AGENTS.md` → `DIRECTOR.md` → `TECHNIQUE.md` → chosen `styles/<slug>/STYLE.md`.

### 3. One-line start (any topic)

> Make a 30-second Swiss Motion film about compound interest — or any topic you want.

> Make a 30-second Caption News film about liquidity / an orange cat / a product launch.

Loop: TREATMENT → `setup.sh demo <slug>` → content layer only → still → TTS → video → mix → mux. See [`DEEPSEEK.md`](DEEPSEEK.md).

### Prerequisites

- Node 20+, ffmpeg, Python 3.11+
- Network (edge-tts Chinese VO; or offline Kokoro)
- DeepSeek Flash host, pick one:
  - **Official DeepSeek API (recommended if you have a key)**: in OpenCode run `/connect` → choose `deepseek` → paste `DEEPSEEK_API_KEY` (from [platform.deepseek.com](https://platform.deepseek.com)) → model `deepseek-flash` (or `deepseek-v4-pro`); base URL `https://api.deepseek.com`
  - **OpenRouter fallback**: `openrouter/deepseek/deepseek-v4.1-flash`
  - **OpenCode free tier**: `opencode/deepseek-v4.1-flash-free` (may run out of quota — switch to one of the above)

---

## 🎬 Feature presentation · my samples

<table><tr>
<td width="50%" valign="top"><a href="https://github.com/riversxiao/lemo-opuscar/releases/tag/showcase-v001"><img src="docs/showcase-hero.jpg" alt="Four DeepSeek sample shorts"></a><br><b>▶ Four sample shorts</b> · ~30 s each<br><sub>Compound interest · Diversification · Liquidity · Hedging — four styles, one DeepSeek workflow. Topics are samples; any story works.</sub></td>
<td width="50%" valign="top"><a href="DEEPSEEK.md"><img src="docs/showcase-workflow.jpg" alt="DeepSeek Flash workflow strip"></a><br><b>Workflow</b> · DeepSeek Flash + engine lock<br><sub>still → TTS / score → video → mix → mux. Content layer only; locked Opus demo engines stay untouched.</sub></td>
</tr></table>

<div align="center">

Every frame and cut in these samples was orchestrated by **DeepSeek Flash** on locked Opus demos.<br>
[**▶ Watch Release**](https://github.com/riversxiao/lemo-opuscar/releases/tag/showcase-v001) · [**Showcase folder**](showcase/README.md) · [**DEEPSEEK.md**](DEEPSEEK.md)

</div>

## 👋 About this fork

Maintained by **[riversxiao](https://github.com/riversxiao)**: DeepSeek workflow + own films.  
Upstream engines & style library by **Lemomo** / [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar).

> **Not an awesome list.** Films highlighted above were made here with **DeepSeek Flash** + code engines.<br>
> Topics are samples (finance vocab is the first set). Product, pets, travel, tutorials — same pipeline. The wall below is the full style library for engine-lock demos.

![Lemo-DeepSeek cover](docs/cover-deepseek.jpg)

## How it works (this fork)

Every short is directed, drawn, scored and mixed by an agent writing code:

- 🎨 **Picture**: canvas / WebGL pages, rendered frame by frame
- 🎵 **Music**: samples / pluck scores (optional)
- 🎙️ **Voice**: edge-tts or Kokoro narration

No video generation models, no stock footage. Rules → [`AGENTS.deepseek.md`](AGENTS.deepseek.md). Day-to-day install → section **How to use** above (not the Claude marketplace plugin).

## The styles

This fork’s style wall — thumbnails regenerated into `docs/frames-ds/`. Four cells marked **riversxiao sample** use this fork’s stills; others are library demos (engine lock). Click a frame for its `STYLE.md`.

<!-- styles:start -->

### Edit & Documentary

<table>
<tr>
<td width="33%" valign="top"><a href="styles/caption-news/STYLE.md"><img src="docs/frames-ds/caption-news.jpg" alt="Caption News"></a><br><b>Caption News</b><br><i>Liquidity · riversxiao sample</i><br><sub>DeepSeek Flash sample — graphics-first news short. <a href="https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/liudong-caption-ds-v001.mp4">mp4</a></sub></td>
<td width="33%" valign="top"><a href="styles/newsreel/STYLE.md"><img src="docs/frames-ds/newsreel.jpg" alt="1920s Newsreel"></a><br><b>1920s Newsreel</b><br><i>Knock-Knee Alert</i><br><sub>1926: the papers say the Charleston will ruin America&#x27;s knees; at Ford&#x27;s own picnic the kids dance it anyway.</sub></td>
<td width="33%" valign="top"><a href="styles/countdown/STYLE.md"><img src="docs/frames-ds/countdown.jpg" alt="Live Countdown Split-screen"></a><br><b>Live Countdown Split-screen</b><br><i>Counting Itself Down</i><br><sub>The last minute of the Artemis II launch, uncut: one cell opens to nine, and they merge into one at ignition.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/city-symphony/STYLE.md"><img src="docs/frames-ds/city-symphony.jpg" alt="Time-lapse Symphony"></a><br><b>Time-lapse Symphony</b><br><i>One Day in New York</i><br><sub>One day in New York in time-lapse: rivers of light, a grid on the sixteenths, 1899 beside today.</sub></td>
<td width="33%" valign="top"><a href="styles/visual-investigation/STYLE.md"><img src="docs/frames-ds/visual-investigation.jpg" alt="Visual Investigation"></a><br><b>Visual Investigation</b><br><i>The Hindenburg: Four Minutes, 32 Seconds</i><br><sub>Newsreel, photos, testimony and the 1937 inquiry on one clock: five sources point to the same spot.</sub></td>
<td width="33%" valign="top"><a href="styles/kino-montage/STYLE.md"><img src="docs/frames-ds/kino-montage.jpg" alt="Constructivist Montage"></a><br><b>Constructivist Montage</b><br><i>410 Days</i><br><sub>The Empire State&#x27;s 1931 brochure credits its builders; the site film and Hine&#x27;s photos answer: 2,500 a day.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/telestrator/STYLE.md"><img src="docs/frames-ds/telestrator.jpg" alt="Sports Telestrator"></a><br><b>Sports Telestrator</b><br><i>Freeze Frame</i><br><sub>Down 3–0 at half-time, Fenerbahçe scored three in 12 minutes: freeze, draw, split screen, shot map.</sub></td>
<td width="33%" valign="top"><a href="styles/news-package/STYLE.md"><img src="docs/frames-ds/news-package.jpg" alt="Broadcast News Package"></a><br><b>Broadcast News Package</b><br><i>The Week in AI</i><br><sub>Four AI stories from one week in a full on-air package: rundown, headline strap, price board, spec card.</sub></td>
</tr>
</table>

### Evidence Films

<table>
<tr>
<td width="33%" valign="top"><a href="styles/satellite-briefing/STYLE.md"><img src="docs/frames-ds/satellite-briefing.jpg" alt="Satellite Briefing"></a><br><b>Satellite Briefing</b><br><i>The Map Still Says Sea</i><br><sub>A satellite follows the map to the Aral Sea and finds a desert; only the part someone dammed came back.</sub></td>
<td width="33%" valign="top"><a href="styles/briefing-board/STYLE.md"><img src="docs/frames-ds/briefing-board.jpg" alt="Engineering Briefing Board"></a><br><b>Engineering Briefing Board</b><br><i>The Ship Decides</i><br><sub>Four bridge types are tested on one briefing wall, and the ship that must pass under picks the winner.</sub></td>
<td width="33%" valign="top"><a href="styles/lidar-survey/STYLE.md"><img src="docs/frames-ds/lidar-survey.jpg" alt="LiDAR Survey"></a><br><b>LiDAR Survey</b><br><i>The Fields Under the Forest</i><br><sub>A laser survey strips the canopy off a Connecticut forest and finds 3.4 km of old farm walls.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/white-model/STYLE.md"><img src="docs/frames-ds/white-model.jpg" alt="Projection on White Model"></a><br><b>Projection on White Model</b><br><i>How a Flattened City Grew Back</i><br><sub>A projector paints Rotterdam&#x27;s white model layer by layer, from the 1940 gap to today&#x27;s towers.</sub></td>
<td width="33%" valign="top"><a href="styles/data-physical/STYLE.md"><img src="docs/frames-ds/data-physical.jpg" alt="Data Physicalization"></a><br><b>Data Physicalization</b><br><i>Two Spirals</i><br><sub>Twelve years of wind and solar stacked as real plates, spiralling round a walnut dial until solar overtakes.</sub></td>
<td width="33%" valign="top"><a href="styles/teardown/STYLE.md"><img src="docs/frames-ds/teardown.jpg" alt="Exploded Teardown"></a><br><b>Exploded Teardown</b><br><i>21 Keys, Opened</i><br><sub>Half an open-source keyboard comes apart in one orbit, down to the chip, then closes with its real dimensions.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/microscope/STYLE.md"><img src="docs/frames-ds/microscope.jpg" alt="Microscope Story"></a><br><b>Microscope Story</b><br><i>Measured Blue</i><br><sub>One continuous move from a liver slide to a single nucleus; two circles, counted pixel by pixel, differ 2.4 times in blue.</sub></td>
<td width="33%" valign="top"><a href="styles/archive-lighttable/STYLE.md"><img src="docs/frames-ds/archive-lighttable.jpg" alt="Archive Light Table"></a><br><b>Archive Light Table</b><br><i>Two Seconds Short</i><br><sub>The telegram said 57 seconds; under a loupe, the Wrights&#x27; glass negatives and the archive say 59.</sub></td>
</tr>
</table>

### Hand-drawn & Painting

<table>
<tr>
<td width="33%" valign="top"><a href="styles/crayon-book/STYLE.md"><img src="docs/frames-ds/crayon-book.jpg" alt="Crayon Picture Book"></a><br><b>Crayon Picture Book</b><br><i>The Moon Can&#x27;t Sleep</i><br><sub>The moon can&#x27;t sleep, so a little girl climbs onto the roof to sing it a lullaby.</sub></td>
<td width="33%" valign="top"><a href="styles/watercolor/STYLE.md"><img src="docs/frames-ds/watercolor.jpg" alt="Watercolor Brush"></a><br><b>Watercolor Brush</b><br><i>Follow the Rain</i><br><sub>Follow the rain from Australia&#x27;s red desert heart to its green coast in one unbroken painted walk.</sub></td>
<td width="33%" valign="top"><a href="styles/ink-wash/STYLE.md"><img src="docs/frames-ds/ink-wash.jpg" alt="Chinese Ink Wash"></a><br><b>Chinese Ink Wash</b><br><i>The Swordsman and the River</i><br><sub>A swordsman crosses the river on the water and splits the current with a single stroke.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/impasto/STYLE.md"><img src="docs/frames-ds/impasto.jpg" alt="Impasto Oil Painting"></a><br><b>Impasto Oil Painting</b><br><i>The Colour of Rain</i><br><sub>In a grey, rainy square one red umbrella opens, and a waltz paints the whole plaza in colour.</sub></td>
<td width="33%" valign="top"><a href="styles/one-line/STYLE.md"><img src="docs/frames-ds/one-line.jpg" alt="One-line Drawing"></a><br><b>One-line Drawing</b><br><i>The Line That Never Lifted</i><br><sub>One unbroken line draws a whole life, then the pen passes to a child.</sub></td>
<td width="33%" valign="top"><a href="styles/whiteboard/STYLE.md"><img src="docs/frames-ds/whiteboard.jpg" alt="Whiteboard Explainer"></a><br><b>Whiteboard Explainer</b><br><i>What is hedging · riversxiao sample</i><br><sub>DeepSeek Flash sample — board + Yunxi VO. <a href="https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/duichong-whiteboard-ds-v001.mp4">mp4</a></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/urban-sketch/STYLE.md"><img src="docs/frames-ds/urban-sketch.jpg" alt="Urban Sketch · Pen &amp; Wash"></a><br><b>Urban Sketch · Pen &amp; Wash</b><br><i>Where the Wind Went</i><br><sub>A park that is only a pen sketch; wherever the wind carries her straw hat, colour follows.</sub></td>
</tr>
</table>

### East Asian Traditions

<table>
<tr>
<td width="33%" valign="top"><a href="styles/shadow-puppet/STYLE.md"><img src="docs/frames-ds/shadow-puppet.jpg" alt="Shadow Puppetry"></a><br><b>Shadow Puppetry</b><br><i>Hou Yi Shoots the Suns</i><br><sub>Ten suns scorch the earth until the archer Hou Yi draws his bow, told with leather puppets on a lit screen.</sub></td>
<td width="33%" valign="top"><a href="styles/ukiyoe/STYLE.md"><img src="docs/frames-ds/ukiyoe.jpg" alt="Ukiyo-e"></a><br><b>Ukiyo-e</b><br><i>Toward the Mountain</i><br><sub>A traveller walks toward a distant mountain; every shot is a woodblock print, a great wave at the climax, the mountain and the whole scroll at the end.</sub></td>
<td width="33%" valign="top"><a href="styles/papercut-red/STYLE.md"><img src="docs/frames-ds/papercut-red.jpg" alt="Red Paper-cut"></a><br><b>Red Paper-cut</b><br><i>Nian Comes to Town</i><br><sub>On New Year&#x27;s Eve the beast Nian comes to town, and one girl&#x27;s giant paper-cut lights up the village to scare it off.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/paper-lantern/STYLE.md"><img src="docs/frames-ds/paper-lantern.jpg" alt="Paper-cut Lightbox"></a><br><b>Paper-cut Lightbox</b><br><i>A Mooncake&#x27;s Longing</i><br><sub>A single mooncake tells the Mid-Autumn story of reunion and longing inside a glowing paper-cut lightbox.</sub></td>
</tr>
</table>

### Print & Printmaking

<table>
<tr>
<td width="33%" valign="top"><a href="styles/risograph/STYLE.md"><img src="docs/frames-ds/risograph.jpg" alt="Risograph Print"></a><br><b>Risograph Print</b><br><i>Sunday Ride</i><br><sub>A Sunday-morning bike ride through the city — bakery, park, riverside — each stop adding an ink until three misregistered plates overprint.</sub></td>
<td width="33%" valign="top"><a href="styles/halftone-dossier/STYLE.md"><img src="docs/frames-ds/halftone-dossier.jpg" alt="Halftone Dossier"></a><br><b>Halftone Dossier</b><br><i>Case File: Chubby</i><br><sub>A chubby orange cat stands trial for testing gravity and 4 a.m. parkour, and walks free.</sub></td>
<td width="33%" valign="top"><a href="styles/woodcut/STYLE.md"><img src="docs/frames-ds/woodcut.jpg" alt="Woodcut Print"></a><br><b>Woodcut Print</b><br><i>The Bell Founder</i><br><sub>A village spends a whole winter casting one bell; the first time it rings, the snow stops.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/engraving/STYLE.md"><img src="docs/frames-ds/engraving.jpg" alt="Copperplate Engraving"></a><br><b>Copperplate Engraving</b><br><i>The Honeybee, Plate VII</i><br><sub>A natural-history plate engraves itself: the burin cuts the copper, the bee builds up line by line, and a watercolour wash brings it to life.</sub></td>
<td width="33%" valign="top"><a href="styles/silkscreen-poster/STYLE.md"><img src="docs/frames-ds/silkscreen-poster.jpg" alt="Silkscreen Travel Poster"></a><br><b>Silkscreen Travel Poster</b><br><i>Three Trails</i><br><sub>Three trail posters are screen-printed one ink at a time, then climbed in one long take from noon to dusk.</sub></td>
</tr>
</table>

### Graphic & Type

<table>
<tr>
<td width="33%" valign="top"><a href="styles/swiss-motion/STYLE.md"><img src="docs/frames-ds/swiss-motion.jpg" alt="Swiss Motion Graphics"></a><br><b>Swiss Motion Graphics</b><br><i>Compound interest · riversxiao sample</i><br><sub>DeepSeek Flash sample on locked Swiss engine — finance vocab demo; any topic works. <a href="https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/fuli-swiss-ds-v001.mp4">mp4</a></sub></td>
<td width="33%" valign="top"><a href="styles/spy-titles/STYLE.md"><img src="docs/frames-ds/spy-titles.jpg" alt="60s Spy Title Sequence"></a><br><b>60s Spy Title Sequence</b><br><i>The Velvet Cipher</i><br><sub>Opening titles for an imaginary 1964 spy film: a chase for a stolen key until the shapes lock into the title.</sub></td>
<td width="33%" valign="top"><a href="styles/art-deco/STYLE.md"><img src="docs/frames-ds/art-deco.jpg" alt="Art Deco"></a><br><b>Art Deco</b><br><i>Midnight at the Starlight Hotel</i><br><sub>A grand hotel, 1930: a bellboy races lifts and revolving doors to deliver one letter before midnight.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/blueprint/STYLE.md"><img src="docs/frames-ds/blueprint.jpg" alt="Blueprint"></a><br><b>Blueprint</b><br><i>Patent Pending: The Cloud Catcher</i><br><sub>An inventor&#x27;s blueprint draws, explodes and assembles a cloud-catching machine, and its revision cloud starts to rain.</sub></td>
<td width="33%" valign="top"><a href="styles/stained-glass/STYLE.md"><img src="docs/frames-ds/stained-glass.jpg" alt="Stained Glass"></a><br><b>Stained Glass</b><br><i>The Dragon of the East Window</i><br><sub>Sunlight crosses a cathedral window from dawn to dusk, waking each pane of a knight-and-dragon tale.</sub></td>
<td width="33%" valign="top"><a href="styles/pictogram-motion/STYLE.md"><img src="docs/frames-ds/pictogram-motion.jpg" alt="Pictogram Motion"></a><br><b>Pictogram Motion</b><br><i>Diversification · riversxiao sample</i><br><sub>DeepSeek Flash sample — beat-locked pictograms; drums, no VO. <a href="https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/fensan-pictogram-ds-v001.mp4">mp4</a></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/ascii-crt/STYLE.md"><img src="docs/frames-ds/ascii-crt.jpg" alt="ASCII / CRT Terminal"></a><br><b>ASCII / CRT Terminal</b><br><i>Tranquility.log</i><br><sub>A moon-base AI wakes after forty years to a signal from Earth, and replies by drawing “home” in characters.</sub></td>
</tr>
</table>

### Information & Keynote

<table>
<tr>
<td width="33%" valign="top"><a href="styles/dataviz/STYLE.md"><img src="docs/frames-ds/dataviz.jpg" alt="Data Storytelling"></a><br><b>Data Storytelling</b><br><i>A Hundred Summers</i><br><sub>A hundred years of summer temperatures, where the chart itself tells the story.</sub></td>
<td width="33%" valign="top"><a href="styles/iso-infographic/STYLE.md"><img src="docs/frames-ds/iso-infographic.jpg" alt="Isometric Infographic"></a><br><b>Isometric Infographic</b><br><i>From Bean to Cup</i><br><sub>A coffee&#x27;s journey from the plantation to your hands, across one isometric world.</sub></td>
<td width="33%" valign="top"><a href="styles/dark-keynote/STYLE.md"><img src="docs/frames-ds/dark-keynote.jpg" alt="Dark Tech Keynote"></a><br><b>Dark Tech Keynote</b><br><i>Room to Think</i><br><sub>Launch film for Tidy, a fictional app: one buried cursor snaps hundreds of windows back into place.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/living-screencast/STYLE.md"><img src="docs/frames-ds/living-screencast.jpg" alt="Living Screencast"></a><br><b>Living Screencast</b><br><i>Clawd Moves In</i><br><sub>Clawd hops out of the terminal into the Claude app and acts out plan mode and self-checks in one take.</sub></td>
<td width="33%" valign="top"><a href="styles/hologram-hud/STYLE.md"><img src="docs/frames-ds/hologram-hud.jpg" alt="Sci-fi Hologram HUD"></a><br><b>Sci-fi Hologram HUD</b><br><i>Volt · Spec Scan</i><br><sub>An e-bike is scanned into a hologram; target boxes lock onto the battery, motor and brakes.</sub></td>
</tr>
</table>

### Cartoon & Anime

<table>
<tr>
<td width="33%" valign="top"><a href="styles/rubber-hose/STYLE.md"><img src="docs/frames-ds/rubber-hose.jpg" alt="1930s Rubber Hose Cartoon"></a><br><b>1930s Rubber Hose Cartoon</b><br><i>Coffee Cup Chase</i><br><sub>A coffee cup chases a runaway sugar cube around the kitchen, 1930s-cartoon style.</sub></td>
<td width="33%" valign="top"><a href="styles/cel-anime-80s/STYLE.md"><img src="docs/frames-ds/cel-anime-80s.jpg" alt="80s Cel Anime"></a><br><b>80s Cel Anime</b><br><i>City Lights, 1987</i><br><sub>A courier girl rides through a rain-soaked neon city to deliver a tape before the dawn launch.</sub></td>
<td width="33%" valign="top"><a href="styles/scifi-toon/STYLE.md"><img src="docs/frames-ds/scifi-toon.jpg" alt="Sci-Fi Sitcom Toon"></a><br><b>Sci-Fi Sitcom Toon</b><br><i>Coffee Run</i><br><sub>A jaded genius opens a portal just to buy coffee and tumbles through ever-stranger universes.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/midcentury-toon/STYLE.md"><img src="docs/frames-ds/midcentury-toon.jpg" alt="Mid-century Cartoon"></a><br><b>Mid-century Cartoon</b><br><i>Meet Pip</i><br><sub>A robot vacuum set up in three steps, told like a 1950s classroom film.</sub></td>
</tr>
</table>

### Games

<table>
<tr>
<td width="33%" valign="top"><a href="styles/pixel-rpg/STYLE.md"><img src="docs/frames-ds/pixel-rpg.jpg" alt="16-bit Pixel RPG"></a><br><b>16-bit Pixel RPG</b><br><i>The Last Save Point</i><br><sub>At the final boss door a hero saves the game, and the save screen replays the whole journey.</sub></td>
<td width="33%" valign="top"><a href="styles/hd-2d/STYLE.md"><img src="docs/frames-ds/hd-2d.jpg" alt="HD-2D"></a><br><b>HD-2D</b><br><i>The Lampbearer</i><br><sub>The lighthouse goes dark; a girl carries the last flame through a night forest and up the storm cliffs.</sub></td>
<td width="33%" valign="top"><a href="styles/microgame/STYLE.md"><img src="docs/frames-ds/microgame.jpg" alt="Microgame Frenzy"></a><br><b>Microgame Frenzy</b><br><i>Five-Second Astronaut</i><br><sub>A clumsy cadet survives a five-second boot camp, faster and faster, until the boss: landing home.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/game-show/STYLE.md"><img src="docs/frames-ds/game-show.jpg" alt="Game Show Flat"></a><br><b>Game Show Flat</b><br><i>Rhythm of AI, 1997 → 2026</i><br><sub>The history of AI as a rhythm game: models take the stage on the beat, and a report card closes the show.</sub></td>
</tr>
</table>

### Cinema & Eras

<table>
<tr>
<td width="33%" valign="top"><a href="styles/silent-film/STYLE.md"><img src="docs/frames-ds/silent-film.jpg" alt="1920s Silent Film"></a><br><b>1920s Silent Film</b><br><i>The Runaway Loaf</i><br><sub>A baker&#x27;s boy chases a runaway loaf downhill, then breaks it in half for a hungry girl.</sub></td>
<td width="33%" valign="top"><a href="styles/backrooms/STYLE.md"><img src="docs/frames-ds/backrooms.jpg" alt="Liminal Found Footage"></a><br><b>Liminal Found Footage</b><br><i>Night Shift Orientation</i><br><sub>A new night-shift hire films their first night in an endless yellow office, following the rules on the wall.</sub></td>
</tr>
</table>

### Materials & 3D

<table>
<tr>
<td width="33%" valign="top"><a href="styles/brick-toy/STYLE.md"><img src="docs/frames-ds/brick-toy.jpg" alt="Brick Toy"></a><br><b>Brick Toy</b><br><i>Rocket from Spare Parts</i><br><sub>A brick astronaut builds a rocket from spare parts and flies to a brick moon.</sub></td>
<td width="33%" valign="top"><a href="styles/paper-popup/STYLE.md"><img src="docs/frames-ds/paper-popup.jpg" alt="Paper Pop-up Book"></a><br><b>Paper Pop-up Book</b><br><i>Pip&#x27;s Paper Adventure</i><br><sub>A pop-up book opens on a desk; a sprite named Pip adventures through paper worlds and jumps out into ours.</sub></td>
<td width="33%" valign="top"><a href="styles/tilt-shift/STYLE.md"><img src="docs/frames-ds/tilt-shift.jpg" alt="Tilt-Shift Miniature"></a><br><b>Tilt-Shift Miniature</b><br><i>Toy Town Rush Hour</i><br><sub>Morning rush hour in a town that looks like a model: traffic, trains and tiny people.</sub></td>
</tr>
<tr>
<td width="33%" valign="top"><a href="styles/lowpoly-island/STYLE.md"><img src="docs/frames-ds/lowpoly-island.jpg" alt="Low-poly Isometric Island"></a><br><b>Low-poly Isometric Island</b><br><i>The Island That Grew</i><br><sub>An island and its village grow tile by tile from an empty sea, each tile a note, into a starry night.</sub></td>
<td width="33%" valign="top"><a href="styles/glass-product/STYLE.md"><img src="docs/frames-ds/glass-product.jpg" alt="Glass Product Render"></a><br><b>Glass Product Render</b><br><i>Aura — Hear the Light</i><br><sub>Unboxing and close-ups of Aura, fictional glass earbuds, in strip-light sweeps and caustics.</sub></td>
</tr>
</table>
<!-- styles:end -->

## Licence

This fork: **riversxiao / Lemo-DeepSeek** · engines from **LemoLab × Claude Opus** demos.

- **Code and docs** (including `DEEPSEEK.md`, `AGENTS.deepseek.md`, `plugin/skills/lemo-deepseek`): **MIT**.
- **Upstream demo engines & their stills** (in `styles/`, when reused): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — credit **LemoLab** with a link to [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar), and note changes.
- **riversxiao showcase films & stills** (`showcase/`, Release `showcase-v001`, and the four sample thumbs in `docs/frames-ds/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — credit **riversxiao/lemo-opuscar** with a link to this repository.
- **Films you make with the library**: yours; no credit required.
- **Third-party assets in demos**: keep their own licences (see each demo’s `CREDITS`).

You are responsible for materials you use in your films.

---

<div align="center">

⭐ **Star this fork** · [riversxiao/lemo-opuscar](https://github.com/riversxiao/lemo-opuscar)<br>
👀 **Watch → Custom → Releases** for new sample drops<br>
<sub>Upstream engines: <a href="https://github.com/lemomo-ai/lemo-opuscar">lemomo-ai/lemo-opuscar</a></sub>

</div>
