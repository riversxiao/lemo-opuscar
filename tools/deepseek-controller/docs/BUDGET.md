# Budget ledger (showcase)

**Scope:** costs observed while building the deepseek-controller + 12-film matrix epic.  
**Timezone:** Asia/Shanghai (UTC+8).  
**Rule:** no secrets; mark unknowns as `unknown` / placeholders. Do **not** silently route free-tier failures to paid models (see 额度总管 / OpenCode pin).

## Summary (known)

| When | Item | Path | Amount | Notes |
|---|---|---|---|---|
| 2026-10-28 | OpenCode → OpenRouter `deepseek/deepseek-v4.1-flash` | Flash films (fuli swiss, fensan pictogram, liudong caption, + whiteboard sibling) | **~$0.43** | Free OpenCode pool hit `FreeUsageLimitError` (429); later official flash 402 (balance); then explicit OpenRouter. **Do not repeat as default.** |
| 2026-10-29 | OpenCode free pool | glm-5.3-flash-free probe | **$0** | Still exhausted (429) at morning check; pin stays free; fail loud if free hangs |
| ongoing | Controller render | `cli.py` scaffold→still→video→mux | **$0 LLM** | Local Chromium Canvas2D; no Seedance/Kling |
| ongoing | TTS edge | `zh-CN-YunxiNeural` via edge-tts | **$0** | Default VO for controller + flash natives |
| optional | TTS kokoro | local onnx | **$0** | Proof route; not delivery default |
| optional | TTS qwen3 / omnivoice | self-host HTTP | **unknown** | Needs `LEMO_TTS_*_BASE`; no key invented |
| music bed | soft-pulse / procedural | local | **$0** | See MUSIC-BED.md |
| fonts | Google Fonts fetch | `fetch_fonts.py` | **$0** | Bandwidth only |
| ASR gate | faster-whisper `small` | local CPU int8 | **$0** | Cached HF model on box |
| AIGC video | Seedance / Kling / etc. | — | **not used** | Hard rule for this library |

## Per-path notes

### Controller (`path=controller`)
- Plan → adapt → scaffold → tts → schedule → mix → quality: **no cloud LLM** once plan exists.
- Cross-style cells (M03/M04/M07/M08/M11/M12) reused locked demos + content overlays; cost = box CPU/GPU time only (**unknown wall-clock $**; treat as $0 cash).

### Flash (`path=flash`)
- Agent edits under OpenCode / DeepSeek Flash: **cash cost only when routed to paid OpenRouter**.
- 2026-10-28 four-film Flash batch ≈ **$0.43** after free exhaustion — ledger line above.
- Promotion to `--delivery` (2026-10-29): plan retrofit + quality only; M02 audio-only loudnorm; **$0** extra model spend.

## Placeholders / still unknown

| Item | Status |
|---|---|
| Exact OpenRouter token breakdown for the $0.43 day | unknown (aggregate only) |
| Box electricity / CI minutes | not tracked |
| HyperFrames Studio / paid HeyGen | not installed; would need user approval |
| Premiere / DaVinci license | N/A (XML handoff only) |

## Policy

1. Prefer **free** OpenCode models; on free fail → **stop + report**, never silent paid fallback.
2. Controller delivery films: local render + edge TTS unless user asks otherwise.
3. Update this ledger when a paid call is intentionally approved.
