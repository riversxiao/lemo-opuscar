# DeepSeek Controller（MVP）

最小控制器：用**代码**卡住内容边界——Flash 只交严格 JSON 计划；适配器只写 `content/`；薄胶合脚手架复制锁定 demo；真实旁白驱动排期；`quality.json` 可阻断交付。

**不**在本目录改 `styles/*/demo` 引擎核心，**不**内嵌 DeepSeek API 调用，**不**声称已接入 Opuscar Studio。

Studio 清点（本机是否存在、与三风格适配器关系）：[`docs/STUDIO.md`](docs/STUDIO.md)。

---

## English (short)

Minimal controller for WordFilm: `validate` → `adapt` / **`scaffold`** → **`tts`** → `schedule` → `mix` → `quality` → **`handoff`**.

- Plan schema: `plan.schema.json` (content only; rejects code/path/shader-looking keys).
- Style manifests: `manifests/{swiss-motion,pictogram-motion,caption-news}.json`.
- Adapters write **content-only** files under `<project>/content/` (see `adapters/TOUCHABLES.md`).
- **`scaffold`** (all three styles): copy `styles/<slug>/demo/` → project, adapt, sync touchable sidecars only, write `engine.lock.json` + `PROJECT.md`. Never rewrites style cores (`ease.js`/`film.js`, `engine.js`/`edl.js`, or `main.js`).
- `schedule` builds `timeline.parsed.json` from measured VO; **pads** under-target (hold-last-beat); **fails** if over target.
- `tts` routes VO through `core/tts/tts_router` (`edge` / `kokoro` ready; `qwen3`/`omnivoice` when `*_BASE` set). See `../tts_router.md`.
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

python3 $CTL/cli.py tts --list
python3 $CTL/cli.py tts --project /tmp/film-fuli --provider kokoro   # offline
# or: --provider auto --fallback kokoro,edge
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
| swiss-motion | `lines.json`, `texts_runtime.json` (page.mjs TEXTS), `palette.json`, `CREDITS` | `ease.js` / `film.js` / `main.js` / `mix.py` / `index.html` |
| pictogram-motion | `edl_content.json` → `edl_runtime.json` (page.mjs overlay), `lines.json`, `timeline.json`, `palette.json`, `CREDITS` | `engine.js` / `edl.js` / `scenes.js` / `poses/**` |
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

## Dialogue gate (DIALOGUE.md §5)

```bash
python3 $CTL/cli.py dialogue-check --project <film> [--target 90]   # PASS/FAIL → evidence/dialogue-check.json
python3 $CTL/cli.py tts --project <film> --provider edge             # runs the gate first; FAIL blocks TTS
```
python3 $CTL/cli.py dialogue-loop --project <film>    # self-loop (default 2 rounds, compact context): gate + free-first critic + reviser
```
`dialogue-loop` (DIALOGUE.md §5.1) is part of the default flow: each round runs dialogue-check, then an LLM critic
(DeepSeek official `deepseek-flash`, JSON mode, grounded in DIALOGUE.md + lemo-dialogue rules + BRIEF/FACTS/TREATMENT)
scores every line (factual / natural / asr_safe / function_fit) and the script (factual / consistency / hook / flow /
no_jinju / natural). Code thresholds decide PASS (line ≥3, script ≥4, 0 high, ≤2 medium; structure issues advisory).
A reviser rewrites only flagged lines (text/say/cap/want; ids/functions/order locked). Evidence:
`evidence/dialogue-loop/round-N.json` + `evidence/dialogue-loop.json` (status + linesSha256). Never-pass after 2 rounds → NEEDS_HUMAN (no more LLM calls; budget stop → BEST_EFFORT)
(exit 1, TTS still blocked); provider error → exit 3, lines untouched. `--max-cny` (default 2) caps spend; cost is one
`llm-api` ledger row from the balance delta. Tests use `--mock` (no network, no ledger).

StepAudio (StepFun, **free preview only**): `tts --provider stepaudio` (stepaudio-3-gen-preview via `/v1/audio/generate`,
pitch-consistency retakes, `LEMO_TTS_STEPAUDIO_SPEED`) and `mix --bed-source stepaudio [--music-caption …]`
(stepaudio-3-music-preview instrumental, cached, cut/faded/RMS-matched). Key from `STEPFUN_API_KEY`; paid `/audio/speech`
TTS and ASR routes are refused in code.

```
Lines need `function` (hook|turn|evidence|payoff|sting), ≤35字 each, hook in the first 3 beats,
Σ字/4.5 within ±15% of `targetDurationSec`, no 金句升华. Legacy films: `tts --skip-dialogue-gate`.

Caption long-form (90 s): `timeline.json` `"capsMode": "per-line"` (one caption card per VO line, `cap` field)
and `"syncShots": true` (schedule rewrites the project-copy style-version `main.js` SHOTS a/b + DUR; refused on hash-locked main.js).
Multi-line shots now play lines back to back (+0.2 s gap) instead of stacking at shot start.
Tests write spend rows to `$DC_BUDGET_LEDGER` (default in tests: /tmp), never `fixtures/budget-ledger.jsonl`.

## Quality flags (post E2E fixes)

```bash
# Absolute --project recommended; relative `.` is resolved.

# Recommended delivery path (zh plan → zh-homophone-tolerant; en stays strict):
python3 tools/deepseek-controller/cli.py quality --project "$P" --media "$P/out.mp4" --delivery

# Explicit modes still available:
python3 tools/deepseek-controller/cli.py quality --project "$P" --require-vo --asr-mode=strict
python3 tools/deepseek-controller/cli.py quality --project "$P" --require-vo \
  --asr-mode=zh-homophone-tolerant
```

