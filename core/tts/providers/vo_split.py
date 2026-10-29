"""Split one continuous narration WAV into per-line clips (one request → one voice).

Finds silence gaps, then picks exactly len(lines)-1 cut gaps by dynamic programming:
cost = (cut time − expected time from cumulative character share)² penalty − gap length bonus.
Returns [(start_s, end_s)] per line. Pure numpy; caller verifies with local ASR.
"""
from __future__ import annotations

import re

import numpy as np


def _chars(t: str) -> int:
    return max(1, len(re.sub(r"[\s，。、；：！？,.;:!?（）()“”\"'—…·]", "", t)))


def silence_gaps(a: np.ndarray, sr: int, *, frame: float = 0.02, min_gap: float = 0.12,
                 rel_db: float = -38.0) -> list[tuple[float, float]]:
    hop = int(frame * sr)
    n = len(a) // hop
    rms = np.sqrt(np.mean(a[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    ref = np.percentile(rms, 95)
    quiet = 20 * np.log10(rms / ref) < rel_db
    gaps, i = [], 0
    while i < n:
        if quiet[i]:
            j = i
            while j < n and quiet[j]:
                j += 1
            if (j - i) * frame >= min_gap and i > 0 and j < n:
                gaps.append((i * frame, j * frame))
            i = j
        else:
            i += 1
    return gaps


def split_points(a: np.ndarray, sr: int, texts: list[str]) -> list[tuple[float, float]]:
    k = len(texts) - 1
    total = len(a) / sr
    gaps = silence_gaps(a, sr)
    if len(gaps) < k:
        gaps = silence_gaps(a, sr, min_gap=0.06, rel_db=-32.0)
    if len(gaps) < k:
        raise ValueError(f"only {len(gaps)} pauses found for {k} cuts")
    ch = np.array([_chars(t) for t in texts], float)
    # speech time ≈ total minus pauses; expected boundary after line i
    exp = np.cumsum(ch)[:-1] / ch.sum() * total
    mids = np.array([(g0 + g1) / 2 for g0, g1 in gaps])
    lens = np.array([g1 - g0 for g0, g1 in gaps])
    G = len(gaps)
    INF = 1e18
    cost = np.full((k, G), INF)
    back = np.zeros((k, G), int)
    def c(i, g):
        return ((mids[g] - exp[i]) / 1.2) ** 2 - 4.0 * min(lens[g], 0.8)
    for g in range(G):
        cost[0, g] = c(0, g)
    for i in range(1, k):
        best, arg = INF, -1
        for g in range(G):
            if g - 1 >= 0 and cost[i - 1, g - 1] < best:
                best, arg = cost[i - 1, g - 1], g - 1
            if arg >= 0:
                cost[i, g] = best + c(i, g)
                back[i, g] = arg
    g = int(np.argmin(cost[k - 1]))
    chosen = [g]
    for i in range(k - 1, 0, -1):
        g = back[i, g]
        chosen.append(int(g))
    chosen = chosen[::-1]
    bounds, prev = [], 0.0
    for g in chosen:
        g0, g1 = gaps[g]
        bounds.append((prev, g0 + min(0.08, (g1 - g0) / 2)))
        prev = max(g0, g1 - min(0.05, (g1 - g0) / 2))
    bounds.append((prev, total))
    return bounds


_PUNCT = r"[\s，。、；：！？,.;:!?（）()“”\"'—…·《》]"


def align_bounds(a: np.ndarray, sr: int, texts: list[str],
                 words: list[tuple[float, float, str]]) -> tuple[list[tuple[float, float]], dict]:
    """ASR-guided split: align target characters to local-ASR character timings
    (difflib), take each line boundary between the last matched char of line i and the
    first matched char of line i+1, then snap the cut into the nearest silence gap.
    `words` = [(start, end, text)] from a local whisper pass (zero-length repeats dropped).
    """
    import difflib

    chars: list[tuple[str, float, float]] = []
    for s, e, w in words:
        if e - s < 0.02:
            continue  # whisper repetition hallucinations come back as zero-length words
        cs = re.sub(_PUNCT, "", w)
        for j, ch in enumerate(cs):
            chars.append((ch, s + (e - s) * j / len(cs), s + (e - s) * (j + 1) / len(cs)))
    tgt, owner = [], []
    for i, t in enumerate(texts):
        for ch in re.sub(_PUNCT, "", t):
            tgt.append(ch)
            owner.append(i)
    sm = difflib.SequenceMatcher(None, "".join(tgt), "".join(c[0] for c in chars), autojunk=False)
    t2a: dict[int, int] = {}
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            t2a[blk.a + k] = blk.b + k
    matched = len(t2a) / max(1, len(tgt))
    total = len(a) / sr
    gaps = silence_gaps(a, sr, min_gap=0.06, rel_db=-34.0)
    starts = [owner.index(i) for i in range(len(texts))]
    ends = [len(owner) - 1 - owner[::-1].index(i) for i in range(len(texts))]
    cuts, report = [], []
    for i in range(len(texts) - 1):
        last = next((chars[t2a[k]][2] for k in range(ends[i], starts[i] - 1, -1) if k in t2a), None)
        first = next((chars[t2a[k]][1] for k in range(starts[i + 1], ends[i + 1] + 1) if k in t2a), None)
        if last is None or first is None:
            raise ValueError(f"cannot align boundary after line {i + 1}")
        want = (last + first) / 2
        cand = [g for g in gaps if g[1] >= last - 0.25 and g[0] <= first + 0.25]
        if cand:
            g = max(cand, key=lambda g: (min(g[1], first + 0.25) - max(g[0], last - 0.25)) - 0.2 * abs((g[0] + g[1]) / 2 - want))
            cut = (max(g[0], last - 0.05), min(g[1], first + 0.05))
        else:
            cut = (want, want)
        cuts.append(cut)
        report.append({"after": i + 1, "lastCharEnd": round(last, 3), "firstCharStart": round(first, 3),
                       "gap": [round(cut[0], 3), round(cut[1], 3)], "snapped": bool(cand)})
    bounds, prev = [], 0.0
    for c0, c1 in cuts:
        bounds.append((prev, min(c1, c0 + 0.08)))
        prev = max(prev, c1 - 0.05)
    bounds.append((prev, total))
    return bounds, {"matchedChars": round(matched, 3), "boundaries": report}
