# finance-term — FRM core100 per-term template films

Worked examples: **#42 风险价值 VaR** v001 → `/workspace/films/var-template-v001/` (`examples/042-var.lines.json`);
**v002** (台词教父 FINAL marks + brand/glossary) → `/workspace/films/var-template-v002/` (+ `-el.mp4` backup) (`examples/042-var-v002.lines.json`).

Source list: `/workspace/finance/frm_core100.csv` (box only; 100 rows,
`序号,英文术语,中文,科目归类`). Not committed — pass its path to `init`.


## Style finance-v002 (default)

Per-term eyebrow + end card via `plan.brand` / `lines.json` `brand` (also CSV columns `eyebrow`,`endTitle`,`endLine`). Acronym-safe uppercase (`upper_keep` / scenes `upKeep`); quality `acronym_case` FAILs VaR→VAR. `plan.glossary` adds （gloss） at first SRT use.


## Style finance-v003 + ElevenLabs narration + StepAudio bed (series from 贝塔 pilot, 2026-10-29)

Pilot: **#4 贝塔 Beta** → `/workspace/films/beta-v001/` (`examples/004-beta-v001.lines.json`).

```bash
TTS_PROVIDER=elevenlabs STYLE_VERSION=finance-v003 \
  bash tools/deepseek-controller/templates/finance-term/build_term.sh /workspace/films/_<term>-term /workspace/films/<name>
# picture/gate fix only (no new EL characters):  REUSE_VOICES=1 … same command
```

- **Narration**: ElevenLabs, one voice per series — Tex `TKaUqol7GKx4m7enpCpP`, `eleven_v4`, speed natural 1.0
  (never Skylar/Shasha/Kathy). The provider reads the voice from `ELEVENLABS_VOICE_ID` (build_term sets it;
  the plan `voiceId` alone falls back to Rachel) and the build stops if `voices/spoken.json` names another voice.
  `say` spells numbers/percent in Chinese words (一百万, 九十九天, 大于一); acronyms only in captions.
  EL has **no take cache**: every `tts` call bills characters (`voices/spoken.json` → `chars`).
- **Per-line visuals**: each line's `visual` (台词教父 drafts — read-only, copy into `<term>/src/lines.json`)
  → `viz_pick.py` → `content/viz.json` (scene + data) + `evidence/visual-content.json`
  (金融专家 lint: no tickers / fund names / K线截图, no monotonically rising return curves, no chips / casino / 赌桌,
  no scene twice in a film). Overrides: `VIZ_OVERRIDES="--override L01='…'"`. Unmapped visual → FAIL:
  add a RULES entry in viz_pick.py and a `VIZ.<scene>` in `styles/pictogram-motion/versions/finance-v003/scenes.js`.
- **End card**: `schedule --outro 1.5` (≤ OUTRO_MAX_SEC) → finale = last line's scene, iris into endTitle/endLine.
  beats.py cuts at the outro instead of a CSS reframe; pacing density metrics use the spoken part (D − outro).
- **Duplicate-visual gate**: `visual_dupe.py --project P` grabs one keyframe per shot → `<film>/keyframes/*.png`,
  dHash + layout correlation vs. own shots and the series (erm, var-plain, risk-appetite, var-template-v002 +
  `/workspace/films/_visual-index/finance.json`); near-duplicate → FAIL. `--register` adds a PASSed film to the index.
  (Calibration: the old pose-card films FAIL against each other — ham 1–9, corr 0.85–0.95.)
- **Music**: StepAudio bed from `/workspace/films/_music-library/finance-calm-01` (`--music-library`, raw copied into
  `<film>/music/`, no new request; usage recorded in its `meta.json`). Ducked mix → mux −14 LUFS,
  `LEMO_TP_CEIL=-2.8` + retry above −2.0; quality requires TP ≤ −2 dBTP for v003 films.
- quality adds required `visual_content` + `visual_duplicate` once `content/viz.json` exists.
- **Language (粤语 drift fix, 2026-10-29)**: eleven_v4 speaks both Mandarin and Cantonese from the same hanzi and guessed
  per request (beta-v001 L06 came out Cantonese). The provider now sends `language_code` on every line plus
  `previous_text`/`next_text`. Per-line `lang` in lines.json: `zh` (default for any line with hanzi) · `en` (no hanzi →
  automatic) · `mixed` (Chinese line with English terms: one `zh` request — Tex still reads the English words naturally,
  seamless). `LEMO_TTS_ELEVENLABS_MIXED=split` = opt-in per-run split (zh/en runs, 40 ms crossfade). `yue` only if a
  line explicitly asks for it. `LEMO_TTS_ELEVENLABS_SEED` optional.
- **Dialect gate** `dialect_mandarin` (required when VO exists): `core/tts/dialect_check.py`, Meta MMS-LID-256
  (`/workspace/_models/mms-lid-256`, or `LEMO_DIALECT_MODEL`; runs in `.venv-spk`). Chinese (zh/mixed) lines FAIL when
  a non-Mandarin Chinese label (yue/nan/hak/wuu/…) wins with p ≥ 0.5; `en` lines never fail (WARN if not heard as
  English). Whisper LID cannot tell yue from zh — don't use it. Evidence: `evidence/dialect-check.json`.
  Fix a FAIL by re-TTS of that film (language_code makes it deterministic); never re-word the line.
