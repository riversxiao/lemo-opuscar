#!/usr/bin/env python3
"""Duplicate-visual gate for a film series (finance-v003).

Extracts one keyframe per shot (mid-point of the shot's scene part, end card excluded:
it is the shared brand template) into <film>/keyframes/<shot>.png, then compares
  · dHash (9×8 gray, 64 bit) Hamming distance
  · layout correlation (Pearson on 48×27 gray, mean-removed)
  · colour signature (mean RGB on a 4×4 grid, L1/255)
within the film and against every other film in the series index. A pair is a
near-duplicate when  ham ≤ HAM_MAX  and  corr ≥ CORR_MIN  (both: same layout *and* look),
or corr ≥ CORR_HARD. Any near-duplicate → FAIL. Writes <film>/evidence/visual-dupe.json.

Index: <films>/_visual-index/<series>.json  {films:{name:{mp4, shots:[{shot,t,file,dhash}]}}}
Usage: visual_dupe.py --project <film> [--series finance] [--others a,b,c] [--register]
<films> = --films, else $WORDFILM_FILMS, else the root that holds the series (the project's own parent
directory or common.films_root(): the first with the series index or a comparison film), else the project's
parent. No comparison film found → WARN (never a vacuous PASS); missing ones are listed in the report.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import os

from common import films_root

HAM_MAX = 10
CORR_MIN = 0.85
CORR_HARD = 0.95
DEFAULT_OTHERS = ["erm-v001", "var-plain-v003", "risk-appetite-v001", "var-template-v002"]


def shots_of(film: Path) -> list[dict]:
    rt = json.loads((film / "edl_runtime.json").read_text("utf-8"))
    out = []
    for s in rt["shots"]:
        d = float(s.get("vizDur") or s["dur"])
        if s.get("kind") == "finale" and not s.get("viz"):
            d = d * 0.5  # legacy finale: the grid part (end card = brand template, excluded)
        out.append({"shot": s["id"], "kind": s.get("kind"), "scene": (s.get("viz") or {}).get("scene"),
                    "t": round(float(s["t0"]) + d * 0.6, 3)})
    return out


def mp4_of(film: Path) -> Path | None:
    p = film / f"{film.name}.mp4"
    if p.is_file():
        return p
    c = sorted(film.glob("*.mp4"))
    return c[0] if c else None


def grab(mp4: Path, t: float, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", str(dst)],
                   check=True)


def feats(png: Path) -> dict:
    im = Image.open(png).convert("RGB")
    g = np.asarray(im.convert("L").resize((9, 8), Image.LANCZOS), dtype=np.float32)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    lay = np.asarray(im.convert("L").resize((48, 27), Image.LANCZOS), dtype=np.float32).flatten()
    lay = lay - lay.mean()
    n = np.linalg.norm(lay)
    col = np.asarray(im.resize((4, 4), Image.BOX), dtype=np.float32).flatten()
    return {"bits": bits, "lay": lay / n if n > 1e-6 else lay, "col": col}


def compare(a: dict, b: dict) -> dict:
    ham = int(np.count_nonzero(a["bits"] != b["bits"]))
    corr = float(np.dot(a["lay"], b["lay"]))
    col = float(np.mean(np.abs(a["col"] - b["col"])) / 255.0)
    dup = (ham <= HAM_MAX and corr >= CORR_MIN) or corr >= CORR_HARD
    return {"ham": ham, "corr": round(corr, 3), "colL1": round(col, 3), "dup": bool(dup)}


def keyframes(film: Path, out_dir: Path | None = None) -> list[dict]:
    mp4 = mp4_of(film)
    if not mp4:
        return []
    kdir = out_dir or film / "keyframes"
    rows = []
    for s in shots_of(film):
        dst = kdir / f"{s['shot']}.png"
        if not dst.is_file() or dst.stat().st_mtime < mp4.stat().st_mtime:
            grab(mp4, s["t"], dst)
        rows.append({**s, "file": str(dst)})
    return rows


def series_root(film: Path, series: str, others: list[str]) -> Path:
    """Films root for the series index and comparison films, tied to the project being checked."""
    env = os.environ.get("WORDFILM_FILMS", "").strip()
    if env:
        return Path(env).expanduser()
    for c in dict.fromkeys((film.parent, films_root())):
        if (c / "_visual-index" / f"{series}.json").is_file() or any(
                (c / o / "edl_runtime.json").is_file() for o in others if o != film.name):
            return c
    return film.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--series", default="finance")
    ap.add_argument("--others", default=",".join(DEFAULT_OTHERS))
    ap.add_argument("--register", action="store_true", help="add this film to the series index on PASS")
    ap.add_argument("--films", default=None, help="films root (default: see module docstring)")
    a = ap.parse_args(argv)
    film = Path(a.project).resolve()
    FILMS = (Path(a.films).expanduser().resolve() if a.films
             else series_root(film, a.series, [o for o in a.others.split(",") if o]))
    idx_p = FILMS / "_visual-index" / f"{a.series}.json"
    idx = json.loads(idx_p.read_text("utf-8")) if idx_p.is_file() else {"films": {}}
    mine = keyframes(film)
    if not mine:
        print("ERROR: no mp4 in project", file=sys.stderr)
        return 2
    F = {r["shot"]: feats(Path(r["file"])) for r in mine}
    pairs, dups = [], []
    for i, r in enumerate(mine):
        for q in mine[i + 1:]:
            c = compare(F[r["shot"]], F[q["shot"]])
            row = {"a": f"{film.name}:{r['shot']}", "b": f"{film.name}:{q['shot']}", **c}
            pairs.append(row)
            if c["dup"]:
                dups.append(row)
    others = [o for o in a.others.split(",") if o and o != film.name]
    others += [o for o in idx["films"] if o not in others and o != film.name]
    compared, missing = [], []
    for o in others:
        of = FILMS / o
        if not (of / "edl_runtime.json").is_file() or not mp4_of(of):
            missing.append(o)
            continue
        orows = keyframes(of, FILMS / "_visual-index" / "keyframes" / o)
        compared.append(o)
        for q in orows:
            fq = feats(Path(q["file"]))
            for r in mine:
                c = compare(F[r["shot"]], fq)
                row = {"a": f"{film.name}:{r['shot']}", "b": f"{o}:{q['shot']}", **c}
                pairs.append(row)
                if c["dup"]:
                    dups.append(row)
    worst = sorted(pairs, key=lambda p: (-p["corr"], p["ham"]))[:8]
    status = "FAIL" if dups else ("WARN" if others and not compared else "PASS")
    rep = {"status": status, "series": a.series, "filmsRoot": str(FILMS),
           "thresholds": {"hamMax": HAM_MAX, "corrMin": CORR_MIN, "corrHard": CORR_HARD},
           "keyframes": mine, "comparedFilms": compared, "missingFilms": missing, "pairs": len(pairs),
           "duplicates": dups, "closest": worst,
           "note": "end card excluded (shared brand template); keyframe = 60% into each shot's scene part"}
    (film / "evidence").mkdir(exist_ok=True)
    (film / "evidence" / "visual-dupe.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", "utf-8")
    if a.register and not dups:
        idx_p.parent.mkdir(parents=True, exist_ok=True)
        idx["films"][film.name] = {"mp4": str(mp4_of(film)), "shots": mine}
        idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(f"{rep['status']} visual-dupe: {len(mine)} keyframes vs {compared} · {len(dups)} near-duplicate(s)")
    if status == "WARN":
        print(f"  WARN no comparison film found under {FILMS} (missing: {', '.join(missing)}); "
              f"only the film's own shots were compared. Set --films or $WORDFILM_FILMS to the series root.")
    for d in dups[:12]:
        print(f"  DUP {d['a']} ~ {d['b']}  ham={d['ham']} corr={d['corr']}")
    for w in worst[:3]:
        print(f"  closest {w['a']} ~ {w['b']}  ham={w['ham']} corr={w['corr']}")
    return 1 if dups else 0


if __name__ == "__main__":
    raise SystemExit(main())
