# Budget ledger (showcase)

**Scope:** costs observed while building the deepseek-controller + 12-film matrix epic.  
**Timezone:** Asia/Shanghai (UTC+8).  
**Rule:** no secrets; mark unknowns as `unknown` / placeholders. Do **not** silently route free-tier failures to paid models (see 额度总管 / OpenCode pin).

## Machine ledger (preferred)

Append-only JSONL:

`tools/deepseek-controller/fixtures/budget-ledger.jsonl`

```sh
# summarize
python3 tools/deepseek-controller/cli.py budget summary

# append an honest line (paid call you approved, or a $0 local step)
python3 tools/deepseek-controller/cli.py budget append \
  --item "quality --delivery M01" --usd 0 --kind local --path-label controller \
  --duration 12.5 --project /workspace/films/matrix-fuli-swiss-controller

# one-shot seed from OpenCode session costs on this box
python3 tools/deepseek-controller/cli.py budget import-opencode --min-usd 0.01
# dry-run first:
python3 tools/deepseek-controller/cli.py budget import-opencode --min-usd 0.01 --dry-run
```

`cli.py handoff` logs a **$0** `kind=local` line unless `--no-budget`.  
Never invent token/$ — only write what you measured (OpenCode `session_v2.cost`, invoice, or explicit $0 local).

Module: `tools/deepseek-controller/budget.py`.

## Summary (known)

| When | Item | Path | Amount | Notes |
|---|---|---|---|---|
| 2026-10-28 | OpenCode → OpenRouter `deepseek/deepseek-v4.1-flash` | Flash films (fuli swiss, fensan pictogram, liudong caption, + whiteboard sibling) | **~$0.43** | Free OpenCode pool hit `FreeUsageLimitError` (429); later official flash 402 (balance); then explicit OpenRouter. **Do not repeat as default.** Seeded into JSONL via `budget import-opencode`. |
| 2026-10-29 | OpenCode free pool | glm-5.3-flash-free probe | **$0** | Still exhausted (429) at morning check; pin stays free; fail loud if free hangs |
| ongoing | Controller render | `cli.py` scaffold→still→video→mux | **$0 LLM** | Local Chromium Canvas2D; no Seedance/Kling |
| ongoing | TTS edge | `zh-CN-YunxiNeural` via edge-tts | **$0** | Default VO for controller + flash natives |
| ongoing | NLE handoff | openfilm / hyperframes / premiere XML | **$0** | Export artifacts only; no Studio license on box |
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
- 2026-10-28 four-film Flash batch ≈ **$0.43** after free exhaustion — ledger line above / JSONL import.
- Promotion to `--delivery` (2026-10-29): plan retrofit + quality only; M02 audio-only loudnorm; **$0** extra model spend.

### Handoff (`path=handoff`)
- OpenFilm / HyperFrames / Premiere XML packaging: **$0** cash; auto-logged on `cli.py handoff`.

## Placeholders / still unknown

| Item | Status |
|---|---|
| Exact OpenRouter per-token rate card behind the $0.43 day | unknown (session aggregates in OpenCode DB) |
| Box electricity / CI minutes | not tracked |
| HyperFrames Studio / paid HeyGen | not installed; would need user approval |
| Premiere / DaVinci license | N/A on box (XML handoff only) |

## Policy

1. Prefer **free** OpenCode models; on free fail → **stop + report**, never silent paid fallback.
2. Controller delivery films: local render + edge TTS unless user asks otherwise.
3. Prefer **`budget append` / `import-opencode`** over hand-editing this markdown; keep the table as a human summary.
4. Update this summary when a paid call is intentionally approved.
