#!/usr/bin/env python3
"""DeepSeek controller CLI: validate | adapt | scaffold | schedule | mix | quality."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters import adapt  # noqa: E402
from common import load_json  # noqa: E402
from quality import main as quality_main  # noqa: E402
from schedule import main as schedule_main  # noqa: E402
from validate import validate_plan  # noqa: E402
from scaffold import scaffold  # noqa: E402


def cmd_validate(args: argparse.Namespace) -> int:
    plan = load_json(Path(args.plan))
    errors = validate_plan(plan, strict_manifest=not args.no_manifest)
    if errors:
        print(f"INVALID ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("OK")
    return 0


def cmd_adapt(args: argparse.Namespace) -> int:
    plan = load_json(Path(args.plan))
    errors = validate_plan(plan, strict_manifest=not args.no_manifest)
    if errors:
        print(f"INVALID plan, refuse adapt ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    out = Path(args.out)
    written = adapt(plan, out)
    print(f"OK adapted {plan['style']} → {out}")
    for w in written:
        print(f"  {w.relative_to(out)}")
    return 0



def cmd_scaffold(args: argparse.Namespace) -> int:
    try:
        info = scaffold(
            Path(args.plan),
            Path(args.out),
            lib=Path(args.lib) if args.lib else None,
            force=args.force,
        )
    except (ValueError, FileExistsError, FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK scaffold {info.get('style')} mode={info.get('mode')} → {info['project']}")
    if info.get("protectedSha256"):
        for name, h in info["protectedSha256"].items():
            print(f"  lock {name}: {h[:16]}…")
    return 0

def cmd_schedule(args: argparse.Namespace) -> int:
    # Re-parse into schedule.main argv
    argv = ["--project", args.project]
    if args.lines:
        argv += ["--lines", args.lines]
    if args.dur:
        argv += ["--dur", args.dur]
    if args.voices_dir:
        argv += ["--voices-dir", args.voices_dir]
    if args.target is not None:
        argv += ["--target", str(args.target)]
    if args.grid is not None:
        argv += ["--grid", str(args.grid)]
    if args.style:
        argv += ["--style", args.style]
    if args.require_vo:
        argv.append("--require-vo")
    if getattr(args, "no_pad", False):
        argv.append("--no-pad")
    if args.output:
        argv += ["-o", args.output]
    return schedule_main(argv)



def cmd_mix(args: argparse.Namespace) -> int:
    """Bed + VO mix (default) or VO-only; does not touch locked style music.py."""
    if args.vo_only:
        from mix_vo_only import mix_vo_only
        try:
            out = mix_vo_only(
                Path(args.project),
                out=Path(args.out) if args.out else None,
            )
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print(f"OK mix_vo_only → {out}")
        return 0
    from music_bed import mix_bed_vo
    try:
        info = mix_bed_vo(
            Path(args.project),
            out=Path(args.out) if args.out else None,
            bed_out=Path(args.bed_out) if args.bed_out else None,
            bed_path=Path(args.bed) if args.bed else None,
            preset=args.preset,
            bpm=args.bpm,
            seed=args.seed,
            bed_gain=args.bed_gain,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK music_bed → {info['mix']}")
    print(f"   bed={info['bed']}  preset={info['metaObj'].get('preset')}")
    return 0


def cmd_quality(args: argparse.Namespace) -> int:
    argv = ["--project", args.project]
    if args.media:
        argv += ["--media", args.media]
    for name in args.force_fail or []:
        argv += ["--force-fail", name]
    if args.skip_heavy:
        argv.append("--skip-heavy")
    if args.allow_unchecked:
        argv.append("--allow-unchecked")
    if getattr(args, "require_vo", False):
        argv.append("--require-vo")
    if getattr(args, "delivery", False):
        argv.append("--delivery")
    if getattr(args, "asr_mode", None):
        argv += ["--asr-mode", args.asr_mode]
    if args.output:
        argv += ["-o", args.output]
    return quality_main(argv)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deepseek-controller",
        description="Minimal DeepSeek film controller (plan → adapt → scaffold → schedule → mix → quality)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="validate plan JSON")
    v.add_argument("plan")
    v.add_argument("--no-manifest", action="store_true")
    v.set_defaults(func=cmd_validate)

    a = sub.add_parser("adapt", help="write content-only files for a style")
    a.add_argument("plan")
    a.add_argument("-o", "--out", required=True, help="project output directory")
    a.add_argument("--no-manifest", action="store_true")
    a.set_defaults(func=cmd_adapt)

    sc = sub.add_parser("scaffold", help="copy style demo + full thin glue (swiss/pictogram/caption)")
    sc.add_argument("plan")
    sc.add_argument("-o", "--out", required=True, help="project output directory")
    sc.add_argument("--lib", help="repo root with styles/*/demo")
    sc.add_argument("--force", action="store_true", help="overwrite existing project")
    sc.set_defaults(func=cmd_scaffold)

    s = sub.add_parser("schedule", help="VO-driven timeline.parsed.json")
    s.add_argument("--project", required=True)
    s.add_argument("--lines")
    s.add_argument("--dur")
    s.add_argument("--voices-dir")
    s.add_argument("--target", type=float)
    s.add_argument("--grid", type=float)
    s.add_argument("--style")
    s.add_argument("--require-vo", action="store_true")
    s.add_argument(
        "--no-pad",
        action="store_true",
        help="do not hold-last-beat pad when content < target",
    )
    s.add_argument("-o", "--output")
    s.set_defaults(func=cmd_schedule)

    q = sub.add_parser("quality", help="write quality.json and gate delivery")
    q.add_argument("--project", required=True)
    q.add_argument("--media")
    q.add_argument("--force-fail", action="append", default=[])
    q.add_argument("--skip-heavy", action="store_true")
    q.add_argument("--allow-unchecked", action="store_true")
    q.add_argument(
        "--require-vo",
        action="store_true",
        help="fail schedule check if measured VO missing (also implied when plan has voice lines)",
    )
    q.add_argument(
        "--asr-mode",
        choices=("strict", "zh-homophone-tolerant", "auto"),
        default=None,
        help="strict / zh-homophone-tolerant / auto (zh*→tolerant). "
        "Default without --delivery: strict",
    )
    q.add_argument(
        "--delivery",
        action="store_true",
        help="recommended delivery path: --require-vo + zh plan → zh-homophone-tolerant "
        "(English stays strict unless --asr-mode set)",
    )
    q.add_argument("-o", "--output")
    q.set_defaults(func=cmd_quality)

    m = sub.add_parser(
        "mix",
        help="music bed + VO → out/mix.wav (placeholder softsynth; or --vo-only / --bed)",
    )
    m.add_argument("--project", required=True)
    m.add_argument("--out", help="default: <project>/out/mix.wav")
    m.add_argument("--bed-out", help="default: <project>/music/bed.wav")
    m.add_argument("--bed", help="use existing bed WAV instead of synthesizing")
    m.add_argument(
        "--preset",
        choices=("soft-pulse", "pad", "silence"),
        default="soft-pulse",
    )
    m.add_argument("--bpm", type=float, default=None)
    m.add_argument("--seed", type=int, default=20261029)
    m.add_argument("--bed-gain", type=float, default=1.0)
    m.add_argument(
        "--vo-only",
        action="store_true",
        help="legacy mix_vo_only (VO + silence, no bed)",
    )
    m.set_defaults(func=cmd_mix)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
