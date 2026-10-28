"""Route lines.json → wavs + dur.json across TTS providers.

    python core/tts/tts_router.py lines.json out_dir [--provider edge|kokoro|qwen3|omnivoice]

Default: edge (tts_zh.py / Yunxi). See tools/tts_router.md.
VO completeness checks apply for every provider (AGENTS.deepseek.md).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Allow `python core/tts/tts_router.py` without installing a package.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers import edge_provider, kokoro_provider, omnivoice, qwen3  # noqa: E402

PROVIDERS = {
    "edge": edge_provider.synthesize,
    "kokoro": kokoro_provider.synthesize,
    "qwen3": qwen3.synthesize,
    "omnivoice": omnivoice.synthesize,
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lines")
    ap.add_argument("out_dir")
    ap.add_argument(
        "--provider",
        default=os.environ.get("LEMO_TTS_PROVIDER", "edge"),
        choices=sorted(PROVIDERS),
    )
    ap.add_argument("--voice", default=None, help="default voice (edge default Yunxi)")
    ap.add_argument("--rate", default="+0%")
    ap.add_argument("--pitch", default="+0Hz")
    a = ap.parse_args()
    lines = json.load(open(a.lines, encoding="utf-8"))
    if not isinstance(lines, list) or not lines:
        sys.exit("tts_router: lines.json must be a non-empty list")
    for L in lines:
        if "id" not in L or "text" not in L:
            sys.exit("tts_router: each line needs id and text")
    opts = {
        "voice": a.voice or ("zh-CN-YunxiNeural" if a.provider == "edge" else None),
        "rate": a.rate,
        "pitch": a.pitch,
    }
    synth = PROVIDERS[a.provider]
    dur = synth(lines, a.out_dir, **{k: v for k, v in opts.items() if v is not None})
    missing = [L["id"] for L in lines if L["id"] not in dur]
    if missing:
        sys.exit(f"tts_router: provider {a.provider!r} did not return durations for: {missing}")
    print(f"tts_router: provider={a.provider} lines={len(lines)} → {a.out_dir}")


if __name__ == "__main__":
    main()
