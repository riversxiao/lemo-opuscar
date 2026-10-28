# Lemo Export NLE

Mux 之后除 MP4 外，导出可交剪辑的工程包（OpenFilm `film.html` + CMX3600 EDL + ffmpeg rebuild）。

## 状态（2026-10-29）

**可用导出（v2）。** 多分镜手递已实现并在本机用真实成片跑通 `openfilm look`。Premiere/DaVinci 专用 XML 仍未做；用 EDL + master 或 OpenFilm Studio 导出。

## 用法

```sh
bash tools/openfilm_handoff.sh <film_dir>
# or
python3 tools/deepseek-controller/cli.py handoff --project <film_dir> --target openfilm
```

写出 `<film_dir>/openfilm-handoff/`：

- `film.html` — 每镜一个 `<video src="assets/master.mp4#t=in,out" at="…">`
- `assets/master.mp4` + 可选 `assets/vo/`、`assets/music.wav`
- `timeline.edl` — CMX3600 画面事件
- `rebuild_shots.sh` / `ffmpeg_concat.txt` — 离线切镜再拼接
- `manifest.json`

详情：[`docs/integrations/nle-handoff.md`](../../../docs/integrations/nle-handoff.md)。

## 非目标

- 不替代 Playwright 出片。
- 不把锁定 `styles/*/demo` 引擎改写成 OpenFilm `frame(t)`。
- 不调用视频大模型。
