# Showcase · riversxiao 的 DeepSeek 金融词卡试片

本目录是 [riversxiao/lemo-opuscar](https://github.com/riversxiao/lemo-opuscar) 的自有成片墙：用 **DeepSeek Flash**（`openrouter/deepseek/deepseek-v4.1-flash`）+ 上游 Opus demo **引擎锁定**，做「一词一图」金融短片。**不用** Seedance / Kling / Runway / Sora 等视频大模型。

成片 MP4 不进 git 主树，统一挂在 Release：**[showcase-v001](https://github.com/riversxiao/lemo-opuscar/releases/tag/showcase-v001)**。

规程：[`AGENTS.deepseek.md`](../AGENTS.deepseek.md)（实测调教 + 多风格 BRIEF 硬规则）· [`DEEPSEEK.md`](../DEEPSEEK.md)  
对照笔记：[`COMPARE.md`](COMPARE.md)

## 方法（一句话）

```
TREATMENT → setup.sh demo <slug> → 只改内容层 → still → TTS/乐 → video → mix → mux → 自检
```

Flash 改 timeline / 文案 / 配色；禁止改 shader、缓动核心、`core/`、库内 `styles/`。词卡优先 **Swiss Motion · Pictogram Motion · Caption News（纯图形）**；Whiteboard 慎用。

## 四支试片

| # | 主题 | 风格 | 时长 | 旁白 | 静帧 | 下载 |
|---|---|---|---|---|---|---|
| 1 | 复利 | Swiss Motion | ~31 s | 中文云希 | [01](stills/fuli-01.jpg) · [02](stills/fuli-02.jpg) | [mp4](https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/fuli-swiss-ds-v001.mp4) |
| 2 | 分散投资 | Pictogram Motion | ~31 s | 无 VO（鼓点） | [01](stills/fensan-01.jpg) · [02](stills/fensan-02.jpg) | [mp4](https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/fensan-pictogram-ds-v001.mp4) |
| 3 | 流动性 | Caption News | ~30 s | 中文云希 | [01](stills/liudong-01.jpg) · [02](stills/liudong-02.jpg) | [mp4](https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/liudong-caption-ds-v001.mp4) |
| 4 | 对冲是什么 | Whiteboard | ~32 s | 中文云希 | [01](stills/duichong-01.jpg) · [02](stills/duichong-02.jpg) | [mp4](https://github.com/riversxiao/lemo-opuscar/releases/download/showcase-v001/duichong-whiteboard-ds-v001.mp4) |

### 静帧预览

<table>
<tr>
<td align="center" width="25%"><img src="stills/fuli-01.jpg" alt="复利 Swiss"><br><sub>复利 · Swiss</sub></td>
<td align="center" width="25%"><img src="stills/fensan-01.jpg" alt="分散 Pictogram"><br><sub>分散 · Pictogram</sub></td>
<td align="center" width="25%"><img src="stills/liudong-01.jpg" alt="流动性 Caption"><br><sub>流动性 · Caption</sub></td>
<td align="center" width="25%"><img src="stills/duichong-01.jpg" alt="对冲 Whiteboard"><br><sub>对冲 · Whiteboard</sub></td>
</tr>
<tr>
<td align="center"><img src="stills/fuli-02.jpg" alt="复利 2"></td>
<td align="center"><img src="stills/fensan-02.jpg" alt="分散 2"></td>
<td align="center"><img src="stills/liudong-02.jpg" alt="流动性 2"></td>
<td align="center"><img src="stills/duichong-02.jpg" alt="对冲 2"></td>
</tr>
</table>

## 观感摘要

- **最稳**：Pictogram、Caption（纯图形）——内容层边界清楚，Flash 很少碰引擎。
- **可用**：Swiss —— `K` 压轴 + 中文拆句即可。
- **最难**：Whiteboard —— 单线字体无汉字 → 「板上拉丁、嘴里中文」；必须绝对秒，跳过 ASR 词对齐。

旁白「中文云希」= 微软 Azure / edge-tts 女声 Yunxi，非真人。

## 上游

引擎与 59 种风格来自 [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar)（Opus 5.5 demo）。本 showcase 仅展示本 fork 的 DeepSeek 工作流与自制片。
