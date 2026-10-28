# DeepSeek 覆盖层（先读本文件，再读 AGENTS.md）

本文件覆盖 Claude Code 专属假设。库内其余规程（`STYLE.md` 不变式、Treatment first、自检清单）仍然有效。

## 角色

你是导演 + 工程师。用 **代码**（Canvas2D / WebGL / three.js + Playwright 逐帧 + TTS/采样乐 + ffmpeg）出片。  
**禁止**调用 Seedance、Kling、Runway、Sora、可灵、即梦等任何视频大模型。

## 提问

- 不要使用 `AskUserQuestion`。用一条消息、编号选项问完：语言、素材、是否先审分镜、机器缺什么。
- 用户已说清的跳过。等回复后，其余用合理默认，总结 brief 就开工，不要连环追问。

## 引擎锁定（Flash 强制）

1. 写完 `TREATMENT.md` 之后，再运行 `sh plugin/skills/lemo-deepseek/scripts/setup.sh demo <slug>`（或 `$LIB` 内等价命令）。
2. 把 `styles/<slug>/demo/` **整份复制**到项目目录（可改名 `engine/`），作为底座。
3. **允许改：** `timeline` / 镜头表、文案与旁白、配色变量、时长、`content` / `lines` 类数据、字幕、CREDITS 故事相关字段。
4. **禁止改（除非更强模型接手且用户明确要求）：** 笔刷/水彩引擎、shader、全局 RNG/seed、精灵缓存、角色骨骼与缓动核心、混音脚手架算法、`core/`、`styles/` 库文件。
5. 先 `still.mjs` 出关键帧对照 `STYLE.md`，再 `video.mjs` 全片。
6. 时长建议 25–40 秒；并行 workers 2–3。

## 模型分工

| 模型 | 职责 |
|---|---|
| DeepSeek Flash | 编排、TREATMENT、改内容、跑 still/tts/mux、读自检结果 |
| DeepSeek V3 / Reasoner（或用户指定的更强模型） | 仅修补 Flash 搞不定的硬核函数（花屏、景深坏掉、角色滑步、锁格失败） |

## 推荐起步风格（Flash）

Swiss Motion · Pictogram Motion · Data Storytelling · Caption News · Blueprint · Whiteboard · Risograph · Halftone · ASCII/CRT · Dark Keynote

难风格（Watercolor、Ink Wash、Impasto、Cel Anime、Brick Toy、Paper Pop-up）：默认「改 demo 参数」，不要从零写引擎。

## 生产循环

```
write TREATMENT.md
→ demo <slug> → copy engine into project
→ adapt timeline/content/palette only
→ still.mjs 关键帧 vs STYLE.md
→ tts (+ asr_check) ∥ sampler/sfx
→ video.mjs --fps 24
→ mix.py → mux.sh
→ sheet.py + blackdetect + ebur128 → 一轮修复 → 交付
```

## 与上游 AGENTS.md 的关系

冲突时以本文件为准（提问方式、引擎锁定、模型分工）。其余章节按 `AGENTS.md` / `DIRECTOR.md` / `TECHNIQUE.md` 执行。

## 实测调教（2026-10-28 · 复利 Swiss 对照）

对照 DeepSeek Flash 与人工引擎锁定版后，Flash 侧强制遵守：

1. **只改内容层**；允许用全局时间缩放 `K = targetDur/demoDur` 压轴；**禁止改** `ease.js` 与刀切/网格/缓动核心。
2. **BRIEF 附参考**：至少 2 张官方 demo still（或 `still.mjs` 关键帧）+ `STYLE.md` 不变式清单（单信号色、巨号、刀切/该风格 native moves）。
3. **中文约定**：旁白按 `。` 拆句；版式与朗读可分离（如 `say` / `text`）；画面与字幕默认全中文（除非 brief 要求双语）。
4. **TTS↔时间轴最多回修 2 次**，然后强制 `still.mjs` → 成片，禁止为抠时长无限改短句。
5. **路径与额度**：在 `films/` 工程里调用工具一律用 `$LIB` 绝对路径；缺 librosa 时用 ffmpeg `atempo` 压乐床；OpenCode 官方 DeepSeek 额度不足时改用 `openrouter/deepseek/deepseek-v4.1-flash`。OpenCode `-s` session id **只能 ASCII**（如 `ses_fuli_swiss`），中文放 `--title`。

