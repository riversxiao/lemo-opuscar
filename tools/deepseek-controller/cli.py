#!/usr/bin/env python3
"""DeepSeek controller CLI: validate | adapt | scaffold | tts | schedule | mix | quality | handoff | matrix | budget."""
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
    if getattr(args, "pad_under_target", False):
        argv.append("--pad-under-target")
    if getattr(args, "pacing", None):
        argv += ["--pacing", args.pacing]
    if getattr(args, "no_beats", False):
        argv.append("--no-beats")
    if getattr(args, "outro", None) is not None:
        argv += ["--outro", str(args.outro)]
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
            bed_source=args.bed_source,
            music_caption=args.music_caption,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK music_bed → {info['mix']}")
    print(f"   bed={info['bed']}  preset={info['metaObj'].get('preset')}")
    return 0


def cmd_tts(args: argparse.Namespace) -> int:
    """Synthesize VO via core/tts/tts_router (edge / kokoro / auto / HTTP providers)."""
    if getattr(args, "list_providers", False):
        import json
        import sys as _sys
        from pathlib import Path as _Path
        root = _Path(__file__).resolve().parents[2]
        tts = root / "core" / "tts"
        if str(tts) not in _sys.path:
            _sys.path.insert(0, str(tts))
        from providers.runtime import list_statuses
        rows = [s.as_dict() for s in list_statuses()]
        if args.json:
            print(json.dumps({"providers": rows}, ensure_ascii=False, indent=2))
        else:
            print(f"{'id':<22} {'state':<14} detail")
            for r in rows:
                print(f"{r['id']:<22} {r['state']:<14} {r['detail']}")
            ready = [r['id'] for r in rows if r['ready']]
            print(f"ready: {', '.join(ready) if ready else '(none)'}")
        return 0
    if not args.project:
        print("ERROR: --project required (or --list)", file=sys.stderr)
        return 2
    if getattr(args, "skip_dialogue_gate", False):
        print("WARN dialogue gate SKIPPED (--skip-dialogue-gate; legacy lines, not DIALOGUE-checked)", file=sys.stderr)
    else:
        import dialogue_check
        try:
            rep = dialogue_check.run(
                Path(args.project),
                lines_path=Path(args.lines) if args.lines else None,
                target=getattr(args, "target", None),
            )
        except (OSError, ValueError) as e:
            print(f"ERROR: dialogue gate: {e}", file=sys.stderr)
            return 1
        print(dialogue_check.format_report(rep))
        if rep["status"] not in ("PASS", "SKIP"):
            print("ERROR: TTS blocked — dialogue-check FAIL (fix lines per DIALOGUE.md, "
                  "or --skip-dialogue-gate for legacy projects)", file=sys.stderr)
            return 1
        if rep["status"] == "PASS":
            import dialogue_loop
            ok, why = dialogue_loop.gate_status(
                Path(args.project).resolve(), Path(args.lines) if args.lines else None)
            print(("OK " if ok else "") + why)
            if not ok:
                print("ERROR: TTS blocked — dialogue-loop not PASS for these lines "
                      "(run `cli.py dialogue-loop --project P`)", file=sys.stderr)
                return 1
    from run_tts import run_tts
    try:
        meta = run_tts(
            Path(args.project),
            provider=args.provider,
            fallback=args.fallback or "",
            lines_path=Path(args.lines) if args.lines else None,
            out_dir=Path(args.out) if args.out else None,
            voice=args.voice,
            rate=args.rate,
            pitch=args.pitch,
            post_words=not args.no_post_words,
            content_type=getattr(args, "content_type", None),
            pacing=getattr(args, "pacing", None),
            speed=getattr(args, "speed", None),
            trim_pauses=not getattr(args, "no_trim", False),
        )
    except (FileNotFoundError, SystemExit) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(f"OK tts provider={meta['provider']} pacing={meta.get('pacing')} ({meta.get('pacingSource')}) "
          f"rate={meta.get('rate')} speed={meta.get('speed')} → {meta['voices']}")
    if meta.get("pauseTrim"):
        print(f"  pause_trim removed {meta['pauseTrim']['removedSec']}s (max pause {meta['pauseTrim']['maxPauseSec']}s)")
    for lid, sec in (meta.get('dur') or {}).items():
        print(f"  {lid}: {sec}s")
    if meta.get('wordsRel'):
        print(f"  words_rel: {meta['wordsRel']}")
    return 0


