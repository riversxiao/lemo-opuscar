# finance-term — FRM core100 per-term template films

Worked examples: **#42 风险价值 VaR** v001 → `/workspace/films/var-template-v001/` (`examples/042-var.lines.json`);
**v002** (台词教父 FINAL marks + brand/glossary) → `/workspace/films/var-template-v002/` (+ `-el.mp4` backup) (`examples/042-var-v002.lines.json`).

Source list: `/workspace/finance/frm_core100.csv` (box only; 100 rows,
`序号,英文术语,中文,科目归类`). Not committed — pass its path to `init`.


## Style finance-v002 (default)

Per-term eyebrow + end card via `plan.brand` / `lines.json` `brand` (also CSV columns `eyebrow`,`endTitle`,`endLine`). Acronym-safe uppercase (`upper_keep` / scenes `upKeep`); quality `acronym_case` FAILs VaR→VAR. `plan.glossary` adds （gloss） at first SRT use.


## Drafting lines (future)

Prefer **OpenCode + `VOLCENGINE_CODING_API_KEY`** (Volcano Coding Plan) for drafting/fact-check of lines — not the Ark normal API. Expert approval still locks wording; dialogue-loop stays check-only.

## 通俗金融学 defaults (wen hao)

- **Narration speed 1.0** hardcoded in `build_term.sh` (`FINANCE_TTS_SPEED=1.0`, pacing `calm`). Never `fast` profile, never standard +10% / brisk StepAudio role.
- **One memorable contrast** per film (e.g. 愿意 ≠ 扛得住). Do not stack definitions.
- **Term + Chinese once** on screen (English label optional once); speak the Chinese term — do not letter-spell English in `say` unless the approved line requires it.
- Douyin-plain: no institutions, returns, or stock tips unless the expert line already has them.
- ElevenLabs backup off by default; only enable with `EL_BACKUP=1` when the user asks (and not with a rejected voice).

## ElevenLabs backup (optional)

`EL_BACKUP=1` (or `batch_terms.py build --el-backup`) builds `<film>/backup-el/` and muxes `<name>-el.mp4` with Skylar (`uDnTdfbGbx3cHHFnY83O`) + `eleven_v4`. Provider spells Chinese numbers and joins letter spellings (E-S→ES) for ASR. Off by default (uses Creator character quota). Tex failed zh number ASR; Skylar+v4 passed.

## Files

| file | who edits | purpose |
|---|---|---|
| `plan.skeleton.json` | nobody per term | pictogram-motion · concept · standard · 7 shots (intro, chapter, 3×card, hard-cut, finale) · StepAudio session |
| `lines.skeleton.json` | **金融专家** | 7 cards (zh/en ≤40) + 7 lines (`cap` with `{强调词}`, optional `say`) + `approvedBy`/`approvedAt` |
| `BRIEF.skeleton.md` / `FACTS.skeleton.md` | generated | brief + provenance; FACTS lists the approved caps, no model-added facts |
| `build_term.sh` | nobody | render + gates + handoffs for one term |
| `../../batch_terms.py` | nobody | `init` / `plan` / `status` |

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
- Expect ~28–32 s at standard pacing for 7 lines of ~18 字 (duration is a ceiling, never padded).
- `quality --delivery` must PASS; pacing WARN is report-only.

## Rework (only on FAIL, max 2 rounds)

| FAIL | fix |
|---|---|
| asr_check: acronym/number misheard | add `say` (pronunciation only) → new check-only → tts |
| asr_check: a slurred word in the take | `LEMO_TTS_STEPAUDIO_REUSE=0` re-take (free) |
| asr_check: session take keeps mishearing a phrase (e.g. 多少钱→多大险) | `LEMO_TTS_STEPAUDIO_MODE=line` re-take (still speed 1.0); speaker gate must PASS |
| pacing interLineGapMax | shots are VO-driven (`beats` 4 minimum); never raise `beats` |
| pacing shot/frozen | `cli.py pacing-rework --project P --media M` |
| anything in wording | stop: report to the 金融专家, never rewrite |

## Run gates one film at a time

Don't run two `quality`/`asr_check` jobs at the same time on the box. On 2026-10-29 the VaR film's
asr_check came back with hallucinated text ("这个,这个,…", sim 0.00) while a second film's quality ran
in parallel; rerun alone on the same wavs it PASSed (and two solo runs give identical output,
temperature=0). If an ASR FAIL shows nonsense rather than a near-miss, rerun it alone before you rework anything.

asr_check also requires the numbers to match exactly (after 一百万≡100万 folding): a wrong digit is a
different fact, even when the char similarity is ≥0.92.