- **`--delivery`**: imply `--require-vo`; for `plan.language` zh/zh-en use `zh-homophone-tolerant` unless `--asr-mode` is set. English never silently weakened.
- Bare default without `--delivery` / `--asr-mode` remains **strict**.
- `schedule` pads under-target by **hold-last-beat** (extends last shot to `targetDurationSec`). Metadata keeps `contentDurationSec` / `padSec` / `underTargetBeforePad`. Use `--no-pad` for raw content length. Over-target still hard-fails (no silent K-scale).
- `schedule` writes `ok` / `errors` on `timeline.parsed.json`. Quality fails if `ok` is false or VO durs are missing when the plan has voice lines.
- Scaffold fetches OFL fonts via `fetch_fonts.py` for **all three styles** (Swiss `.ttf`, Pictogram `.ttf`, Caption `.woff2` subsets via cache/sibling/`tools/fonts.sh`). Override with `$LEMO_FONT_CACHE`. Swiss also writes `voices/words_rel.json` for zh (`zh_words_rel.py` / `post_tts.py`). Do **not** run English `tools/words.py` on CJK.
- Pictogram: `edl_runtime.json` + optional `brand_strings.json` (HUD/intro/finale literal rewrite at eval time). Disk `edl.js`/`scenes.js` hashes stay locked on default scaffold. Audio: **`cli mix` / `music_bed.py`** writes `music/bed.wav` + ducked VO → `out/mix.wav` (locked Olympics `music.py` unused). See `docs/MUSIC-BED.md`.
- Pictogram **style version** `finance-v001`: `apply_pictogram_style_version.py --version finance-v001` replaces `scenes.js` with content-driven intro/finale (see `styles/pictogram-motion/versions/finance-v001/VERSION.md`). Demo lock path unchanged.
- Swiss: `texts_runtime.json` + `page.mjs` installs `window.TEXTS(t)` (no film.js unlock). Without overlay → `NOT_APPLICABLE` (`swiss-demo-without-registry`), not eternal `NOT_CHECKED`.
- When `content/engine.lock.json` protects `film.js`, `media_duration` uses **`style_locked_duration`**: compare mux length to engine `DUR` (±1s). Plan `targetDurationSec` stays the schedule budget.
- `--asr-mode=zh-homophone-tolerant` uses `asr_homophones.json` v2 (`members` + optional `short` truncations, longest-match).

### Visual check (look at the finished film) + rework

```bash
python3 tools/deepseek-controller/cli.py visual-check --project "$P" --media "$P/film.mp4" [--rework] [--no-semantic]
```

- **Deterministic (local, free):** frames sampled per shot (3) + per VO line + per caption; whole-video 160×90 luma scan
  (black ≥0.5 s, blank, frozen = identical frames ≥4 s, single-frame corrupt spikes, ffmpeg decode errors); RapidOCR on
  every sample vs `window.TEXTS(t)` (`texts_dump.mjs`) + `timeline.json` caps/hook (char recall <0.75 → high, <0.9 →
  medium; best of two frames; lone glyphs are not OCR-verified); the subtitle OCR'd during each VO line must be that line
  (`subtitle_vo_mismatch` / `subtitle_missing` / `subtitle_not_rendered` → high); text touching the frame edge → high,
  inside the 5% title-safe margin → medium; overlapping text boxes → medium; Otsu/WCAG contrast <2 high, <3 medium;
  caption on-screen time vs readcheck rule (<0.75×need high).
- **Semantic (free only):** per-shot contact sheet + VO + captions to an OpenRouter `:free` vision model (topic, explicit
  contradiction, overcrowding, visual errors, tofu/garbled glyphs). Non-`:free` ids are refused, `provider.max_price=0`,
  key usage read before/after every shot → any delta stops the layer. No free model → `NOT_AVAILABLE` (not a block).
  A contradiction / garbled glyphs with confidence ≥0.7 is high; everything else from the model is medium.
- **Rework (`--rework`, max 2 rounds):** hook subtitle follows the VO line (`TL.hook.subs` + project `main.js` reads it,
  only when `content/engine.lock.json` unlocks `main.js`; cues/srt split; the VO-synced hook line is then the subtitle bar, so its
  `hook-say` TEXTS entry is dropped per readcheck's "don't report the subtitle bar" rule — subtitle correctness stays covered by OCR), caption size (`caps[i].big`), caption timing
  (`caps[i].t1`), re-render for black/corrupt frames. Only the changed frame ranges are re-rendered (`render_range.mjs`,
  keyframe-aligned lossless splice into `out/video.mp4`, frame count verified), then `mux.sh` and a full re-check.
  Anything left high → `finalStatus=BEST_EFFORT`.
- `quality --delivery` requires `visual_check`: reads `evidence/visual-check.json`; it must be for the same media file,
  not older than the media, and have no high issue. Also requires `speaker_consistency` for ≥3 VO lines.

### Handoff (OpenFilm / HyperFrames)

```bash
python3 $CTL/cli.py handoff --project /workspace/films/fensan-pictogram-finance-v001 --target both --lint
```

See [`docs/nle-handoff.md`](docs/nle-handoff.md) and repo [`docs/integrations/nle-handoff.md`](../../docs/integrations/nle-handoff.md).

## 18-film matrix

See [docs/MATRIX-18.md](docs/MATRIX-18.md) (full factorial; 16/18 delivery-pass). CLI: `python3 tools/deepseek-controller/cli.py matrix [--path flash]`.
