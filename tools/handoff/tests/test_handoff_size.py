"""Frame size / fps resolution for the handoff exporters (9:16 and friends).

Run: python3 -m pytest tools/handoff/tests -q
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.handoff import common
from tools.handoff.cli import main as cli_main
from tools.handoff.hyperframes import _index_html, export_hyperframes
from tools.handoff.openfilm import export_openfilm
from tools.handoff.premiere import export_premiere, write_xmeml

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tools" / "deepseek-controller" / "fixtures" / "handoff-mini"
HAS_FFPROBE = bool(shutil.which("ffprobe"))
HAS_FFMPEG = bool(shutil.which("ffmpeg")) and HAS_FFPROBE


@pytest.fixture
def film(tmp_path: Path) -> Path:
    dst = tmp_path / "handoff-mini"
    shutil.copytree(FIXTURE, dst)
    return dst


@pytest.fixture
def no_ffprobe(monkeypatch: pytest.MonkeyPatch) -> None:
    real = shutil.which

    def fake(cmd, *a, **kw):
        if cmd in ("ffprobe", "ffmpeg"):
            return None
        return real(cmd, *a, **kw)

    monkeypatch.setattr(common.shutil, "which", fake)


def _shots():
    return [
        {"id": "a", "t0": 0.0, "t1": 1.0, "dur": 1.0, "text": "a"},
        {"id": "b", "t0": 1.0, "t1": 2.0, "dur": 1.0, "text": "b"},
    ]


# --- parsing ---------------------------------------------------------------


@pytest.mark.parametrize("spec,want", [("1080x1920", (1080, 1920)), ("1920X1080", (1920, 1080)), ("16x16", (16, 16))])
def test_parse_size_ok(spec, want):
    assert common.parse_size(spec) == want


@pytest.mark.parametrize("spec", ["1081x1920", "1080x1921", "8x8", "9000x1080", "1080", "axb", "1080x1920x2", ""])
def test_parse_size_rejects(spec):
    with pytest.raises(ValueError):
        common.parse_size(spec)


@pytest.mark.parametrize("spec,want", [("24", 24.0), ("29.97", 29.97), ("30000/1001", 30000 / 1001), (25, 25.0)])
def test_parse_fps(spec, want):
    assert common.parse_fps(spec) == pytest.approx(want)


@pytest.mark.parametrize("spec", ["0", "-1", "abc", "1/0", "500"])
def test_parse_fps_rejects(spec):
    with pytest.raises(ValueError):
        common.parse_fps(spec)


def test_fps_timebase_ntsc():
    assert common.fps_timebase(24.0) == (24, False)
    assert common.fps_timebase(30000 / 1001) == (30, True)
    assert common.fps_timebase(24000 / 1001) == (24, True)
    assert common.fps_timebase(25.0) == (25, False)


@pytest.mark.parametrize("cmd", ["premiere", "openfilm", "hyperframes", "both"])
def test_cli_rejects_odd_size(cmd, film, capsys):
    with pytest.raises(SystemExit) as ei:
        cli_main([cmd, str(film), "--size", "1081x1920"])
    assert ei.value.code == 2
    assert "even" in capsys.readouterr().err


# --- xmeml / html ----------------------------------------------------------


def test_write_xmeml_portrait(tmp_path):
    xml = tmp_path / "p.xml"
    master = tmp_path / "m.mp4"
    master.write_bytes(b"")
    write_xmeml(xml, name="p", master=master, shots=_shots(), duration_sec=2.0, fps=24, width=1080, height=1920)
    body = xml.read_text()
    assert body.count("<width>1080</width>") == 2
    assert body.count("<height>1920</height>") == 2
    assert "<width>1920</width>" not in body
    assert "<ntsc>TRUE</ntsc>" not in body


def test_write_xmeml_ntsc(tmp_path):
    xml = tmp_path / "n.xml"
    master = tmp_path / "m.mp4"
    master.write_bytes(b"")
    write_xmeml(xml, name="n", master=master, shots=_shots(), duration_sec=2.0, fps=30000 / 1001)
    body = xml.read_text()
    assert "<timebase>30</timebase>" in body
    assert "<ntsc>TRUE</ntsc>" in body
    assert "<ntsc>FALSE</ntsc>" not in body


def test_hyperframes_index_html_portrait():
    html = _index_html("x", 2.0, _shots(), "assets/master.mp4", 1080, 1920)
    assert 'content="width=1080, height=1920"' in html
    assert "width: 1080px; height: 1920px" in html
    assert 'data-width="1080"' in html and 'data-height="1920"' in html
    assert "1920px; height: 1080px" not in html
    assert 'data-width="1920"' not in html


def test_exports_with_size_flag(film, tmp_path):
    of = export_openfilm(film, out_dir=tmp_path / "of", width=1080, height=1920, fps=30)
    hf = export_hyperframes(film, out_dir=tmp_path / "hf", width=1080, height=1920)
    pr = export_premiere(film, out_dir=tmp_path / "pr", width=1080, height=1920, fps=30)
    for info in (of, hf, pr):
        assert (info["width"], info["height"], info["sizeSource"]) == (1080, 1920, "flag")
    film_html = (tmp_path / "of" / "film.html").read_text()
    assert 'content="width=1080, height=1920"' in film_html
    assert "width:1080px;height:1920px" in film_html
    assert "1920px;height:1080px" not in film_html
    assert "<width>1080</width>" in (tmp_path / "of" / "premiere.xml").read_text()
    index = (tmp_path / "hf" / "index.html").read_text()
    assert 'data-width="1080"' in index and 'data-height="1920"' in index
    man = json.loads((tmp_path / "pr" / "manifest.json").read_text())
    assert man["width"] == 1080 and man["height"] == 1920 and man["fps"] == 30
    assert "<timebase>30</timebase>" in (tmp_path / "pr" / "premiere.xml").read_text()


def test_cli_premiere_json_reports_source(film, tmp_path, capsys):
    rc = cli_main(["premiere", str(film), "-o", str(tmp_path / "pr"), "--size", "1080x1920", "--fps", "25", "--json"])
    assert rc == 0
    info = json.loads(capsys.readouterr().out)
    assert info["width"] == 1080 and info["height"] == 1920
    assert info["sizeSource"] == "flag" and info["fpsSource"] == "flag"
    xml = (tmp_path / "pr" / "premiere.xml").read_text()
    assert "<width>1080</width>" in xml and "<height>1920</height>" in xml


# --- probe fallbacks -------------------------------------------------------


def test_probe_video_fallback_without_ffprobe(no_ffprobe, film):
    info = common.probe_video(film / "handoff-mini.mp4")
    assert info == {"width": 1920, "height": 1080, "fps": 24.0, "duration": 30.0, "probed": False}
    assert common.probe_duration(film / "handoff-mini.mp4") == 30.0


def test_resolve_frame_default_without_ffprobe(no_ffprobe, film, tmp_path):
    fr = common.resolve_frame(film / "handoff-mini.mp4")
    assert (fr["width"], fr["height"], fr["fps"]) == (1920, 1080, 24.0)
    assert fr["sizeSource"] == "default" and fr["fpsSource"] == "default"
    pr = export_premiere(film, out_dir=tmp_path / "pr")
    assert pr["sizeSource"] == "default"
    assert "<width>1920</width>" in (tmp_path / "pr" / "premiere.xml").read_text()
    # flag still wins with no ffprobe
    fr = common.resolve_frame(film / "handoff-mini.mp4", size=(1080, 1920), fps=30)
    assert (fr["width"], fr["height"], fr["sizeSource"], fr["fpsSource"]) == (1080, 1920, "flag", "flag")


def test_probe_video_unreadable_file(tmp_path):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    info = common.probe_video(bad)
    assert info["probed"] is False
    assert (info["width"], info["height"]) == (1920, 1080)


@pytest.mark.skipif(not HAS_FFPROBE, reason="ffprobe not installed")
def test_probe_fixture(film):
    info = common.probe_video(film / "handoff-mini.mp4")
    assert info["probed"] is True
    assert (info["width"], info["height"]) == (640, 360)
    assert info["fps"] == pytest.approx(25.0)
    assert info["duration"] == pytest.approx(2.0, abs=0.05)


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")
def test_probe_portrait_mp4_drives_exports(tmp_path, capsys):
    film = tmp_path / "portrait"
    (film / "out").mkdir(parents=True)
    mp4 = film / "out" / "final.mp4"
    subprocess.check_call(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=1080x1920:r=30000/1001:d=1",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(mp4),
        ]
    )
    info = common.probe_video(mp4)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert info["fps"] == pytest.approx(29.97, abs=0.01)

    rc = cli_main(["premiere", str(film), "-o", str(tmp_path / "pr"), "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["width"], out["height"], out["sizeSource"], out["fpsSource"]) == (1080, 1920, "probe", "probe")
    xml = (tmp_path / "pr" / "premiere.xml").read_text()
    assert xml.count("<width>1080</width>") == 2 and xml.count("<height>1920</height>") == 2
    assert "<ntsc>TRUE</ntsc>" in xml

    of = export_openfilm(film, out_dir=tmp_path / "of")
    hf = export_hyperframes(film, out_dir=tmp_path / "hf")
    assert of["sizeSource"] == hf["sizeSource"] == "probe"
    for f in (tmp_path / "of" / "film.html", tmp_path / "hf" / "index.html"):
        txt = f.read_text()
        assert "1080" in txt and "width=1920" not in txt and "1920px; height: 1080px" not in txt