def cmd_dialogue_loop(args: argparse.Namespace) -> int:
    import dialogue_loop
    argv = ["--project", args.project, "--max-rounds", str(args.max_rounds),
            "--max-cny", str(args.max_cny), "--min-balance", str(args.min_balance), "--effort", args.effort]
    for flag, val in (("--lines", args.lines), ("--brief", args.brief), ("--target", args.target),
                      ("--mock", args.mock), ("--item", args.item)):
        if val:
            argv += [flag, str(val)]
    if args.no_ledger:
        argv.append("--no-ledger")
    if getattr(args, "allow_paid", False):
        argv.append("--allow-paid")
    return dialogue_loop.main(argv)


def cmd_dialogue_check(args: argparse.Namespace) -> int:
    import dialogue_check
    argv = ["--project", args.project, "--tolerance", str(args.tolerance)]
    if args.rate:
        argv += ["--rate", str(args.rate)]
    if getattr(args, "pacing", None):
        argv += ["--pacing", args.pacing]
    if args.lines:
        argv += ["--lines", args.lines]
    if args.target:
        argv += ["--target", str(args.target)]
    if args.json:
        argv.append("--json")
    return dialogue_check.main(argv)


def cmd_beats(args: argparse.Namespace) -> int:
    import beats
    argv = ["--project", args.project]
    if args.pacing:
        argv += ["--pacing", args.pacing]
    if args.dry_run:
        argv.append("--dry-run")
    return beats.main(argv)


def cmd_pacing_rework(args: argparse.Namespace) -> int:
    import pacing_rework
    argv = ["--project", args.project, "--media", args.media, "--max-rounds", str(args.max_rounds)]
    if args.mix:
        argv += ["--mix", args.mix]
    if args.pacing:
        argv += ["--pacing", args.pacing]
    if args.dry_run:
        argv.append("--dry-run")
    return pacing_rework.main(argv)


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
    if getattr(args, "pacing_enforce", False):
        argv.append("--pacing-enforce")
    if args.output:
        argv += ["-o", args.output]
    return quality_main(argv)



def cmd_visual_check(args: argparse.Namespace) -> int:
    import visual_check as _vc

    argv = ["--project", args.project]
    if args.media:
        argv += ["--media", args.media]
    if args.rework:
        argv.append("--rework")
    if args.no_semantic:
        argv.append("--no-semantic")
    for m in args.model or []:
        argv += ["--model", m]
    return _vc.main(argv)


