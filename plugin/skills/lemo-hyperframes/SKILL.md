# lemo-hyperframes — alternate rail **export** (+ optional local CLI)

Read [`docs/integrations/hyperframes.md`](../../../docs/integrations/hyperframes.md) and [`docs/integrations/nle-handoff.md`](../../../docs/integrations/nle-handoff.md).

## 状态（2026-10-29）

**导出可用。** `bash tools/hyperframes_export.sh <film>` 写出可 `npx hyperframes lint` 的工程。默认出片仍是 Playwright。桌面 Studio / HeyGen cloud / skills 安装 = **needs-user**。

## 用法

```sh
bash tools/hyperframes_export.sh <film_dir>
# or
python3 tools/deepseek-controller/cli.py handoff --project <film_dir> --target hyperframes --lint
```

## When not to use

- Engine-locked DeepSeek Flash job that must stay on demo Playwright contract
- User only asked for Premiere/Resolve → prefer `lemo-export-nle` / OpenFilm

## Needs-user

- Desktop HyperFrames app
- `hyperframes auth` / cloud render
- Interactive `npx hyperframes skills update`

Never claim Opuscar Studio is connected via this path.
