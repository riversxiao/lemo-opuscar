"""Premiere-adjacent FCP XML (xmeml) export from a finished lemo mux.

Honest scope:
- Writes Final Cut Pro XML (xmeml v5) that Premiere Pro / Resolve / FCP can
  usually *Import* as a sequence of trims of one master file.
- Does **not** write a native .prproj, AAF, or Resolve .drp.
- Picture + optional audio file references; no effects, transitions, or titles.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from .common import (
    probe_fps,
    copy_stem_audio,
    find_master_mp4,
    load_shots,
    probe_duration,
)


def _frames(sec: float, fps: int) -> int:
    return max(0, int(round(float(sec) * fps)))


def _file_url(path: Path) -> str:
    # Absolute file URL — NLEs resolve local paths; relative is brittle across machines.
    return path.resolve().as_uri()


def write_xmeml(
    path: Path,
    *,
    name: str,
    master: Path,
    shots: list[dict[str, Any]],
    duration_sec: float,
    fps: int = 24,
    width: int = 1920,
    height: int = 1080,
) -> None:
    """Write a minimal xmeml v5 sequence (one video track of master trims)."""
    tb = str(fps)
    file_id = "file-master"
    master_uri = escape(_file_url(master))
    master_name = escape(master.name)
    seq_name = escape(name)
    dur_f = _frames(duration_sec, fps)

    clip_xml: list[str] = []
    for i, sh in enumerate(shots, start=1):
        t0, t1 = float(sh["t0"]), float(sh["t1"])
        if t1 <= t0:
            continue
        src_in = _frames(t0, fps)
        src_out = _frames(t1, fps)
        # Record timeline starts at shot t0 (contiguous mux layout).
        rec_in = src_in
        rec_out = src_out
        clip_name = escape(str(sh.get("text") or sh.get("id") or f"shot-{i}")[:80])
        clip_xml.append(
            f"""        <clipitem id="clip-{i}">
          <name>{clip_name}</name>
          <duration>{src_out - src_in}</duration>
          <rate>
            <timebase>{tb}</timebase>
            <ntsc>FALSE</ntsc>
          </rate>
          <start>{rec_in}</start>
          <end>{rec_out}</end>
          <in>{src_in}</in>
          <out>{src_out}</out>
          <file id="{file_id}"/>
        </clipitem>"""
        )

    if not clip_xml:
        # Single full-length clip
        clip_xml.append(
            f"""        <clipitem id="clip-1">
          <name>{seq_name}</name>
          <duration>{dur_f}</duration>
          <rate>
            <timebase>{tb}</timebase>
            <ntsc>FALSE</ntsc>
          </rate>
          <start>0</start>
          <end>{dur_f}</end>
          <in>0</in>
          <out>{dur_f}</out>
          <file id="{file_id}"/>
        </clipitem>"""
        )

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="5">
  <sequence id="seq-1">
    <name>{seq_name}</name>
    <duration>{dur_f}</duration>
    <rate>
      <timebase>{tb}</timebase>
      <ntsc>FALSE</ntsc>
    </rate>
    <media>
      <video>
        <format>
          <samplecharacteristics>
            <rate>
              <timebase>{tb}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
            <width>{width}</width>
            <height>{height}</height>
            <pixelaspectratio>square</pixelaspectratio>
            <fielddominance>none</fielddominance>
          </samplecharacteristics>
        </format>
        <track>
{chr(10).join(clip_xml)}
          <enabled>TRUE</enabled>
          <locked>FALSE</locked>
        </track>
      </video>
      <audio>
        <format>
          <samplecharacteristics>
            <depth>16</depth>
            <samplerate>48000</samplerate>
          </samplecharacteristics>
        </format>
        <track>
          <clipitem id="audio-1">
            <name>{master_name}</name>
            <duration>{dur_f}</duration>
            <rate>
              <timebase>{tb}</timebase>
              <ntsc>FALSE</ntsc>
            </rate>
            <start>0</start>
            <end>{dur_f}</end>
            <in>0</in>
            <out>{dur_f}</out>
            <file id="{file_id}"/>
          </clipitem>
          <enabled>TRUE</enabled>
          <locked>FALSE</locked>
        </track>
      </audio>
    </media>
  </sequence>
  <file id="{file_id}">
    <name>{master_name}</name>
    <pathurl>{master_uri}</pathurl>
    <rate>
      <timebase>{tb}</timebase>
      <ntsc>FALSE</ntsc>
    </rate>
    <duration>{dur_f}</duration>
    <media>
      <video>
        <duration>{dur_f}</duration>
        <samplecharacteristics>
          <rate>
            <timebase>{tb}</timebase>
            <ntsc>FALSE</ntsc>
          </rate>
          <width>{width}</width>
          <height>{height}</height>
        </samplecharacteristics>
      </video>
      <audio>
        <samplecharacteristics>
          <depth>16</depth>
          <samplerate>48000</samplerate>
        </samplecharacteristics>
        <channelcount>2</channelcount>
      </audio>
    </media>
  </file>
</xmeml>
"""
    path.write_text(body, encoding="utf-8")


