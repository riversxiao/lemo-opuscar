"""No-network tests for ElevenLabs Text-to-Dialogue provider."""
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


def pcm_tone(sec=0.8, sr=24000, f0=160.0) -> bytes:
    t = np.arange(int(sec * sr)) / sr
    a = (0.25 * np.sin(2 * np.pi * f0 * t) * 32767).astype("<i2")
    return a.tobytes()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        payload = json.loads(body.decode("utf-8"))
        HITS.append((self.path, {k.lower(): v for k, v in dict(self.headers).items()}, payload))
        assert self.headers.get("xi-api-key") == "el-dlg-mock"
        assert self.path.startswith("/v1/text-to-dialogue")
        assert "output_format=pcm_24000" in self.path
        assert isinstance(payload.get("inputs"), list) and payload["inputs"]
        for inp in payload["inputs"]:
            assert "text" in inp and "voice_id" in inp
        # Prefer eleven_v4; if client sends eleven_v4 we accept; eleven_v3 also ok
        assert payload.get("model_id") in ("eleven_v4", "eleven_v3")
        n = len(payload["inputs"])
        self.send_response(200)
        self.send_header("Content-Type", "audio/pcm")
        self.end_headers()
        self.wfile.write(pcm_tone(sec=0.5 * n))


# --- pure helpers (no key) ---
os.environ.pop("ELEVENLABS_API_KEY", None)
os.environ.pop("ELEVEN_API_KEY", None)
from providers import elevenlabs_dialogue as D  # noqa: E402
from providers.runtime import probe_elevenlabs_dialogue, list_statuses  # noqa: E402

st = probe_elevenlabs_dialogue()
assert st.state == "needs-key" and "ELEVENLABS_API_KEY" in st.detail, st

# voice map + chunking
os.environ["ELEVENLABS_VOICE_HOST"] = "voiceHostAAA"
os.environ["ELEVENLABS_VOICE_GUEST"] = "voiceGuestBBB"
os.environ["ELEVENLABS_VOICE_MAP"] = json.dumps({"narrator": "voiceNarrCCC"})
turns = D.normalize_turns([
    {"id": "L01", "speaker": "host", "text": "你好。"},
    {"id": "L02", "speaker_id": "guest", "text": "你好啊。"},
    {"id": "L03", "role": "narrator", "text": "旁白。", "say": "旁白说。"},
    {"id": "L04", "speaker": "host", "text": "继续。", "voice_id": "overrideVoice"},
])
assert turns[0]["voice_id"] == "voiceHostAAA"
assert turns[1]["voice_id"] == "voiceGuestBBB"
assert turns[2]["voice_id"] == "voiceNarrCCC" and turns[2]["text"] == "旁白说。"
assert turns[3]["voice_id"] == "overrideVoice"

# chunk by char budget
long = "字" * 1200
chunks = D.chunk_turns([
    {"id": "A", "speaker": "h", "text": long, "voice_id": "v1"},
    {"id": "B", "speaker": "g", "text": long, "voice_id": "v2"},
])
assert len(chunks) == 2 and chunks[0][0]["id"] == "A"

# >10 unique voices forces a new chunk earlier
many = [{"id": f"L{i}", "speaker": f"s{i}", "text": "短", "voice_id": f"v{i}"} for i in range(12)]
ch = D.chunk_turns(many)
assert len(ch) == 2 and len(ch[0]) == 10 and len(ch[1]) == 2

try:
    D.chunk_turns([{"id": "X", "speaker": "h", "text": "超" * 2001, "voice_id": "v"}])
    raise AssertionError("expected oversize turn error")
except D.DialogueError:
    pass

# synthesize without key → SystemExit
try:
    D.synthesize([{"id": "L01", "speaker": "host", "text": "测"}], tempfile.mkdtemp())
    raise AssertionError("expected SystemExit")
except SystemExit as e:
    assert "ELEVENLABS_API_KEY" in str(e)

# --- mock server ---
srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["ELEVENLABS_API_KEY"] = "el-dlg-mock"
os.environ["LEMO_TTS_ELEVENLABS_BASE"] = f"http://127.0.0.1:{srv.server_port}/v1"
os.environ["LEMO_TTS_ELEVENLABS_DIALOGUE_MODEL"] = "eleven_v4"
assert probe_elevenlabs_dialogue().state == "ready"

tmp = Path(tempfile.mkdtemp())
lines = [
    {"id": "L01", "speaker": "host", "text": "第一句。"},
    {"id": "L02", "speaker": "guest", "text": "第二句。"},
]
dur = D.synthesize(lines, str(tmp / "v"))
assert set(dur) == {"L01", "L02"} and all(d > 0.1 for d in dur.values()), dur
assert (tmp / "v" / "dialogue.wav").is_file()
assert (tmp / "v" / "L01.wav").is_file() and (tmp / "v" / "dur.json").is_file()
man = json.loads((tmp / "v" / "dialogue_manifest.json").read_text())
assert man["provider"] == "elevenlabs-dialogue" and man["requests"] == 1
assert man["turns"][0]["speaker"] == "host" and man["turns"][1]["end"] > man["turns"][0]["start"]
a, sr = sf.read(tmp / "v" / "dialogue.wav")
assert sr == 24000 and len(a) > 1000
assert len(HITS) == 1
assert HITS[0][1]["xi-api-key"] == "el-dlg-mock"
assert HITS[0][2]["model_id"] == "eleven_v4"
assert [x["voice_id"] for x in HITS[0][2]["inputs"]] == ["voiceHostAAA", "voiceGuestBBB"]

# model fallback: force primary to fail once
HITS.clear()


class H2(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
        HITS.append(body.get("model_id"))
        if body.get("model_id") == "eleven_v4":
            self.send_response(422)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"detail":[{"msg":"model eleven_v4 not available"}]}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/pcm")
        self.end_headers()
        self.wfile.write(pcm_tone(sec=0.4))


srv2 = ThreadingHTTPServer(("127.0.0.1", 0), H2)
threading.Thread(target=srv2.serve_forever, daemon=True).start()
os.environ["LEMO_TTS_ELEVENLABS_BASE"] = f"http://127.0.0.1:{srv2.server_port}/v1"
raw, _, used = D.post_dialogue_with_fallback(
    [{"text": "hi", "voice_id": "voiceHostAAA"}], model="eleven_v4"
)
assert used == "eleven_v3" and HITS == ["eleven_v4", "eleven_v3"], (used, HITS)

# listed in --list
ids = [s.id for s in list_statuses()]
assert "elevenlabs-dialogue" in ids and "elevenlabs" in ids

import subprocess
r = subprocess.run(
    [sys.executable, str(ROOT / "core" / "tts" / "tts_router.py"), "--list", "--json"],
    capture_output=True, text=True, env={**os.environ},
)
by = {p["id"]: p for p in json.loads(r.stdout)["providers"]}
assert by["elevenlabs-dialogue"]["ready"] is True

# router without key
os.environ.pop("ELEVENLABS_API_KEY", None)
os.environ.pop("ELEVEN_API_KEY", None)
lines_path = tmp / "dlg.json"
lines_path.write_text(json.dumps(lines), encoding="utf-8")
r2 = subprocess.run(
    [sys.executable, str(ROOT / "core" / "tts" / "tts_router.py"),
     str(lines_path), str(tmp / "out2"), "--provider", "elevenlabs-dialogue", "--fallback", ""],
    capture_output=True, text=True,
    env={k: v for k, v in os.environ.items() if k not in ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY")},
)
assert r2.returncode != 0 and "needs-key" in (r2.stderr + r2.stdout)

print("elevenlabs_dialogue mock OK")
