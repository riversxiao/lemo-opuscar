# Lemo Remotion Infographic

用 Remotion 做**数据/字幕信息图**第二引擎，与 Swiss Motion / Caption News **互补**，不替代官方 demo 底座。

详细桥接说明见 [`docs/integrations/remotion.md`](../../../docs/integrations/remotion.md)。

## 状态

**可用 · 2026-10-29。** 本技能自带一个最小 Remotion 模板、一个 plan → props 转换器、一个渲染并接入现有 mux 的脚本。端到端已跑通：控制器 fixture 计划 → props → 1920x1080 与 1080x1920 @ 24 fps 成片 → `core/render/mux.sh`（−14 LUFS），以及透明 WebM 叠加到风格渲染之上。

| 文件 | 作用 |
|---|---|
| `template/` | Remotion 4 工程（`remotion` / `@remotion/cli` 4.0.539，React 19.2）。`src/Root.tsx` 注册 `Infographic`（1920x1080）与 `InfographicPortrait`（1080x1920），都是 24 fps，时长取自 props |
| `template/src/Infographic.tsx` | 全部由 props 驱动的 7 种场景：`title` 标题卡、`chapter` 章节卡、`caption` 关键词字幕条、`bigNumber` 大数字、`compare` 对比条、`chart` 柱状序列、`end` 片尾 |
| `template/props.schema.json` | props 字段子集（JSON Schema，唯一事实来源） |
| `scripts/plan_to_props.py` | 控制器 `plan.json` → `props.json`（只用标准库），自带 `--check` 校验 |
| `scripts/setup.sh` | 把模板拷进影片项目、准备字体、`npm install` |
| `scripts/render.sh` | `remotion render` → 全画面 mp4 或透明 WebM 叠加 → `core/render/mux.sh` |

