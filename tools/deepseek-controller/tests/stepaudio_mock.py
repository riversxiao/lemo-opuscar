"""No-network tests for the StepAudio provider + music bed source.

Spins a local mock of the StepFun API on 127.0.0.1 and points LEMO_TTS_STEPAUDIO_BASE
at it; a fake key is used. Asserts: only free preview models/routes are hit, the
paid /audio/speech route is never called, retakes pick the closest pitch, 402 stops,
music bed is cut/faded/RMS-matched and cached.
"""
import base64, io, json, os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import numpy as np, soundfile as sf

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "core" / "tts"))
sys.path.insert(0, str(ROOT / "tools" / "deepseek-controller"))
HITS = []
STATE = {"gen": 0, "mode": "ok", "polls": 0}


def tone(f0, sec=1.2, sr=24000):
    t = np.arange(int(sec * sr)) / sr
    a = 0.3 * np.sin(2 * np.pi * f0 * t) + 0.1 * np.sin(4 * np.pi * f0 * t)
    b = io.BytesIO(); sf.write(b, a.astype(np.float32), sr, format="WAV"); return b.getvalue()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        HITS.append(("GET", self.path, None))
        self._send(200, json.dumps({"balance": 15.0, "total_cash_balance": 0, "total_voucher_balance": 15.0}).encode())

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        HITS.append(("POST", self.path, body))
        assert self.headers["Authorization"] == "Bearer sk-mock"
        if self.path.endswith("/audio/generate"):
            if STATE["mode"] == "402":
                return self._send(402, b'{"error":{"type":"insufficient_credit"}}')
            STATE["gen"] += 1
            text = body["scripts"][0]["text"]
            # line "B" drifts high on its first take, then comes back in range
            f0 = 240 if ("B" in text and STATE["gen"] <= 3) else 140
            return self._send(200, tone(f0), "audio/wav")
        if self.path.endswith("/audio/music/submit"):
            return self._send(200, b'{"task_id":"t-1"}')
        if self.path.endswith("/audio/music/query"):
            STATE["polls"] += 1
            if STATE["polls"] < 2:
                return self._send(200, b'{"status":"RUNNING"}')
            sr = 48000; t = np.arange(int(5 * sr)) / sr
            a = np.stack([0.5 * np.sin(2 * np.pi * 220 * t)] * 2, 1).astype(np.float32)
            b = io.BytesIO(); sf.write(b, a, sr, format="WAV")
            return self._send(200, json.dumps({"status": "SUCCESS", "audio": base64.b64encode(b.getvalue()).decode()}).encode())
        self._send(404, b"{}")


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ.update({"LEMO_TTS_STEPAUDIO_BASE": f"http://127.0.0.1:{srv.server_port}/v1", "STEPFUN_API_KEY": "sk-mock"})
os.environ.pop("STEP_API_KEY", None)
from providers import stepaudio as S  # noqa: E402
S.MIN_INTERVAL = 0.0

tmp = Path(tempfile.mkdtemp())
lines = [{"id": "L01", "text": "A一"}, {"id": "L02", "text": "B二", "say": "B二说"}, {"id": "L03", "text": "A三"}]
dur = S.synthesize(lines, str(tmp / "v"), voice="zh-CN-YunxiNeural")
meta = json.loads((tmp / "v" / "stepaudio_meta.json").read_text())
assert set(dur) == {"L01", "L02", "L03"} and all(d > 1.0 for d in dur.values()), dur
assert json.loads((tmp / "v" / "dur.json").read_text()) == dur
assert meta["consistency"]["lines"]["L02"]["takes"] >= 2 and abs(meta["consistency"]["lines"]["L02"]["f0"] - 140) < 8, meta
assert "Yunxi" not in meta["role"]
gens = [b for m, p, b in HITS if p.endswith("/audio/generate")]
assert all(b["model"] == "stepaudio-3-gen-preview" and "voice" not in b for b in gens)
assert any("B二说" in b["scripts"][0]["text"] for b in gens), "say must be voiced"
assert not any("/audio/speech" in p or "asr" in p for _, p, _ in HITS)
# refusing paid models / routes
for bad in (lambda: S._post("/audio/speech", {"model": "stepaudio-3-gen-preview"}),
            lambda: S._post("/audio/generate", {"model": "stepaudio-3-tts"})):
    try: bad(); raise AssertionError("paid route/model not refused")
    except S.StepFunError: pass
# 402 stops (no silent fallback)
STATE["mode"] = "402"
try:
    S.synthesize([{"id": "L01", "text": "A"}], str(tmp / "v402")); raise AssertionError("402 not fatal")
except SystemExit as e:
    assert "402" in str(e)
STATE["mode"] = "ok"
# runtime probe
from providers.runtime import probe_stepaudio  # noqa: E402
assert probe_stepaudio().state == "ready"
os.environ.pop("STEPFUN_API_KEY"); assert probe_stepaudio().state == "needs-key"; os.environ["STEPFUN_API_KEY"] = "sk-mock"

# music bed source
import music_bed as MB  # noqa: E402
proj = tmp / "film"; proj.mkdir()
bed, m = MB.fetch_stepaudio_bed(proj, 12.0)
a, sr = sf.read(str(bed))
assert sr == MB.SR and abs(len(a) / sr - 12.0) < 0.01 and m["loops"] >= 1, m
assert abs(20 * np.log10(np.sqrt(np.mean(a ** 2))) - MB.BED_RMS_DB) < 0.5
assert np.abs(a[-10:]).max() < 1e-3, "fade-out missing"
subs = [b for _, p, b in HITS if p.endswith("/music/submit")]
assert len(subs) == 1 and subs[0]["model_id"] == "stepaudio-3-music-preview" and subs[0]["instrumental"] is True
bed2, m2 = MB.fetch_stepaudio_bed(proj, 12.0)
assert m2["cached"] and len([1 for _, p, _ in HITS if p.endswith("/music/submit")]) == 1, "cache not used"
print("stepaudio mock OK", len(HITS), "requests")
srv.shutdown()
