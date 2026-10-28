# Opuscar Studio · inventory (box · 2026-10-29)

**Status on this box: MISSING.** Do not claim Studio is installed, wired, or available for delivery.

This note inventories what “Opuscar Studio” means for the DeepSeek fork, what is (and is not) on the build machine, and how it relates to `tools/deepseek-controller/` Swiss / Pictogram / Caption adapters.

---

## 1. What the fork means by “Opuscar Studio”

[`docs/NEXT-ROUND.md`](../../../docs/NEXT-ROUND.md) cites an **evaluation document** at a sibling path:

```text
../../opuscar-studio/README.md
```

That path was expected to describe a richer controller / studio layer whose pieces might later migrate into this fork:

| Hoped-for piece (eval language) | Why it mattered |
|---|---|
| JSON plan | Flash / agent emits structure, not free JS |
| Hash / engine lock | Demo cores stay pin-able |
| Budget ledger | Cost per accepted film |
| Expert candidates | Isolated engine patches, not per-film hacks |

**Decision already taken (Sprint A):** until that Studio tree is provided, build a **minimal in-repo controller** (`tools/deepseek-controller/`) and **do not claim Studio integration** (see NEXT-ROUND “明确不做”).

This inventory re-checked the box on **2026-10-29 (Asia/Shanghai)**. The sibling README is still absent.

---

## 2. Box status (hard facts)

| Check | Result |
|---|---|
| `/workspace/opuscar-studio` | **absent** |
| `/home/box/opuscar-studio` | **absent** |
| Relative `../../opuscar-studio` from repo / workspace | **absent** |
| `opuscar` / Studio binary on `PATH` | **absent** |
| Installed HyperFrames CLI (`hyperframes`) | **absent** |
| OpenFilm project / `npx openfilm` tree on box | **absent** |
| In-repo Studio product under `tools/` or `plugin/` | **none** (controller + stubs only) |

**Conclusion:** Opuscar Studio is **not present** on this box. There is **no local install path, license file, API, or CLI** to call from the three-style adapters today.

---

## 3. Names that look similar (do not conflate)

### 3.1 Community “Opuscar Studio” GitHub repos (public)

These are **documentary production houses that use Lemo-Opuscar**, not the missing sibling evaluation Studio, and **not** vendored into this fork:

| Repo | What it is | License signal |
|---|---|---|
| [ansaribilal14/opuscar-studio](https://github.com/ansaribilal14/opuscar-studio) | “Documentary Engine” — agent docs (`BRAIN.md`), film workspaces, Releases | GitHub license field empty; embeds / depends on lemo-opuscar (upstream MIT) |
| [superz1402/documentary-engine](https://github.com/superz1402/documentary-engine) | Public film library / landing page; README still titles “Opuscar Studio — Video Library” | Same pattern (pipeline on lemo-opuscar) |

They share vocabulary (timeline, TTS, mix, Releases) with lemo workflows, but they are **not** a drop-in JSON-plan controller for Swiss / Pictogram / Caption demos, and cloning them does **not** satisfy NEXT-ROUND’s Studio dependency.

### 3.2 HyperFrames Studio (HeyGen)

Desktop + browser editor for [HyperFrames](https://hyperframes.heygen.com) (Apache-2.0 open-source CLI; optional HeyGen-hosted features may bill separately). Documented as a **stub alternate rail** only: [`docs/integrations/hyperframes.md`](../../../docs/integrations/hyperframes.md). **Not installed on this box.** Not Opuscar Studio.

### 3.3 OpenFilm Studio

OpenFilm’s editor / NLE surface (`npx openfilm open …`, MIT). This fork has a **research stub** handoff (`plugin/skills/lemo-export-nle/`, `tools/openfilm_handoff.sh`) — single-shot `film.html` pack, **not** a full Studio install. **Not on this box.**

### 3.4 `styles/*/demo/studio.js`

Files such as `styles/glass-product/demo/studio.js` and `styles/white-model/demo/studio.js` are **style demo modules**, not a product named Opuscar Studio.

### 3.5 Upstream Lemo-Opuscar

[lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) describes itself as a **style toolbox / Claude skill** (“works like a small studio”), MIT + demo CC BY 4.0. It does **not** ship a separate “Opuscar Studio” product binary in the public tree.

---

## 4. Fit for deepseek-controller adapters

| Adapter | Needs from a Studio product | Current substitute in-repo |
|---|---|---|
| Swiss (`swiss_motion`) | Plan → content; VO schedule; quality gate | `adapters/swiss_motion.py` + `scaffold` / `schedule` / `quality --delivery` |
| Pictogram (`pictogram_motion`) | Same + EDL / brand / optional style version | `edl_runtime.json`, `brand_strings.json`, `finance-v001` |
| Caption (`caption_news`) | Same + timeline / facts / assets prep | `timeline_content` + caption style version path |

**Plug-in verdict:** **cannot plug Studio into the adapters today** — nothing to point at. Overlap already owned by the controller: JSON plan schema, manifests, engine hash lock, VO-driven schedule, `--delivery` quality gate, optional music bed. Still **missing vs eval wish-list** (and therefore still “Studio-shaped gaps”):

- Per-film **budget ledger** (model + TTS + build + fail retries, no secrets)
- Formal **expert-candidate** workflow (isolated engine PR, not per-film patches)
- Any Studio GUI / multi-agent orchestration API

Avoid dual controllers: if Studio later arrives, **diff its plan/hash/ledger/expert pieces against `tools/deepseek-controller/`** and migrate only the gaps — do not re-implement a second plan→adapt path.

---

## 5. Install / license / user decision

| Option | Action allowed without further approval | Needs user decision |
|---|---|---|
| Keep using `deepseek-controller` only | **Yes** (current path) | — |
| User drops private / sibling `opuscar-studio` tree | Document path + re-inventory | Provide absolute path or clone URL + access |
| Clone public `ansaribilal14/opuscar-studio` as “Studio” | Research read-only OK | **Do not** treat as the eval Studio or wire as adapter backend without explicit OK |
| Install HyperFrames Studio app / paid HeyGen features | — | **Approval required** (desktop app / account / possible paid tiers) |
| Install OpenFilm + open Studio in browser | Research OK; npm install needs intent | Confirm before `npx` installs on the box |

**This inventory did not install any Studio product or paid software.**

---

## 6. Recommended next step

1. **If you have the evaluation Studio** (the `../../opuscar-studio/README.md` tree): put it on the box (path or private clone) and ask for a **diff against `tools/deepseek-controller/`** — import only ledger + expert-candidate gaps.
2. **If you do not:** treat Studio as **out of scope**; continue controller gaps (12-film matrix, HyperFrames/OpenFilm only as optional rails; TTS multi-route is wired — see docs/TTS.md).
3. **Do not** rename community documentary repos or HyperFrames/OpenFilm as “Opuscar Studio integrated.”

---

## 7. Pointers

- Plan / policy: [`docs/NEXT-ROUND.md`](../../../docs/NEXT-ROUND.md)
- Controller: [`tools/deepseek-controller/README.md`](../README.md)
- HyperFrames stub: [`docs/integrations/hyperframes.md`](../../../docs/integrations/hyperframes.md)
- NLE handoff stub: `plugin/skills/lemo-export-nle/SKILL.md`

*Inventory date: 2026-10-29 (Asia/Shanghai). Re-run path checks if the user adds a Studio tree.*
