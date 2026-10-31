#!/usr/bin/env python3
"""Speaker-consistency check for multi-line VO (local, free).

Embeds every line WAV with Resemblyzer (GE2E d-vector, CPU) and compares each line to
the leave-one-out centroid of the other lines (cosine). A narration that is meant to be
ONE voice fails when any line drops below --min-sim, or the pairwise minimum is below
--min-pair. Prints JSON. Runs under any python that has `resemblyzer` (set
WORDFILM_SPK_PYTHON, or the old LEMO_SPK_PYTHON, for a dedicated venv; quality.py shells out to it).

  python3 core/tts/speaker_check.py <voices_dir> [--ids L01,L02,…] [--min-sim 0.80]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np


def score(ids: list[str], E: np.ndarray, min_sim: float = 0.80, min_pair: float = 0.70) -> dict:
    """Pure metric (unit-tested): line → leave-one-out centroid cosine + pairwise minimum."""
    E = E / np.linalg.norm(E, axis=1, keepdims=True)
    per = {}
    for k, i in enumerate(ids):
        c = (E.sum(0) - E[k]) / max(1, len(ids) - 1)
        per[i] = round(float(E[k] @ (c / np.linalg.norm(c))), 4)
    P = E @ E.T
    iu = np.triu_indices(len(ids), 1)
    pmin = float(P[iu].min()) if len(ids) > 1 else 1.0
    bad = [i for i in ids if per[i] < min_sim]
    ok = not bad and pmin >= min_pair
    return {"status": "PASS" if ok else "FAIL", "model": "resemblyzer-ge2e", "minSim": min_sim,
            "minPair": min_pair, "lines": per, "pairMin": round(pmin, 4),
            "pairMean": round(float(P[iu].mean()), 4) if len(ids) > 1 else 1.0,
            "belowMin": bad, "worst": sorted(per, key=per.get)[:3]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("voices_dir")
    ap.add_argument("--ids", default="")
    ap.add_argument("--min-sim", type=float, default=0.80)
    ap.add_argument("--min-pair", type=float, default=0.70)
    a = ap.parse_args()
    try:
        from resemblyzer import VoiceEncoder, preprocess_wav
    except ImportError:
        print(json.dumps({"status": "DEPS_MISSING", "detail": "resemblyzer not importable (set WORDFILM_SPK_PYTHON)"}))
        return 2
    ids = [i for i in a.ids.split(",") if i] or sorted(
        os.path.basename(p)[:-4] for p in glob.glob(os.path.join(a.voices_dir, "*.wav")))
    enc = VoiceEncoder("cpu", verbose=False)
    E = []
    for i in ids:
        E.append(enc.embed_utterance(preprocess_wav(os.path.join(a.voices_dir, f"{i}.wav"))))
    d = score(ids, np.array(E), a.min_sim, a.min_pair)
    print(json.dumps(d, ensure_ascii=False))
    ok = d["status"] == "PASS"
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