许可提醒：Remotion 本身不是 MIT，个人与小团队免费，公司使用需看 [Remotion License](https://www.remotion.dev/license)。模板代码随本库许可，字体为 OFL。

## 硬边界

- **禁止**读取后修改 `styles/*/demo` 或把 Remotion 输出写回 Opus 引擎文件。
- Remotion 工程放在影片项目目录（如 `films/<id>/remotion/`）或 `~/lemo-my-styles/`，与 `$LIB/styles` 隔离。`setup.sh` 拒绝 `$LIB/styles` 下的任何目标。
- Flash/控制器仍只许改内容 JSON（`plan.json` 或 `props.json`）；合成图经 mux 或叠加进入时间轴，而非任意注入 shader。`src/*.tsx` 只在开发模板时改，做片时不改。

## 适合题材

- 数字对比、累积曲线、关键词字幕条、章节卡片（讲解/词卡类）。
- 不适合：依赖官方笔刷/水彩/角色骨骼的难风格。

## 1. 模板：1080p24，字体与库内策略对齐

```sh
sh "<skill>/scripts/setup.sh" films/<id>          # 打印 REMOTION=<films/<id>/remotion>
```

- 已存在的 `films/<id>/remotion/` 不会被覆盖（只刷新字体），所以 props 与改动安全。
- 字体全部自托管在项目 `public/fonts/`，渲染时不连 Google Fonts（同 `TECHNIQUE.md` 的字体规则）：
  - 正文对：**Inter Tight**（拉丁、数字）+ **Noto Sans SC**（中文），与控制器引擎同一批文件，由 `tools/deepseek-controller/fetch_fonts.py --style remotion-infographic` 下载；离线时设 `LEMO_FONT_CACHE` 指向已有字体目录。
  - 库内展示字体：`core/fonts/` 整个拷到 `public/fonts/core/`，`src/fonts.ts` 读取这份 `fonts.css` 逐条注册 `@font-face`，所以族名与 `core/fonts/fonts.css` 完全一致（`Fredoka`、`Lilita One`、`IM Fell English`、`ZCOOL KuaiLe`；后者只有约 200 字，不够正文）。
  - 任一字体加载失败就 `cancelRender`，不会悄悄出豆腐块。
- 竖屏布局把文字放在 y 220..1600，和库内原生 9:16 风格的安全带一致。

## 2. JSON → Remotion props（与控制器计划对齐）

```sh
python3 "$LIB/tools/deepseek-controller/cli.py" validate plan.json          # 先过控制器校验
python3 "<skill>/scripts/plan_to_props.py" plan.json -o films/<id>/remotion/props.json
python3 "<skill>/scripts/plan_to_props.py" plan.json --timeline films/<id>/content/timeline.json -o …   # 有实测旁白时
```

| plan.json | props.json |
|---|---|
| `aspect` 16:9 / 9:16 | `width`x`height` 1920x1080 / 1080x1920；合成 `Infographic` / `InfographicPortrait` |
| `targetDurationSec` | `durationInFrames` = 秒 × 24；有 `--timeline` 时取 `scheduledDurationSec` 与每镜 `t0/t1` |
| `shots[].onScreenText` | `lines`：`|` 换行，`{词}` 为强调色片段（与 Caption News 写法相同）；空时用 `text` |
| `shots[].text` | `voText`（旁白原文，留作字幕或校对） |
| `shots[].role` | `chapter` → chapter，`end`/`credits` → end，`hook`/`setup` → title，其余 → caption |
| `shots[].data` | 一个数组 → `chart`；一个数 → `bigNumber`（0..1 的小数且无 `unit` 时显示为 %）；2–4 个数 → `compare`（`现金|{快}|房产|{慢}` 这种成对文字作条目名）；字符串只认 `unit`；布尔值是引擎开关，丢弃并提示 |
| `palette.page / ink / signal(或 accent)` | `palette.bg / ink / accent`，`muted` 由 ink 与 bg 混出 |
| `credits` | 片尾署名行 |

没有 `--timeline` 时按 `schedule.py` 同一套阅读时长估算分配目标时长（`beats` 作下限）。画不诚实的输入直接报错退出（非 0）：不支持的 aspect、一个镜头里数组和数字混用、负数做条形、超过 12 根柱 / 4 条对比、镜头太多每镜不足 1 秒、未知展示字体（`--display` 只能选正文对或 `core/fonts` 里的族名）。`--check props.json` 只校验。

## 3. 渲染并挂进现有 mux

```sh
# 全画面：picture.mp4 → mux.sh（grain 默认 0，矢量画面）
sh "<skill>/scripts/render.sh" films/<id>/remotion --audio films/<id>/mix.wav --out films/<id>/<id>.mp4

# 叠加：透明 props → VP8+alpha WebM → 叠在同尺寸风格渲染上 → mux.sh
python3 "<skill>/scripts/plan_to_props.py" plan.json --overlay -o films/<id>/remotion/overlay-props.json
sh "<skill>/scripts/render.sh" films/<id>/remotion --props films/<id>/remotion/overlay-props.json \
   --over films/<id>/out/picture.mp4 --audio films/<id>/mix.wav --out films/<id>/<id>.mp4
```

- 合成按 `props.aspect` 自动选；props 与合成方向不符时 Remotion 直接报错，不会出黑边片。
- 不带 `--audio` 时停在画面（`out/picture.mp4` 或 `out/composite.mp4`），之后照常 `sh core/render/mux.sh <画面> mix.wav out.mp4 24 0`。
- 叠加底片必须与 props 同尺寸（竖屏用 `video.mjs --size 1080x1920` 渲染）；脚本会检查。
- 设了 `PLAYWRIGHT_CHROME` 就用它当浏览器（库里的 chrome-headless-shell 可用）；`--frames 0-47` 只渲一段做检查。
- 需要 PNG 序列时直接用 Remotion：`npx remotion render src/index.ts Infographic out/frames --sequence --image-format=png --props=props.json`，再 `ffmpeg -framerate 24 -i out/frames/element-%03d.png -c:v libx264 -pix_fmt yuv420p out/picture.mp4`（序号位数随总帧数变，以 `out/frames/` 里的实际文件名为准）后进 mux。

## 非目标

- 不把 Remotion 设为默认 `video.mjs` 替代。
- 不调用视频大模型生成画面。
- 不在测试里 `npm install`：`npm test` 只测转换器；设 `WORDFILM_REMOTION_DIR=<films/<id>/remotion>` 才会真的渲 12 帧（两种方向）。
