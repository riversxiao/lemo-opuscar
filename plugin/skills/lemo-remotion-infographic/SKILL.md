# Lemo Remotion Infographic（研究桩）

用 Remotion 做**数据/字幕信息图**第二引擎，与 Swiss Motion / Caption News **互补**，不替代官方 demo 底座。

详细桥接说明见 [`docs/integrations/remotion.md`](../../../docs/integrations/remotion.md)。

## 状态

**Research stub · 2026-10-28。** 可复用宿主侧已有 Remotion 技能（若环境有）；本仓库尚未放入可渲染模板。

## 硬边界

- **禁止**读取后修改 `styles/*/demo` 或把 Remotion 输出写回 Opus 引擎文件。
- Remotion 工程放在影片项目目录（如 `films/<id>/remotion/`）或 `~/lemo-my-styles/`，与 `$LIB/styles` 隔离。
- Flash/控制器仍只许改内容 JSON；合成图经适配器进入时间轴，而非任意注入 shader。

## 适合题材

- 数字对比、累积曲线、关键词字幕条、章节卡片（讲解/词卡类）。
- 不适合：依赖官方笔刷/水彩/角色骨骼的难风格。

## TODO

1. 选定最小 Remotion 模板（1080p24、中文字体加载方式与库内 Noto/Inter 策略对齐）。
2. 定义 JSON → Remotion props 的字段子集（与控制器计划对齐）。
3. 导出 PNG/WebM 序列后如何挂进现有 mux（文档化一种路径即可）。

## 非目标

- 不把 Remotion 设为默认 `video.mjs` 替代。
- 不调用视频大模型生成画面。