- **Draft copy**: `batch_terms.py from-draft --draft /workspace/films/dialogue-drafts/<name>.lines.json --term <term>`
  copies `visual`/`lang`/voice into `<term>/src/lines.json` only if every text/say equals the approved line
  (draft folder never written). `elevenlabs:<id>` voice prefix accepted.
- Same-term earlier takes (beta-v001 when building beta-v002) are skipped by `visual_dupe.py`; a delivered film is
  `--register`ed into the series index after quality, so later films are checked against it.

## Drafting lines (future)

Prefer **OpenCode + `VOLCENGINE_CODING_API_KEY`** (Volcano Coding Plan) for drafting/fact-check of lines — not the Ark normal API. Expert approval still locks wording; dialogue-loop stays check-only.

## 通俗金融学 defaults (wen hao)

- Captions/screen show content only: `text`/`cap`/`onScreenText` must never carry stage directions (「屏幕上写…」). Put the acronym in brackets instead (「叫风险价值（VaR）」); `say` speaks Chinese only. dialogue-check and validate FAIL on 屏幕上/画面上/字幕上.

- **Narration speed 1.0** hardcoded in `build_term.sh` (`FINANCE_TTS_SPEED=1.0`, pacing `calm`). Never `fast` profile, never standard +10% / brisk StepAudio role.
- **One memorable contrast** per film (e.g. 愿意 ≠ 扛得住). Do not stack definitions.
- **Term + Chinese once** on screen (English label optional once); speak the Chinese term — do not letter-spell English in `say` unless the approved line requires it.
- Douyin-plain: no institutions, returns, or stock tips unless the expert line already has them.
- ElevenLabs backup off by default; only enable with `EL_BACKUP=1` when the user asks (and not with a rejected voice).

## ElevenLabs backup (optional)

`EL_BACKUP=1` (or `batch_terms.py build --el-backup`) builds `<film>/backup-el/` and muxes `<name>-el.mp4` with Skylar (`uDnTdfbGbx3cHHFnY83O`) + `eleven_v4`. Provider spells Chinese numbers and joins letter spellings (E-S→ES) for ASR. Off by default (uses Creator character quota). Tex failed zh number ASR with Arabic numerals; with Chinese-word `say` Tex + v4 passes (number test 2026-10-29: 一百万 / 九十九天 / 贝塔大于一 exact) and is the series narrator for finance-v003.

## Variable length (wen hao, 2026-10-30)

Line count follows concept difficulty: simple ≈ 7 lines / ~30 s; hard (VaR, CAPM) 10–14 lines / ~45–70 s;
the longest concepts up to 17 lines / 90 s (wen hao 2026-10-30, after CAPM long).
Still **one memory point per film**, speed 1.0, `PACING=calm`; duration is a ceiling, never padded.

- 5–17 lines; one card per shot (`p0…pN`), every card has ≥1 line, every line's shot has a card, cards in line order.
  `plan` refuses anything else.
- `plan.shots` is generated from the cards: `p0` intro/hook · `p1` chapter · cards · the `turn` line's shot = hard-cut
  (pose diving) · last = finale (relay). Each shot 4 beats; the schedule stretches to the VO.
- Default ceiling tiered by line count (`batch_terms.DURATION_TIERS`): ≤7 → 40 s · ≤10 → 55 s · ≤14 → 75 s · ≤17 → 90 s.
  lines.json `targetDurationSec` overrides (clamped 15–90). Manifest `pictogram-motion` max 90 s.
  Top tier sizing: Tex ≈ 4.0 字/s + ≈0.6 s/shot + 1.5 s outro → 17 lines ≈ 14.6 s overhead → ≈ 300 字 of speech
  (≈ 17–18 字/line). Ceiling only: a 15-line film that reads in 70 s stays 70 s.
- `init --lines N` writes an N-line skeleton. An approved 台词教父 draft becomes a term folder with
  `batch_terms.py init-from-draft --draft /workspace/films/dialogue-drafts/<name>.lines.json --term <term>
  --approved-by "金融专家 …" [--meta <other-term>/src/term.json] [--cards cards.json]` — reads the draft only
  (refuses a `--term` inside dialogue-drafts), copies say/visual/lang/voice verbatim, one shot per line.
  `cards.json` = `{"cards": {"p0": {"zh": "…", "en": "…"}}, "brand": {…}, "glossary": {…}}` (card `en` ≤40, ASCII `-` not `–`, no `?`).
- Scene library finance-v003 batch 3 (14 scenes for the VaR long film, all distinct from the series index):
  cap_crossed · bank_report · three_slots · slots_filled · grid_10x10 · square_over · year_strip · red_cluster ·
  bottomless · old_ledger · sky_change · expect_actual · tail_dots_es · bank_on_line. Metaphor: 0 at the top,
  losses go down, the gold line is a threshold (never a floor); nothing below it has a drawn bottom.

