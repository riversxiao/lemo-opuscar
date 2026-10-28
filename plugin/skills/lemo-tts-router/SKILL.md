# Lemo TTS Router

中文旁白路由：默认 **edge-tts 云希**；第二条真路径 **kokoro**（离线，`.venv-voice`）；`qwen3` / `omnivoice` 在设置 `LEMO_TTS_*_BASE` 后走已实现的 HTTP 客户端（无 Key 不臆造）。

## 实现入口

- CLI：`python core/tts/tts_router.py lines.json out_dir [--provider edge|kokoro|qwen3|omnivoice|auto] [--fallback edge,kokoro]`
- 列表：`python core/tts/tts_router.py --list`
- 控制器：`python3 tools/deepseek-controller/cli.py tts --project <film> [--provider …]`
- 合同：[`tools/tts_router.md`](../../../tools/tts_router.md)
- Provider：`core/tts/providers/`（`edge`·`kokoro` 委托现有脚本；`qwen3`·`omnivoice` = HTTP client，需自托管 BASE）

## 路由表

| id | 状态 |
|---|---|
| `edge` | 生产默认（`tts_zh.py`，需网络） |
| `kokoro` | 离线真路径（`tts.py` + `lang: cmn`；需 `.venv-voice` / `LEMO_TTS_PYTHON`） |
| `qwen3` | HTTP ready when `LEMO_TTS_QWEN3_BASE` set；否则 `needs-server` |
| `omnivoice` | 同上（`LEMO_TTS_OMNIVOICE_BASE`） |
| 用户 WAV | 允许；仍过完整性检查 |

## 验收

跳过 ASR **词**对齐 ≠ 跳过 VO 完整性。任意 provider：每句非静音 WAV + `dur.json`；终混仍含该语音；画面/字幕中文与朗读一致。

## 非目标

- 不在仓库提交 API Key 或多 GB 权重。
- 不把未配置 BASE 的 HTTP provider 标成已支持生产。
