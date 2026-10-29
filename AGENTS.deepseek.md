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
→ cli.py dialogue-loop --project <film> --max-rounds 4（确定性门禁 + DeepSeek flash 评审 + 只改被标记行，自循环到 PASS；不需要人工逐句 check）——未 PASS 禁止 tts
→ still.mjs 关键帧 vs STYLE.md
→ tts (+ asr_check) ∥ sampler/sfx
→ video.mjs --fps 24
→ mix.py → mux.sh
→ cli.py visual-check --project <film> --media <mp4> --rework（看成片：抽帧 OCR 对照排期字幕/大字、字幕≠正在说的那句、出画/安全框、黑帧/坏帧/冻结、对比度、阅读时长 + 免费视觉模型看每镜联系表；high 自动修 ≤2 轮、只重渲受影响帧段，修不好标 BEST_EFFORT）
→ cli.py quality --delivery（visual_check、speaker_consistency 都是必过项）→ 交付
```

- visual-check 只用免费：本地 ffmpeg/OpenCV/RapidOCR；语义层只调 OpenRouter `:free` 视觉模型（默认 `dots-studio/dots-3-note-preview:free`，`provider.max_price=0`），每镜前后读 `/api/v1/key` usage，任何增量立即停；没有免费模型可用就标 NOT_AVAILABLE，不回落付费。证据：`evidence/visual-check.json` + `evidence/visual-check/{sheets,issues,frames}`。
- 多句旁白必须是**同一个人**：`quality` 的 `speaker_consistency`（Resemblyzer GE2E，本地 CPU，`.venv-spk`）每句对其余句质心余弦 ≥0.80、两两 ≥0.70，否则 high FAIL。

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
- 第二条真路径：**kokoro**（离线；`.venv-voice` 或 `LEMO_TTS_PYTHON`）。`python core/tts/tts_router.py --list` 看 ready。
- 控制器：`python3 tools/deepseek-controller/cli.py tts --project <film> [--provider auto|kokoro|edge|stepaudio]`。`tts` 先查 `dialogue-check` PASS **且** `evidence/dialogue-loop.json` PASS（sha 锁定台词）；任一不满足即拒绝。
- `stepaudio`：阶跃星辰 **限时免费预览** `stepaudio-3-gen-preview`（`/v1/audio/generate`，按文字描述设定音色）；只在显式 `--provider stepaudio` 时用，不进 auto。Key 只读环境变量 `STEPFUN_API_KEY`。**禁止**调付费 TTS（`/v1/audio/speech`、`stepaudio-3-tts`、`step-tts-*`）与 ASR；代码里已白名单拒绝。预览接口**没有音色锁定**：文档写明 gen-preview 不支持 `voice`/`voice_label`，reference_to_audio「暂未开放」，复刻音色只给付费 TTS；实测传 `voice`（boyinnansheng / qinqienvsheng）HTTP 200 但被忽略（女声 id 出来仍是同一男声，embedding 0.885–0.953）。逐句请求 = 每句一个新说话人（speaker 门禁 0.746/0.589 FAIL）。所以默认 **session 模式**（`LEMO_TTS_STEPAUDIO_MODE=session`）：全片台词作为同一说话人的连续 scripts **一次请求**（≤1000 字），本地 faster-whisper 字级时间对齐 + 停顿处切句（`providers/vo_split.py`，对齐 <85% 直接失败）；实测 speaker 0.887/0.784 PASS（Yunxi 0.866/0.785）。`per-line` 模式（按中位音高重录）仅作对照。可用 `LEMO_TTS_STEPAUDIO_SPEED` 调速以塞进目标时长。
- `elevenlabs`：ElevenLabs 云端 TTS（`eleven_multilingual_v2`，适合中文旁白）。只在显式 `--provider elevenlabs` 时用，不进 auto。Key 只读 `ELEVENLABS_API_KEY`（别名 `ELEVEN_API_KEY`）；音色 `ELEVENLABS_VOICE_ID`（默认 `21m00Tcm4TlvDq8ikWAM` / Rachel）。无 key 时 `--list` 报 `needs-key`。密钥从不打印。
- `elevenlabs-dialogue`：ElevenLabs **Text-to-Dialogue** 多说话人（`POST /v1/text-to-dialogue`，模型优先 `eleven_v4` 回退 `eleven_v3`）。只在显式 `--provider elevenlabs-dialogue` 时用。台词需带 `speaker`；音色用 `ELEVENLABS_VOICE_HOST` / `ELEVENLABS_VOICE_GUEST` 或 `ELEVENLABS_VOICE_MAP`。与单声线 `elevenlabs`（`/v1/text-to-speech`）分开；这是对话 TTS 层，不是完整播客流水线。
- 配乐：`cli.py mix --project <film> --bed-source stepaudio` 调 `stepaudio-3-music-preview`（限时免费，`instrumental:true` 纯器乐），原始 1–3 min 输出存 `music/stepaudio_raw.wav`，裁到片长 + 淡入淡出 + RMS 对齐 → 走原有 ducking。有缓存，不重复请求。
- `qwen3` / `omnivoice`：HTTP 客户端已接；仅当设置 `LEMO_TTS_QWEN3_BASE` / `LEMO_TTS_OMNIVOICE_BASE` 时为 ready（不臆造 Key）。见 [`tools/tts_router.md`](tools/tts_router.md)。
- **「中文跳过 ASR 词对齐」只影响词级时间事件，不影响语音内容完整性检查。** 无论哪个 provider：`lines.json` 每句都要有非静音 WAV + `dur.json`；成片混音须保留这些语音；画面/字幕中文与朗读内容一致（可标点），禁止默默缩短意译。
- 无旁白片可在质量报告里把 ASR 标为 `NOT_APPLICABLE`；有旁白片不得用「缺依赖」冒充通过。