def cmd_handoff(args: argparse.Namespace) -> int:
    """OpenFilm / HyperFrames / Premiere-XML export from a finished film dir."""
    import json
    import sys as _sys
    import time as _time

    root = Path(__file__).resolve().parents[2]
    if str(root) not in _sys.path:
        _sys.path.insert(0, str(root))
    from tools.handoff.openfilm import export_openfilm
    from tools.handoff.hyperframes import export_hyperframes
    from tools.handoff.premiere import export_premiere

    from budget import log_local_step

    film = Path(args.project)
    target = args.target
    infos = {}
    t0 = _time.perf_counter()
    if target in ("openfilm", "both", "all"):
        infos["openfilm"] = export_openfilm(
            film,
            name=args.name,
            out_dir=Path(args.out) if args.out and target == "openfilm" else None,
            extract_shots=args.extract_shots,
        )
    if target in ("hyperframes", "both", "all"):
        infos["hyperframes"] = export_hyperframes(
            film,
            name=args.name,
            out_dir=Path(args.out) if args.out and target == "hyperframes" else None,
            try_init_cli=args.try_init_cli,
            run_lint=args.lint,
        )
    if target in ("premiere", "all"):
        infos["premiere"] = export_premiere(
            film,
            name=args.name,
            out_dir=Path(args.out) if args.out and target == "premiere" else None,
        )
    # both also gets premiere when --with-premiere
    if target == "both" and getattr(args, "with_premiere", False):
        infos["premiere"] = export_premiere(film, name=args.name)

    if not getattr(args, "no_budget", False):
        log_local_step(
            f"handoff:{target}",
            duration_sec=_time.perf_counter() - t0,
            project=str(film),
            path_label="handoff",
            notes=",".join(infos.keys()),
        )

    if args.json:
        print(json.dumps(infos, ensure_ascii=False, indent=2))
    else:
        for k, info in infos.items():
            print(f"OK handoff {k} → {info['out']} shots={info['shotCount']} ({info['shotSource']})")
            if k == "hyperframes" and info.get("lintOk") is True:
                print("  lint: PASS")
            elif k == "hyperframes" and info.get("lintOk") is False:
                print("  lint: FAIL")
            if k == "premiere" and info.get("xml"):
                print(f"  xml: {info['xml']}")
    if infos.get("hyperframes", {}).get("lintOk") is False:
        return 1
    return 0


def cmd_budget(args: argparse.Namespace) -> int:
    """Append / summarize / import OpenCode costs into fixtures/budget-ledger.jsonl."""
    import json
    from budget import (
        append_entry,
        import_opencode_sessions,
        ledger_path,
        summarize,
    )

    ledger = Path(args.ledger) if args.ledger else None
    action = args.budget_cmd
    if action == "summary":
        s = summarize(ledger)
        if args.json:
            print(json.dumps(s, ensure_ascii=False, indent=2))
        else:
            print(f"ledger: {s['ledger']}")
            print(f"entries: {s['entries']}")
            print(f"totalUsd: ${s['totalUsd']:.6f}")
            if s.get("totalCny"):
                print(f"totalCny: ¥{s['totalCny']:.4f} (rows with billed CNY, e.g. DeepSeek balance delta)")
            print(f"tokensIn/Out: {s['tokensIn']} / {s['tokensOut']}")
            if s["byKind"]:
                print("byKind:")
                for k, v in s["byKind"].items():
                    print(f"  {k}: ${v:.6f}")
            if s["byPath"]:
                print("byPath:")
                for k, v in s["byPath"].items():
                    print(f"  {k}: ${v:.6f}")
        return 0
    if action == "append":
        row = append_entry(
            {
                "kind": args.kind,
                "item": args.item,
                "usd": args.usd,
                "cny": args.cny,
                "tokensIn": args.tokens_in,
                "tokensOut": args.tokens_out,
                "durationSec": args.duration,
                "path": args.path_label,
                "project": args.project,
                "model": args.model,
                "source": args.source or "cli",
                "notes": args.notes or "",
                "meta": {"sessionId": args.session_id} if args.session_id else {},
            },
            path=ledger,
        )
        if args.json:
            print(json.dumps(row, ensure_ascii=False, indent=2))
        else:
            extra = f" cny=¥{row['cny']}" if "cny" in row else ""
            print(f"OK appended → {ledger_path(ledger)} usd=${row['usd']}{extra}")
        return 0
    if action == "import-opencode":
        res = import_opencode_sessions(
            db_path=Path(args.db) if args.db else None,
            ledger=ledger,
            title_substr=args.filter,
            min_usd=args.min_usd,
            dry_run=args.dry_run,
        )
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            if not res.get("ok"):
                print(f"ERROR: {res.get('error')}", file=sys.stderr)
                return 1
            print(
                f"OK opencode import dryRun={res['dryRun']} "
                f"imported={res['imported']} would={res['wouldImport']} "
                f"skipped={res['skipped']} sumUsdWould=${res['sumUsdWould']:.6f}"
            )
        return 0 if res.get("ok") else 1
    print(f"unknown budget action {action}", file=sys.stderr)
    return 2



