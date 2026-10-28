# DeepSeek Controller（MVP）

最小控制器：用**代码**卡住内容边界——Flash 只交严格 JSON 计划；适配器只写 `content/`；真实旁白驱动排期；`quality.json` 可阻断交付。

**不**在本目录改 `styles/*/demo` 引擎核心，**不**内嵌 DeepSeek API 调用，**不**声称已接入 Opuscar Studio。

---

## English (short)

Minimal controller for Lemo-DeepSeek: `validate` → `adapt` → `schedule` → `quality`.

- Plan schema: `plan.schema.json` (content only; rejects code/path/shader-looking keys).
- Style manifests: `manifests/{swiss-motion,pictogram-motion,caption-news}.json`.
- Adapters write **content-only** files under `<project>/content/` (see each `TOUCHABLES.md`).
- `schedule` builds `timeline.parsed.json` from measured VO (+ read time + pad), snaps to beat grid; **fails** if over target (no silent global K-scale as final).
- `quality` writes `quality.json` with `PASS|FAIL|NOT_CHECKED|NOT_APPLICABLE`; required `FAIL` or `NOT_CHECKED` blocks delivery.

```bash
# from repo root
python3 tools/deepseek-controller/cli.py validate tools/deepseek-controller/fixtures/plan-swiss-motion.json
python3 tools/deepseek-controller/cli.py adapt   tools/deepseek-controller/fixtures/plan-swiss-motion.json \
  -o /tmp/film-fuli
python3 tools/deepseek-controller/cli.py schedule --project /tmp/film-fuli --dur /tmp/film-fuli/voices/dur.json
python3 tools/deepseek-controller/cli.py quality  --project /tmp/film-fuli --skip-heavy   # engine/ASR later
bash tools/deepseek-controller/tests/test_mvp.sh
```

Still **manual**: copy `styles/<slug>/demo/` into the project, wire `content/*` into the engine with thin glue, run TTS / Playwright / mux. Controller does not render MP4 yet.

---

## 中文

### 怎么跑

```bash
# 在仓库根目录
python3 tools/deepseek-controller/cli.py validate tools/deepseek-controller/fixtures/plan-swiss-motion.json
python3 tools/deepseek-controller/cli.py adapt tools/deepseek-controller/fixtures/plan-swiss-motion.json -o /tmp/film-fuli

# 旁白合成后写入 voices/<id>.wav 与 voices/dur.json，再排期
python3 tools/deepseek-controller/cli.py schedule --project /tmp/film-fuli --require-vo

# 验收门（无引擎/成片阶段可用 --skip-heavy；正式交付不要 --allow-unchecked）
python3 tools/deepseek-controller/cli.py quality --project /tmp/film-fuli --media /tmp/film-fuli/out.mp4
```

回归：`bash tools/deepseek-controller/tests/test_mvp.sh`

### 目录

| 路径 | 作用 |
|---|---|
| `plan.schema.json` | 计划字段说明（代码侧以 `validate.py` 为准） |
| `manifests/*.json` | 三风格能力说明 / 白名单 |
| `adapters/` | 计划 → `content/*` |
| `schedule.py` | VO → `timeline.parsed.json` |
| `quality.py` | 统一 `quality.json` |
| `fixtures/` | 复利 / 分散 / 流动性样例计划与输出 |
| `cli.py` | `validate \| adapt \| schedule \| quality` |

### Flash / 控制器可碰的文件

见各风格适配后的 `content/TOUCHABLES.md`，以及 manifest 的 `touchableOutputs` / `protectedGlobs`。

### 仍手工的部分

1. `setup.sh demo <slug>` 后把 demo **复制**进项目（引擎锁定）。
2. 用薄胶水把 `content/shots.json`（或 edl/timeline_content）接到引擎——**不要**改 `ease.js` / `film.js` / `engine.js` / `poses/**`。
3. TTS（`core/tts/tts_router.py` / `tts_zh.py`）→ `voices/` + `dur.json`。
4. `still.mjs` / `video.mjs` / `mix` / `mux` → 再跑 `quality`（含 readcheck / asr / ebur128）。

### 与评估文档的对应

见 [`docs/NEXT-ROUND.md`](../../docs/NEXT-ROUND.md) P1：结构化边界、真实语音排期、统一验收门。本 MVP 落地骨架；12 支对照矩阵与完整 Playwright 出片不在本 PR。
