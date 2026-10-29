"""HyperFrames export: composition folder from a finished lemo mux.

Local CLI (`npx hyperframes`) is installable. Desktop Studio / HeyGen cloud /
interactive skills install are **needs-user**. This exporter always writes a
complete project a human or agent can `lint` / `check` / `render` without
claiming Opuscar Studio or a paid connect.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .common import (
    copy_stem_audio,
    find_master_mp4,
    html_escape,
    load_shots,
    probe_duration,
)


HF_JSON = {
    "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
    "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
    "paths": {
        "blocks": "compositions",
        "components": "compositions/components",
        "assets": "assets",
    },
    "media": {"autoProxy": True},
}

PACKAGE_JSON = {
    "name": "lemo-hyperframes-handoff",
    "private": True,
    "type": "module",
    "scripts": {
        "dev": "npx --yes hyperframes@0.8.212 preview",
        "check": "npx --yes hyperframes@0.8.212 check",
        "lint": "npx --yes hyperframes@0.8.212 lint",
        "render": "npx --yes hyperframes@0.8.212 render",
        "publish": "npx --yes hyperframes@0.8.212 publish",
    },
}


def _index_html(name: str, dur: float, shots: list[dict[str, Any]], video_src: str) -> str:
    # A-roll: full master. Shot markers on track 1 as short title cards (edit hints).
    markers = []
    for sh in shots:
        label = html_escape((sh.get("text") or sh["id"])[:40])
        # brief overlay at shot start (0.8s or shot dur, whichever smaller)
        overlay_dur = min(0.8, max(0.2, float(sh["dur"])))
        markers.append(
            f'''      <div id="mark-{html_escape(sh["id"])}" class="clip marker"
           data-start="{sh["t0"]:.3f}" data-duration="{overlay_dur:.3f}" data-track-index="1"
           style="position:absolute;left:48px;top:48px;padding:12px 20px;background:rgba(0,0,0,.55);
                  color:#fff;font:600 36px/1.2 system-ui,sans-serif;border-radius:8px">{label}</div>'''
        )
    markers_html = "\n".join(markers)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{
        margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: #000;
      }}
      .marker {{ pointer-events: none; }}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{dur:.3f}"
      data-width="1920"
      data-height="1080"
    >
      <video
        id="a-roll"
        class="clip"
        src="{html_escape(video_src)}"
        playsinline
        data-start="0"
        data-duration="{dur:.3f}"
        data-track-index="0"
        data-has-audio="true"
        style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"
      ></video>
{markers_html}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines = window.__timelines || {{}};
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def export_hyperframes(
    film_dir: Path,
    *,
    name: str | None = None,
    out_dir: Path | None = None,
    try_init_cli: bool = False,
    run_lint: bool = False,
) -> dict[str, Any]:
    film_dir = film_dir.resolve()
    name = name or film_dir.name
    out = (out_dir or (film_dir / "hyperframes-handoff")).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    assets = out / "assets"
    assets.mkdir()

    mp4 = find_master_mp4(film_dir)
    dur = probe_duration(mp4)
    shots, shot_src, _ = load_shots(film_dir)
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

    # Prefer assets/master.mp4 relative path (stable name)
    shutil.copy2(mp4, assets / "master.mp4")
    video_src = "assets/master.mp4"
    stems = copy_stem_audio(film_dir, assets)

    init_meta: dict[str, Any] = {"usedCliInit": False}
    if try_init_cli and shutil.which("npx"):
        # Optional: let upstream init shape the project, then overwrite index with our markers.
        scratch = out / ".init-scratch"
        if scratch.exists():
            shutil.rmtree(scratch)
        try:
            subprocess.check_call(
                [
                    "npx",
                    "-y",
                    "hyperframes@0.8.212",
                    "init",
                    str(scratch),
                    "--video",
                    str(assets / "master.mp4"),
                    "--non-interactive",
                    "--skip-transcribe",
                    "--skip-skills",
                    "--keep-original",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            for fname in ("hyperframes.json", "package.json", "meta.json", "AGENTS.md", "CLAUDE.md"):
                src = scratch / fname
                if src.is_file():
                    shutil.copy2(src, out / fname)
            # Upstream may have copied mp4 to project root — keep assets/master as canonical.
            init_meta["usedCliInit"] = True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            init_meta["cliInitError"] = str(e)
        finally:
            if scratch.exists():
                shutil.rmtree(scratch, ignore_errors=True)

    if not (out / "hyperframes.json").is_file():
        (out / "hyperframes.json").write_text(
            json.dumps(HF_JSON, indent=2) + "\n", encoding="utf-8"
        )
    pkg = dict(PACKAGE_JSON)
    pkg["name"] = f"lemo-hf-{name}"[:64]
    (out / "package.json").write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
    (out / "meta.json").write_text(
        json.dumps({"id": name, "name": name, "source": "wordfilm-handoff"}, indent=2)
        + "\n",
        encoding="utf-8",
    )

    (out / "index.html").write_text(
        _index_html(name, dur, shots, video_src), encoding="utf-8"
    )

    lemo_manifest = {
        "kind": "lemo-hyperframes-handoff",
        "version": 1,
        "name": name,
        "sourceFilm": str(film_dir),
        "sourceMp4": str(mp4),
        "durationSec": round(dur, 3),
        "shotSource": shot_src,
        "shotCount": len(shots),
        "shots": shots,
        "stems": stems,
        "init": init_meta,
        "needsUser": [
            "Desktop HyperFrames app / `hyperframes open` GUI — optional; not required for lint/render.",
            "HeyGen cloud render / `hyperframes auth` — paid/account path; do not use unless the user asks.",
            "`npx hyperframes skills update` / interactive skills picker — agent skills install is needs-user.",
            "Opuscar Studio is unrelated and not connected by this export.",
        ],
        "runsOnBox": [
            "npx hyperframes@0.8.212 doctor",
            "npx hyperframes@0.8.212 lint",
            "npx hyperframes@0.8.212 check   # may need Chrome; slow on software WebGL",
            "npx hyperframes@0.8.212 render --output out.mp4  # re-encode; optional bake-off",
        ],
        "limits": [
            "Default lemo delivery remains Playwright still/video/mux — this is an alternate rail export.",
            "Composition wraps the finished mux + shot-label overlays; it does not migrate the locked engine.",
        ],
    }
    (out / "lemo-manifest.json").write_text(
        json.dumps(lemo_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    (out / "README.md").write_text(
        f"""# HyperFrames handoff · {name}

