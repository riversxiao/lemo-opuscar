"""No-network tests for the ElevenLabs TTS provider.

Spins a local mock of the ElevenLabs TTS API on 127.0.0.1 and points
WORDFILM_TTS_ELEVENLABS_BASE at it; a fake key is used. Asserts: missing-key
probe/state, xi-api-key header, multilingual model, pcm_24000 decode → wavs.
"""
import io
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "core" / "tts"))

HITS: list[tuple] = []


def pcm_tone(f0=140.0, sec=0.6, sr=24000) -> bytes:
    t = np.arange(int(sec * sr)) / sr
    a = (0.3 * np.sin(2 * np.pi * f0 * t) * 32767).astype("<i2")
    return a.tobytes()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        payload = json.loads(body.decode("utf-8"))
        HITS.append((self.path, dict(self.headers), payload))
        assert self.headers.get("xi-api-key") == "el-mock-key"
        assert "/text-to-speech/" in self.path
        assert "output_format=pcm_24000" in self.path
        assert payload.get("model_id") == "eleven_multilingual_v2"
        assert payload.get("text")
        raw = pcm_tone()
        self.send_response(200)
        self.send_header("Content-Type", "audio/pcm")
        self.end_headers()
        self.wfile.write(raw)


# --- missing key ---
os.environ.pop("ELEVENLABS_API_KEY", None)
os.environ.pop("ELEVEN_API_KEY", None)
from providers.runtime import probe_elevenlabs  # noqa: E402
from providers import elevenlabs as E  # noqa: E402

st = probe_elevenlabs()
assert st.state == "needs-key" and st.as_dict()["ready"] is False and "ELEVENLABS_API_KEY" in st.detail, st

try:
    E.synthesize([{"id": "L01", "text": "测试"}], tempfile.mkdtemp())
    raise AssertionError("expected SystemExit without key")
except SystemExit as e:
    assert "ELEVENLABS_API_KEY" in str(e), e

# --- ready + synthesize via local mock ---
srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["ELEVENLABS_API_KEY"] = "el-mock-key"
os.environ["WORDFILM_TTS_ELEVENLABS_BASE"] = f"http://127.0.0.1:{srv.server_port}/v1"
os.environ.pop("ELEVEN_API_KEY", None)

assert probe_elevenlabs().state == "ready"
# alias works
os.environ.pop("ELEVENLABS_API_KEY")
os.environ["ELEVEN_API_KEY"] = "el-mock-key"
assert probe_elevenlabs().state == "ready"
os.environ["ELEVENLABS_API_KEY"] = "el-mock-key"

tmp = Path(tempfile.mkdtemp())
lines = [{"id": "L01", "text": "政策利率降到零。"}, {"id": "L02", "text": "钱却还是不动。", "say": "钱却还是不动呀。"}]
dur = E.synthesize(lines, str(tmp / "v"))
assert set(dur) == {"L01", "L02"} and all(d > 0.3 for d in dur.values()), dur
assert (tmp / "v" / "L01.wav").is_file() and (tmp / "v" / "dur.json").is_file()
a, sr = sf.read(tmp / "v" / "L01.wav")
assert sr == 24000 and a.ndim == 1 and len(a) > 1000
assert len(HITS) == 2
assert {k.lower(): v for k, v in HITS[0][1].items()}.get("xi-api-key") == "el-mock-key"
assert "21m00Tcm4TlvDq8ikWAM" in HITS[0][0]  # default voice in path
assert HITS[1][2]["text"] == "钱却还是不动呀。"  # say overrides text

# custom voice via env
HITS.clear()
os.environ["ELEVENLABS_VOICE_ID"] = "customVoiceIdXYZ"
dur2 = E.synthesize([{"id": "L03", "text": "自定义音色。"}], str(tmp / "v2"))
assert "customVoiceIdXYZ" in HITS[0][0], HITS[0][0]
assert dur2["L03"] > 0.3

# list_statuses includes elevenlabs
from providers.runtime import list_statuses  # noqa: E402
ids = [s.id for s in list_statuses()]
assert "elevenlabs" in ids and ids.index("elevenlabs") > ids.index("stepaudio")

# tts_router --list --json surfaces it
import subprocess
r = subprocess.run(
    [sys.executable, str(ROOT / "core" / "tts" / "tts_router.py"), "--list", "--json"],
    capture_output=True, text=True, env={**os.environ},
)
assert r.returncode == 0, r.stderr
data = json.loads(r.stdout)
by = {p["id"]: p for p in data["providers"]}
assert by["elevenlabs"]["ready"] is True
os.environ.pop("ELEVENLABS_API_KEY")
os.environ.pop("ELEVEN_API_KEY", None)
r2 = subprocess.run(
    [sys.executable, str(ROOT / "core" / "tts" / "tts_router.py"), "--list", "--json"],
    capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k not in ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY")},
)
by2 = {p["id"]: p for p in json.loads(r2.stdout)["providers"]}
assert by2["elevenlabs"]["state"] == "needs-key" and by2["elevenlabs"]["ready"] is False

# router refuses synthesize without key
(tmp / "lines.json").write_text(json.dumps([{"id": "L01", "text": "测"}]), encoding="utf-8")
r3 = subprocess.run(
    [sys.executable, str(ROOT / "core" / "tts" / "tts_router.py"),
     str(tmp / "lines.json"), str(tmp / "out"), "--provider", "elevenlabs", "--fallback", ""],
    capture_output=True, text=True,
    env={k: v for k, v in os.environ.items() if k not in ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY")},
)
assert r3.returncode != 0 and "needs-key" in (r3.stderr + r3.stdout) and "ELEVENLABS_API_KEY" in (r3.stderr + r3.stdout)

print("elevenlabs mock OK")
