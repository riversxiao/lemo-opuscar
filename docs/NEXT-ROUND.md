# 下一轮优化计划（采纳评估 · 2026-10-28）

评估对象：fork [`f3d2e1c`](https://github.com/riversxiao/wordfilm/commit/f3d2e1c934be18ac4cb816ecaa5e9d27176afaae) vs 上游基线 [`413a6bd`](https://github.com/lemomo-ai/lemo-opuscar/commit/413a6bd6d78ebd3bdd5abaec9538a26867f890df)。  
目标：**同样的视觉底座，换内容更可靠；相同的制作预算，影片更容易看懂。**

> **Opuscar Studio**：评估文档提到的 `../../opuscar-studio/README.md` **不在本构建机上**。在用户提供路径/仓库之前，**不假设可复用**；本 fork 内先做最小控制器（建议目录 `tools/deepseek-controller/` 或 `controller/`）。若日后拿到 Studio，再评估 JSON 计划 / hash / 预算账本 / 专家候选的迁入，避免双份控制器。完整清点见 [`tools/deepseek-controller/docs/STUDIO.md`](../tools/deepseek-controller/docs/STUDIO.md)（2026-10-29：仍为 MISSING）。

## P0（本 PR 已做）

`plugin/skills/lemo-deepseek/scripts/setup.sh` 三个版本锁定缺陷：

| ID | 修复 |
|---|---|
| P1-1 | 返回的 `LIB` 必须含 DeepSeek 覆盖层（`AGENTS.deepseek.md`、`DEEPSEEK.md`、`plugin/skills/lemo-deepseek/…`）；缺失则非零退出 |
| P1-2 | **所有**安装路径（首次 clone / managed 更新 / 用户自有库）在设置了 `LEMO_OPUSCAR_PIN`（现名 `WORDFILM_PIN`，旧名仍有效）时都会解析并检出；检出后核对 `HEAD` |
| P1-3 | 显式 PIN 无法兑现时 **exit 1**（不再「warn 后继续用本地」）；短 SHA 解析失败亦失败 |

回归：`plugin/skills/lemo-deepseek/scripts/setup-pin-tests.sh`。

**双钉说明**：`413a6bd` 是上游引擎基线（覆盖层之前），**不能**当作 DeepSeek 控制层 PIN。应分别记录：

- **引擎 / 上游基线提交**（demo 材质来源）
- **控制层 / 本 fork 提交**（DeepSeek 规程与 setup；完整 40 字符 SHA 或 tag）

## P1 下一轮：控制器（优先）

### 落地状态（MVP · `tools/deepseek-controller/`）

已合并最小控制器骨架（**尚未**跑满 12 支对照 / 真 DeepSeek API / Playwright 成片）：

| 组件 | 路径 |
|---|---|
| 计划 schema + 校验 | `tools/deepseek-controller/plan.schema.json` · `validate.py` |
| 三风格 manifest | `tools/deepseek-controller/manifests/{swiss,pictogram,caption}-*.json` |
| 适配器（只写 content/） | `tools/deepseek-controller/adapters/` |
| VO 排期（超目标则失败） | `tools/deepseek-controller/schedule.py` |
| `quality.json` 验收门 | `tools/deepseek-controller/quality.py` |
| CLI | `python3 tools/deepseek-controller/cli.py validate / adapt / scaffold / schedule / quality` |
| 三风格薄胶合 | `glue_base.py` + `glue_{swiss,pictogram,caption}.py` · `scaffold.py`（复制 demo、同步可触 sidecar、engine.lock；不改各风格核心） |
| 样例 / 回归 | `fixtures/` · `tests/test_mvp.sh` |

说明见 [`tools/deepseek-controller/README.md`](../tools/deepseek-controller/README.md)。

### 原计划要点

### 1. 结构化内容边界

- Flash 只输出**严格 JSON 计划**（题材、镜头、文案、数字、调色、允许的运动方案）；**不**接收 JS / shader / 表达式 / 任意路径。
- 校验计划 → **每风格固定适配器** → 受保护的 demo 引擎。
- 每风格一份**能力说明（manifest）**：语言、镜头/pose、数据规模、文案长度、时长、声音模式、字体/资源、受保护文件 hash；BRIEF 白名单由 manifest 生成。
- **保留风格运动语言**（Swiss 刀切网格、Pictogram 姿态节拍、Caption 关键词强调）；不要为统一 JSON 收成同一套淡入模板。
- 完成标准：同计划可重复构建；越权参数渲染前失败；底座/产物 hash；改一句文案不必重写整部影片程序。

### 2. 真实语音驱动时间轴

- 全局 `K = targetDur/demoDur` 仅作试片；最终排期：产出文案 → 合成并测量逐句 WAV → 按 **旁白时长 + 全文可读时间 + 进出场 + 稳定停留** 求镜长 → 吸附风格节拍网格。
- 字幕 / 旁白 / 镜头事件 / 混音共一份**已解析时间表**；旁白与字幕默认一致。
- 中文「跳过 ASR 词对齐」≠ 跳过语音完整性检查（句级/绝对秒仍核源 WAV 与最终混音）。
- TTS 最多回修 2 次后：输出**预览 + 失败证据**，不得标为正式交付 PASS。
- 底座 mix 与新时间轴不匹配时，适配器生成 cue 表，复用固定混音实现（禁止每片 Flash 自写 mix）。

### 3. 统一验收门（可阻断交付）

- 包装既有 `readcheck.mjs` / `asr_check.py`（已有失败退出码），统一写出 `quality.json`：`PASS` / `FAIL` / `NOT_CHECKED` / 有理由的 `NOT_APPLICABLE`。
- 必需检查缺失 → 阻断交付；无旁白可声明 ASR N/A，有旁白不得用缺依赖冒充通过。
- 建议发布标准：响度 **−14±1 LUFS**，真峰值 **≤ −1 dBTP**（给 AAC 留余量）。
- 黑场：按镜头声明允许区间 + 原因；深色镜头结合变化量/可见性复核。

建议首轮控制器范围：**Swiss + Pictogram + 纯图形 Caption 适配器 + 一个控制器**；对照矩阵 **3 风格 × 2 题材 × 2 路径 = 12 支**（锁定引擎人工路径 vs Flash 结构化编排；同题材同事实/声音/时长/规格）。

## P2：可复现与中文信息设计

- 公开三种优先风格的**影片工程源码**（不止 MP4 Release）；含 BRIEF、计划、内容数据、底座提交、字体/声音来源、已解析时间表、构建命令、`quality.json`、媒体 hash、费用账本（无密钥）。
- 每构建记录实际解析的引擎提交 + 控制层提交；PIN 失败必须退出。
- 成本按「每条合格成片」计：模型+语音+构建+失败尝试，另列人工分钟。
- 内容向：Swiss 累积/投入取出图形；Pictogram 中文主标题；Caption 数据驱动；Whiteboard 先 CJK 主标签+强调线，完整笔顺引擎另作强模型候选。

## 强模型介入

失败归因：内容 → Flash；环境/资源 → 控制器或停止；引擎 → 专家。专家只拿必要函数与证据，产出**隔离候选**，经回归后由维护者发版；禁止每片临时塞改正式引擎。

## 能力补强（Capability track · 与控制器并行）

与「视频大模型换人 / Seedance」划清界限：下列项与**代码做片**同构，可进本仓；H3 / Ref2VA / Seedance 短剧仍归酒楼诗人等线，不并入本 fork 主路径。**未实测前不得声称已完整接通。**

### 落地状态（2026-10-28 脚手架）

| # | 能力 | 路径 | Stub vs 已实现 |
|---|---|---|---|
| 1 | **OpenFilm NLE 手递** | `docs/integrations/nle-handoff.md` · `tools/openfilm_handoff.sh` · `tools/handoff/` | **v2 多分镜导出可用**（`film.html` + EDL + ffmpeg rebuild）；本机 `openfilm look` 已过；Studio GUI 需一次浏览器下载；Premiere XML / `frame(t)` 适配器 **未做** |
| 2 | **HyperFrames 备用轨** | `docs/integrations/hyperframes.md` · `tools/hyperframes_export.sh` | **导出可用** + 本机 `lint`；默认仍 Playwright；desktop/cloud/skills = needs-user |
| 3 | **中文 TTS 路由** | `tools/tts_router.md` · `core/tts/tts_router.py` · `cli.py tts` · `providers/` | edge + kokoro **ready**（`.venv-voice`）；qwen3/omnivoice **HTTP ready when `*_BASE` set**（不臆造 Key、不下载大模型）；`AGENTS.deepseek.md`：跳过词对齐 ≠ 跳过 VO 完整性 |
| 4 | **Remotion 信息图** | `docs/integrations/remotion.md` · `plugin/skills/lemo-remotion-infographic/SKILL.md` | 桥接说明 **stub**；不 vendoring Remotion 模板；不碰 Opus demo |
| 5 | Stickman my-style | `docs/integrations/stickman-style.md` + `MY-STYLES.md` 指针 | 调研笔记（偏 stix / 自研 SVG，勿走视频大模型） |
| 6 | 动效 / 合集 stitch | `docs/integrations/motion-and-stitch.md` | 计划短文 |
| 7 | 本地歌床 YuE2/Plenio | `docs/integrations/local-music.md` | 调研（VRAM / 许可注意） |

### Sprint 分期

| Sprint | 范围 |
|---|---|
| **A · 现在** | setup.sh P1（上节）+ 能力脚手架 + **`tools/deepseek-controller/` MVP** |
| **B** | TTS HTTP 客户端 MVP（`7946de1`）+ 真实 mux 片跑通 OpenFilm/HyperFrames handoff（本轮） |
| **C** | Remotion 桥接试做：一个 Caption 类中文题材（Flash 只填 props/data JSON） |
| **D** | HyperFrames 试片（非锁定引擎片）；Stickman styleframe；本地乐床 drop-in |

Playwright 逐帧仍为默认出片路径。不重生成片、不扩写 59 格。

## 明确不做（本轮）

- 不重跑 showcase 成片 / 不扩写全部 59 风格
- 不声称已集成 Opuscar Studio
- 不把 H3 换人、Seedance 短剧并进本仓主技能
