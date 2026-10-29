"""Canonical numbers for zh ASR comparison: Whisper writes 一百万 as "100万" (or 1000000),
the script may say 一百万 — same words, different notation. Char-by-char digit folding
(一→1) turns 一百万 into "1百万" ≠ "100万", so number phrases are folded to one Arabic
form first. Applied to BOTH sides of a compare, so it can only remove notation noise,
never hide a different number.

  一百万 / 100万 / 1000000 → 1000000      九十九 → 99      两千零五 → 2005
  97.5 stays 97.5 (九十七点五 → 97.5)      一定 / 千万别 / 万一 are left alone (no leading digit)
"""
from __future__ import annotations

import re

_D = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_U = {"十": 10, "百": 100, "千": 1000}
_BIG = {"万": 10 ** 4, "亿": 10 ** 8}
_CN = re.compile(r"(?:[零〇一二两三四五六七八九]|十)[零〇一二两三四五六七八九十百千万亿]*(?:点[零〇一二三四五六七八九]+)?")
_AR_BIG = re.compile(r"(\d+(?:\.\d+)?)([万亿])")


def _small(s: str) -> int:
    total, cur = 0, 0
    for ch in s:
        if ch in _D:
            cur = _D[ch]
        elif ch in _U:
            total += (cur or 1) * _U[ch]
            cur = 0
    return total + cur


def cn_int(s: str) -> int:
    total, sec = 0, ""
    for ch in s:
        if ch in _BIG:
            total += (_small(sec) or 1) * _BIG[ch]
            sec = ""
        else:
            sec += ch
    return total + _small(sec)


def _cn_repl(m: re.Match) -> str:
    tok = m.group(0)
    whole, _, frac = tok.partition("点")
    if not any(c in _U or c in _BIG for c in whole) and not frac:
        return tok  # bare digits (一定, 二维) keep the per-char fold downstream
    out = str(cn_int(whole))
    if frac:
        out += "." + "".join(str(_D[c]) for c in frac)
    return out


def _ar_repl(m: re.Match) -> str:
    v = float(m.group(1)) * _BIG[m.group(2)]
    return str(int(v)) if v == int(v) else repr(v)


def fold_numbers(s: str) -> str:
    s = _CN.sub(_cn_repl, s)
    return _AR_BIG.sub(_ar_repl, s)
