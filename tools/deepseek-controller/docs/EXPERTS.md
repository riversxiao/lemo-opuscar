# Expert / capability candidates

Shortlist of **next investments** after the 18-film matrix (18/18 filled, 16/18 delivery-pass). Priority is impact × fit with deepseek-controller — not fluff.

| Priority | Candidate | Why next | Depends on |
|---|---|---|---|
| **P0** | Flash delivery-gate maturity | Flash cells now pass `--delivery`, but path still hand-retrofits `plan.json` / voices layout. Codify `flash→controller` adaptor (lines/timeline → plan + schedule) so new Flash cuts gate without one-off scripts. | MATRIX flash aliases |
| **P0** | Caption×flash 30s fit (M14/M16) | Cross×flash done (M13–M18, ¥4.61 DeepSeek official); both caption cells overflow the locked 30s timeline. Give Flash a per-shot char budget from the scheduler in the BRIEF, or let caption accept a 32s DUR. | MATRIX-18.md |
| **P1** | Premiere / FCP XML polish | `nle-handoff` exists; harden round-trip + one documented import per style. Unlocks human color/VO finish without re-render. | nle-handoff.md |
| **P1** | HyperFrames desktop (if available) | Handoff JSON already exports; Studio inventory found no Opuscar Studio product — HyperFrames is the nearest composition UI. | User approval for app install |
| **P1** | Budget ledger automation | Partly done: `budget append --cny/--session-id`, balance-delta per run. Emit per-film `evidence/cost.json` (provider, tokens/$, TTS route, retries) from OpenCode/controller hooks — no secrets. | BUDGET.md |
| **P2** | qwen3 / omnivoice self-host | TTS router already has stubs; local/near-local VO reduces edge drift and ASR retries. | Server + `LEMO_TTS_*_BASE` |
| **P2** | Remotion second engine | Parallel path for React-timeline styles; keep engine-lock philosophy (content vs core). Only if Remotion demos map cleanly to plan schema. | remotion skills / owner OK |
| **P2** | Caption Commons packs | Shared stock/loss/stress assets for diversify/compound cells; cuts Flash “fetch 410MB” footgun. | E2E-caption |
| **P3** | Swiss German-poster literal rebrand toolkit | texts_runtime + brand packs so Flash/controller share one rebrand recipe. | E2E-swiss |
| **P3** | Opuscar Studio (if user provides tree) | STUDIO.md: diff ledger + expert-candidate gaps only — **do not** dual-controller. | User drops path/clone |

## Explicitly deferred / out of scope

- Seedance / Kling / other AIGC video generators for this library
- Silent OpenRouter paid fallback when free pool is empty
- Unlocking hashed demo engines without a named style-version sibling

## How to pick the next knife

1. If Free OpenCode is healthy → **P0 cross-style × flash** cell or two.  
2. If editing/finish pain → **P1 NLE XML** or HyperFrames (with approval).  
3. If VO/ASR flake dominates → **P2 self-host TTS**.  
4. Always log cash spend into [BUDGET.md](BUDGET.md).
