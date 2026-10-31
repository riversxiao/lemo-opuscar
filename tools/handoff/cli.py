#!/usr/bin/env python3
"""CLI: openfilm | hyperframes | premiere | both handoff from a finished lemo film dir."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .common import parse_fps, parse_size
from .openfilm import export_openfilm
from .hyperframes import export_hyperframes
from .premiere import export_premiere


def _size_arg(spec: str) -> tuple[int, int]:
    try:
        return parse_size(spec)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def _fps_arg(spec: str) -> float:
    try:
        return parse_fps(spec)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def _add_frame_args(sp: argparse.ArgumentParser, *, fps: bool = True) -> None:
    sp.add_argument(
        "--size",
        type=_size_arg,
        default=None,
        metavar="WxH",
        help="frame size, e.g. 1080x1920 (default: ffprobe of the master, else 1920x1080)",
    )
    if fps:
        sp.add_argument(
            "--fps",
            type=_fps_arg,
            default=None,
            help="frame rate, e.g. 24, 29.97 or 30000/1001 (default: ffprobe, else 24)",
        )


def _wh(args: argparse.Namespace) -> dict:
    if args.size:
        return {"width": args.size[0], "height": args.size[1]}
    return {}


def _frame_line(info: dict) -> str:
    fps = info.get("fps")
    rate = f" @ {fps:g}fps (fps from {info.get('fpsSource')})" if fps else ""
    return f"  frame: {info['width']}x{info['height']} (size from {info['sizeSource']}){rate}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lemo-handoff")
    sub = p.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("openfilm", help="multi-shot OpenFilm package + EDL + premiere.xml + ffmpeg rebuild")
    o.add_argument("film_dir")
    o.add_argument("--name", default=None)
    o.add_argument("-o", "--out", default=None, help="default: <film>/openfilm-handoff")
    o.add_argument(
        "--extract-shots",
        action="store_true",
        help="also write shots/*.mp4 (re-encode; slower)",
    )
    _add_frame_args(o)
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
    _add_frame_args(h, fps=False)
    h.add_argument("--json", action="store_true")

    pr = sub.add_parser(
        "premiere",
        help="FCP xmeml v5 + master for Premiere/Resolve import (not .prproj)",
    )
    pr.add_argument("film_dir")
    pr.add_argument("--name", default=None)
    pr.add_argument("-o", "--out", default=None, help="default: <film>/premiere-handoff")
    _add_frame_args(pr)
    pr.add_argument("--json", action="store_true")

    a = sub.add_parser("both", help="openfilm + hyperframes (+ premiere) for one film")
    a.add_argument("film_dir")
    a.add_argument("--name", default=None)
    a.add_argument("--extract-shots", action="store_true")
    a.add_argument("--lint", action="store_true")
    a.add_argument(
        "--with-premiere",
        action="store_true",
        help="also write premiere-handoff/ (xmeml)",
    )
    _add_frame_args(a)
    a.add_argument("--json", action="store_true")

    args = p.parse_args(argv)
    film = Path(args.film_dir)

    if args.cmd == "openfilm":
        info = export_openfilm(
            film,
            name=args.name,
            out_dir=Path(args.out) if args.out else None,
            extract_shots=args.extract_shots,
            fps=args.fps,
            **_wh(args),
        )
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"openfilm_handoff: wrote {info['out']}")
            print(f"  mp4: {info['mp4']}")
            print(f"  duration: {info['durationSec']}s")
            print(_frame_line(info))
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
            **_wh(args),
        )
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"hyperframes_export: wrote {info['out']}")
            print(f"  mp4: {info['mp4']}")
            print(f"  duration: {info['durationSec']}s")
            print(_frame_line(info))
            print(f"  shots: {info['shotCount']} ({info['shotSource']})")
            if info.get("lintOk") is True:
                print("  lint: PASS")
            elif info.get("lintOk") is False:
                print("  lint: FAIL")
                print(info.get("lintDetail") or "")
            print("  needs-user: desktop Studio / HeyGen cloud / skills install")
            print(f"  next: cd {info['out']} && npx -y hyperframes@0.8.212 lint")
        return 0 if info.get("lintOk") is not False else 1

    if args.cmd == "premiere":
        info = export_premiere(
            film,
            name=args.name,
            out_dir=Path(args.out) if args.out else None,
            fps=args.fps,
            **_wh(args),
        )
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"premiere_handoff: wrote {info['out']}")
            print(f"  xml: {info['xml']}")
            print(_frame_line(info))
            print(f"  shots: {info['shotCount']} ({info['shotSource']})")
            print("  import: Premiere File→Import premiere.xml (keep assets/ beside it)")
        return 0

    if args.cmd == "both":
        of = export_openfilm(
            film,
            name=args.name,
            extract_shots=args.extract_shots,
            fps=args.fps,
            **_wh(args),
        )
        hf = export_hyperframes(film, name=args.name, run_lint=args.lint, **_wh(args))
        blob: dict = {"openfilm": of, "hyperframes": hf}
        if args.with_premiere:
            blob["premiere"] = export_premiere(
                film, name=args.name, fps=args.fps, **_wh(args)
            )
        if args.json:
            print(json.dumps(blob, ensure_ascii=False, indent=2))
        else:
            print(f"openfilm → {of['out']} ({of['shotCount']} shots, {of['width']}x{of['height']} from {of['sizeSource']})")
            print(f"hyperframes → {hf['out']} (lint={hf.get('lintOk')})")
            if "premiere" in blob:
                print(f"premiere → {blob['premiere']['out']}")
        return 0 if hf.get("lintOk") is not False else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