## Files

| file | who edits | purpose |
|---|---|---|
| `plan.skeleton.json` | nobody per term | pictogram-motion · concept · standard · shots regenerated from the cards by `plan` (5–17) · tiered ceiling |
| `lines.skeleton.json` | **金融专家** | 7 cards by default (`init --lines N` for 5–17) (zh/en ≤40) + 7 lines (`cap` with `{强调词}`, optional `say`) + `approvedBy`/`approvedAt` |
| `BRIEF.skeleton.md` / `FACTS.skeleton.md` | generated | brief + provenance; FACTS lists the approved caps, no model-added facts |
| `build_term.sh` | nobody | render + gates + handoffs for one term |
| `../../batch_terms.py` | nobody | `init` / `init-from-draft` / `from-draft` / `plan` / `status` / `build` |

Line roles: L01 hook · L02–L04 evidence · L05 turn · L06 evidence · L07a payoff (+ optional L07b on same finale shot). Multiple VO lines per shotId are OK (schedule maps by shot).
`text` is generated from `cap` (braces stripped). `say` is spoken-only: use it for acronyms the TTS
blurs (VaR → `V-A-R`, verified ASR "VAR"); captions, srt and ASR expectations keep `text`.

## Batch steps

```bash
cd /workspace/lemo-opuscar-deepseek
python3 tools/deepseek-controller/batch_terms.py init --csv /workspace/finance/frm_core100.csv \
  --out /workspace/films/frm --skip 42              # 99 skeletons: <out>/<NNN>-<slug>/src/lines.json
# 金融专家 fills src/lines.json per term and sets approvedBy/approvedAt (no LLM writes wording)
python3 tools/deepseek-controller/batch_terms.py plan --term /workspace/films/frm/043-es
bash tools/deepseek-controller/templates/finance-term/build_term.sh /workspace/films/frm/043-es
python3 tools/deepseek-controller/batch_terms.py status --out /workspace/films/frm
```

States: `awaiting-expert-lines` → `approved` → `planned` → `delivered` (quality PASS) / `quality-FAIL`.

## Gates and budget per term (VaR measured)

- dialogue-loop `--check-only`: 1 call on TokenHarbor `deepseek-v4.1-flash:free` (~5–7k tokens),
  quota-routed by `x-th-free-used-pct` (OpenRouter `:free` at ≥80%). FLAGGED is expected on
  locked wording: the approval + `linesSha256` pass the gate; flags go into the report.
  Any change to `text`/`cap`/`say`/`voice` changes the sha → re-run check-only
  (build_term.sh skips the call while the evidence sha still matches).
- StepAudio `stepaudio-3-gen-preview` (限时免费), one session request = script chars incl. punctuation + an 8-char tone prefix
  (VaR: 168). Never paid StepFun TTS/ASR. A failed split re-uses the cached take
  (`voices/_session.json` sha) and retries a second local ASR pass; `LEMO_TTS_STEPAUDIO_REUSE=0`
  forces a new take.
- Expect ~28–32 s at standard pacing for 7 lines of ~18 字; 14 lines ≈ 60–70 s calm, 17 lines ≈ 85–90 s (duration is a ceiling, never padded).
- `quality --delivery` must PASS; pacing WARN is report-only.

## Rework (only on FAIL, max 2 rounds)

| FAIL | fix |
|---|---|
| asr_check: acronym/number misheard | add `say` (pronunciation only) → new check-only → tts |
| asr_check: a slurred word in the take | `LEMO_TTS_STEPAUDIO_REUSE=0` re-take (free) |
| asr_check: session take keeps mishearing a phrase (e.g. 多少钱→多大险) | `LEMO_TTS_STEPAUDIO_MODE=line` re-take (still speed 1.0); speaker gate must PASS |
| pacing interLineGapMax | shots are VO-driven (`beats` 4 minimum); never raise `beats` |
| pacing shot/frozen | `cli.py pacing-rework --project P --media M` |
| visual_content (v003) | fix the scene library / data, or a `--override` agreed with 金融专家; never edit the drafts |
| visual_duplicate (v003) | change that shot's scene layout/motion (new `VIZ.<scene>` variant), re-render with `REUSE_VOICES=1` |
| anything in wording | stop: report to the 金融专家, never rewrite |

## Run gates one film at a time

Don't run two `quality`/`asr_check` jobs at the same time on the box. On 2026-10-29 the VaR film's
asr_check came back with hallucinated text ("这个,这个,…", sim 0.00) while a second film's quality ran
in parallel; rerun alone on the same wavs it PASSed (and two solo runs give identical output,
temperature=0). If an ASR FAIL shows nonsense rather than a near-miss, rerun it alone before you rework anything.

asr_check also requires the numbers to match exactly (after 一百万≡100万 folding): a wrong digit is a
different fact, even when the char similarity is ≥0.92.