def cmd_matrix(args: argparse.Namespace) -> int:
    """List 18-film comparison matrix status (tracker JSON; no render)."""
    import json
    from matrix import cell_by_id, format_table, load_matrix, summary

    tracker = Path(args.tracker) if args.tracker else None
    data = load_matrix(tracker)
    if args.id:
        cell = cell_by_id(args.id, data)
        if not cell:
            print(f"ERROR: unknown cell id {args.id}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(cell, ensure_ascii=False, indent=2))
        else:
            print(format_table(data, cell_id=args.id))
        return 0
    if args.json:
        print(json.dumps(summary(data), ensure_ascii=False, indent=2))
        return 0
    print(format_table(data, filled_only=args.filled, path=getattr(args, "path", None)))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="deepseek-controller",
        description="Minimal DeepSeek film controller (plan → adapt → scaffold → tts → schedule → mix → quality → handoff → matrix → budget)",
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
        help="(default) no hold-last-beat pad; kept for old scripts",
    )
    s.add_argument("--pad-under-target", action="store_true",
                   help="LEGACY hold-last-beat pad to target (quality FAILs padding > 1.5s)")
    s.add_argument("--pacing", help="fast|standard|calm (default plan.json pacing / content_type)")
    s.add_argument("--no-beats", action="store_true", help="skip beats_runtime.json (P1 sub-beats)")
    s.add_argument("--outro", type=float, default=None, help="outro/brand card seconds (≤1.5)")
    s.add_argument("-o", "--output")
    s.set_defaults(func=cmd_schedule)


    t = sub.add_parser(
        "tts",
        help="synthesize VO via tts_router (edge/kokoro/auto; qwen3|omnivoice|*_BASE; stepaudio|elevenlabs|elevenlabs-dialogue when key set)",
    )
    t.add_argument("--project", help="film project root (required unless --list)")
    t.add_argument(
        "--provider",
        default="edge",
        help="edge|kokoro|qwen3|omnivoice|stepaudio|elevenlabs|elevenlabs-dialogue|auto (cloud providers need keys; explicit only)",
    )
    t.add_argument(
        "--fallback",
        default="edge,kokoro",
        help="comma list for retries / auto preference (empty disables)",
    )
    t.add_argument("--lines", help="override lines.json path")
    t.add_argument("--out", help="voices dir (default: <project>/voices)")
    t.add_argument("--voice", default=None)
    t.add_argument("--rate", default=None, help="edge rate (default: pacing profile edgeRate, standard +10%%)")
    t.add_argument("--speed", type=float, default=None,
                   help="stepaudio speed (default: env LEMO_TTS_STEPAUDIO_SPEED, else pacing profile)")
    t.add_argument("--pacing", default=None, help="fast|standard|calm (default plan.json pacing / content_type)")
    t.add_argument("--no-trim", action="store_true", help="skip pause_trim after synthesis")
    t.add_argument("--pitch", default="+0Hz")
    t.add_argument(
        "--content-type",
        default=None,
        help="elevenlabs-dialogue guest by content: market|concept|personal|english "
             "(default: plan.json content_type, else market→Linda; ELEVENLABS_VOICE_GUEST overrides)",
    )
    t.add_argument("--no-post-words", action="store_true", help="skip zh words_rel refresh")
    t.add_argument("--list", dest="list_providers", action="store_true", help="show provider readiness")
    t.add_argument("--json", action="store_true", help="with --list, JSON output")
    t.add_argument("--target", type=float, default=None, help="dialogue gate target sec (default plan.json)")
    t.add_argument(
        "--skip-dialogue-gate",
        action="store_true",
        help="legacy projects only: bypass the DIALOGUE.md pre-TTS gate (logged as SKIPPED)",
    )
    t.set_defaults(func=cmd_tts)

    dc = sub.add_parser("dialogue-check", help="DIALOGUE.md §4–§5 gate on lines.json (run before TTS)")
    dc.add_argument("--project", required=True)
    dc.add_argument("--lines")
    dc.add_argument("--target", type=float, default=None, help="seconds (default content/plan.json)")
    dc.add_argument("--rate", type=float, default=None, help="字/秒 estimate (default: pacing profile, standard 5.3)")
    dc.add_argument("--pacing", default=None, help="fast|standard|calm (default plan.json pacing / content_type)")
    dc.add_argument("--tolerance", type=float, default=0.15)
    dc.add_argument("--json", action="store_true")
    dc.set_defaults(func=cmd_dialogue_check)

    dl = sub.add_parser("dialogue-loop", help="self-loop: dialogue-check + LLM critic + reviser until PASS (gates TTS)")
    dl.add_argument("--project", required=True)
    dl.add_argument("--lines")
    dl.add_argument("--brief", help="default <project>/BRIEF.md")
    dl.add_argument("--max-rounds", type=int, default=4)
    dl.add_argument("--target", type=float, default=None)
    dl.add_argument("--effort", default="high", choices=["low", "high", "max"])
    dl.add_argument("--max-cny", type=float, default=2.0)
    dl.add_argument("--min-balance", type=float, default=5.0)
    dl.add_argument("--mock", help="tests only: canned critic/reviser replies (no network)")
    dl.add_argument("--item", help="ledger item label")
    dl.add_argument("--no-ledger", action="store_true")
    dl.add_argument("--allow-paid", action="store_true",
                    help="after all free models fail, use paid DeepSeek official (OFF by default)")
    dl.set_defaults(func=cmd_dialogue_loop)

    be = sub.add_parser("beats", help="visual sub-beats + {keyword} emphasis → beats_runtime.json (all styles)")
    be.add_argument("--project", required=True)
    be.add_argument("--pacing", default=None)
    be.add_argument("--dry-run", action="store_true")
    be.set_defaults(func=cmd_beats)

    pr = sub.add_parser("pacing-rework", help="pacing gate visual FAIL → re-render, max 2 rounds (WARN untouched)")
    pr.add_argument("--project", required=True)
    pr.add_argument("--media", required=True)
    pr.add_argument("--mix", default=None, help="default <project>/out/mix.wav")
    pr.add_argument("--pacing", default=None)
    pr.add_argument("--max-rounds", type=int, default=2)
    pr.add_argument("--dry-run", action="store_true")
    pr.set_defaults(func=cmd_pacing_rework)

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
    q.add_argument("--pacing-enforce", action="store_true",
                   help="pacing gate FAIL blocks delivery (P1); default report-only WARN under --delivery")
    q.add_argument("-o", "--output")
    q.set_defaults(func=cmd_quality)

    vc = sub.add_parser("visual-check", help="look at the rendered film: OCR/frames (+ free vision model), optional rework")
    vc.add_argument("--project", required=True)
    vc.add_argument("--media")
    vc.add_argument("--rework", action="store_true", help="auto-fix high issues (max 2 rounds), re-render only changed frames")
    vc.add_argument("--no-semantic", action="store_true", help="deterministic layer only (no network)")
    vc.add_argument("--model", action="append", help="OpenRouter vision model; must end in :free")
    vc.set_defaults(func=cmd_visual_check)

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
    m.add_argument("--bed-source", choices=("procedural", "stepaudio"), default="procedural",
                   help="stepaudio = StepFun stepaudio-3-music-preview instrumental (free preview; STEPFUN_API_KEY)")
    m.add_argument("--music-caption", default=None, help="style prompt for --bed-source stepaudio")
    m.add_argument(
        "--vo-only",
        action="store_true",
        help="legacy mix_vo_only (VO + silence, no bed)",
    )
    m.set_defaults(func=cmd_mix)

    ho = sub.add_parser(
        "handoff",
        help="OpenFilm / HyperFrames / Premiere-XML from finished mux + timeline",
    )
    ho.add_argument("--project", required=True, help="film project directory with muxed mp4")
    ho.add_argument(
        "--target",
        choices=("openfilm", "hyperframes", "premiere", "both", "all"),
        default="both",
        help="both=openfilm+hyperframes; all=+premiere; premiere=xmeml only",
    )
    ho.add_argument("--name", default=None)
    ho.add_argument("-o", "--out", default=None, help="override out dir (single-target only)")
    ho.add_argument("--extract-shots", action="store_true")
    ho.add_argument("--try-init-cli", action="store_true", help="hyperframes: try npx init --video")
    ho.add_argument("--lint", action="store_true", help="hyperframes: run lint after export")
    ho.add_argument(
        "--with-premiere",
        action="store_true",
        help="when --target both, also write premiere-handoff/",
    )
    ho.add_argument(
        "--no-budget",
        action="store_true",
        help="skip $0 ledger line for this handoff",
    )
    ho.add_argument("--json", action="store_true")
    ho.set_defaults(func=cmd_handoff)



    mx = sub.add_parser(
        "matrix",
        help="list 18-film comparison matrix status (docs/MATRIX-18.md)",
    )
    mx.add_argument(
        "--tracker",
        default=None,
        help="override fixtures/matrix-18.json",
    )
    mx.add_argument("--json", action="store_true", help="JSON summary or single cell")
    mx.add_argument("--path", choices=["controller", "flash"], default=None, help="only cells on this path")
    mx.add_argument("--filled", action="store_true", help="hide empty cells")
    mx.add_argument("--id", help="show one cell (e.g. M01)")
    mx.set_defaults(func=cmd_matrix)

    bg = sub.add_parser(
        "budget",
        help="append/summarize/import spend into fixtures/budget-ledger.jsonl",
    )
    bg_sub = bg.add_subparsers(dest="budget_cmd", required=True)

    def _budget_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--ledger",
            default=None,
            help="override fixtures/budget-ledger.jsonl",
        )
        sp.add_argument("--json", action="store_true")

    bgs = bg_sub.add_parser("summary", help="sum usd/tokens in the ledger")
    _budget_common(bgs)
    bgs.set_defaults(func=cmd_budget)

    bga = bg_sub.add_parser("append", help="append one honest ledger line")
    _budget_common(bga)
    bga.add_argument("--item", required=True)
    bga.add_argument("--usd", type=float, required=True)
    bga.add_argument("--kind", default="manual")
    bga.add_argument("--tokens-in", type=int, default=0)
    bga.add_argument("--tokens-out", type=int, default=0)
    bga.add_argument("--duration", type=float, default=None)
    bga.add_argument("--path-label", default=None, dest="path_label")
    bga.add_argument("--project", default=None)
    bga.add_argument("--model", default=None)
    bga.add_argument("--source", default="cli")
    bga.add_argument("--notes", default="")
    bga.add_argument("--cny", type=float, default=None, help="billed CNY (e.g. DeepSeek /user/balance delta)")
    bga.add_argument("--session-id", default=None, dest="session_id", help="OpenCode session id → meta.sessionId")
    bga.set_defaults(func=cmd_budget)

    bgi = bg_sub.add_parser(
        "import-opencode",
        help="seed from OpenCode session_v2 costs (optional one-shot)",
    )
    _budget_common(bgi)
    bgi.add_argument(
        "--db",
        default=None,
        help="default: /home/box/.local/share/opencode/opencode.db",
    )
    bgi.add_argument(
        "--filter",
        default=None,
        help="substring filter on title/directory/id",
    )
    bgi.add_argument(
        "--min-usd",
        type=float,
        default=0.0,
        help="only import sessions with cost >= this (default 0 = paid+free rows)",
    )
    bgi.add_argument("--dry-run", action="store_true")
    bgi.set_defaults(func=cmd_budget)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
