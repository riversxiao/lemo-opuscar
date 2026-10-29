"""visual-check: look at the rendered film the way a viewer would, then (optionally) rework it.

Two layers, both free:

1. Deterministic (local: ffmpeg + OpenCV + RapidOCR, no network)
   - samples frames per shot (3 positions from timeline.parsed.json) + one per VO line + one per caption
   - whole-video luma scan (160x90): black runs, flat/blank runs, frozen runs, single-frame corrupt spikes,
     plus ffmpeg decode errors
   - OCR each sampled frame and compare with what the schedule says should be on screen:
     window.TEXTS(t) registry (texts_dump.mjs) + timeline caps/hook captions → missing / wrong characters
   - subtitle vs narration: the subtitle on screen during a VO line must be that line
   - safe area: OCR boxes touching the frame edge (clipped) / inside the 5% title-safe margin
   - text overlap (registry boxes that intersect), caption contrast (Otsu split inside the OCR box,
     WCAG luminance ratio), caption display time vs readable time
2. Semantic (vision model on per-shot contact sheets): topic vs VO line, overcrowding, obvious visual
   errors, garbled glyphs (tofu / Japanese fallback forms). FREE ONLY: OpenRouter model ids that end in
   ":free" with provider max_price 0, and the key's usage is read before/after — any non-zero delta
   stops the layer (status FAIL, no further calls). Never falls back to a paid model. If no free model
   answers, the layer is NOT_AVAILABLE and the report says so.

Severity: high = rework required (unreadable, wrong/missing chars, clipped, black/corrupt frames,
subtitle ≠ narration, image contradicts narration); medium = report only; low = ignored in status.

Rework (--rework): only for high issues, max 2 rounds. Fixes are content-layer only:
  subtitle_vo_mismatch/subtitle_missing in the hook → TL.hook.subs per VO line (+ project main.js hook
    reads it, only when content/engine.lock.json lists main.js as unlocked), cues/srt split
  caption_clipped / ocr_mismatch on a caption → caps[i].big shrink (size) ; readable_time → caps[i].t1 extend
  black/corrupt → re-render the affected frame range
Re-renders only the frame ranges that changed (render_range.mjs + keyframe-aligned lossless splice),
then mux and re-check. Unfixable → BEST_EFFORT with the reason.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.request
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
W, H = 1920, 1080
SAFE = 0.05

# ---------------------------------------------------------------- small helpers

def _j(p: Path, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = s.replace("|", "").replace("{", "").replace("}", "")
    return "".join(ch for ch in s if ch.isalnum())


def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return 0x3040 <= o <= 0x30FF or 0x3400 <= o <= 0x9FFF or 0xAC00 <= o <= 0xD7AF or 0xF900 <= o <= 0xFAFF


def recall(expected: str, got: str) -> float:
    e, g = Counter(norm(expected)), Counter(norm(got))
    n = sum(e.values())
    if not n:
        return 1.0
    return sum(min(c, g[ch]) for ch, c in e.items()) / n


def sim(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def need_read(text: str, cjk_cps=4.5, latin_cps=15.0, pad=1.5, mn=1.5) -> float:
    cjk = sum(1 for ch in str(text) if not ch.isspace() and is_cjk(ch))
    other = sum(1 for ch in str(text) if not ch.isspace() and not is_cjk(ch) and ch not in "|{}")
    return max(mn, cjk / cjk_cps + other / latin_cps + pad)


def issue(sev: str, kind: str, t: float | None, detail: str, **kw) -> dict:
    d = {"severity": sev, "kind": kind, "t": None if t is None else round(float(t), 3), "detail": detail}
    d.update(kw)
    return d


# ---------------------------------------------------------------- schedule model

class Schedule:
    """Everything the film *should* show, from project files only."""

    def __init__(self, project: Path, texts: dict | None):
        self.p = project
        self.tl = _j(project / "timeline.json", {}) or {}
        parsed = _j(project / "timeline.parsed.json", {}) or {}
        self.shots = [s for s in parsed.get("shots", []) if "t0" in s and "t1" in s]
        self.dur = float(self.tl.get("dur") or parsed.get("scheduledDurationSec") or (self.shots[-1]["t1"] if self.shots else 0))
        self.content_end = float(parsed.get("contentDurationSec") or self.dur)
        rows = _j(project / "audio" / "lines.json") or _j(project / "content" / "lines.json") or []
        rows = rows if isinstance(rows, list) else rows.get("lines", [])
        self.lines = {str(r.get("id")): r for r in rows if r.get("id")}
        vo = self.tl.get("vo") or {}
        self.vo = []  # (id, t0, t1, text)
        for lid, t0 in sorted(vo.items(), key=lambda kv: float(kv[1])):
            d = self._wav_dur(project / "audio" / "vo" / f"{lid}.wav")
            txt = (self.lines.get(lid) or {}).get("text", "")
            self.vo.append((lid, float(t0), float(t0) + (d or 2.0), txt))
        self.caps = [c for c in (self.tl.get("caps") or []) if "t0" in c and "t1" in c]
        self.hook = self.tl.get("hook") if isinstance(self.tl.get("hook"), dict) else None
        self.texts = texts or {"frames": []}
        self._tf = [(float(f["t"]), f["texts"]) for f in self.texts.get("frames", [])]
        self.uses_subs = sum(1 for c in self.caps if c.get("en")) >= max(1, len(self.caps) // 2)

    @staticmethod
    def _wav_dur(p: Path) -> float | None:
        try:
            import wave
            with wave.open(str(p)) as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            return None

    def registry(self, t: float) -> list[dict]:
        if not self._tf:
            return []
        i = min(range(len(self._tf)), key=lambda k: abs(self._tf[k][0] - t))
        return self._tf[i][1]

    def stable_registry(self, t: float, before=0.5, after=0.3) -> list[dict]:
        """Registry entries present (same id + text) from t-before to t+after: settled, not mid-animation."""
        cur = self.registry(t)
        keep = []
        for b in cur:
            ok = True
            for dt in (-before, -before / 2, after):
                tt = t + dt
                if tt < 0 or tt > self.dur:
                    continue
                if not any(x["id"] == b["id"] and x["text"] == b["text"] for x in self.registry(tt)):
                    ok = False
                    break
            if ok:
                keep.append(b)
        return keep

    def caps_at(self, t: float, settle=0.5) -> list[dict]:
        return [c for c in self.caps if c["t0"] + settle <= t < c["t1"] - 0.05]

    def shot_at(self, t: float) -> dict | None:
        for s in self.shots:
            if s["t0"] <= t < s["t1"]:
                return s
        return self.shots[-1] if self.shots else None

    def vo_at(self, t: float):
        for v in self.vo:
            if v[1] <= t < v[2]:
                return v
        return None

    def hook_subs(self) -> list[dict]:
        return list((self.hook or {}).get("subs") or [])

    def subtitles_at(self, t: float) -> list[tuple[str, str]]:
        """(source, text) of subtitle sentences the schedule puts on screen at t."""
        out = [("cap:" + str(c.get("id", "")), c["en"]) for c in self.caps if c.get("en") and c["t0"] + 0.3 <= t < c["t1"]]
        for b in self.registry(t):
            if b["id"].endswith("-say") or b["id"] in ("hook-say", "sub", "subtitle"):
                out.append(("tx:" + b["id"], b["text"]))
        return out

    def sample_times(self) -> list[tuple[float, str]]:
        ts: list[tuple[float, str]] = []
        for s in self.shots:
            a, b = float(s["t0"]), float(s["t1"])
            for f in (0.3, 0.6, 0.9):
                ts.append((round(min(b - 0.2, a + (b - a) * f), 2), f"shot:{s['id']}"))
        for lid, a, b, _ in self.vo:
            ts.append((round(a + min(0.6 * (b - a), max(0.2, b - a - 0.3)), 2), f"vo:{lid}"))
        for c in self.caps:
            ts.append((round(min(c["t1"] - 0.15, c["t0"] + max(0.6, 0.5 * (c["t1"] - c["t0"]))), 2), f"cap:{c.get('id', '')}"))
        ts = [(min(max(0.0, t), self.dur - 0.05), why) for t, why in ts]
        ts.sort()
        merged: list[tuple[float, str]] = []
        for t, why in ts:
            if merged and abs(merged[-1][0] - t) < 0.15:
                merged[-1] = (merged[-1][0], merged[-1][1] + "," + why)
            else:
                merged.append((t, why))
        return merged


# ---------------------------------------------------------------- media

def ffprobe_size(media: Path) -> tuple[int, int, float, float]:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate:format=duration", "-of", "json", str(media)],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    st = d["streams"][0]
    n, m = st["r_frame_rate"].split("/")
    return int(st["width"]), int(st["height"]), float(n) / float(m), float(d["format"]["duration"])


def grab_frames(media: Path, times: list[float], out_dir: Path) -> dict[float, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    from concurrent.futures import ThreadPoolExecutor
    res: dict[float, Path] = {}

    def one(t):
        p = out_dir / f"f_{t:07.2f}.jpg"
        if not p.exists():
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", str(media), "-frames:v", "1",
                            "-q:v", "2", str(p)], check=True)
        return t, p

    with ThreadPoolExecutor(6) as ex:
        for t, p in ex.map(one, times):
            res[t] = p
    return res


def luma_scan(media: Path, fps: float) -> dict:
    import numpy as np
    w, h = 160, 90
    proc = subprocess.run(["ffmpeg", "-v", "error", "-i", str(media), "-vf", f"scale={w}:{h},format=gray",
                           "-f", "rawvideo", "-"], capture_output=True)
    buf = np.frombuffer(proc.stdout, dtype=np.uint8)
    n = buf.size // (w * h)
    fr = buf[: n * w * h].reshape(n, h, w).astype(np.float32)
    errs = subprocess.run(["ffmpeg", "-v", "error", "-i", str(media), "-f", "null", "-"],
                          capture_output=True, text=True).stderr.strip()
    return {"frames": fr, "fps": fps, "decodeErrors": errs[:500]}


def video_issues(scan: dict, sch: Schedule) -> list[dict]:
    import numpy as np
    fr, fps = scan["frames"], scan["fps"]
    out: list[dict] = []
    if scan["decodeErrors"]:
        out.append(issue("high", "decode_error", None, "ffmpeg reported decode errors: " + scan["decodeErrors"][:200]))
    if len(fr) < 3:
        out.append(issue("high", "no_frames", None, "video has fewer than 3 decodable frames"))
        return out
    mean = fr.mean(axis=(1, 2))
    std = fr.std(axis=(1, 2))
    cuts = [float(s["t0"]) for s in sch.shots]

    def runs(mask):
        i = 0
        while i < len(mask):
            if mask[i]:
                j = i
                while j + 1 < len(mask) and mask[j + 1]:
                    j += 1
                yield i, j
                i = j + 1
            else:
                i += 1

    black = (mean < 12) & (std < 5)
    for a, b in runs(black):
        d = (b - a + 1) / fps
        t = a / fps
        near_cut = any(abs(t - c) < 0.25 for c in cuts) or t < 0.25 or t > sch.dur - 0.6
        if d >= 0.5 and not (t > sch.content_end - 0.1):
            out.append(issue("high", "black_frames", t, f"black for {d:.2f}s ({a}–{b} frames)", dur=round(d, 3)))
        elif not near_cut:
            out.append(issue("medium", "black_flash", t, f"black flash {d:.2f}s outside a cut", dur=round(d, 3)))
    flat = (std < 3) & ~black
    for a, b in runs(flat):
        d = (b - a + 1) / fps
        if d >= 0.5:
            out.append(issue("high", "blank_frames", a / fps, f"near-uniform frame (std<3) for {d:.2f}s", dur=round(d, 3)))
    diff = np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))  # diff[i] = |f[i+1]-f[i]|
    # frozen = duplicated frames (a stalled render/encode), not a calm hold: ambient motion keeps diff > 0.02
    for a, b in runs(diff < 0.02):
        d = (b - a + 2) / fps
        t = a / fps
        if d < 4.0:
            continue
        sev = "low" if t >= sch.content_end - 0.5 else "medium"
        out.append(issue(sev, "frozen", t, f"identical frames for {d:.2f}s", dur=round(d, 3)))
    for a, b in runs(diff < 0.15):
        d = (b - a + 2) / fps
        if d >= 8.0:
            out.append(issue("low", "static_hold", a / fps, f"almost no motion for {d:.2f}s", dur=round(d, 3)))
    for i in range(1, len(fr) - 1):
        d1, d2 = diff[i - 1], diff[i]
        if d1 > 25 and d2 > 25:
            skip = float(np.abs(fr[i + 1] - fr[i - 1]).mean())
            if skip < 0.35 * min(d1, d2):
                out.append(issue("high", "corrupt_frame", i / fps, f"single-frame spike Δ={d1:.0f}/{d2:.0f} vs skip Δ={skip:.0f}", frameIndex=i))
    return out


# ---------------------------------------------------------------- OCR

class OCR:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.eng = RapidOCR()
        self.cache: dict[str, list] = {}

    def __call__(self, img_path: Path) -> list[dict]:
        k = str(img_path)
        if k in self.cache:
            return self.cache[k]
        res, _ = self.eng(str(img_path))
        boxes = []
        for box, text, score in res or []:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            boxes.append({"text": text, "score": float(score), "x0": min(xs), "y0": min(ys), "x1": max(xs), "y1": max(ys)})
        self.cache[k] = boxes
        return boxes


def boxes_text(boxes: list[dict]) -> str:
    return "".join(b["text"] for b in sorted(boxes, key=lambda b: (round(b["y0"] / 30), b["x0"])))


def match_boxes(expected: str, boxes: list[dict]) -> list[dict]:
    """OCR boxes that are (mostly) part of the expected string."""
    e = Counter(norm(expected))
    out = []
    for b in boxes:
        t = norm(b["text"])
        if not t:
            continue
        hit = sum(1 for ch in t if e[ch] > 0) / len(t)
        if hit >= 0.6 and (len(t) >= 2 or len(norm(expected)) <= 2):
            out.append(b)
    return out


def caption_boxes(expected: str, boxes: list[dict], reg_boxes: list[dict]) -> list[dict]:
    """OCR boxes that belong to a caption (not to registry text that happens to share characters)."""
    out = []
    for b in match_boxes(expected, boxes):
        owner = [r for r in reg_boxes if inside(b, r, pad=8)]
        if owner and max(recall(b["text"], r["text"]) for r in owner) >= recall(b["text"], expected):
            continue
        if any(recall(b["text"], r["text"]) > recall(b["text"], expected) + 0.1 for r in reg_boxes):
            continue
        out.append(b)
    return out


def _find(e: dict, boxes: list[dict], reg_boxes: list[dict]) -> tuple[float, list[dict], str]:
    """Best OCR evidence for expected text e: inside its registry box first, else anywhere in the frame."""
    if e["box"]:
        pool = [b for b in boxes if inside(b, e["box"])]
        r = recall(e["text"], boxes_text(pool))
        if r >= 0.9:
            return r, pool, "box"
        any_pool = match_boxes(e["text"], boxes)
        r2 = recall(e["text"], boxes_text(any_pool))
        return (r2, any_pool, "elsewhere") if r2 > r else (r, pool, "box")
    pool = caption_boxes(e["text"], boxes, reg_boxes)
    return recall(e["text"], boxes_text(pool)), pool, "caption"


def inside(b: dict, r: dict, pad=24) -> bool:
    cx, cy = (b["x0"] + b["x1"]) / 2, (b["y0"] + b["y1"]) / 2
    return r["x0"] - pad <= cx <= r["x1"] + pad and r["y0"] - pad <= cy <= r["y1"] + pad


def contrast_ratio(img, box: dict) -> float | None:
    import numpy as np
    import cv2
    x0, y0, x1, y1 = (int(max(0, box["x0"])), int(max(0, box["y0"])), int(min(img.shape[1], box["x1"])), int(min(img.shape[0], box["y1"])))
    if x1 - x0 < 6 or y1 - y0 < 6:
        return None
    crop = img[y0:y1, x0:x1].astype(np.float32) / 255.0
    lin = np.where(crop <= 0.04045, crop / 12.92, ((crop + 0.055) / 1.055) ** 2.4)
    lum = 0.2126 * lin[..., 2] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 0]  # BGR
    g = np.clip(lum * 255, 0, 255).astype(np.uint8)
    thr, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    hi, lo = lum[g > thr], lum[g <= thr]
    if hi.size < 10 or lo.size < 10:
        return None
    a, b = float(np.median(hi)), float(np.median(lo))
    return (a + 0.05) / (b + 0.05)


# ---------------------------------------------------------------- deterministic layer

def text_issues(sch: Schedule, frames: dict[float, Path], whys: dict[float, str], ocr: OCR, media: Path, fdir: Path) -> tuple[list[dict], list[dict]]:
    import cv2
    out: list[dict] = []
    samples: list[dict] = []
    seen_clip: set = set()
    for t in sorted(frames):
        path = frames[t]
        boxes = ocr(path)
        img = cv2.imread(str(path))
        fh, fw = img.shape[:2]
        sx, sy = fw / W, fh / H
        expected: list[dict] = []
        reg_boxes = [{"text": b["text"], **{k: b[k] * (sx if k[0] == "x" else sy) for k in ("x0", "y0", "x1", "y1")}} for b in sch.registry(t)]
        for b in sch.stable_registry(t):
            if norm(b["text"]):
                expected.append({"src": "tx:" + b["id"], "text": b["text"],
                                 "box": {k: b[k] * (sx if k[0] == "x" else sy) for k in ("x0", "y0", "x1", "y1")}})
        for c in sch.caps_at(t):
            if norm(c.get("zh", "")):
                expected.append({"src": f"cap:{c.get('id', '')}:zh", "text": c["zh"], "box": None, "cap": c})
            if norm(c.get("en", "")):
                expected.append({"src": f"cap:{c.get('id', '')}:sub", "text": c["en"], "box": None, "cap": c})
        rec = {"t": t, "why": whys.get(t, ""), "frame": str(path), "ocr": boxes_text(boxes), "checks": []}
        for e in expected:
            if len(norm(e["text"])) < 2:  # a lone glyph/number (e.g. a 380px "0") is not OCR-verifiable
                continue
            r, pool, where = _find(e, boxes, reg_boxes)
            if r < 0.9:  # retry once a bit later (animation / OCR noise): best of 2 frames
                t2 = round(min(sch.dur - 0.05, t + 0.4), 2)
                p2 = grab_frames(media, [t2], fdir)[t2]
                r2, pool2, where2 = _find(e, ocr(p2), reg_boxes)
                if r2 > r:
                    r, pool, where = r2, pool2, where2
            if where == "elsewhere" and r >= 0.75:
                out.append(issue("low", "registry_bbox_off", t, f"{e['src']} {e['text']!r} found outside its TEXTS box (registry geometry is approximate)", src=e["src"]))
            small_latin = e["box"] is not None and (e["box"]["y1"] - e["box"]["y0"]) < 46 * sy and not any(is_cjk(c) for c in e["text"])
            rec["checks"].append({"src": e["src"], "expected": e["text"], "got": boxes_text(pool), "recall": round(r, 3)})
            if r < 0.75:
                sev = "medium" if small_latin else "high"
                out.append(issue(sev, "ocr_mismatch", t, f"{e['src']} expected {e['text']!r}, OCR read {boxes_text(pool)!r} (char recall {r:.2f})",
                                 src=e["src"], expected=e["text"], got=boxes_text(pool), recall=round(r, 3), frame=str(path), shot=(sch.shot_at(t) or {}).get("id")))
            elif r < 0.9:
                out.append(issue("medium", "ocr_partial", t, f"{e['src']} char recall {r:.2f}: expected {e['text']!r}, OCR {boxes_text(pool)!r}",
                                 src=e["src"], recall=round(r, 3), frame=str(path)))
            # contrast on the matched boxes
            for b in pool[:3]:
                cr = contrast_ratio(img, b)
                if cr is None:
                    continue
                if cr < 2.0:
                    out.append(issue("high", "low_contrast", t, f"{e['src']} {b['text']!r} contrast {cr:.2f}:1 (<2.0)", src=e["src"], ratio=round(cr, 2), frame=str(path)))
                elif cr < 3.0:
                    out.append(issue("medium", "low_contrast", t, f"{e['src']} {b['text']!r} contrast {cr:.2f}:1 (<3.0)", src=e["src"], ratio=round(cr, 2), frame=str(path)))
        # clipping / safe area on what OCR actually sees
        for b in boxes:
            if len(norm(b["text"])) < 2 or b["score"] < 0.5:
                continue
            edge = b["x0"] <= 2 or b["y0"] <= 2 or b["x1"] >= fw - 3 or b["y1"] >= fh - 3
            unsafe = b["x0"] < SAFE * fw or b["y0"] < SAFE * fh or b["x1"] > (1 - SAFE) * fw or b["y1"] > (1 - SAFE) * fh
            key = (norm(b["text"]), edge)
            if edge and key not in seen_clip:
                seen_clip.add(key)
                out.append(issue("high", "text_clipped", t, f"OCR text {b['text']!r} touches the frame edge ({b['x0']:.0f},{b['y0']:.0f})–({b['x1']:.0f},{b['y1']:.0f})", frame=str(path), box=[round(b[k]) for k in ("x0", "y0", "x1", "y1")]))
            elif unsafe and key not in seen_clip:
                seen_clip.add(key)
                out.append(issue("medium", "outside_title_safe", t, f"OCR text {b['text']!r} inside the 5% margin", frame=str(path), box=[round(b[k]) for k in ("x0", "y0", "x1", "y1")]))
        # registry boxes partly outside the frame = clipped text
        for b in sch.registry(t):
            if b["x0"] < -1 or b["y0"] < -1 or b["x1"] > W + 1 or b["y1"] > H + 1:
                key = ("tx", b["id"])
                if key not in seen_clip:
                    seen_clip.add(key)
                    out.append(issue("high", "text_clipped", t, f"registry box {b['id']} {b['text']!r} extends outside the frame", frame=str(path)))
        # overlap between registered text boxes
        reg = sch.stable_registry(t)
        for i in range(len(reg)):
            for j in range(i + 1, len(reg)):
                a, c = reg[i], reg[j]
                ix = max(0, min(a["x1"], c["x1"]) - max(a["x0"], c["x0"]))
                iy = max(0, min(a["y1"], c["y1"]) - max(a["y0"], c["y0"]))
                amin = min((a["x1"] - a["x0"]) * (a["y1"] - a["y0"]), (c["x1"] - c["x0"]) * (c["y1"] - c["y0"])) or 1
                if ix * iy / amin > 0.2:
                    out.append(issue("medium", "text_overlap", t, f"{a['id']} and {c['id']} boxes overlap {ix * iy / amin:.0%}", frame=str(path)))
        # caption band vs registry text: OCR'd caption boxes intersecting a registered box
        for e in expected:
            if e["box"] is not None:
                continue
            for b in caption_boxes(e["text"], boxes, reg_boxes):
                for r in reg:
                    rb = {k: r[k] * (sx if k[0] == "x" else sy) for k in ("x0", "y0", "x1", "y1")}
                    ix = max(0, min(b["x1"], rb["x1"]) - max(b["x0"], rb["x0"]))
                    iy = max(0, min(b["y1"], rb["y1"]) - max(b["y0"], rb["y0"]))
                    if ix * iy > 0.3 * (b["x1"] - b["x0"]) * (b["y1"] - b["y0"]):
                        out.append(issue("medium", "caption_overlap", t, f"{e['src']} overlaps {r['id']}", frame=str(path)))
        samples.append(rec)
    out.extend(subtitle_issues(sch, frames, ocr))
    out.extend(readtime_issues(sch))
    return _dedupe(out), samples


def subtitle_issues(sch: Schedule, frames: dict[float, Path], ocr: OCR) -> list[dict]:
    """During every VO line the subtitle actually on screen (OCR) must be that line."""
    out = []
    if not sch.uses_subs:
        return out
    for lid, a, b, text in sch.vo:
        if not norm(text):
            continue
        t = round(a + min(0.6 * (b - a), max(0.2, b - a - 0.3)), 2)
        t = min(frames, key=lambda x: abs(x - t)) if frames else t
        boxes = ocr(frames[t]) if t in frames else []
        seen = max((sim(x["text"], text) for x in boxes), default=0.0)
        if seen >= 0.6:
            continue
        subs = sch.subtitles_at(t)
        on_screen = max(boxes, key=lambda x: max((sim(x["text"], s) for _, s in subs), default=0.0))["text"] if boxes and subs else ""
        shown = max(subs, key=lambda s: sim(s[1], text)) if subs else None
        base = dict(line=lid, said=text, frame=str(frames.get(t, "")), shot=(sch.shot_at(t) or {}).get("id"), ocrBestSim=round(seen, 3))
        if shown and sim(shown[1], text) < 0.6:
            out.append(issue("high", "subtitle_vo_mismatch", t,
                             f"{lid} is being spoken ({a:.2f}–{b:.2f}s) {text!r} but the subtitle shows {on_screen or shown[1]!r} ({shown[0]})",
                             shown=shown[1], source=shown[0], **base))
        elif not subs:
            out.append(issue("high", "subtitle_missing", t, f"{lid} is being spoken ({a:.2f}–{b:.2f}s) but no subtitle is on screen", **base))
        else:
            out.append(issue("high", "subtitle_not_rendered", t,
                             f"{lid}: schedule has the right subtitle but OCR does not see it on screen (best {seen:.2f})", **base))
    return out


def readtime_issues(sch: Schedule) -> list[dict]:
    out = []
    for i, c in enumerate(sch.caps):
        shown = float(c["t1"]) - float(c["t0"])
        n = need_read(c.get("zh", ""))
        if shown < 0.75 * n:
            out.append(issue("high", "caption_readtime", c["t0"], f"caption {c.get('id')} {c.get('zh')!r} on {shown:.2f}s < 0.75×need {n:.2f}s", cap=i))
        elif shown < n:
            out.append(issue("medium", "caption_readtime", c["t0"], f"caption {c.get('id')} {c.get('zh')!r} on {shown:.2f}s < need {n:.2f}s", cap=i))
        if c.get("en"):
            ns = max(1.0, len(norm(c["en"])) / 9.0)
            if shown < 0.75 * ns:
                out.append(issue("high", "subtitle_readtime", c["t0"], f"subtitle {c.get('id')} {len(norm(c['en']))} chars on {shown:.2f}s (< 0.75×{ns:.2f}s at 9 chars/s)", cap=i))
    return out


def _dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for it in items:
        k = (it["kind"], it.get("src"), it.get("line"), it.get("expected"), it["detail"][:60] if it["kind"] in ("text_overlap", "caption_overlap", "low_contrast") else it.get("t"))
        if it["kind"] in ("text_overlap", "caption_overlap", "low_contrast", "ocr_partial"):
            k = (it["kind"], it.get("src"), it["detail"][:40])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


# ---------------------------------------------------------------- contact sheets + evidence shots

def contact_sheets(sch: Schedule, frames: dict[float, Path], out_dir: Path) -> dict[str, str]:
    from PIL import Image, ImageDraw
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {}
    for s in sch.shots:
        ts = [t for t in sorted(frames) if s["t0"] <= t < s["t1"]]
        if not ts:
            continue
        if len(ts) > 6:
            idx = [round(i * (len(ts) - 1) / 5) for i in range(6)]
            ts = [ts[i] for i in idx]
        tw, th = 640, 360
        cols = 3
        rows = (len(ts) + cols - 1) // cols
        sheet = Image.new("RGB", (tw * cols, th * rows), (0, 0, 0))
        d = ImageDraw.Draw(sheet)
        for k, t in enumerate(ts):
            im = Image.open(frames[t]).convert("RGB").resize((tw, th))
            x, y = (k % cols) * tw, (k // cols) * th
            sheet.paste(im, (x, y))
            d.rectangle([x, y, x + 92, y + 22], fill=(0, 0, 0))
            d.text((x + 4, y + 4), f"{t:.2f}s", fill=(255, 255, 0))
        p = out_dir / f"{s['id']}.jpg"
        sheet.save(p, quality=85)
        res[s["id"]] = str(p)
    return res


def mark_evidence(issues: list[dict], out_dir: Path) -> None:
    from PIL import Image, ImageDraw
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for it in issues:
        if it["severity"] != "high" or not it.get("frame") or not Path(it["frame"]).exists():
            continue
        n += 1
        im = Image.open(it["frame"]).convert("RGB")
        d = ImageDraw.Draw(im)
        if it.get("box"):
            d.rectangle(it["box"], outline=(255, 0, 0), width=6)
        d.rectangle([0, 0, im.width, 40], fill=(160, 0, 0))
        d.text((10, 12), f"HIGH {it['kind']} @ {it.get('t')}s", fill=(255, 255, 255))
        p = out_dir / f"high_{n:02d}_{it['kind']}_{(it.get('t') or 0):06.2f}.jpg"
        im.save(p, quality=85)
        it["screenshot"] = str(p)


# ---------------------------------------------------------------- semantic layer (free only)

FREE_DEFAULT = ["dots-studio/dots-3-note-preview:free", "google/gemma-4-31b-it:free", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"]


def _or_get(path: str, key: str, timeout=30) -> dict:
    req = urllib.request.Request("https://openrouter.ai/api/v1" + path, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _or_usage(key: str) -> float:
    return float(_or_get("/key", key)["data"].get("usage") or 0.0)


def _or_chat(key: str, model: str, prompt: str, img_b64: str, timeout=180) -> tuple[str, dict]:
    assert model.endswith(":free"), "refusing a non-:free model"
    body = {"model": model, "temperature": 0, "max_tokens": 4000, "reasoning": {"effort": "low", "exclude": True},
            "provider": {"max_price": {"prompt": 0, "completion": 0, "image": 0, "request": 0}, "allow_fallbacks": False},
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt},
                                                      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img_b64}}]}]}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    if d.get("error"):
        raise RuntimeError(str(d["error"])[:200])
    return d["choices"][0]["message"]["content"] or "", d.get("usage") or {}


SEM_PROMPT = """你是短视频质检员。图中是同一个镜头按时间顺序截取的几帧（左上角是时间）。
这个镜头的旁白（配音原文）：
{vo}
这个镜头计划出现的字幕/大字：
{caps}
只根据你在图里真正看到的内容判断，不要猜测。输出严格 JSON（不要 markdown）：
{{"topic_match": true/false,            // 画面主题是否与旁白一致（图表/文字讲的是同一件事）
 "contradiction": null 或 "一句话",     // 画面内容明确与旁白矛盾（如数字、国家、年份相反）才写
 "overcrowded": true/false,             // 文字/元素过多以致难以阅读
 "visual_errors": ["…"],                // 明显的画面错误（元素错位、遮挡、残缺），没有就 []
 "garbled_glyphs": null 或 "一句话",    // 方框豆腐块□、乱码、日文字形替代中文字形等
 "confidence": 0.0-1.0}}"""


def semantic_layer(sch: Schedule, sheets: dict[str, str], models: list[str], enabled: bool) -> dict:
    res: dict[str, Any] = {"status": "NOT_RUN", "model": None, "billing": None, "shots": {}, "issues": [], "notes": []}
    if not enabled:
        res["status"] = "SKIPPED"
        res["notes"].append("--no-semantic")
        return res
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        res["status"] = "NOT_AVAILABLE"
        res["notes"].append("no local vision model installed (CPU-only box) and OPENROUTER_API_KEY not set")
        return res
    models = [m for m in models if m.endswith(":free")]
    if not models:
        res["status"] = "NOT_AVAILABLE"
        res["notes"].append("no :free model configured — paid models are never used")
        return res
    try:
        before = _or_usage(key)
    except Exception as e:  # cannot verify billing → do not call
        res["status"] = "NOT_AVAILABLE"
        res["notes"].append(f"cannot read OpenRouter key usage to verify $0 billing: {type(e).__name__}")
        return res
    from PIL import Image
    chosen = None
    for sid, sp in sheets.items():
        s = next((x for x in sch.shots if x["id"] == sid), {})
        vo = "\n".join(f"{v[0]}: {v[3]}" for v in sch.vo if v[0] in (s.get("voIds") or []))
        caps = [c.get("zh", "").replace("|", " ").replace("{", "").replace("}", "") + " / " + c.get("en", "")
                for c in sch.caps if s.get("t0", 0) <= c["t0"] < s.get("t1", 0)]
        if s.get("role") == "hook" and sch.hook:
            caps.insert(0, f"{sch.hook.get('zh', '')} / {sch.hook.get('en', '')}")
        im = Image.open(sp).convert("RGB")
        im.thumbnail((1536, 1536))
        bio = io.BytesIO()
        im.save(bio, "JPEG", quality=80)
        b64 = base64.b64encode(bio.getvalue()).decode()
        prompt = SEM_PROMPT.format(vo=vo or "(无)", caps="\n".join(caps) or "(无)")
        small = io.BytesIO()
        im2 = im.copy()
        im2.thumbnail((1024, 1024))
        im2.save(small, "JPEG", quality=75)
        b64s = base64.b64encode(small.getvalue()).decode()
        ans, err = None, None
        order = ([chosen] if chosen else []) + [m for m in models if m != chosen]
        for m, img in [(m, x) for m in order for x in (b64, b64s)]:
            for attempt in range(3):
                try:
                    txt, usage = _or_chat(key, m, prompt, img)
                    mm = re.search(r"\{.*\}", re.sub(r"//[^\n]*", "", txt), re.S)
                    ans = json.loads(mm.group(0)) if mm else None
                    if ans is not None:
                        chosen = chosen or m
                        res["shots"][sid] = {"model": m, "answer": ans, "usage": usage, "imageMax": 1536 if img is b64 else 1024}
                        break
                    err = "unparseable answer"
                except Exception as e:
                    body = ""
                    try:
                        body = e.read().decode()[:160]  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    err = f"{m}: {type(e).__name__}: {str(e)[:80]} {body}"
                    if "429" in err:
                        time.sleep(8 * (attempt + 1))
                        continue
                    break
            if ans is not None:
                break
        if ans is None:
            res["shots"][sid] = {"error": err}
            continue
        conf = float(ans.get("confidence") or 0)
        if ans.get("contradiction") and conf >= 0.7:
            res["issues"].append(issue("high", "semantic_contradiction", s.get("t0"), f"{sid}: {ans['contradiction']}", shot=sid, sheet=sp, frame=sp))
        elif ans.get("contradiction"):
            res["issues"].append(issue("medium", "semantic_contradiction", s.get("t0"), f"{sid} (conf {conf:.2f}): {ans['contradiction']}", shot=sid, sheet=sp))
        if ans.get("garbled_glyphs"):
            res["issues"].append(issue("high" if conf >= 0.7 else "medium", "garbled_glyphs", s.get("t0"), f"{sid}: {ans['garbled_glyphs']}", shot=sid, sheet=sp, frame=sp))
        if ans.get("topic_match") is False:
            res["issues"].append(issue("medium", "topic_mismatch", s.get("t0"), f"{sid}: model says the picture is off-topic for the VO", shot=sid, sheet=sp))
        if ans.get("overcrowded"):
            res["issues"].append(issue("medium", "overcrowded", s.get("t0"), f"{sid}: overcrowded", shot=sid, sheet=sp))
        for v in ans.get("visual_errors") or []:
            res["issues"].append(issue("medium", "visual_error", s.get("t0"), f"{sid}: {v}", shot=sid, sheet=sp))
        try:
            now = _or_usage(key)
        except Exception:
            now = None
        if now is None or now - before > 1e-9:
            res["status"] = "FAIL"
            res["billing"] = {"usageBefore": before, "usageAfter": now, "deltaUsd": None if now is None else round(now - before, 6)}
            res["notes"].append("stopped: could not verify $0 after a call" if now is None else "stopped: OpenRouter usage increased")
            return res
    after = _or_usage(key)
    res["billing"] = {"usageBefore": before, "usageAfter": after, "deltaUsd": round(after - before, 9), "verified": abs(after - before) < 1e-9}
    res["model"] = chosen
    res["models"] = sorted({v["model"] for v in res["shots"].values() if "model" in v})
    answered = sum(1 for v in res["shots"].values() if "answer" in v)
    res["status"] = "PASS" if answered == len(sheets) and answered else ("PARTIAL" if answered else "NOT_AVAILABLE")
    if not answered:
        res["notes"].append("no free vision model answered: " + "; ".join(str(v.get("error")) for v in res["shots"].values())[:300])
    return res


# ---------------------------------------------------------------- run one check

def dump_texts(project: Path) -> dict | None:
    try:
        r = subprocess.run(["node", str(HERE / "texts_dump.mjs"), str(project), "--step", "0.1"], capture_output=True, text=True, timeout=300, cwd=str(REPO))
        if r.returncode != 0:
            return None
        return json.loads(r.stdout)
    except Exception:
        return None


def find_media(project: Path) -> Path | None:
    q = _j(project / "quality.json", {}) or {}
    m = q.get("media")
    if m and Path(m).exists():
        return Path(m)
    cands = sorted(project.glob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def run_check(project: Path, media: Path, *, semantic=True, models=None, tag="", texts=None, ocr=None) -> dict:
    project = project.resolve()
    ev = project / "evidence" / ("visual-check" + (f"-{tag}" if tag else ""))
    if ev.exists():
        shutil.rmtree(ev)
    fdir = ev / "frames"
    texts = texts if texts is not None else dump_texts(project)
    sch = Schedule(project, texts)
    vw, vh, fps, vdur = ffprobe_size(media)
    samples = sch.sample_times()
    whys = {t: w for t, w in samples}
    frames = grab_frames(media, [t for t, _ in samples], fdir)
    ocr = ocr or OCR()
    issues = video_issues(luma_scan(media, fps), sch)
    tissues, srec = text_issues(sch, frames, whys, ocr, media, fdir)
    issues += tissues
    sheets = contact_sheets(sch, {t: p for t, p in frames.items()}, ev / "sheets")
    sem = semantic_layer(sch, sheets, models or FREE_DEFAULT, semantic)
    issues += sem["issues"]
    mark_evidence(issues, ev / "issues")
    high = [i for i in issues if i["severity"] == "high"]
    med = [i for i in issues if i["severity"] == "medium"]
    rep = {
        "media": str(media), "project": str(project), "video": {"w": vw, "h": vh, "fps": fps, "dur": round(vdur, 3)},
        "deterministic": {"samples": len(frames), "ocr": "rapidocr_onnxruntime", "registry": "window.TEXTS(t)" if texts else "unavailable",
                          "frames": srec},
        "semantic": {k: v for k, v in sem.items() if k != "issues"},
        "contactSheets": sheets,
        "issues": issues, "high": len(high), "medium": len(med),
        "status": "FAIL" if high else "PASS",
        "evidenceDir": str(ev),
    }
    return rep


# ---------------------------------------------------------------- rework

HOOK_SAY_OLD = "HOOK_CUE[3] || '"
HOOK_FN = "\nconst hookSay = t => { const s = ((TL && TL.hook && TL.hook.subs) || []).find(x => t >= x.t0 && t < x.t1); return s ? s.en : HOOK_CUE[3]; };\n"


def _unlocked(project: Path, name: str) -> bool:
    lock = _j(project / "content" / "engine.lock.json", {}) or {}
    return name in (lock.get("unlocked") or [])


def fix_hook_subs(project: Path, sch: Schedule) -> tuple[bool, str, list[tuple[float, float]]]:
    if not sch.hook:
        return False, "no TL.hook", []
    a, b = float(sch.hook.get("t0", 0)), float(sch.hook.get("t1", 0))
    ids = [v for v in sch.vo if a <= v[1] < b]
    if len(ids) < 2:
        return False, "hook has a single VO line", []
    mj = project / "main.js"
    src = mj.read_text(encoding="utf-8")
    if "hookSay(" not in src:
        if not _unlocked(project, "main.js"):
            return False, "main.js is locked (engine.lock.json) — cannot teach the hook to switch subtitles", []
        pat = re.compile(r"HOOK_CUE\[3\] \|\| '[^']*'")
        if len(pat.findall(src)) < 1 or "function shotHook" not in src:
            return False, "main.js hook subtitle pattern not found", []
        src = pat.sub("hookSay(t)", src)
        src = src.replace("function shotHook", HOOK_FN.strip() + "\nfunction shotHook", 1)
        mj.write_text(src, encoding="utf-8")
    # Once the hook line follows the VO it is the subtitle bar, and readcheck's contract says the subtitle bar
    # is not a reading-time block (its hold is the VO/.srt); capCard's subtitle line is likewise not in TEXTS.
    # Subtitle correctness is still checked here by OCR (subtitle_vo_mismatch / subtitle_not_rendered).
    txp = re.compile(r"\n[ \t]*if \(\w+ > 0\) TX\.push\(\{ id: 'hook-say', text: hookSay\(t\)[^\n]*\}\);")
    if txp.search(src) and _unlocked(project, "main.js"):
        src = txp.sub("", src)
        mj.write_text(src, encoding="utf-8")
    subs = []
    for k, v in enumerate(ids):
        t0 = a if k == 0 else round(v[1] - 0.05, 3)
        t1 = b if k == len(ids) - 1 else round(ids[k + 1][1] - 0.05, 3)
        subs.append({"id": v[0], "t0": round(t0, 3), "t1": round(t1, 3), "en": v[3]})
    tlp = project / "timeline.json"
    tl = _j(tlp, {})
    tl.setdefault("hook", {})["subs"] = subs
    tlp.write_text(json.dumps(tl, ensure_ascii=False, indent=2), encoding="utf-8")
    cp = project / "audio" / "cues.json"
    cues = _j(cp, [])
    if isinstance(cues, list) and cues and abs(float(cues[0].get("t0", -1)) - a) < 1e-3 and abs(float(cues[0].get("t1", -1)) - b) < 0.3:
        head = (sch.hook.get("zh") or "").strip()
        new = [{"t0": s["t0"], "t1": s["t1"], "text": (head + "\n" if head and k == 0 else "") + s["en"]} for k, s in enumerate(subs)]
        cues = new + cues[1:]
        cp.write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, f"hook subtitles now follow VO lines {[s['id'] for s in subs]}", [(a, b)]


def fix_caption(project: Path, sch: Schedule, it: dict) -> tuple[bool, str, list[tuple[float, float]]]:
    tlp = project / "timeline.json"
    tl = _j(tlp, {})
    caps = tl.get("caps") or []
    idx = it.get("cap")
    if idx is None:
        src = str(it.get("src", ""))
        cid = src.split(":")[1] if src.startswith("cap:") else None
        idx = next((k for k, c in enumerate(caps) if str(c.get("id")) == cid), None)
    if idx is None or idx >= len(caps):
        return False, "caption not found in timeline caps", []
    c = caps[idx]
    if it["kind"] in ("caption_readtime", "subtitle_readtime"):
        nxt = caps[idx + 1]["t0"] if idx + 1 < len(caps) else sch.dur
        shot = sch.shot_at(c["t0"]) or {"t1": sch.dur}
        new_t1 = round(min(float(shot["t1"]), max(float(c["t1"]), float(nxt) - 0.05 if nxt > c["t1"] else float(c["t1"]) + 0.6)), 3)
        if new_t1 <= c["t1"] + 0.01:
            return False, "no room to extend caption inside its shot", []
        old = c["t1"]
        c["t1"] = new_t1
        tl["caps"] = caps
        tlp.write_text(json.dumps(tl, ensure_ascii=False, indent=2), encoding="utf-8")
        return True, f"caption {c.get('id')} t1 {old}→{new_t1}", [(float(c["t0"]), new_t1)]
    big = float(c.get("big") or 1)
    if big <= 0.7:
        return False, "caption already at minimum size", []
    c["big"] = round(big * 0.85, 3)
    tl["caps"] = caps
    tlp.write_text(json.dumps(tl, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, f"caption {c.get('id')} size ×{c['big']}", [(float(c["t0"]), float(c["t1"]))]


def plan_fixes(project: Path, rep: dict) -> tuple[list[dict], list[tuple[float, float]], list[dict]]:
    sch = Schedule(project, None)
    done, ranges, unfixable = [], [], []
    hook_done = False
    for it in rep["issues"]:
        if it["severity"] != "high":
            continue
        k = it["kind"]
        ok, why, rg = False, "no automatic fix for this kind", []
        if k in ("subtitle_vo_mismatch", "subtitle_missing") and sch.hook and float(sch.hook.get("t0", 0)) <= float(it["t"] or 0) < float(sch.hook.get("t1", 0)):
            if hook_done:
                continue
            ok, why, rg = fix_hook_subs(project, sch)
            hook_done = ok
        elif k in ("caption_readtime", "subtitle_readtime") or (k in ("ocr_mismatch", "text_clipped") and str(it.get("src", "")).startswith("cap:")):
            ok, why, rg = fix_caption(project, sch, it)
        elif k == "subtitle_not_rendered" and it.get("t") is not None:
            sh = sch.shot_at(float(it["t"])) or {"t0": 0, "t1": sch.dur}
            ok, why, rg = True, "picture is stale vs schedule: re-render the shot", [(float(sh["t0"]), float(sh["t1"]))]
        elif k in ("black_frames", "corrupt_frame", "blank_frames", "decode_error") and it.get("t") is not None:
            t = float(it["t"])
            ok, why, rg = True, "re-render frame range", [(max(0, t - 0.5), min(sch.dur, t + float(it.get("dur") or 0) + 0.5))]
        (done if ok else unfixable).append({"kind": k, "t": it.get("t"), "fix": why})
        ranges += rg
    return done, ranges, unfixable


def keyframes(video: Path) -> list[float]:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-skip_frame", "nokey", "-show_entries",
                        "frame=pts_time", "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True)
    return sorted(float(x.strip(",")) for x in r.stdout.split() if x.strip(", "))


def _nb_frames(video: Path) -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                          "stream=nb_read_packets", "-of", "csv=p=0", str(video)], capture_output=True, text=True).stdout
    return int(out.strip().strip(",").strip() or 0)


def rerender_ranges(project: Path, ranges: list[tuple[float, float]], fps: float, video: Path, log) -> dict:
    """Re-render only the changed time ranges into out/video.mp4 (keyframe-aligned lossless splice)."""
    kf = keyframes(video)
    total = _nb_frames(video)
    spans = []
    for a, b in sorted(ranges):
        ka = max([k for k in kf if k <= a + 1e-6] or [0.0])
        later = [k for k in kf if k >= b - 1e-6]
        kb = later[0] if later else total / fps
        fa, fb = int(round(ka * fps)), int(round(kb * fps))
        if spans and fa <= spans[-1][1]:
            spans[-1] = (spans[-1][0], max(spans[-1][1], fb))
        else:
            spans.append((fa, fb))
    tmp = video.parent / ".vc_splice"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    parts, cur = [], 0
    for k, (fa, fb) in enumerate(spans):
        if fa > cur:
            p = tmp / f"keep_{k}.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{cur / fps:.6f}", "-i", str(video), "-frames:v", str(fa - cur), "-c", "copy", "-an", str(p)], check=True)
            parts.append(p)
        p = tmp / f"new_{k}.mp4"
        log(f"  render frames {fa}–{fb} ({fa / fps:.2f}–{fb / fps:.2f}s)")
        subprocess.run(["node", str(HERE / "render_range.mjs"), str(project), "--fps", str(fps), "--from", str(fa), "--to", str(fb), "--out", str(p)],
                       check=True, cwd=str(REPO), stdout=subprocess.DEVNULL)
        parts.append(p)
        cur = fb
    if cur < total:
        p = tmp / "keep_tail.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{cur / fps:.6f}", "-i", str(video), "-c", "copy", "-an", str(p)], check=True)
        parts.append(p)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
    out = tmp / "spliced.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True, cwd=str(tmp))
    n = _nb_frames(out)
    if n != total:
        shutil.rmtree(tmp)
        raise RuntimeError(f"splice frame count {n} != {total}")
    shutil.copy2(video, video.with_suffix(".pre-rework.mp4"))
    shutil.move(str(out), str(video))
    shutil.rmtree(tmp)
    return {"spans": [[a, b] for a, b in spans], "framesRendered": sum(b - a for a, b in spans), "totalFrames": total}


def remux(project: Path, video: Path, media: Path, fps: float) -> None:
    mix = project / "out" / "mix.wav"
    tmp = media.with_name(media.stem + ".rework.mp4")
    subprocess.run(["sh", str(REPO / "core/render/mux.sh"), str(video), str(mix), str(tmp), str(int(round(fps))), "1"], check=True, cwd=str(REPO),
                   stdout=subprocess.DEVNULL)
    shutil.move(str(tmp), str(media))
    cues = project / "audio" / "cues.json"
    srt = media.with_suffix(".srt")
    if cues.exists():
        subprocess.run([sys.executable, str(REPO / "core/render/srt.py"), str(cues), str(srt)], check=False, stdout=subprocess.DEVNULL)


def run(project: Path, media: Path | None, *, rework=False, rounds=2, semantic=True, models=None, log=print) -> dict:
    project = project.resolve()
    media = (media or find_media(project))
    if not media or not Path(media).exists():
        raise SystemExit("visual-check: no media (pass --media)")
    media = Path(media).resolve()
    ocr = OCR()
    rep = run_check(project, media, semantic=semantic, models=models, ocr=ocr)
    history = [{"round": 0, "high": rep["high"], "medium": rep["medium"], "status": rep["status"]}]
    reworks = []
    final_status = rep["status"]
    if rework and rep["high"]:
        video = project / "out" / "video.mp4"
        r = 0
        while rep["high"] and r < rounds:
            r += 1
            done, ranges, unfix = plan_fixes(project, rep)
            entry = {"round": r, "fixes": done, "unfixable": unfix}
            if not done:
                reworks.append(entry)
                break
            if ranges and video.exists():
                fps = rep["video"]["fps"]
                entry["render"] = rerender_ranges(project, ranges, fps, video, log)
                remux(project, video, media, fps)
            else:
                entry["render"] = "video.mp4 missing: cannot re-render" if ranges else "no frames changed"
            reworks.append(entry)
            rep = run_check(project, media, semantic=semantic, models=models, tag="", ocr=OCR())
            history.append({"round": r, "high": rep["high"], "medium": rep["medium"], "status": rep["status"]})
        final_status = "PASS" if not rep["high"] else "BEST_EFFORT"
    rep["rework"] = reworks
    rep["history"] = history
    rep["finalStatus"] = final_status if rework else rep["status"]
    out = project / "evidence" / "visual-check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    rep["path"] = str(out)
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="visual-check")
    ap.add_argument("--project", required=True)
    ap.add_argument("--media")
    ap.add_argument("--rework", action="store_true")
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--no-semantic", action="store_true")
    ap.add_argument("--model", action="append", help="OpenRouter :free vision model (repeatable)")
    a = ap.parse_args(argv)
    rep = run(Path(a.project), Path(a.media) if a.media else None, rework=a.rework, rounds=min(2, a.rounds),
              semantic=not a.no_semantic, models=a.model)
    for it in rep["issues"]:
        if it["severity"] != "low":
            print(f"{it['severity'].upper():6} {it['kind']:22} t={it.get('t')}  {it['detail'][:150]}")
    print(f"semantic={rep['semantic']['status']} model={rep['semantic'].get('model')} billing={rep['semantic'].get('billing')}")
    print(f"visual-check {rep['finalStatus']}: high={rep['high']} medium={rep['medium']} → {rep['path']}")
    return 0 if rep["finalStatus"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
