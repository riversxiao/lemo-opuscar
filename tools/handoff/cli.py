#!/usr/bin/env python3
"""CLI: openfilm | hyperframes handoff from a finished lemo film dir."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .openfilm import export_openfilm
from .hyperframes import export_hyperframes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lemo-handoff")
    sub = p.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("openfilm", help="multi-shot OpenFilm package + EDL + ffmpeg rebuild")
    o.add_argument("film_dir")
    o.add_argument("--name", default=None)
    o.add_argument("-o", "--out", default=None, help="default: <film>/openfilm-handoff")
    o.add_argument(
        "--extract-shots",
        action="store_true",
        help="also write shots/*.mp4 (re-encode; slower)",
    )
    o.add_argument("--json", action="store_true")

    h = sub.add_parser("hyperframes", help="HyperFrames composition export (lintable locally)")
    h.add_argument("film_dir")
    h.add_argument("--name", default=None)
    h.add_argument("-o", "--out", default=None, help="default: <film>/hyperframes-handoff")
    h.add_argument(
        "--try-init-cli",
        action="store_true",
        help="also run npx hyperframes init --video (optional shape)",
    )
    h.add_argument("--lint", action="store_true", help="run hyperframes lint after export")
    h.add_argument("--json", action="store_true")

    a = sub.add_parser("both", help="openfilm + hyperframes for one film")
    a.add_argument("film_dir")
    a.add_argument("--name", default=None)
    a.add_argument("--extract-shots", action="store_true")
    a.add_argument("--lint", action="store_true")
    a.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    film = Path(args.film_dir)

    if args.cmd == "openfilm":
        info = export_openfilm(
            film,
            name=args.name,
            out_dir=Path(args.out) if args.out else None,
            extract_shots=args.extract_shots,
        )
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"openfilm_handoff: wrote {info['out']}")
            print(f"  mp4: {info['mp4']}")
            print(f"  duration: {info['durationSec']}s")
            print(f"  shots: {info['shotCount']} ({info['shotSource']})")
            print(f"  next: cd {info['out']} && npx -y openfilm@latest look")
        return 0

    if args.cmd == "hyperframes":
        info = export_hyperframes(
            film,
            name=args.name,
            out_dir=Path(args.out) if args.out else None,
            try_init_cli=args.try_init_cli,
            run_lint=args.lint,
        )
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"hyperframes_export: wrote {info['out']}")
            print(f"  mp4: {info['mp4']}")
            print(f"  duration: {info['durationSec']}s")
            print(f"  shots: {info['shotCount']} ({info['shotSource']})")
            if info.get("lintOk") is True:
                print("  lint: PASS")
            elif info.get("lintOk") is False:
                print("  lint: FAIL")
                print(info.get("lintDetail") or "")
            print("  needs-user: desktop Studio / HeyGen cloud / skills install")
            print(f"  next: cd {info['out']} && npx -y hyperframes@0.8.212 lint")
        return 0 if info.get("lintOk") is not False else 1

    if args.cmd == "both":
        of = export_openfilm(film, name=args.name, extract_shots=args.extract_shots)
        hf = export_hyperframes(film, name=args.name, run_lint=args.lint)
        blob = {"openfilm": of, "hyperframes": hf}
        if args.json:
            print(json.dumps(blob, ensure_ascii=False, indent=2))
        else:
            print(f"openfilm → {of['out']} ({of['shotCount']} shots)")
            print(f"hyperframes → {hf['out']} (lint={hf.get('lintOk')})")
        return 0 if hf.get("lintOk") is not False else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
