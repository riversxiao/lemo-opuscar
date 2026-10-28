# DeepSeek Controller（MVP）

最小控制器：用**代码**卡住内容边界——Flash 只交严格 JSON 计划；适配器只写 `content/`；薄胶合脚手架复制锁定 demo；真实旁白驱动排期；`quality.json` 可阻断交付。

**不**在本目录改 `styles/*/demo` 引擎核心，**不**内嵌 DeepSeek API 调用，**不**声称已接入 Opuscar Studio。

---

## English (short)

Minimal controller for Lemo-DeepSeek: `validate` → `adapt` / **`scaffold`** → `schedule` → `quality`.

- Plan schema: `plan.schema.json` (content only; rejects code/path/shader-looking keys).
- Style manifests: `manifests/{swiss-motion,pictogram-motion,caption-news}.json`.
- Adapters write **content-only** files under `<project>/content/` (see `adapters/TOUCHABLES.md`).
- **`scaffold`** (all three styles): copy `styles/<slug>/demo/` → project, adapt, sync touchable sidecars only, write `engine.lock.json` + `PROJECT.md`. Never rewrites style cores (`ease.js`/`film.js`, `engine.js`/`edl.js`, or `main.js`).
- `schedule` builds `timeline.parsed.json` from measured VO; **fails** if over target.
- `quality` writes `quality.json`; required `FAIL` / `NOT_CHECKED` blocks delivery.

### One-shot paths (fixtures)

```bash
# from repo root
LIB="$PWD"
CTL=tools/deepseek-controller

python3 $CTL/cli.py scaffold $CTL/fixtures/plan-swiss-motion.json \
  -o /tmp/film-fuli --lib "$LIB"

python3 $CTL/cli.py scaffold $CTL/fixtures/plan-pictogram-motion.json \
  -o /tmp/film-diversify --lib "$LIB"

python3 $CTL/cli.py scaffold $CTL/fixtures/plan-caption-news.json \
  -o /tmp/film-liquidity --lib "$LIB"

# shell wrapper (same args):
# bash $CTL/scaffold_project.sh $CTL/fixtures/plan-swiss-motion.json -o /tmp/film-fuli --lib "$LIB"

python3 $CTL/cli.py schedule --project /tmp/film-fuli --require-vo
python3 $CTL/cli.py quality  --project /tmp/film-fuli --skip-heavy
bash $CTL/tests/test_mvp.sh
```

Do **not** full-render MP4 in CI — glue + hash tests are enough.

---

## 中文

### 三风格一键脚手架

```bash
LIB="$PWD"
CTL=tools/deepseek-controller

# Swiss · 复利
python3 $CTL/cli.py scaffold $CTL/fixtures/plan-swiss-motion.json \
  -o /tmp/film-fuli --lib "$LIB"

# Pictogram · 分散投资
python3 $CTL/cli.py scaffold $CTL/fixtures/plan-pictogram-motion.json \
  -o /tmp/film-diversify --lib "$LIB"

# Caption · 流动性
python3 $CTL/cli.py scaffold $CTL/fixtures/plan-caption-news.json \
  -o /tmp/film-liquidity --lib "$LIB"
```

每个脚手架都会：

1. 复制 `styles/<slug>/demo/` → 项目（引擎锁定）
2. `adapt` → `content/*`
3. 只写可触 sidecar（见下），写入 `content/engine.lock.json` + `PROJECT.md`
4. 校验受保护文件 hash 与 demo 一致

| 风格 | 可触同步 | 绝不改 |
|---|---|---|
| swiss-motion | `lines.json`, `palette.json`, `CREDITS` | `ease.js` / `film.js` / `main.js` / `mix.py` |
| pictogram-motion | `edl_content.json`, `lines.json`, `palette.json`, `CREDITS` | `engine.js` / `edl.js` / `scenes.js` / `poses/**` |
| caption-news | `timeline.json`, `lines.json`, `audio/lines.json`, `FACTS.md`, `palette.json`, `CREDITS` | `main.js` / `build.sh` / `assets/**` |

### 逐步命令

```bash
python3 tools/deepseek-controller/cli.py validate tools/deepseek-controller/fixtures/plan-swiss-motion.json
python3 tools/deepseek-controller/cli.py adapt … -o /tmp/…   # content-only，不复制 demo
python3 tools/deepseek-controller/cli.py schedule --project /tmp/film-fuli --require-vo
python3 tools/deepseek-controller/cli.py quality --project /tmp/film-fuli --media /tmp/film-fuli/out.mp4
```

回归：`bash tools/deepseek-controller/tests/test_mvp.sh`

### 目录

| 路径 | 作用 |
|---|---|
| `plan.schema.json` | 计划字段说明 |
| `manifests/*.json` | 三风格能力说明 / 白名单 |
| `adapters/` | 计划 → `content/*`；`TOUCHABLES.md` |
| `glue_base.py` | 复制 / 锁定 / 校验共享逻辑 |
| `glue_{swiss,pictogram,caption}.py` | 各风格薄胶合 |
| `scaffold.py` / `scaffold_project.sh` | 统一入口 |
| `schedule.py` / `quality.py` | 排期与验收门 |
| `cli.py` | `validate \| adapt \| scaffold \| schedule \| quality` |

### 与评估文档的对应

见 [`docs/NEXT-ROUND.md`](../../docs/NEXT-ROUND.md) P1。12 支对照与完整 Playwright 出片不在本 PR。

## Quality flags (post E2E fixes)

```bash
# Absolute --project recommended; relative `.` is resolved.
python3 tools/deepseek-controller/cli.py quality --project "$P" --require-vo

# Default ASR is strict. Finance Whisper homophones (本金/本经, 复利/赋利, …):
python3 tools/deepseek-controller/cli.py quality --project "$P" --require-vo \
  --asr-mode=zh-homophone-tolerant
```

- `schedule` writes `ok` / `errors` on `timeline.parsed.json`. Quality fails if `ok` is false or VO durs are missing when the plan has voice lines.
- Swiss scaffold fetches OFL `.ttf` via `fetch_fonts.py` and writes `voices/words_rel.json` for zh (`zh_words_rel.py` / `post_tts.py`). Do **not** run English `tools/words.py` on CJK.
- Swiss readcheck without `window.TEXTS(t)` → `NOT_APPLICABLE` (`swiss-demo-without-registry`), not a forever-blocking `NOT_CHECKED`.
- When `content/engine.lock.json` protects `film.js`, `media_duration` uses **`style_locked_duration`**: compare mux length to engine `DUR` (±1s). Plan `targetDurationSec` stays the schedule budget.
- `--asr-mode=zh-homophone-tolerant` uses `asr_homophones.json` v2 (`members` + optional `short` truncations, longest-match). Default ASR stays **strict**.
