# Lemo Export NLE（研究桩）

Mux 之后除 MP4 外，导出可交剪辑的工程（Premiere / DaVinci / HTML 工程包）。灵感来自 openfilm 一类「片子即工程」做法。

## 状态

**Research stub · 2026-10-28。** 无稳定 CLI、无已验证的 Premiere/DaVinci XML 写出实现。不要在制片主路径里假装本技能已可用。

## 目标输入（拟定）

- 已解析时间表（与控制器 `timeline` 同源）
- 素材清单：帧序列或中间 ProRes/PNG、旁白 WAV、混音 stem、字幕
- 元数据：帧率、分辨率、风格 slug、控制层/引擎提交

## 目标输出（拟定）

```
export/<film-id>/
  film.mp4                 # 已有 mux 产物（不变）
  premiere/…               # TODO: FCPXML / Premiere 可导入结构
  davinci/…                # TODO: DRP 或 XML + media relatives
  html/index.html          # TODO: 可 scrub 的时间轴预览页
  manifest.json            # 素材与时间码索引
```

已有最小手递：`tools/openfilm_handoff.sh`（把成片 MP4 包成单镜 `film.html` 工程，**不是**把 lemo 引擎迁成 frame(t)）。

## TODO

1. 调研 openfilm / 同类开源导出格式与许可。
2. 先实现 `manifest.json` + HTML scrubber（最低可用），再攻 NLE XML。
3. 接入点：`mux.sh` 成功且 `quality.json` 非 FAIL 交付后可选调用。
4. 禁止在本技能里改 `styles/*/demo` 引擎。

## 非目标

- 不替代 Playwright 出片。
- 不调用视频大模型。
