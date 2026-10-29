"""Route lines.json → wavs + dur.json across TTS providers.

    python core/tts/tts_router.py lines.json out_dir \\
        [--provider edge|kokoro|qwen3|omnivoice|stepaudio|elevenlabs|elevenlabs-dialogue|auto] \\
        [--fallback edge,kokoro] [--list] [--voice …]

Default provider: edge (tts_zh.py / Yunxi). Offline second path: kokoro
(via repo .venv-voice when present). qwen3 / omnivoice activate only when
LEMO_TTS_*_BASE is set (HTTP client ready; no API keys invented).

See tools/tts_router.md. VO completeness checks apply for every provider.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# Allow `python core/tts/tts_router.py` without installing a package.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers import edge_provider, elevenlabs, elevenlabs_dialogue, kokoro_provider, omnivoice, qwen3, stepaudio  # noqa: E402
from providers.runtime import list_statuses, probe_edge, probe_elevenlabs, probe_elevenlabs_dialogue, probe_kokoro, probe_omnivoice, probe_qwen3, probe_stepaudio  # noqa: E402

SYNTH = {
    "edge": edge_provider.synthesize,
    "kokoro": kokoro_provider.synthesize,
    "qwen3": qwen3.synthesize,
    "omnivoice": omnivoice.synthesize,
    "stepaudio": stepaudio.synthesize,
    "elevenlabs": elevenlabs.synthesize,
    "elevenlabs-dialogue": elevenlabs_dialogue.synthesize,
}
PROBES = {
    "edge": probe_edge,
    "kokoro": probe_kokoro,
    "qwen3": probe_qwen3,
    "omnivoice": probe_omnivoice,
    "stepaudio": probe_stepaudio,
    "elevenlabs": probe_elevenlabs,
    "elevenlabs-dialogue": probe_elevenlabs_dialogue,
}
DEFAULT_FALLBACK = ("edge", "kokoro")


def _print_list(as_json: bool = False) -> int:
    rows = [s.as_dict() for s in list_statuses()]
    if as_json:
        json.dump({"providers": rows}, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    print(f"{'id':<22} {'state':<14} network         detail")
    print("-" * 88)
    for r in rows:
        print(f"{r['id']:<22} {r['state']:<14} {r['network']:<14} {r['detail']}")
    ready = [r["id"] for r in rows if r["ready"]]
    print()
    print(f"ready: {', '.join(ready) if ready else '(none)'}")
    print("hint: --provider auto picks first ready in edge,kokoro,qwen3,omnivoice")
    print("      --fallback edge,kokoro retries the next ready provider on failure")
    return 0


def _parse_fallback(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_FALLBACK)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    bad = [p for p in parts if p not in SYNTH]
    if bad:
        sys.exit(f"tts_router: unknown fallback provider(s): {bad}; choose from {sorted(SYNTH)}")
    return parts


def _load_lines(path: str) -> list[dict]:
    lines = json.load(open(path, encoding="utf-8"))
    if not isinstance(lines, list) or not lines:
        sys.exit("tts_router: lines.json must be a non-empty list")
    for L in lines:
        if not isinstance(L, dict) or "id" not in L or "text" not in L:
            sys.exit("tts_router: each line needs id and text")
    return lines


def _default_voice(provider: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    if provider == "edge":
        return "zh-CN-YunxiNeural"
    if provider == "kokoro":
        return "zf_xiaoxiao"
    if provider == "elevenlabs":
        return elevenlabs.voice_id()
    return None


def _run_one(provider: str, lines: list[dict], out_dir: str, voice: str | None, rate: str, pitch: str) -> dict[str, float]:
    st = PROBES[provider]()
    if st.state == "deps-missing":
        sys.exit(f"tts_router: provider {provider!r} not ready: {st.detail}")
    if st.state in ("needs-server", "needs-key"):
        sys.exit(f"tts_router: provider {provider!r} not ready: {st.detail}")
    opts = {
        "voice": _default_voice(provider, voice),
        "rate": rate,
        "pitch": pitch,
    }
    synth = SYNTH[provider]
    dur = synth(lines, out_dir, **{k: v for k, v in opts.items() if v is not None})
    missing = [L["id"] for L in lines if L["id"] not in dur]
    if missing:
        sys.exit(f"tts_router: provider {provider!r} did not return durations for: {missing}")
    return dur


def synthesize(
    lines: list[dict],
    out_dir: str,
    *,
    provider: str = "edge",
    fallback: list[str] | None = None,
    voice: str | None = None,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> tuple[str, dict[str, float]]:
    """Programmatic entry. Returns (provider_used, dur_map)."""
    chain: list[str]
    if provider == "auto":
        prefer = fallback or list(DEFAULT_FALLBACK) + ["qwen3", "omnivoice"]
        chain = []
        seen: set[str] = set()
        for p in prefer:
            if p in seen:
                continue
            seen.add(p)
            if PROBES[p]().state == "ready":
                chain.append(p)
        if not chain:
            sys.exit(
                "tts_router: --provider auto found no ready providers.\n"
                "  Install edge-tts and/or create .venv-voice for kokoro; "
                "or set LEMO_TTS_QWEN3_BASE / LEMO_TTS_OMNIVOICE_BASE.\n"
                "  Run: python core/tts/tts_router.py --list"
            )
    else:
        if provider not in SYNTH:
            sys.exit(f"tts_router: unknown provider {provider!r}")
        fb = fallback if fallback is not None else []
        chain = [provider] + [p for p in fb if p != provider]

    errors: list[str] = []
    for name in chain:
        st = PROBES[name]()
        if st.state != "ready":
            errors.append(f"{name}: skip ({st.state}) {st.detail}")
            continue
        try:
            dur = _run_one(name, lines, out_dir, voice, rate, pitch)
            return name, dur
        except SystemExit as e:
            # SystemExit(code) or SystemExit(message)
            msg = e.code if isinstance(e.code, str) else f"exit {e.code}"
            errors.append(f"{name}: {msg}")
            if name == chain[-1]:
                break
            print(f"tts_router: provider {name!r} failed, trying fallback…\n  {msg}", file=sys.stderr)
            continue
    detail = "\n  ".join(errors) if errors else "(no attempts)"
    sys.exit(f"tts_router: all providers failed\n  {detail}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lines", nargs="?", help="lines.json")
    ap.add_argument("out_dir", nargs="?", help="output directory for <id>.wav + dur.json")
    ap.add_argument(
        "--provider",
        default=os.environ.get("LEMO_TTS_PROVIDER", "edge"),
        help="edge|kokoro|qwen3|omnivoice|stepaudio|elevenlabs|elevenlabs-dialogue|auto (default: env LEMO_TTS_PROVIDER or edge)",
    )
    ap.add_argument(
        "--fallback",
        default=os.environ.get("LEMO_TTS_FALLBACK", "edge,kokoro"),
        help="comma list tried after the primary fails (also seeds auto order). empty disables",
    )
    ap.add_argument("--voice", default=None, help="default voice (edge: Yunxi; kokoro: zf_xiaoxiao)")
    ap.add_argument("--rate", default="+0%")
    ap.add_argument("--pitch", default="+0Hz")
    ap.add_argument("--list", action="store_true", help="print provider readiness and exit")
    ap.add_argument("--json", action="store_true", help="with --list, emit JSON")
    a = ap.parse_args(argv)

    if a.list:
        raise SystemExit(_print_list(as_json=a.json))

    if not a.lines or not a.out_dir:
        ap.error("lines and out_dir required unless --list")

    lines = _load_lines(a.lines)
    fb_raw = (a.fallback or "").strip()
    fallback = _parse_fallback(fb_raw) if fb_raw else []
    # For explicit primary, still honor fallback list; for auto, use fallback as preference order.
    used, dur = synthesize(
        lines,
        a.out_dir,
        provider=a.provider,
        fallback=fallback,
        voice=a.voice,
        rate=a.rate,
        pitch=a.pitch,
    )
    print(f"tts_router: provider={used} lines={len(lines)} → {a.out_dir}")
    print(f"tts_router: dur={json.dumps(dur, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
