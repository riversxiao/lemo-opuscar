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


# ---------------------------------------------------------------- spell (TTS side)
# The reverse direction, for voices that read Arabic numerals in English inside Chinese text
# (ElevenLabs read 97.5% as "ninety-seven point five percent"): 97.5% → 百分之九十七点五.
_CD = "零一二三四五六七八九"


def _sec_cn(n: int) -> str:
    """0 < n < 10000."""
    out, zero = "", False
    for unit, name in ((1000, "千"), (100, "百"), (10, "十"), (1, "")):
        d = n // unit % 10
        if d:
            if zero and out:
                out += "零"
            out += _CD[d] + name
            zero = False
        elif out:
            zero = True
    return out


def int_cn(n: int) -> str:
    if n == 0:
        return "零"
    parts, out, need_zero = [(n // 10 ** 8, "亿"), (n // 10 ** 4 % 10 ** 4, "万"), (n % 10 ** 4, "")], "", False
    for v, unit in parts:
        if v:
            if out and (need_zero or v < 1000):
                out += "零"
            out += _sec_cn(v) + unit
            need_zero = False
        elif out:
            need_zero = True
    if out.startswith("一十"):
        out = out[1:]  # 十五 / 十二万, not 一十五
    return out


def num_cn(tok: str) -> str:
    whole, _, frac = tok.partition(".")
    out = int_cn(int(whole))
    if frac:
        out += "点" + "".join(_CD[int(c)] for c in frac)
    return out


_SPELL = re.compile(r"(\d+(?:\.\d+)?)\s*(%|％|[万亿])?")


def spell_numbers(s: str) -> str:
    """Arabic numbers → Chinese words: 97.5% → 百分之九十七点五, 100万 → 一百万, 2026 → 二零二六 is NOT
    done (years are ambiguous) — only percentages, 万/亿 amounts and plain integers/decimals."""
    def rep(m: re.Match) -> str:
        n, unit = m.group(1), m.group(2) or ""
        if unit in ("%", "％"):
            return "百分之" + num_cn(n)
        if unit in ("万", "亿"):
            return num_cn(n) + unit
        return num_cn(n)
    return _SPELL.sub(rep, s)
