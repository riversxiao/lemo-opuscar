#!/usr/bin/env python3
"""zh-homophone-tolerant number check runs after the homophone tokenize (no network):
不灵/不零 (bù líng) is a lexicon pair, so Whisper's 零→0 fold no longer fails it; any other number change still fails."""
from __future__ import annotations

import sys
from pathlib import Path

CTL = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(CTL)]
import quality as Q  # noqa: E402

n = 0


def ok(c, m):
    global n
    if not c:
        print("FAIL:", m)
        sys.exit(1)
    n += 1
    print("ok", m)


cls = Q._load_homophone_classes()
want = "回测用的是过去的数据，换个时期可能不灵。"
ok(Q._homophone_tolerant_match(want, "回测用的是过去的数据,换个时期可能不零。", cls)[0], "不灵 → 不零 passes (lexicon pair, 零 folded to 0)")
ok(Q._homophone_tolerant_match(want, want, cls)[0], "exact text still passes")
ok(not Q._homophone_tolerant_match("大盘动一，它大约动一点五。", "大盘动1,它大约动2.5。", cls)[0], "a different number (一点五 → 2.5) still fails")
ok(not Q._homophone_tolerant_match("在负一到一之间。", "在负一到二之间。", cls)[0], "一 → 二 still fails")
ok(not Q._homophone_tolerant_match("换个时期可能不灵。", "换个时期可能不9。", cls)[0], "不灵 → 不9 still fails (only the lexicon pair absorbs a digit)")
ok(Q._homophone_tolerant_match("用一个数来表示，在负一到一之间。", "用一个数来表示,在-1到1之间。", cls)[0], "same numbers in digits still pass")
ok(Q._homophone_tolerant_match("这个原始数，叫协方差。", "这个原始数叫斜方差。", cls)[0], "existing class (协方差/斜方差) unaffected")
ok(Q._homophone_tolerant_match("用一个数来表示，在负一到一之间。", "用一个数来表示,在-1-1之间。", cls)[0], "Whisper '-1-1' reads as 负1到1")
ok(Q._homophone_tolerant_match("接近负一，基本一个往上、一个往下。", "接近-1,基本一个往上一个往下。", cls)[0], "Whisper '-1' reads as 负1")
ok(not Q._homophone_tolerant_match("在负一到一之间。", "在-1-2之间。", cls)[0], "'-1-2' still fails against 负一到一")
ok(not Q._homophone_tolerant_match("接近一。", "接近-1。", cls)[0], "a sign the narrator did not say still fails (一 vs -1)")
print(f"{n} ok")
