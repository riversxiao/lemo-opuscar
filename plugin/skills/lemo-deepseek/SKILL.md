---
name: lemo-deepseek
description: Direct and produce a short film made entirely in code with DeepSeek Flash (or stronger DeepSeek), using the WordFilm style library. Prefer this over the Claude-only lemo-opuscar skill when the coding agent is DeepSeek. Same styles (Swiss Motion, Watercolor, Caption News, etc.). Engine-lock workflow: copy an Opus demo engine, change content only. Not for editing the user's existing video files, and not for Seedance/Kling/MJ video models.
---

# WordFilm（DeepSeek Flash 版）

本技能把 WordFilm（fork 自上游 [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar)）的**代码做片**管线接到 DeepSeek（优先 Flash）。**禁止调用任何文生视频 / 图生视频 API。**

官方样片引擎由 Claude Opus 5.5 写成；Flash 的最佳路径是 **把 demo 引擎当只读底座，只改故事与参数**，而不是从零重写笔刷。细则见仓库根目录 [`DEEPSEEK.md`](../../../DEEPSEEK.md) 与 [`AGENTS.deepseek.md`](../../../AGENTS.deepseek.md)。

## 启动步骤

1. **拿库。** 运行 `sh "<skill base directory>/scripts/setup.sh"`。默认仓库是 fork：`https://github.com/riversxiao/wordfilm`。最后一行打印 `LIB=<path>`。若要钉死版本：`export WORDFILM_PIN=<full-sha-or-tag>`（旧名 `LEMO_OPUSCAR_PIN` 仍有效）（完整 SHA 优先；钉到无 DeepSeek 覆盖层的提交会失败）。setup.sh 自己克隆的库（`lemo.managed`）会重置到 `WORDFILM_REPO` 的 `main`，所以改名前克隆的 `~/lemo-opuscar` 现在跟随 fork；用户在里面有改动的话先让他拷出来。仍用旧插件 id `lemo-opuscar@lemolab` 的用户：见 `$LIB/README.zh-CN.md` 的「从 Lemo-Opuscar 迁移」。
2. **装依赖。** 立刻后台跑 `sh "<skill base directory>/scripts/setup.sh" deps`。需要旁白再 `deps voice`，拨弦再 `deps music`。系统缺 Node 20+ / ffmpeg / Python 3.11+ 时在一轮提问里报告，不要擅自装系统包。
3. **跟规程。** 先读 `$LIB/AGENTS.deepseek.md`（DeepSeek 覆盖层），再读 `$LIB/AGENTS.md`、`$LIB/DIRECTOR.md`、`$LIB/TECHNIQUE.md`，按 **Start → 一轮提问 → TREATMENT → 复制引擎 → 生产 → 自检** 执行。

## 与 Claude 版的差异

| | |
|---|---|
| 提问工具 | **禁止**依赖 `AskUserQuestion`；用编号选项的纯文本一轮问完 |
| 生产默认 | **引擎锁定**：`setup.sh demo <slug>` 后把 `styles/<slug>/demo/` 拷进项目，只改 timeline / content / palette / 旁白；禁止重写笔刷、shader、全局 RNG、角色骨骼 |
| 模型分工 | Flash 编排与改内容；水彩 / 水墨 / 3D / 复杂缓动出问题的函数，交给更强 DeepSeek（V3 / Reasoner）修一小段再塞回 |
| 起步风格 | Swiss Motion、Pictogram Motion、Data Storytelling、Caption News、Blueprint、Whiteboard |
| 项目目录 | 用户启动目录下的 `<name>/`（小写、数字、连字符） |
| 跑工具 | `cd "$LIB" && node core/render/still.mjs "<project-abs>" …` |
| Demo | TREATMENT 写完后再 `setup.sh demo <slug>`；学技术、换故事，不抄样片剧情 |

交付物严格按 `$LIB/DIRECTOR.md` §11，并告诉用户文件在哪。

## 控制器（内容边界）

写完 TREATMENT、选定风格后，优先走结构化计划而不是手改引擎：

1. 按 `$LIB/tools/deepseek-controller/plan.schema.json` 写出计划 JSON（只含题材/镜头/文案/数字/调色/白名单运动）。
2. `python3 "$LIB/tools/deepseek-controller/cli.py" validate <plan.json>`
3. `… adapt <plan.json> -o "<project>"` → 只生成 `content/`（见 `content/TOUCHABLES.md`）。
4. 写完 lines.json 先跑 `… dialogue-loop --project "<project>" --max-rounds 4`（门禁 + DeepSeek flash 评审 + 定点改写自循环，见 `$LIB/DIALOGUE.md` §5.1）；不 PASS 不准 TTS，也不要让用户逐句人工 check。BEST_EFFORT 如实报告。
5. TTS 后写 `voices/dur.json`，再 `… schedule --project "<project>" --require-vo`。
   可选 `--provider stepaudio`（阶跃免费预览 gen-preview，`STEPFUN_API_KEY`；付费 TTS/ASR 禁用）与 `mix --bed-source stepaudio`（免费 music-preview 纯器乐床）。
6. 成片后 `… quality --project "<project>" --media <out.mp4>`；`quality.json` 非 PASS 不得标正式交付。

说明：`$LIB/tools/deepseek-controller/README.md` · 计划见 `$LIB/docs/NEXT-ROUND.md`。

