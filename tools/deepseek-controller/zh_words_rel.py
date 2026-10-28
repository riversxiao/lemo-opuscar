"""Sentence-level words_rel.json for Chinese lines (tools/words.py is English word-alignment only).

    python3 tools/deepseek-controller/zh_words_rel.py --project <film>

Each subtitle "word" (whitespace split; a CJK sentence is one token) appears at t=0 of its line.
Never overwrites a non-CJK entry produced by tools/words.py. Does NOT replace ASR content checks.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

CJK = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def build(project: Path) -> Path:
    project = Path(project).resolve()
    lines_p = project / "lines.json"
    if not lines_p.is_file():
        lines_p = project / "content" / "lines.json"
    lines = json.loads(lines_p.read_text(encoding="utf-8"))
    out_p = project / "voices" / "words_rel.json"
    out = json.loads(out_p.read_text(encoding="utf-8")) if out_p.is_file() else {}
    for L in lines:
        if CJK.search(L["text"]) or L["id"] not in out:
            out[L["id"]] = [0.0] * max(1, len(L["text"].split()))
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    return out_p


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    print("wrote", build(Path(ap.parse_args().project)))
