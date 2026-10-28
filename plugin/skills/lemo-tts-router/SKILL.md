# Lemo TTS Router

中文旁白路由：默认 **edge-tts 云希**；可插拔 `kokoro` / 调研中的 `qwen3` / `omnivoice`。

## 实现入口

- CLI：`python core/tts/tts_router.py lines.json out_dir [--provider edge|kokoro|qwen3|omnivoice]`
- 合同：[`tools/tts_router.md`](../../../tools/tts_router.md)
- Provider：`core/tts/providers/`（`edge`·`kokoro` 委托现有脚本；`qwen3`·`omnivoice` 为 **HTTP stub**，未实现客户端）
- 可选依赖注释：`requirements-voice-extra.txt`（**不会**被 `setup.sh deps voice` 安装）

## 路由表

| id | 状态 |
|---|---|
| `edge` | 生产默认（`tts_zh.py`） |
| `kokoro` | 已有 voice tier（中文需 `lang: cmn`） |
| `qwen3` | stub → 需自托管 OpenAI-compatible `/v1/audio/speech` |
| `omnivoice` | stub → 同上 |
| 用户 WAV | 允许；仍过完整性检查 |

## 验收

跳过 ASR **词**对齐 ≠ 跳过 VO 完整性。任意 provider：每句非静音 WAV + `dur.json`；终混仍含该语音；画面/字幕中文与朗读一致。

## 非目标

- 不在仓库提交 API Key 或多 GB 权重。
- 不把 stub provider 标成已支持生产。
