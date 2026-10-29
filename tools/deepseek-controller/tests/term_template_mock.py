#!/usr/bin/env python3
"""Finance term template mocks (no network, temp ledgers): dialogue-loop --check-only on locked
wording (FLAGGED + approval/sha gate), plan say/role/cap + VaR validator, zh number folding for ASR,
spoken-syllable pacing count, pictogram beatsAuthored (no re-schedule ratchet), narration srt,
handoff timebase probe, StepAudio take reuse + second ASR pass, batch_terms init/plan;
v002: acronym-safe uppercase + case gate, per-term brand/glossary, EL number spelling, --el-backup."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CTL = Path(__file__).resolve().parents[1]
REPO = CTL.parents[1]
sys.path[:0] = [str(CTL), str(REPO / "core" / "tts"), str(REPO / "tools")]
td = Path(tempfile.mkdtemp(prefix="term-mock-"))
os.environ["DC_BUDGET_LEDGER"] = str(td / "ledger.jsonl")
os.environ["DC_QUOTA_LEDGER"] = str(td / "quota.jsonl")
import dialogue_loop as D  # noqa: E402

n = 0


def ok(c, m):
    global n
    if not c:
        print("FAIL:", m)
        sys.exit(1)
    n += 1
    print("ok", m)


SC = {"factual": 5, "natural": 5, "asr_safe": 5, "function_fit": 5, "rhythm": 5}
SS = {"factual": 5, "consistency": 5, "hook": 5, "flow": 5, "no_jinju": 5, "natural": 5, "rhythm": 5}


class Crit:
    def __init__(self):
        self.calls, self.step, self.call_log, self.model, self.usage = [], None, [], "rec", {"calls": 0}

    def balance(self):
        return None

    def chat_json(self, system, user):
        self.calls.append((self.step, system[:10]))
        lines = [{"id": f"L0{i}", "scores": SC, "issues": []} for i in range(1, 7)]
        lines[5] = {"id": "L06", "scores": {**SC, "rhythm": 2},
                    "issues": [{"type": "rhythm", "severity": "medium", "detail": "长"}]}
        return {"lines": lines, "script": {"scores": SS, "issues": []}, "summary": "x"}


# 1) --check-only: one critic call, no reviser, wording untouched; gate needs approval + same sha
p = td / "lock"
shutil.copytree(CTL / "fixtures" / "dialogue" / "pass" / "content", p / "content")
(p / "BRIEF.md").write_text("# t\n\n## FACTS\n- x\n", encoding="utf-8")
before = (p / "content" / "lines.json").read_text("utf-8")
c = Crit()
s = D.run_loop(p, client=c, settle_sec=0, log=lambda *_: None, check_only=True)
ok(s["status"] == "FLAGGED" and len(c.calls) == 1, f"check-only: 1 critic call → FLAGGED ({s['status']}, {len(c.calls)})")
ok((p / "content" / "lines.json").read_text("utf-8") == before, "check-only never writes lines back")
ok(not D.gate_status(p)[0], "FLAGGED without approval keeps the TTS gate shut")
c2 = Crit()
s2 = D.run_loop(p, client=c2, settle_sec=0, log=lambda *_: None, check_only=True, approved_by="金融专家")
ok(s2["approval"]["approvedBy"] == "金融专家" and s2["approval"]["linesSha256"] == s2["linesSha256"],
   "approval block records approver + linesSha256")
ok(D.gate_status(p)[0], "FLAGGED + approval + same sha opens the gate")
L = json.loads(before)
rows = L["lines"] if isinstance(L, dict) else L
rows[0]["say"] = rows[0]["text"] + "啊"
(p / "content" / "lines.json").write_text(json.dumps(L, ensure_ascii=False), "utf-8")
ok(not D.gate_status(p)[0], "changing say (spoken text) after approval closes the gate")

# 2) validator: VaR text, role/cap/say keys; function key and empty say rejected
import validate  # noqa: E402

plan = json.loads((CTL / "templates" / "finance-term" / "plan.skeleton.json").read_text("utf-8").replace("{{zh}}", "风险价值").replace("{{short}}", "VaR"))
ex = json.loads((CTL / "templates" / "finance-term" / "examples" / "042-var.lines.json").read_text("utf-8"))
import batch_terms as BT  # noqa: E402

for sh in plan["shots"]:
    sh["text"] = sh["onScreenText"] = "VaR"
plan["voice"]["lines"] = [{"id": x["id"], "role": x["role"], "text": BT.strip_cap(x["cap"]), "cap": x["cap"],
                           "shotId": x["shot"], **({"say": x["say"]} if x.get("say") else {})} for x in ex["lines"]]
ok(validate.validate_plan(plan) == [], f"VaR plan with role/cap/say validates {validate.validate_plan(plan)[:2]}")
bad = json.loads(json.dumps(plan))
bad["voice"]["lines"][0]["function"] = "hook"
bad["voice"]["lines"][1]["say"] = " "
errs = validate.validate_plan(bad)
ok(any("function" in e for e in errs) and any(".say" in e for e in errs), "function key + empty say rejected")

# 3) zh number folding (both sides) — notation only, never a different number
import asr_check as A  # noqa: E402
import zh_num  # noqa: E402

ok(zh_num.fold_numbers("一百万元") == zh_num.fold_numbers("100万元") == "1000000元", "一百万 ≡ 100万")
ok(zh_num.fold_numbers("九十七点五") == "97.5" and zh_num.fold_numbers("两千零五") == "2005", "九十七点五 / 两千零五")
ok(zh_num.fold_numbers("一定") == "一定" and zh_num.fold_numbers("千万别") == "千万别", "non-number 一定/千万别 untouched")
ok(A.compare("一百万。不是最多亏这么多。", "100万不是最多亏这么多。", "zh")[0], "asr_check: 一百万 vs 100万 PASS")
ok(not A.compare("一百万。不是最多亏这么多。", "200万不是最多亏这么多。", "zh")[0], "asr_check: 一百万 vs 200万 still FAIL (number gate, sim alone is ≥0.92)")
ok(not A.compare("是99%的日子，亏不过它。", "是98%的日子，亏不过它。", "zh")[0], "asr_check: 99% vs 98% FAIL")
ok(A.compare("所以看97.5%的ES", "所以看97.5%的ES", "zh")[0], "asr_check: identical decimals PASS")
import quality as Q  # noqa: E402

ok(Q._norm_zh("一百万") == Q._norm_zh("100万"), "quality tolerant norm folds numbers too")

# 4) spoken syllables: digits / % / acronyms count (VaR film was 108 Han chars, ~147 spoken)
import pacing_check as PC  # noqa: E402

ok([PC.spoken_units(t) for t in ("99%", "97.5%", "VaR", "一百万", "105")] == [6, 8, 3, 3, 4], "spoken_units 99%/97.5%/VaR/一百万/105")
ok(PC.spoken_units("所以银行监管改看尾巴：97.5%的ES，最差那 2.5% 的日子平均亏多少。") == 38, "L07 = 38 spoken units")

# 5) pictogram: authored beats survive apply (no re-schedule ratchet)
import apply_pictogram_edl as APE  # noqa: E402
import schedule as SCH  # noqa: E402

fp = td / "pic"
(fp / "content").mkdir(parents=True)
edl = {"bpm": 150, "shots": [{"id": "p0", "zh": "风险价值", "role": "hook", "motionPreset": "intro", "beats": 4},
                             {"id": "p1", "zh": "VaR", "role": "chapter", "motionPreset": "chapter", "beats": 4}]}
(fp / "content" / "edl_content.json").write_text(json.dumps(edl, ensure_ascii=False), "utf-8")
parsed = {"scheduledDurationSec": 8.8, "shots": [{"id": "p0", "t0": 0, "t1": 4.8, "dur": 4.8, "voIds": [], "voOffsets": []},
                                                 {"id": "p1", "t0": 4.8, "t1": 8.8, "dur": 4.0, "voIds": [], "voOffsets": []}]}
APE.apply_pictogram_edl(fp, parsed=parsed)
after = json.loads((fp / "content" / "edl_content.json").read_text("utf-8"))["shots"]
ok(after[0]["beats"] == 12 and after[0]["beatsAuthored"] == 4, f"apply writes scheduled beats + keeps beatsAuthored {after[0].get('beats')}/{after[0].get('beatsAuthored')}")
ok([s["beats"] for s in SCH._load_shots_from_project(fp)] == [4, 4], "schedule reads the authored minimum, not last take's length")
APE.apply_pictogram_edl(fp, parsed=parsed)
ok(json.loads((fp / "content" / "edl_content.json").read_text("utf-8"))["shots"][0]["beatsAuthored"] == 4, "beatsAuthored stable across re-applies")

# 6) narration srt chunks
import vo_srt  # noqa: E402

ch = vo_srt._chunks("所以银行监管改看尾巴：97.5%的ES，最差那 2.5% 的日子平均亏多少。", 18)
ok(len(ch) == 3 and "".join(ch).replace(" ", "") == "所以银行监管改看尾巴：97.5%的ES，最差那2.5%的日子平均亏多少。", f"srt splits long line at clauses {ch}")
ok(vo_srt._chunks("一百万。不是最多亏这么多。", 18) == ["一百万。不是最多亏这么多。"], "short line stays one cue")

# 7) handoff timebase probe
from handoff.common import probe_fps  # noqa: E402

ok(probe_fps(td / "missing.mp4") == 24, "probe_fps falls back to 24")
if shutil.which("ffmpeg"):
    mp4 = td / "t30.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=64x64:r=30:d=0.5", str(mp4)], check=True)
    ok(probe_fps(mp4) == 30, "probe_fps reads 30 from a 30fps master")

# 8) StepAudio session: identical take reused (0 requests); second ASR pass before giving up
import numpy as np  # noqa: E402
from providers import stepaudio as S  # noqa: E402

calls = []
tone = np.concatenate([np.zeros(4800), 0.2 * np.sin(np.linspace(0, 2000, 24000)), np.zeros(4800),
                       0.2 * np.sin(np.linspace(0, 2000, 24000)), np.zeros(4800)]).astype(np.float32)


def fake_post(path, body, **_):
    calls.append(path)
    import io

    import soundfile as sf
    b = io.BytesIO()
    sf.write(b, tone, S.SR, format="WAV")
    return b.getvalue(), None


S._post = fake_post
T = ["甲乙丙丁", "戊己庚辛"]
def _asr_words_plain(a, sr, texts):
    return [(0.25, 1.1, "甲乙丙丁"), (1.45, 2.3, "戊己庚辛")]


def _asr_words(a, sr, texts):  # hallucinated first pass
    return [(0.0, 0.01, "这"), (0.2, 2.0, "这些人都不知道")]


words_ok = _asr_words_plain
S._asr_words = _asr_words
S._asr_words_plain = _asr_words_plain
out = td / "sa"
out.mkdir()
lines = [{"id": "L01", "text": T[0]}, {"id": "L02", "text": T[1]}]
d1, m1 = S.synthesize_session(lines, str(out), role="r", speed=1.1)
ok(m1["requests"] == 1 and m1["split"]["asr"] == "_asr_words_plain", f"bad prompted ASR → plain second pass ({m1['split'].get('asr')})")
d2, m2 = S.synthesize_session(lines, str(out), role="r", speed=1.1)
ok(m2["requests"] == 0 and m2["reusedTake"] and len(calls) == 1 and d1 == d2, "identical scripts reuse the cached take (no 2nd request)")
os.environ["LEMO_TTS_STEPAUDIO_REUSE"] = "0"
S.synthesize_session(lines, str(out), role="r", speed=1.1)
ok(len(calls) == 2, "LEMO_TTS_STEPAUDIO_REUSE=0 forces a new take")
os.environ.pop("LEMO_TTS_STEPAUDIO_REUSE")
S.synthesize_session([{"id": "L01", "text": T[0] + "壬"}, lines[1]], str(out), role="r", speed=1.1)
ok(len(calls) == 3, "changed script → new take")
meta = (out / "_session.json").read_text("utf-8")
ok("KEY" not in meta.upper().replace("SHA256", ""), "take sidecar holds a sha, no key material")

# 9) batch_terms init / plan
csvp = td / "terms.csv"
csvp.write_text("序号,英文术语,中文,科目归类（按GARP大纲,非官方词表）\n42,Value at Risk (VaR),风险价值,P1 估值与风险模型\n"
                "43,Expected Shortfall (ES),预期损失,P1 估值与风险模型\n66,Liquidity-Adjusted VaR,流动性调整VaR,P2 市场风险\n",
                encoding="utf-8")
root = td / "frm"
ok(BT.main(["init", "--csv", str(csvp), "--out", str(root), "--skip", "66"]) == 0, "init")
ok(sorted(x.name for x in root.iterdir()) == ["042-var", "043-es"], "init: <NNN>-<acronym slug>, --skip honoured")
try:
    BT.build_plan(root / "043-es")
    ok(False, "unapproved plan must refuse")
except SystemExit as e:
    ok("approvedBy" in str(e) and "cap empty" in str(e), "plan refuses without expert approval / caps")
shutil.copy(CTL / "templates" / "finance-term" / "examples" / "042-var.lines.json", root / "042-var" / "src" / "lines.json")
ok(BT.main(["plan", "--term", str(root / "042-var")]) == 0, "example lines → plan validates")
pl = json.loads((root / "042-var" / "src" / "plan.json").read_text("utf-8"))
ok(pl["voice"]["lines"][1]["text"] == "这个指标叫 VaR，中文是风险价值。" and pl["voice"]["lines"][1]["say"].count("V-A-R") == 1
   and pl["voice"]["provider"] == "stepaudio" and pl["pacing"] == "calm", "plan: text from cap, say kept, stepaudio/calm")
ok(BT.term_state(root / "042-var") == "planned" and BT.term_state(root / "043-es") == "awaiting-expert-lines", "status states")
ok("金融专家" in (root / "042-var" / "src" / "FACTS.md").read_text("utf-8"), "FACTS records the approver")
ok(BT.main(["init", "--csv", str(csvp), "--out", str(root)]) == 0 and
   json.loads((root / "042-var" / "src" / "lines.json").read_text("utf-8"))["approvedBy"], "re-init never overwrites approved lines")

# 10) v002: acronyms keep their case; per-term brand + glossary; EL spells numbers
import common as CM  # noqa: E402
ok(CM.upper_keep("Beyond VaR, CVaR and CoVaR value") == "BEYOND VaR, CVaR AND CoVaR VALUE", "upper_keep keeps mixed-case acronyms")
ok(CM.acronym_case_violations(["风险价值 VAR"], {"VaR"}) and not CM.acronym_case_violations(["风险价值 VaR", "VARIANCE"], {"VaR"}),
   "case guard: VAR flagged, VaR / VARIANCE not")
import apply_pictogram_edl as APE  # noqa: E402
ok(APE._en_title("VaR") == "VaR" and APE._en_title("beyond VaR") == "BEYOND VaR", "pictogram titles: no VaR→VAR")
ok(BT.term_meta({"a": "42", "b": "Value at Risk (VaR)", "c": "风险价值", "d": "P1 估值与风险模型"})["eyebrow"] == "VALUATION & RISK MODELS",
   "eyebrow default from 科目归类")
m66 = BT.term_meta({"a": "66", "b": "Liquidity-Adjusted VaR", "c": "流动性调整VaR", "d": "P2 市场风险", "eyebrow": "LIQUIDITY RISK"})
ok(m66["eyebrow"] == "LIQUIDITY RISK" and BT._fill("{{EN_UPPER}}", m66) == "LIQUIDITY-ADJUSTED VaR", "CSV eyebrow column wins; EN_UPPER keeps VaR")
v2 = root / "042-var"
shutil.copy(CTL / "templates" / "finance-term" / "examples" / "042-var-v002.lines.json", v2 / "src" / "lines.json")
ok(BT.main(["plan", "--term", str(v2)]) == 0, "v002 example (8 lines, L07a/L07b share p6) → plan validates")
pl2 = json.loads((v2 / "src" / "plan.json").read_text("utf-8"))
ok(pl2["brand"]["eyebrow"] == "Valuation and Risk Models" and pl2["brand"]["endTitle"] == "风险价值 VaR"
   and pl2["brand"]["endLine"] == "→ 预期尾部损失 ES" and pl2["glossary"] == {"ES": "预期尾部损失"}, "v002 brand + glossary in plan")
ok([ln["shotId"] for ln in pl2["voice"]["lines"]][-2:] == ["p6", "p6"] and all(len(s["text"]) <= 40 for s in pl2["shots"]),
   "two lines on the finale shot; shot text ≤ 40")
bs = APE.build_brand_strings(pl2, [])
ok(bs["eyebrow"] == "Valuation and Risk Models" and "VaR" in bs["keepCase"] and not bs["titleEn"].isupper(), "brand_strings carries the per-term labels")
bad = APE.case_guard({"shots": [{"en": "VAR"}]}, bs)
ok(bad and not APE.case_guard({"shots": [{"en": "VaR"}]}, bs), "case_guard flags an uppercased VaR in the EDL")
gs = set()
ok(vo_srt.apply_glossary("97.5% 的 ES。", {"ES": "预期尾部损失"}, gs) == "97.5% 的 ES（预期尾部损失）。"
   and vo_srt.apply_glossary("ES 又一次", {"ES": "预期尾部损失"}, gs) == "ES 又一次", "glossary once, at first use")
ok(zh_num.spell_numbers("97.5% 的 ES，最差 2.5%，99%，100万，15") == "百分之九十七点五 的 ES，最差 百分之二点五，百分之九十九，一百万，十五",
   "spell_numbers for ElevenLabs")

from providers import elevenlabs as EL  # noqa: E402
ok(EL.spoken_text({"text": "97.5% 的 ES。", "say": "所以 97.5% 的 E-S。"}) == "所以 百分之九十七点五 的 ES。", "EL spoken text: numbers spelled, E-S joined")
ok(EL.spoken_text({"text": "VaR is 1%"}) == "VaR is 1%", "EL: non-Chinese lines untouched")
scn = (REPO / "styles" / "pictogram-motion" / "versions" / "finance-v002" / "scenes.js").read_text("utf-8")
ok(all(".toUpperCase()" not in ln or "upKeep" in ln for ln in scn.splitlines()) and "EYEBROW" in scn and "END_LINE" in scn,
   "finance-v002 scenes: eyebrow/end card from brand, no raw toUpperCase")
import quality as QQ  # noqa: E402
qp = td / "qcase"
(qp / "content").mkdir(parents=True)
(qp / "content" / "plan.json").write_text(json.dumps(pl2, ensure_ascii=False), "utf-8")
(qp / "brand_strings.json").write_text(json.dumps({"titleEn": "风险价值 VAR"}, ensure_ascii=False), "utf-8")
ok(QQ.run_acronym_case(qp)["status"] == "FAIL", "quality acronym_case FAILs on VAR")
(qp / "brand_strings.json").write_text(json.dumps(bs, ensure_ascii=False), "utf-8")
ok(QQ.run_acronym_case(qp)["status"] == "PASS", "quality acronym_case PASS on VaR")
ok("EL_BACKUP" in (CTL / "templates" / "finance-term" / "build_term.sh").read_text("utf-8")
   and BT.main(["build", "--out", str(td / "empty-out")]) == 0 if (td / "empty-out").mkdir() is None else False,
   "build --el-backup wired (off by default)")

print(f"term template mock: {n} checks OK")
