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
→ 台词定稿（读 $LIB/DIALOGUE.md：字段 + 门禁 + TTS 前活人感）——未过门禁禁止 tts；可与上步交错，不拦 demo
→ 写入 lines.json（旁白与画面同句；戏剧字段见 DIALOGUE.md）
→ still.mjs 关键帧 vs STYLE.md
→ tts (+ asr_check) ∥ sampler/sfx
→ video.mjs --fps 24
→ mix.py → mux.sh
→ sheet.py + blackdetect + ebur128 → 一轮修复 → 交付
```

无旁白：TREATMENT 写明「无 VO」，跳过「台词定稿」与 tts。

## 与上游 AGENTS.md 的关系

冲突时以本文件为准（提问方式、引擎锁定、模型分工）。其余章节按 `AGENTS.md` / `DIRECTOR.md` / `DIALOGUE.md` / `TECHNIQUE.md` 执行。旁白与对白以 `DIALOGUE.md` 为准；TTS 工具细节仍以 `TECHNIQUE.md` §4 为准。

## 实测调教（2026-10-28 · 复利 Swiss 对照）

对照 DeepSeek Flash 与人工引擎锁定版后，Flash 侧强制遵守：

1. **只改内容层**；允许用全局时间缩放 `K = targetDur/demoDur` 压轴；**禁止改** `ease.js` 与刀切/网格/缓动核心。
2. **BRIEF 附参考**：至少 2 张官方 demo still（或 `still.mjs` 关键帧）+ `STYLE.md` 不变式清单（单信号色、巨号、刀切/该风格 native moves）。
3. **中文约定**：旁白按 `。` 拆句；版式与朗读可分离（如 `say` / `text`）；画面与字幕默认全中文（除非 brief 要求双语）。
4. **TTS↔时间轴最多回修 2 次**，然后输出当前预览 + 失败证据（`quality` / 日志）；**验收未过不得标为正式交付**。禁止为抠时长无限改短句。
5. **路径与额度**：在 `films/` 工程里调用工具一律用 `$LIB` 绝对路径；缺 librosa 时用 ffmpeg `atempo` 压乐床；模型优先走 DeepSeek 官方 API（OpenCode `/connect` → `deepseek`，`DEEPSEEK_API_KEY`，模型 `deepseek-flash`）；没有官方 Key 或被限流时改用 OpenRouter `openrouter/deepseek/deepseek-v4.1-flash`；OpenCode 免费档 `opencode/deepseek-v4.1-flash-free` 可能没额度。OpenCode `-s` session id **只能 ASCII**（如 `ses_fuli_swiss`），中文放 `--title`。


## 多风格 BRIEF 硬规则（2026-10-28）

多风格样片试跑后追加；与上文「实测调教」五条并用。

1. **BRIEF 白名单优于整份 STYLE**：每个项目 BRIEF 必须写死「允许改的文件名」「禁止改的文件」「可用 pose / 镜头 k 白名单」「精确 still/video/mux 命令」。不要只扔 STYLE.md 全文。
2. **无实拍风格先声明替代路径**：Caption News 等只允许 `stock|loss|stress|end`（或该风格等价纯图形镜头）；禁止 Flash 去拉 demo 实拍包。
3. **中文 × 词级时间轴**：凡依赖 `words.json` / `at(id,word)` 的风格（如 Whiteboard），BRIEF 强制「绝对秒时间轴 + 跳过 ASR 词对齐」；板上可拉丁、旁白可中文时必须写明。**跳过词对齐 ≠ 跳过语音完整性检查**：仍须核源 WAV 与最终混音（句级/绝对秒即可）。
4. **字体与混音预置**：BRIEF 写明字体已就位（Inter/Noto 等）与 mix 降级路径（demo mix 绑旧时间轴时允许项目内自写 mix）。
5. **旁白必须跟画面同句**：`audio/lines.json` 朗读文本与画面/字幕中文一致（可加标点），禁止缩短意译导致「没把字读全」；语速默认 `+0%`，勿默认 `+6%`。
6. **优先风格**：信息图 / 讲解类样片优先 Swiss Motion、Pictogram Motion、Caption News（纯图形）；Whiteboard 慎用或接受英文字板。
7. **台词门禁：** 有旁白时，BRIEF / TREATMENT 须指向 `$LIB/DIALOGUE.md`；`lines.json` 含 `function`（及可选 `want`/`speaker`）；TTS 前过句长 ≤35 字、钩子在前 3 拍、字速估时 ±15%、禁止金句升华与缩短意译。Cel Anime / Sci-Fi Sitcom 自动跑角色戏三问（见 `DIALOGUE.md` §7）。可选跑 `plugin/skills/lemo-dialogue`。

## 下一轮

控制器、真实 VO 排期、统一验收与能力补强见 [`docs/NEXT-ROUND.md`](docs/NEXT-ROUND.md)。
MVP CLI：[`tools/deepseek-controller/README.md`](tools/deepseek-controller/README.md)（`validate` → `adapt` → `schedule` → `quality`）。Flash 输出严格 JSON 计划，不要直接改引擎核心。

## VO / TTS（所有供应商）

- 默认中文旁白：`python core/tts/tts_zh.py`（edge-tts 云希/晓晓）或 `python core/tts/tts_router.py … --provider edge`。
- 路由与自托管计划见 [`tools/tts_router.md`](tools/tts_router.md)；`qwen3` / `omnivoice` 目前为 stub。
- **「中文跳过 ASR 词对齐」只影响词级时间事件，不影响语音内容完整性检查。** 无论哪个 provider：`lines.json` 每句都要有非静音 WAV + `dur.json`；成片混音须保留这些语音；画面/字幕中文与朗读内容一致（可标点），禁止默默缩短意译。
- 无旁白片可在质量报告里把 ASR 标为 `NOT_APPLICABLE`；有旁白片不得用「缺依赖」冒充通过。
