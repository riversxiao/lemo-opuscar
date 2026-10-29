# DeepSeek 版使用说明（WordFilm）

本 fork（[riversxiao/wordfilm](https://github.com/riversxiao/wordfilm)）在上游 [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) 之上，增加了 **DeepSeek Flash 友好** 的技能与规程。

上游本质不变：用编码智能体写确定性 `render(t)` 做片，**不用视频大模型**。官方 demo 引擎由 Claude Opus 5.5 写成；DeepSeek 侧采用 **「Opus 引擎作只读底座 + Flash 改内容 + 偶发强模型补丁」**。

## 快速开始

```bash
git clone https://github.com/riversxiao/wordfilm.git
cd wordfilm

# 可选：钉死 DeepSeek 控制层提交（完整 40 字符 SHA 或 tag；勿用裸上游 413a6bd）
# 413a6bd 是引擎/上游基线，不含本 fork 覆盖层；setup 钉到无覆盖层的提交会失败退出
# 改名前的 LEMO_OPUSCAR_PIN / LEMO_OPUSCAR_HOME / LEMO_OPUSCAR_REPO 仍然有效（WORDFILM_* 优先）
export WORDFILM_PIN=f3d2e1c934be18ac4cb816ecaa5e9d27176afaae

sh plugin/skills/lemo-deepseek/scripts/setup.sh
sh plugin/skills/lemo-deepseek/scripts/setup.sh deps
# 需要旁白 / 拨弦时再加：
# sh plugin/skills/lemo-deepseek/scripts/setup.sh deps voice
# sh plugin/skills/lemo-deepseek/scripts/setup.sh deps music
```

把 DeepSeek 宿主（OpenCode / Cursor / 自建 Agent）的技能指向：

`plugin/skills/lemo-deepseek/SKILL.md`

并确保 agent 能读到：

- `AGENTS.deepseek.md`（先读）
- `AGENTS.md` · `DIRECTOR.md` · `TECHNIQUE.md`
- 所选 `styles/<slug>/STYLE.md`

## 模型接入

三条路由任选其一（宿主 agent 调 DeepSeek，片子本身不调任何视频模型 API）：

1. **DeepSeek 官方 API（推荐）**：base URL `https://api.deepseek.com`，模型 `deepseek-flash`（V4.1-Flash）或 `deepseek-v4-pro`。在 OpenCode 里 `/connect` → 选 `deepseek` → 粘贴 Key；或设环境变量 `DEEPSEEK_API_KEY`。文档：[Coding Agents 接入](https://api-docs.deepseek.com/guides/coding_agents)、[价格](https://api-docs.deepseek.com/quick_start/pricing)。
2. **OpenRouter 回退**：`openrouter/deepseek/deepseek-v4.1-flash`（无官方 Key 或被限流时）。
3. **OpenCode 免费档**：`opencode/deepseek-v4.1-flash-free`（可能没额度）。

> Key 只放在环境变量或 OpenCode 凭据里；不要让 agent 把 Key echo 到聊天、shell 日志或提交里。

## 最佳方案（摘要）

1. **底座锁定，不是「看一眼参考」。** 复制 `styles/<slug>/demo/` 进项目，Flash 只改 timeline / 文案 / 配色。
2. **双模型。** Flash 编排；硬核函数交给更强 DeepSeek。
3. **简单风格先跑通。** Swiss Motion 等矢量信息图类。
4. **验收自动化。** still 关键帧、readcheck、asr_check、contact sheet、loudnorm −14 LUFS。

完整规则见 `AGENTS.deepseek.md` 与 `plugin/skills/lemo-deepseek/SKILL.md`。

## 还需要更多「CC 5.5 / Opus 产出代码」吗？

| 情况 | 要不要额外 Opus 代码 |
|---|---|
| 用库内已有 59 个风格出片 | **一般不用。** 官方 `demo/` 本身就是 Opus 5.5 写的引擎；`setup.sh demo <slug>` 拉下来即可当底座 |
| Flash 改内容后某风格仍翻车（花屏、角色滑步） | **先**把坏掉的函数丢给更强 DeepSeek 修；仍不行再考虑用 Claude Code 按该 `STYLE.md` 重出一版引擎放进 `~/lemo-my-styles/` |
| 要做库里没有的新风格 | **需要。** 用 Claude Code / Opus 走一遍 `MY-STYLES.md` 做出引擎底座，再交给 Flash 日常改内容 |
| 酒楼诗人 / 词卡等固定视觉要复用 | **建议做一次**「我的风格」：Opus 或强模型沉淀 `STYLE.md` + 引擎，之后 Flash 只换 TREATMENT |

**当前不缺参考的起步包：** `swiss-motion`、`pictogram-motion`、`dataviz`、`caption-news`、`blueprint`、`whiteboard`（先 `setup.sh demo <slug>`）。

若你之后用 Claude Code 跑出了更好的引擎，把项目目录或 `film.js` / `index.html` 丢回本仓库的 `reference-engines/<slug>/`，并在 PR 说明来源与许可即可。

## 实测调教（写入 Skill）

详见 [`AGENTS.deepseek.md`](AGENTS.deepseek.md)：

- **「实测调教」五条**：内容层 + `K` 压缩、BRIEF 附 still、中文拆句、TTS 回修上限 2 次、`$LIB` 路径与模型路由（官方 API 优先、OpenRouter 回退）/ ASCII session id。
- **「多风格 BRIEF 硬规则」**：BRIEF 白名单、无实拍替代镜头、中文×绝对秒、字体/mix 预置、旁白与画面同句、信息图样片优先 Swiss / Pictogram / Caption。

试片与对照见 [`showcase/`](showcase/README.md)。

## 控制器（MVP）

内容边界开始用代码卡住（计划校验 → 风格适配器 → VO 排期 → `quality.json`）：

- 目录与用法：[`tools/deepseek-controller/README.md`](tools/deepseek-controller/README.md)
- 计划：`python3 tools/deepseek-controller/cli.py validate|adapt|schedule|quality …`
- 竖屏：计划加 `"aspect": "9:16"`（默认 `"16:9"`），渲染 1080x1920；caption-news / swiss-motion / pictogram-motion 都支持（原生竖屏版式）。`PROJECT.md` 的渲染命令自动带 `--size`。
- 下一轮范围：[`docs/NEXT-ROUND.md`](docs/NEXT-ROUND.md)

Flash 仍须先复制官方 `demo/` 引擎；控制器**只写** `content/` 与时间表/质量报告，不改引擎核心。

## 安全提示

- 默认 `setup.sh` 在 managed clone 上会拉远端；本 DeepSeek 技能默认指向 **本 fork**，并支持 `WORDFILM_PIN`（旧名 `LEMO_OPUSCAR_PIN` 仍有效；完整 SHA 优先）。**无 DeepSeek 覆盖层的库或 PIN 会非零退出**。引擎基线提交与控制层 fork 提交应分别记录（见 `docs/NEXT-ROUND.md`）。
- 中文旁白 `tts_zh.py` 走微软 edge-tts（出网）；可改用离线 Kokoro。
- 不要把含密钥的环境变量暴露给会执行 shell 的 agent。

## 上游同步

```bash
git remote add upstream https://github.com/lemomo-ai/lemo-opuscar.git  # 若尚未添加
git fetch upstream
git merge upstream/main   # 或 rebase；解决冲突时保留 DEEPSEEK.md / AGENTS.deepseek.md / plugin/skills/lemo-deepseek/
```

## 许可

与上游相同：代码与文档 MIT；样片与静帧 CC BY 4.0。用户自制片归用户。DeepSeek 规程文件同 MIT。
