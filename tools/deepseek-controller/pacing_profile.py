"""One pacing profile (fast | standard | calm) drives every layer.

Consumers: dialogue_check (字/秒 estimate, ceiling, per-line length WARN), run_tts
(edge rate, StepAudio speed), pause_trim (max pause kept), schedule (shot overhead,
line gap, no hold-last-beat pad), quality (pacing gate thresholds).

Resolution order (first hit wins):
  1. explicit --pacing (CLI) / function argument
  2. plan.json "pacing"   (content/plan.json, then <project>/plan.json)
  3. env LEMO_PACING
  4. content_type → profile: market→fast; concept/personal/english→standard
  5. "standard"

Duration policy: the plan target is a CEILING. No hold-last-beat padding by default;
only an outro / brand card ≤ OUTRO_MAX_SEC may follow the last line.
Numbers are design targets (see docs/PACING.md); 5.3/5.8 字/秒 are assumptions
calibrated just above Chinese TV-news pace (240–300 字/分), not measured benchmarks.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

OUTRO_MAX_SEC = 1.5

PROFILES: dict[str, dict[str, Any]] = {
    "fast": {
        "cps": 5.8,                 # target articulation 字/秒 (estimate + gate)
        "edgeRate": "+20%",
        "stepaudioSpeed": 1.18,
        "elevenlabsSpeed": 1.15,
        "lineGapSec": 0.15,         # between lines inside one shot
        "enterSec": 0.12, "exitSec": 0.08, "settleSec": 0.10,   # per-shot overhead 0.30
        "maxPauseSec": 0.25,        # pause_trim: intra-line silences longer than this shrink
        "keepPauseSec": 0.12,       # … to this
        "beatPauseSec": 0.45,       # extra hold after a line marked beat:true
        "lineMaxChars": 20,         # WARN above (FAIL stays at dialogue_check.MAX_CHARS)
        "maxShotSec": 3.0,
        "changesPer10s": 4.0,
        "bpm": 128,
    },
    "standard": {
        "cps": 5.3,
        "edgeRate": "+10%",
        "stepaudioSpeed": 1.10,
        "elevenlabsSpeed": 1.08,
        "lineGapSec": 0.25,
        "enterSec": 0.15, "exitSec": 0.10, "settleSec": 0.15,   # 0.40
        "maxPauseSec": 0.35,
        "keepPauseSec": 0.18,
        "beatPauseSec": 0.6,
        "lineMaxChars": 26,
        "maxShotSec": 4.5,
        "changesPer10s": 2.5,
        "bpm": 110,
    },
    "calm": {
        "cps": 4.6,
        "edgeRate": "+0%",
        "stepaudioSpeed": 1.0,
        "elevenlabsSpeed": 1.0,
        "lineGapSec": 0.45,
        "enterSec": 0.25, "exitSec": 0.15, "settleSec": 0.2,    # 0.60
        "maxPauseSec": 0.5,
        "keepPauseSec": 0.25,
        "beatPauseSec": 0.8,
        "lineMaxChars": 32,
        "maxShotSec": 6.0,
        "changesPer10s": 1.5,
        "bpm": 90,
    },
}
DEFAULT = "standard"

CONTENT_TYPE_PACING = {
    "market": "fast",
    "concept": "standard",
    "personal": "standard",
    "english": "standard",
}
# same aliases as elevenlabs_dialogue.CONTENT_TYPE_ALIASES (kept local: no provider import)
_CT_ALIASES = {
    "macro": "market", "news": "market", "bonds": "market", "rates": "market", "index": "market",
    "财经新闻": "market", "市场": "market", "宏观": "market",
    "explainer": "concept", "teaching": "concept", "bilingual": "concept", "概念": "concept",
    "lifestyle": "personal", "budgeting": "personal", "saving": "personal", "personal-finance": "personal",
    "理财习惯": "personal", "个人理财": "personal",
    "investing": "english", "strategy": "english", "dca": "english", "diversification": "english",
    "en": "english", "english-heavy": "english",
}

# Pacing gate thresholds (standard values; cps/shot/changes scale with the profile).
# (warn, fail) — direction given by key suffix: *_min → below is bad, *_max → above is bad.
def gate_thresholds(name: str) -> dict[str, tuple[float, float]]:
    p = PROFILES[normalize(name) or DEFAULT]
    cps = p["cps"]
    return {
        "articulation_cps_min": (round(cps - 0.3, 2), round(cps - 0.8, 2)),
        "overall_cps_min": (round(cps - 1.0, 2), round(cps - 1.5, 2)),
        "speech_ratio_min": (0.85, 0.75),
        "inter_line_gap_max": (0.6 if name != "calm" else 0.8, 1.0 if name != "calm" else 1.3),
        "intra_pause_max": (0.45, 0.8),
        "tail_silence_max": (OUTRO_MAX_SEC, 3.0),
        "pad_max": (1.0, 2.0),
        "shot_max_max": (p["maxShotSec"], round(p["maxShotSec"] * 1.5, 2)),
        "frozen_max_max": (2.5, 4.0),
        "changes_per_10s_min": (p["changesPer10s"], 1.0),
        "first_vo_max": (0.3, 1.0),
        "hook_end_max": (3.0, 5.0),
    }


def normalize(name: Any) -> str | None:
    if name is None:
        return None
    s = str(name).strip().lower()
    return s if s in PROFILES else None


def normalize_content_type(ct: Any) -> str | None:
    if ct is None:
        return None
    s = str(ct).strip().lower()
    if not s:
        return None
    s = _CT_ALIASES.get(s, s)
    return s if s in CONTENT_TYPE_PACING else None


def load_plan(project: Path | None) -> dict[str, Any]:
    if project is None:
        return {}
    project = Path(project)
    for rel in ("content/plan.json", "plan.json"):
        p = project / rel
        if p.is_file():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(d, dict):
                    return d
            except (OSError, ValueError):
                pass
    return {}


def resolve(project: Path | None = None, explicit: str | None = None,
            plan: dict[str, Any] | None = None) -> tuple[str, str]:
    """Return (profile_name, source)."""
    n = normalize(explicit)
    if explicit and not n:
        raise ValueError(f"unknown pacing profile {explicit!r} (fast|standard|calm)")
    if n:
        return n, "explicit"
    plan = plan if plan is not None else load_plan(project)
    n = normalize(plan.get("pacing"))
    if n:
        return n, "plan.pacing"
    n = normalize(os.environ.get("LEMO_PACING"))
    if n:
        return n, "env LEMO_PACING"
    ct = normalize_content_type(plan.get("content_type") or plan.get("contentType"))
    if ct:
        return CONTENT_TYPE_PACING[ct], f"content_type={ct}"
    return DEFAULT, "default"


def profile(project: Path | None = None, explicit: str | None = None,
            plan: dict[str, Any] | None = None) -> dict[str, Any]:
    name, src = resolve(project, explicit, plan)
    return {"name": name, "source": src, **PROFILES[name]}


def shot_overhead(p: dict[str, Any]) -> float:
    return float(p["enterSec"]) + float(p["exitSec"]) + float(p["settleSec"])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="print the resolved pacing profile")
    ap.add_argument("--project")
    ap.add_argument("--pacing")
    a = ap.parse_args()
    print(json.dumps(profile(Path(a.project) if a.project else None, a.pacing), ensure_ascii=False, indent=1))
