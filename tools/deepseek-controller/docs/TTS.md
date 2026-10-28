# Controller TTS

Wire-up for `cli.py tts` → `core/tts/tts_router.py`.

## On this box (2026-10-29)

| Provider | State | How |
|---|---|---|
| **edge** | ready | system `edge-tts` → Yunxi (`tts_zh.py`) |
| **kokoro** | ready | `.venv-voice` + `core/tts/kokoro-v1.0.onnx` |
| qwen3 | needs-server | set `LEMO_TTS_QWEN3_BASE` (HTTP client implemented; no key invented) |
| omnivoice | needs-server | set `LEMO_TTS_OMNIVOICE_BASE` |

Proof (fuli l1 only, did not replace Yunxi delivery WAVs):

```bash
python3 tools/deepseek-controller/cli.py tts \
  --project /workspace/films/fuli-controller-e2e \
  --lines /tmp/fuli-l1-lines.json \
  --out /workspace/films/fuli-controller-e2e/voices/proof-kokoro \
  --provider kokoro --fallback '' --no-post-words
```

Contract: [`../../tts_router.md`](../../tts_router.md).
