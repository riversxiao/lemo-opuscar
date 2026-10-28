#!/usr/bin/env python3
"""Post-TTS helper: refresh zh words_rel.json (never call English tools/words.py on CJK).

    python3 tools/deepseek-controller/post_tts.py --project <film>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from zh_words_rel import build, CJK
from common import load_json


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    args = ap.parse_args(argv)
    project = Path(args.project).resolve()
    lines_p = project / "content" / "lines.json"
    if not lines_p.is_file():
        lines_p = project / "lines.json"
    if not lines_p.is_file():
        print(f"ERROR: no lines.json under {project}", file=sys.stderr)
        return 1
    lines = load_json(lines_p)
    if not isinstance(lines, list):
        print("ERROR: lines.json must be a list", file=sys.stderr)
        return 1
    if not any(CJK.search(str(L.get("text") or "")) for L in lines if isinstance(L, dict)):
        print("skip: no CJK lines (use tools/words.py for English word alignment)")
        return 0
    out = build(project)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
