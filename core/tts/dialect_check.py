#!/usr/bin/env python3
"""Spoken-language / dialect gate for Chinese narration (local, free, CPU).

  python core/tts/dialect_check.py <voices_dir> --ids L01,L02,… [--langs L01=zh,L02=en] [--model DIR]

Why: ElevenLabs eleven_v4 speaks both Mandarin (zh) and Cantonese (yue); both are written in
hanzi, so without language_code the model guesses per request. In the 贝塔 pilot (beta-v001,
2026-10-29) L06 came out in 粤语 while ASR text still matched — a text check cannot catch it.
Whisper LID cannot either (large-v3-turbo scores Cantonese edge-tts WanLung as zh 0.98).

Model: Meta MMS-LID-256 (wav2vec2 audio classifier, labels incl. cmn/yue/nan/hak/wuu/…):
default /workspace/_models/mms-lid-256 (box copy) or env WORDFILM_DIALECT_MODEL (old name LEMO_DIALECT_MODEL), else facebook/mms-lid-256.
Needs torch + transformers (use .venv-spk/bin/python; quality.py shells out to it).
Calibration 2026-10-29: edge Yunxi cmn 1.000/0.999, edge WanLung (粤) yue 1.000/1.000,
Tex v4 Mandarin lines cmn ≥0.999, Tex L06 (heard as 粤语 by wen hao) yue 0.997,
Tex English line eng 0.997, Tex 「叫贝塔，Beta。」 cmn 0.868.

Per-line expected language (`lang` from spoken.json langs / lines.json; default CJK → zh, else en):
  zh / mixed  Chinese part must be Mandarin. FAIL (high) when the top label is a non-Mandarin
              Chinese variety (yue, nan, hak, wuu, …) or any other non-English language with
              p ≥ --fail-prob (0.5) and p > cmn. Top = eng on a zh line → WARN (English is allowed).
              Split-mode mixed lines (spoken.json `segments`) are checked on their zh runs only.
  en          intended English — never FAILs here (WARN when not eng).
WARN (report-only) when a Chinese dialect reaches --warn-prob (0.2). Last stdout line = JSON.
Exit 0 PASS/WARN, 1 FAIL, 2 could not run.
"""
import argparse, json, os, re, sys

_LOCAL = "/workspace/_models/mms-lid-256"
DEFAULT_MODEL = os.environ.get("WORDFILM_DIALECT_MODEL") or os.environ.get("LEMO_DIALECT_MODEL") or (_LOCAL if os.path.isfile(_LOCAL + "/model.safetensors")
                                                         else "facebook/mms-lid-256")
ZH_DIALECTS = {"yue", "nan", "hak", "wuu", "hsn", "cpx", "cdo", "czh", "mnp", "gan", "cjy"}
MIN_SEG_SEC = 0.6


def classify(probs, lang, fail_prob, warn_prob):
    """Pure rule (unit-tested). probs: {label: p}. Returns (status, reason)."""
    top = max(probs, key=probs.get); p = probs[top]
    dial = max(((k, v) for k, v in probs.items() if k in ZH_DIALECTS), key=lambda kv: kv[1], default=("", 0.0))
    if lang == "en":
        return ("PASS", "eng") if top == "eng" else ("WARN", f"intended English, heard {top} {p:.2f}")
    cmn = probs.get("cmn", 0.0)
    if top not in ("cmn", "eng") and p >= fail_prob and p > cmn:
        kind = "Chinese dialect" if top in ZH_DIALECTS else "non-Mandarin language"
        return "FAIL", f"{kind} {top} {p:.3f} > cmn {cmn:.3f}"
    if top == "eng" and lang == "zh":
        return "WARN", f"zh line heard as eng {p:.2f}"
    if dial[1] >= warn_prob:
        return "WARN", f"{dial[0]} {dial[1]:.2f}"
    return "PASS", f"cmn {cmn:.3f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("voices_dir"); ap.add_argument("--ids", required=True)
    ap.add_argument("--langs", default="", help="L01=zh,L02=en (overrides spoken.json langs)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--fail-prob", type=float, default=0.5); ap.add_argument("--warn-prob", type=float, default=0.2)
    a = ap.parse_args()
    try:
        import numpy as np, soundfile as sf, soxr, torch
        from transformers import AutoFeatureExtractor, Wav2Vec2ForSequenceClassification
        torch.set_num_threads(min(8, os.cpu_count() or 4))
        fe = AutoFeatureExtractor.from_pretrained(a.model)
        m = Wav2Vec2ForSequenceClassification.from_pretrained(a.model).eval()
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"status": "NOT_CHECKED", "detail": f"LID model load failed: {type(e).__name__}: {str(e)[:200]}"}))
        sys.exit(2)
    labels = m.config.id2label
    spoken = {}
    try:
        spoken = json.load(open(os.path.join(a.voices_dir, "spoken.json"), encoding="utf-8"))
    except (OSError, ValueError):
        pass
    langs = dict(spoken.get("langs") or {})
    langs.update(dict(kv.split("=", 1) for kv in a.langs.split(",") if "=" in kv))
    texts = spoken.get("lines") or {}
    segs_all = spoken.get("segments") or {}

    def lid(y):
        with torch.no_grad():
            pr = m(**fe(y, sampling_rate=16000, return_tensors="pt")).logits.softmax(-1)[0]
        top = pr.topk(5)
        return {labels[i.item()]: float(v) for v, i in zip(top.values, top.indices)}

    rows, fails, warns = {}, [], []
    for lid_ in [x for x in a.ids.split(",") if x]:
        y, sr = sf.read(os.path.join(a.voices_dir, lid_ + ".wav"))
        if y.ndim > 1: y = y.mean(1)
        y = soxr.resample(y, sr, 16000, quality="HQ").astype(np.float32)
        t = texts.get(lid_, "")
        lg = langs.get(lid_) or ("zh" if re.search(r"[\u3400-\u9fff]", t) or not t else "en")
        parts = [(lg, 0.0, len(y) / 16000)]
        if segs_all.get(lid_):   # split-mode mixed line: zh runs only
            parts = [(s["lang"], s["start"], s["end"]) for s in segs_all[lid_] if s["lang"] != "en"
                     and s["end"] - s["start"] >= MIN_SEG_SEC] or [("mixed", 0.0, len(y) / 16000)]
        res = []
        for plg, s0, s1 in parts:
            probs = lid(y[int(s0 * 16000):int(s1 * 16000)])
            st, why = classify(probs, plg, a.fail_prob, a.warn_prob)
            res.append({"lang": plg, "start": round(s0, 2), "end": round(s1, 2), "status": st, "why": why,
                        "top": {k: round(v, 3) for k, v in list(probs.items())[:3]}})
        st = "FAIL" if any(r["status"] == "FAIL" for r in res) else ("WARN" if any(r["status"] == "WARN" for r in res) else "PASS")
        (fails if st == "FAIL" else warns if st == "WARN" else []).append(lid_)
        rows[lid_] = {"status": st, "lang": lg, "parts": res}
        print(st, lid_, lg, "; ".join(r["why"] for r in res), file=sys.stderr)
    status = "FAIL" if fails else ("WARN" if warns else "PASS")
    print(json.dumps({"status": status, "model": os.path.basename(a.model.rstrip("/")), "failProb": a.fail_prob,
                      "warnProb": a.warn_prob, "fail": fails, "warn": warns, "lines": rows}, ensure_ascii=False))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