Export-only package from a finished lemo mux. **Not** Opuscar Studio.

- source: `{mp4}`
- duration: {dur:.3f}s
- shots: **{len(shots)}** (`{shot_src}`) with on-screen markers

## Runs on this box (no account)

```sh
cd hyperframes-handoff
npx -y hyperframes@0.8.212 lint
# optional:
# npx -y hyperframes@0.8.212 check
# npx -y hyperframes@0.8.212 render --output bakeoff.mp4
```

## Needs user

- HyperFrames **desktop** / GUI preview comfort
- HeyGen **cloud** render or `hyperframes auth`
- Interactive `skills` install (`npx hyperframes skills update`)

Do **not** paste API keys into `films/` or this folder.

## Limits

Locked Opus demo engines stay on Playwright. Use this rail for greenfield HTML
motion or a bake-off against an already-muxed lemo MP4.
""",
        encoding="utf-8",
    )

    lint_ok: bool | None = None
    lint_detail = ""
    if run_lint and shutil.which("npx"):
        try:
            proc = subprocess.run(
                ["npx", "-y", "hyperframes@0.8.212", "lint"],
                cwd=str(out),
                capture_output=True,
                text=True,
                timeout=180,
            )
            lint_ok = proc.returncode == 0
            lint_detail = (proc.stdout or "")[-500:] + (proc.stderr or "")[-200:]
        except (subprocess.SubprocessError, OSError) as e:
            lint_ok = False
            lint_detail = str(e)

    return {
        "out": str(out),
        "mp4": str(mp4),
        "durationSec": round(dur, 3),
        "shotCount": len(shots),
        "shotSource": shot_src,
        "lintOk": lint_ok,
        "lintDetail": lint_detail[-300:] if lint_detail else "",
        "manifest": str(out / "lemo-manifest.json"),
        "needsUser": lemo_manifest["needsUser"],
    }
