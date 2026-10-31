"""visual_check.py frame geometry follows the film's size (no fixed 1920x1080).

Two tiny synthetic clips (numpy frames piped to ffmpeg, scaled-down web cuts): a 16:9 project
rendered 960x540 and a 9:16 project (content/engine.lock.json aspect 9:16) rendered 540x960.
The window.TEXTS registry is given in page px WITHOUT W/H, so visual_check must take the page
size from the project. OCR is a stub that returns the registry boxes scaled to the frame, so
no OCR engine is needed and the result is deterministic.

  16:9: the issues must be exactly what the old fixed-1920x1080 code reported.
  9:16: a title low in the portrait frame is neither "outside the frame" nor "found outside
        its TEXTS box"; a box really past the portrait right edge is still clipped; the luma
        scan and contact sheets are portrait rasters.
Exits 77 (SKIP in test_mvp.sh) when numpy / OpenCV / Pillow / ffmpeg are missing.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKIP = 77
_missing = [m for m in ("numpy", "cv2", "PIL") if importlib.util.find_spec(m) is None]
_missing += [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
if _missing:
    print("SKIP: missing " + ", ".join(_missing))
    sys.exit(SKIP)

import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "deepseek-controller"))
import visual_check as V  # noqa: E402

fails = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def make_project(root: Path, name: str, fw: int, fh: int, aspect: str | None, boxes: list[dict]) -> tuple[Path, Path, dict]:
    """Project + 2 s clip at fw x fh; boxes are in page px of the project's render size."""
    p = root / name
    (p / "content").mkdir(parents=True)
    if aspect:
        (p / "content" / "engine.lock.json").write_text(json.dumps({"aspect": aspect}))
    (p / "timeline.json").write_text(json.dumps({"dur": 2.0}))
    (p / "timeline.parsed.json").write_text(json.dumps({"contentDurationSec": 2.0, "shots": [{"id": "s1", "t0": 0.0, "t1": 2.0}]}))
    pw, ph = V.project_size(p)
    sx, sy = fw / pw, fh / ph
    fps, n = 10, 20
    media = p / "film.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{fw}x{fh}", "-r", str(fps),
                           "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", str(media)], stdin=subprocess.PIPE)
    yy, xx = np.mgrid[0:fh, 0:fw]
    for i in range(n):
        a = (40 + 20 * np.sin(xx / 37.0 + yy / 53.0 + i * 0.6)).astype(np.uint8)
        img = np.stack([a, a, a], axis=-1)
        for b in boxes:  # "text": white stripes inside the box (clipped to the frame)
            x0, x1 = max(0, int(b["x0"] * sx)), min(fw, int(b["x1"] * sx))
            y0, y1 = max(0, int(b["y0"] * sy)), min(fh, int(b["y1"] * sy))
            for y in range(y0, y1, 8):
                img[y:min(y1, y + 4), x0:x1] = 240
        ff.stdin.write(img.tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg failed")
    reg = [{k: v for k, v in b.items() if k != "ocr"} for b in boxes]
    texts = {"frames": [{"t": round(k * 0.1, 3), "texts": [dict(b) for b in reg]} for k in range(21)]}
    return p, media, texts


class StubOCR:
    """Reads back the registry boxes scaled to frame px ("ocr" overrides the score)."""

    def __init__(self, boxes, sx, sy, fw, fh):
        self.boxes = [{"text": b["text"], "score": b.get("ocr", 0.99), "x0": max(0, b["x0"] * sx), "y0": max(0, b["y0"] * sy),
                       "x1": min(fw - 1, b["x1"] * sx), "y1": min(fh - 1, b["y1"] * sy)}
                      for b in boxes]

    def __call__(self, _img):
        return [dict(b) for b in self.boxes]


def summary(rep):
    return sorted((i["severity"], i["kind"], i["detail"]) for i in rep["issues"])


tmp = Path(tempfile.mkdtemp())
try:
    # ---- 16:9: page 1920x1080, web cut 960x540
    land_boxes = [
        {"id": "title", "text": "流动性陷阱", "x0": 200, "y0": 180, "x1": 900, "y1": 320},
        # past the right edge; low OCR score so only the registry check (page px vs W/H) reports it
        {"id": "edge", "text": "边缘文字", "x0": 1500, "y0": 500, "x1": 1950, "y1": 620, "ocr": 0.4},
        {"id": "low", "text": "底部说明", "x0": 300, "y0": 1000, "x1": 1100, "y1": 1060},  # inside the 5% margin
    ]
    P, M, T = make_project(tmp, "land", 960, 540, None, land_boxes)
    rep = V.run_check(P, M, semantic=False, texts=T, ocr=StubOCR(land_boxes, 0.5, 0.5, 960, 540))
    # What the fixed W, H = 1920, 1080 code reported for this clip (recorded before the change).
    expected_land = [
        ("high", "text_clipped", "registry box edge '边缘文字' extends outside the frame"),
        ("medium", "outside_title_safe", "OCR text '底部说明' inside the 5% margin"),
    ]
    got = summary(rep)
    check(got == sorted(expected_land), f"16:9 960x540: issues unchanged from the fixed-1920x1080 code: {got}")
    check(rep["video"]["w"] == 960 and rep["video"]["h"] == 540, "16:9 probe 960x540")
    sheet = next(iter(rep["contactSheets"].values()), None)
    from PIL import Image
    if sheet:
        with Image.open(sheet) as im:
            check(im.size == (640 * 3, 360), f"16:9 contact sheet tiles stay 640x360 ({im.size})")
    check(V.scan_size(1920, 1080) == (160, 90) and V.scan_size(960, 540) == (160, 90), "16:9 luma scan stays 160x90")

    # ---- 9:16: page 1080x1920, web cut 540x960
    port_boxes = [
        {"id": "title", "text": "竖屏标题", "x0": 120, "y0": 300, "x1": 960, "y1": 460},
        {"id": "low", "text": "底部字幕", "x0": 120, "y0": 1500, "x1": 960, "y1": 1660},   # below y=1080: in frame for 9:16
        {"id": "edge", "text": "边缘文字", "x0": 700, "y0": 900, "x1": 1120, "y1": 1020, "ocr": 0.4},  # past the portrait right edge
    ]
    P, M, T = make_project(tmp, "port", 540, 960, "9:16", port_boxes)
    check(V.page_size(P, T) == (1080, 1920), f"9:16 page size from engine.lock.json ({V.page_size(P, T)})")
    check(V.page_size(P, {"W": 1080, "H": 1920}) == (1080, 1920) and V.page_size(tmp / "land", {"W": 1080, "H": 1920}) == (1080, 1920),
          "texts_dump W/H wins over the project size")
    rep = V.run_check(P, M, semantic=False, texts=T, ocr=StubOCR(port_boxes, 0.5, 0.5, 540, 960))
    iss = rep["issues"]
    kinds = [(i["kind"], i["detail"]) for i in iss]
    check(not any("'底部字幕'" in d and k == "text_clipped" for k, d in kinds), f"9:16 low caption not clipped: {kinds}")
    check(not any(k == "registry_bbox_off" for k, d in kinds), f"9:16 registry boxes scaled to the portrait frame: {kinds}")
    check(not any(k == "ocr_mismatch" for k, d in kinds), f"9:16 OCR found inside its registry box: {kinds}")
    check(any(k == "text_clipped" and "registry box edge" in d for k, d in kinds), f"9:16 box past the right edge still clipped: {kinds}")
    check(not any(k == "text_clipped" and ("title" in d or "竖屏标题" in d) for k, d in kinds), "9:16 title not clipped")
    check(V.scan_size(1080, 1920) == (90, 160) and V.scan_size(540, 960) == (90, 160), "9:16 luma scan raster 90x160")
    scan = V.luma_scan(M, 10, V.scan_size(540, 960))
    check(scan["frames"].shape[1:] == (160, 90), f"9:16 luma frames {scan['frames'].shape[1:]}")
    sheet = next(iter(rep["contactSheets"].values()), None)
    check(bool(sheet), "9:16 contact sheet written")
    if sheet:
        with Image.open(sheet) as im:
            check(im.size == (360 * 3, 640), f"9:16 contact sheet tiles 360x640 ({im.size})")
    for e in rep["deterministic"]["frames"]:
        for c in e["checks"]:
            check(c["recall"] >= 0.9, f"9:16 t={e['t']} {c['src']} recall {c['recall']}")
            break
        break
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("FAILED: " + "; ".join(fails) if fails else "all visual_check aspect checks passed")
sys.exit(1 if fails else 0)
