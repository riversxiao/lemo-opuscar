"""Shared runtime helpers for TTS providers (Python selection + readiness probes)."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from . import env

HERE = os.path.dirname(os.path.abspath(__file__))
TTS_DIR = os.path.abspath(os.path.join(HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(TTS_DIR, "..", ".."))


def resolve_voice_python(*, need_kokoro: bool = False) -> str:
    """Pick an interpreter that can run the requested provider.

    Order: $WORDFILM_TTS_PYTHON (or $LEMO_TTS_PYTHON) → repo .venv-voice (when need_kokoro or always preferred
    if present for kokoro) → sys.executable.
    """
    py = env("TTS_PYTHON").strip()
    if py and os.path.isfile(py) and os.access(py, os.X_OK):
        return py
    venv_py = os.path.join(REPO_ROOT, ".venv-voice", "bin", "python")
    if need_kokoro and os.path.isfile(venv_py) and os.access(venv_py, os.X_OK):
        return venv_py
    if need_kokoro:
        # fall through to sys.executable; probe will report deps-missing if broken
        return sys.executable
    # edge: system python usually has edge-tts; venv also has it after install
    if os.path.isfile(venv_py) and os.access(venv_py, os.X_OK):
        # Prefer sys.executable for edge when it already has edge_tts (faster cold start)
        if _module_in_python(sys.executable, "edge_tts"):
            return sys.executable
        return venv_py
    return sys.executable


def _module_in_python(python: str, module: str) -> bool:
    if python == sys.executable:
        return importlib.util.find_spec(module) is not None
    try:
        r = subprocess.run(
            [python, "-c", f"import {module}"],
            capture_output=True,
            timeout=20,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@dataclass
class ProviderStatus:
    id: str
    state: str  # ready | deps-missing | needs-server | stub
    detail: str
    network: str  # required | offline | optional-http

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "detail": self.detail,
            "network": self.network,
            "ready": self.state == "ready",
        }


def probe_edge() -> ProviderStatus:
    py = resolve_voice_python(need_kokoro=False)
    if _module_in_python(py, "edge_tts"):
        return ProviderStatus(
            "edge",
            "ready",
            f"edge-tts via {py} → tts_zh.py (Yunxi/Xiaoxiao)",
            "required",
        )
    return ProviderStatus(
        "edge",
        "deps-missing",
        "edge-tts not importable; pip install edge-tts or use .venv-voice",
        "required",
    )


def probe_kokoro() -> ProviderStatus:
    model = os.path.join(TTS_DIR, "kokoro-v1.0.onnx")
    voices = os.path.join(TTS_DIR, "voices-v1.0.bin")
    if not (os.path.isfile(model) and os.path.isfile(voices)):
        return ProviderStatus(
            "kokoro",
            "deps-missing",
            "kokoro-v1.0.onnx / voices-v1.0.bin missing (sh tools/fetch.sh voice)",
            "offline",
        )
    py = resolve_voice_python(need_kokoro=True)
    if not _module_in_python(py, "kokoro_onnx"):
        return ProviderStatus(
            "kokoro",
            "deps-missing",
            "kokoro-onnx missing; create .venv-voice "
            "(uv venv .venv-voice --python 3.12 && uv pip install --python .venv-voice/bin/python "
            "kokoro-onnx soundfile numpy) or set WORDFILM_TTS_PYTHON",
            "offline",
        )
    return ProviderStatus(
        "kokoro",
        "ready",
        f"kokoro-onnx via {py} → tts.py (lang=cmn / zf_* voices)",
        "offline",
    )


def probe_qwen3() -> ProviderStatus:
    base = env("TTS_QWEN3_BASE", "").strip()
    if not base:
        return ProviderStatus(
            "qwen3",
            "needs-server",
            "set WORDFILM_TTS_QWEN3_BASE to an OpenAI-compatible /v1 speech server "
            "(no API key invented here; optional WORDFILM_TTS_QWEN3_API_KEY)",
            "optional-http",
        )
    return ProviderStatus(
        "qwen3",
        "ready",
        f"HTTP client → {base} (WORDFILM_TTS_QWEN3_MODEL / optional API key)",
        "optional-http",
    )


def probe_omnivoice() -> ProviderStatus:
    base = env("TTS_OMNIVOICE_BASE", "").strip()
    if not base:
        return ProviderStatus(
            "omnivoice",
            "needs-server",
            "set WORDFILM_TTS_OMNIVOICE_BASE (e.g. http://127.0.0.1:8880/v1); "
            "optional WORDFILM_TTS_OMNIVOICE_API_KEY",
            "optional-http",
        )
    return ProviderStatus(
        "omnivoice",
        "ready",
        f"HTTP client → {base}",
        "optional-http",
    )


PROBES = {
    "edge": probe_edge,
    "kokoro": probe_kokoro,
    "qwen3": probe_qwen3,
    "omnivoice": probe_omnivoice,
}


def probe_stepaudio() -> ProviderStatus:
    """StepFun stepaudio-3-gen-preview (limited-time free). Explicit opt-in only (not in auto)."""
    if not (os.environ.get("STEPFUN_API_KEY") or os.environ.get("STEP_API_KEY")):
        return ProviderStatus("stepaudio", "needs-key",
                              "set STEPFUN_API_KEY (StepFun free preview stepaudio-3-gen-preview; "
                              "paid /audio/speech TTS is never called)", "cloud")
    return ProviderStatus("stepaudio", "ready",
                          "StepFun /v1/audio/generate stepaudio-3-gen-preview (限时免费 preview)", "cloud")


PROBES["stepaudio"] = probe_stepaudio


def probe_elevenlabs() -> ProviderStatus:
    """ElevenLabs multilingual TTS. Explicit opt-in only (not in auto)."""
    if not (os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_API_KEY")):
        return ProviderStatus(
            "elevenlabs",
            "needs-key",
            "set ELEVENLABS_API_KEY (alias ELEVEN_API_KEY); voice via ELEVENLABS_VOICE_ID "
            "(default 21m00Tcm4TlvDq8ikWAM / Rachel) + model eleven_multilingual_v2",
            "cloud",
        )
    return ProviderStatus(
        "elevenlabs",
        "ready",
        "ElevenLabs /v1/text-to-speech (eleven_multilingual_v2; voice ELEVENLABS_VOICE_ID)",
        "cloud",
    )


PROBES["elevenlabs"] = probe_elevenlabs


def probe_elevenlabs_dialogue() -> ProviderStatus:
    """ElevenLabs Text-to-Dialogue (multi-speaker). Explicit opt-in only."""
    if not (os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_API_KEY")):
        return ProviderStatus(
            "elevenlabs-dialogue",
            "needs-key",
            "set ELEVENLABS_API_KEY; multi-speaker POST /v1/text-to-dialogue "
            "(model eleven_v4→eleven_v3); map voices via ELEVENLABS_VOICE_HOST/_GUEST "
            "or ELEVENLABS_VOICE_MAP JSON",
            "cloud",
        )
    return ProviderStatus(
        "elevenlabs-dialogue",
        "ready",
        "ElevenLabs /v1/text-to-dialogue (multi-speaker; ≤10 voices, ≤2000 chars/req)",
        "cloud",
    )


PROBES["elevenlabs-dialogue"] = probe_elevenlabs_dialogue


def list_statuses() -> list[ProviderStatus]:
    return [PROBES[name]() for name in ("edge", "kokoro", "qwen3", "omnivoice", "stepaudio", "elevenlabs", "elevenlabs-dialogue")]


def ready_providers(prefer: list[str] | None = None) -> list[str]:
    order = prefer or ["edge", "kokoro", "qwen3", "omnivoice"]
    out = []
    for name in order:
        st = PROBES[name]()
        if st.state == "ready":
            out.append(name)
    return out