def export_premiere(
    film_dir: Path,
    *,
    name: str | None = None,
    out_dir: Path | None = None,
    fps: int | None = None,
) -> dict[str, Any]:
    """Package assets + premiere.xml (xmeml) for Premiere-adjacent import.
    fps None → probe the master's video rate (fallback 24)."""
    film_dir = film_dir.resolve()
    name = name or film_dir.name
    out = (out_dir or (film_dir / "premiere-handoff")).resolve()
    if out.exists():
        shutil.rmtree(out)
    assets = out / "assets"
    assets.mkdir(parents=True)

    mp4 = find_master_mp4(film_dir)
    dur = probe_duration(mp4)
    fps = int(fps or probe_fps(mp4))
    shots, shot_src, dur_hint = load_shots(film_dir)
    if dur_hint and not shots:
        dur = float(dur_hint)
    if not shots:
        shots = [
            {
                "id": "master",
                "t0": 0.0,
                "t1": round(dur, 6),
                "dur": round(dur, 6),
                "text": name,
                "role": "full",
                "voIds": [],
            }
        ]
        shot_src = "fallback-full"

    shutil.copy2(mp4, assets / "master.mp4")
    master_local = assets / "master.mp4"
    stems = copy_stem_audio(film_dir, assets)

    xml_path = out / "premiere.xml"
    write_xmeml(
        xml_path,
        name=name,
        master=master_local,
        shots=shots,
        duration_sec=dur,
        fps=fps,
    )

    # Also drop a CMX3600 EDL next to XML for NLEs that prefer EDL.
    from .common import write_cmx3600_edl

    write_cmx3600_edl(out / "timeline.edl", title=name, shots=shots, fps=fps)

    manifest = {
        "kind": "lemo-premiere-handoff",
        "version": 1,
        "name": name,
        "format": "xmeml-v5",
        "sourceFilm": str(film_dir),
        "sourceMp4": str(mp4),
        "durationSec": round(dur, 3),
        "fps": fps,
        "shotSource": shot_src,
        "shotCount": len(shots),
        "shots": shots,
        "stems": stems,
        "artifacts": {
            "xml": "premiere.xml",
            "edl": "timeline.edl",
            "master": "assets/master.mp4",
        },
        "importHint": [
            "Premiere Pro: File → Import → premiere.xml (FCP XML).",
            "DaVinci Resolve: File → Import Timeline → XML / EDL (verify reel path).",
            "pathurl points at assets/master.mp4 next to the XML; keep the folder together.",
        ],
        "limits": [
            "Not a native .prproj / AAF / Resolve .drp — xmeml import only.",
            "No titles, transitions, or color — picture trims + full audio of the mux.",
            f"Timebase {fps}fps non-drop (probed from the master; 24 if unreadable).",
            "Paid desktop apps are not required on the box; this is an export artifact only.",
        ],
        "needsUser": [
            "Adobe Premiere Pro / DaVinci Resolve / FCP license + desktop to verify import.",
        ],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "README.md").write_text(
        f"""# Premiere-adjacent handoff · {name}

FCP XML (`xmeml` v5) + master MP4 for **import** into Premiere Pro / Resolve / FCP.

- source: `{mp4}`
- duration: {dur:.3f}s
- shots: **{len(shots)}** (`{shot_src}`)
- fps assumption: {fps} (non-drop)

## Import

1. Keep this folder intact (`premiere.xml` + `assets/master.mp4`).
2. Premiere: **File → Import → `premiere.xml`**.
3. Resolve: import XML/EDL and relink media to `assets/master.mp4` if asked.

## Limits

- Not a `.prproj`. No effects/titles. Audio is the full mux on one track.
- OpenFilm Studio / HyperFrames remain separate rails (`tools/handoff/`).
""",
        encoding="utf-8",
    )

    return {
        "out": str(out),
        "mp4": str(mp4),
        "durationSec": round(dur, 3),
        "shotCount": len(shots),
        "shotSource": shot_src,
        "xml": str(xml_path),
        "manifest": str(out / "manifest.json"),
    }
