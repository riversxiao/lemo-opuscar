# DeepSeek Controller（MVP）

最小控制器：用**代码**卡住内容边界——Flash 只交严格 JSON 计划；适配器只写 `content/`；薄胶合脚手架复制锁定 demo；真实旁白驱动排期；`quality.json` 可阻断交付。

**不**在本目录改 `styles/*/demo` 引擎核心，**不**内嵌 DeepSeek API 调用，**不**声称已接入 Opuscar Studio。

---

## English (short)

Minimal controller for Lemo-DeepSeek: `validate` → `adapt` / **`scaffold`** → `schedule` → `quality`.

- Plan schema: `plan.schema.json` (content only; rejects code/path/shader-looking keys).
- Style manifests: `manifests/{swiss-motion,pictogram-motion,caption-news}.json`.
- Adapters write **content-only** files under `<project>/content/` (see `adapters/TOUCHABLES.md`).
- **`scaffold`**: copies `styles/<slug>/demo/` → project, runs adapt, Swiss thin-glues touchables (`lines.json`, `palette.json` sidecar, `CREDITS`), locks protected SHA-256. Never rewrites `ease.js` / `film.js` / shaders.
- `schedule` builds `timeline.parsed.json` from measured VO; **fails** if over target.
- `quality` writes `quality.json`; required `FAIL` / `NOT_CHECKED` blocks delivery.

### One-shot Swiss path (fixture)

```bash
# from repo root
python3 tools/deepseek-controller/cli.py scaffold \
  tools/deepseek-controller/fixtures/plan-swiss-motion.json \
  -o /tmp/film-fuli --lib "$PWD"

# same via shell wrapper:
# bash tools/deepseek-controller/scaffold_project.sh \
#   tools/deepseek-controller/fixtures/plan-swiss-motion.json -o /tmp/film-fuli --lib "$PWD"

# then: TTS → schedule → (render) → quality
python3 tools/deepseek-controller/cli.py schedule --project /tmp/film-fuli --require-vo
python3 tools/deepseek-controller/cli.py quality  --project /tmp/film-fuli --skip-heavy
bash tools/deepseek-controller/tests/test_mvp.sh
```

Pictogram / Caption: `scaffold` does **copy demo + adapt** only (stub); deep engine wire not implemented.

Do **not** full-render MP4 in CI — glue + hash tests are enough.

---

## 中文

### 一键 Swiss（样例计划）

```bash
# 在仓库根目录
python3 tools/deepseek-controller/cli.py scaffold \
  tools/deepseek-controller/fixtures/plan-swiss-motion.json \
  -o /tmp/film-fuli --lib "$PWD"
```

脚手架会：

1. 复制 `styles/swiss-motion/demo/` → 项目（引擎锁定）
2. `adapt` → `content/*`
3. 只改可触文件：根目录 `lines.json`、`palette.json`（sidecar，**不**改 `film.js` 的 `C`）、`CREDITS`；写入 `content/engine.lock.json`
4. 写出 `PROJECT.md`（后续 TTS → schedule → still/video/mix/mux → quality）

**禁止**改：`ease.js` / `film.js` / `main.js` / `mix.py` / `index.html` / `fonts/**`

### 逐步命令

```bash
python3 tools/deepseek-controller/cli.py validate tools/deepseek-controller/fixtures/plan-swiss-motion.json
python3 tools/deepseek-controller/cli.py adapt tools/deepseek-controller/fixtures/plan-swiss-motion.json -o /tmp/film-fuli-content-only

# 旁白合成后
python3 tools/deepseek-controller/cli.py schedule --project /tmp/film-fuli --require-vo
python3 tools/deepseek-controller/cli.py quality --project /tmp/film-fuli --media /tmp/film-fuli/out.mp4
```

回归：`bash tools/deepseek-controller/tests/test_mvp.sh`

### 目录

| 路径 | 作用 |
|---|---|
| `plan.schema.json` | 计划字段说明（代码侧以 `validate.py` 为准） |
| `manifests/*.json` | 三风格能力说明 / 白名单 |
| `adapters/` | 计划 → `content/*`；`TOUCHABLES.md` 约定 |
| `glue_swiss.py` / `scaffold.py` | 复制 demo + 薄胶合 |
| `scaffold_project.sh` | 脚手架 shell 入口 |
| `schedule.py` | VO → `timeline.parsed.json` |
| `quality.py` | 统一 `quality.json` |
| `fixtures/` | 复利 / 分散 / 流动性样例 |
| `cli.py` | `validate \| adapt \| scaffold \| schedule \| quality` |

### 与评估文档的对应

见 [`docs/NEXT-ROUND.md`](../../docs/NEXT-ROUND.md) P1。本目录落地控制器 + Swiss 薄胶合；12 支对照与完整 Playwright 出片不在本 PR。
