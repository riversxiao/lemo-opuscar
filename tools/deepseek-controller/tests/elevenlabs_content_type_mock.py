"""No-network tests: elevenlabs-dialogue guest voice chosen by content type (Tex host)."""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
CTL = ROOT / "tools" / "deepseek-controller"
sys.path.insert(0, str(ROOT / "core" / "tts"))

for k in ("ELEVENLABS_API_KEY", "ELEVEN_API_KEY", "ELEVENLABS_VOICE_HOST", "ELEVENLABS_VOICE_GUEST",
          "ELEVENLABS_VOICE_COHOST", "ELEVENLABS_VOICE_MAP", "ELEVENLABS_VOICE_MAP_FILE",
          "LEMO_TTS_ELEVENLABS_CONTENT_TYPE"):
    os.environ.pop(k, None)

from providers import elevenlabs_dialogue as D  # noqa: E402

TEX, LINDA, LADAISY, SHUSITA, JOAN = (
    "TKaUqol7GKx4m7enpCpP", "t5SIDRTVMdbNUqrSAycs", "8RCmdqih4CKjJ7Bd3ZxT",
    "iCrb0E1mQG2baVhfLIGF", "qgrPcGqsZG6TpPzso4fK",
)
n = 0


def check(cond, msg):
    global n
    assert cond, msg
    n += 1


# 1) canonical mapping + default
check(D.guest_voice_for("market") == LINDA, "market→Linda")
check(D.guest_voice_for("concept") == LADAISY, "concept→Ladaisy")
check(D.guest_voice_for("personal") == SHUSITA, "personal→Shusita")
check(D.guest_voice_for("english") == JOAN, "english→Joan")
check(D.guest_voice_for(None) == LINDA and D.guest_voice_for("") == LINDA, "default→Linda")

# 2) aliases (case-insensitive, zh)
for alias, want in [("Bonds", LINDA), ("macro", LINDA), ("财经新闻", LINDA), ("explainer", LADAISY),
                    ("理财习惯", SHUSITA), ("budgeting", SHUSITA), ("DCA", JOAN), ("diversification", JOAN)]:
    check(D.guest_voice_for(alias) == want, f"alias {alias}")

# 3) unknown type → error
try:
    D.normalize_content_type("crypto-memes")
    raise AssertionError("expected DialogueError")
except D.DialogueError as e:
    check("market" in str(e), "unknown type lists valid values")

# 4) resolve: host default Tex; guest by content type; cohost alias
check(D.resolve_voice("host", None, {}) == TEX, "host default Tex")
check(D.resolve_voice("guest", None, {}) == LINDA, "guest default Linda")
check(D.resolve_voice("guest", None, {}, "personal") == SHUSITA, "guest personal")
check(D.resolve_voice("cohost", None, {}, "english") == JOAN, "cohost english")

# 5) env content type used when no explicit type; explicit arg beats env
os.environ["LEMO_TTS_ELEVENLABS_CONTENT_TYPE"] = "concept"
check(D.resolve_voice("guest", None, {}) == LADAISY, "env content type")
check(D.resolve_voice("guest", None, {}, "english") == JOAN, "explicit beats env")
os.environ.pop("LEMO_TTS_ELEVENLABS_CONTENT_TYPE")

# 6) overrides: ELEVENLABS_VOICE_GUEST > content type; voice map > env; line voice_id > all
os.environ["ELEVENLABS_VOICE_GUEST"] = "guestOverrideX"
check(D.resolve_voice("guest", None, {}, "personal") == "guestOverrideX", "VOICE_GUEST overrides")
check(D.resolve_voice("guest", None, {"guest": "mapG"}, "personal") == "mapG", "map beats env")
check(D.resolve_voice("guest", "lineVoice", {"guest": "mapG"}, "personal") == "lineVoice", "line voice wins")
os.environ.pop("ELEVENLABS_VOICE_GUEST")
os.environ["ELEVENLABS_VOICE_HOST"] = "hostOverrideY"
check(D.resolve_voice("host", None, {}) == "hostOverrideY", "VOICE_HOST overrides Tex")
os.environ.pop("ELEVENLABS_VOICE_HOST")

# 7) normalize_turns threads content type
turns = D.normalize_turns([{"id": "L01", "speaker": "host", "text": "Hi."},
                           {"id": "L02", "speaker": "guest", "text": "你好。"}], {}, "english")
check([t["voice_id"] for t in turns] == [TEX, JOAN], "normalize_turns english")

# --- mock API: end-to-end via provider, tts_router CLI, and run_tts plan.json ---
HITS: list = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
        HITS.append([x["voice_id"] for x in body["inputs"]])
        t = np.arange(int(0.5 * len(body["inputs"]) * 24000)) / 24000
        self.send_response(200)
        self.send_header("Content-Type", "audio/pcm")
        self.end_headers()
        self.wfile.write((0.25 * np.sin(2 * np.pi * 160 * t) * 32767).astype("<i2").tobytes())


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["ELEVENLABS_API_KEY"] = "el-ct-mock"
os.environ["LEMO_TTS_ELEVENLABS_BASE"] = f"http://127.0.0.1:{srv.server_port}/v1"
os.environ["LEMO_TTS_ELEVENLABS_DIALOGUE_MODEL"] = "eleven_v4"

tmp = Path(tempfile.mkdtemp())
lines = [{"id": "L01", "speaker": "host", "text": "Quick one."}, {"id": "L02", "speaker": "guest", "text": "中文就是。"}]

D.synthesize(lines, str(tmp / "a"), content_type="personal")
man = json.loads((tmp / "a" / "dialogue_manifest.json").read_text())
check(HITS[-1] == [TEX, SHUSITA] and man["contentType"] == "personal", "provider content_type → Shusita")

try:
    D.synthesize(lines, str(tmp / "bad"), content_type="nope")
    raise AssertionError("expected SystemExit")
except SystemExit as e:
    check("unknown content_type" in str(e), "provider rejects unknown type")

lp = tmp / "lines.json"
lp.write_text(json.dumps(lines, ensure_ascii=False), encoding="utf-8")
r = subprocess.run([sys.executable, str(ROOT / "core" / "tts" / "tts_router.py"), str(lp), str(tmp / "b"),
                    "--provider", "elevenlabs-dialogue", "--fallback", "", "--content-type", "concept"],
                   capture_output=True, text=True, env={**os.environ})
check(r.returncode == 0 and HITS[-1] == [TEX, LADAISY], f"router --content-type concept: {r.stderr[-300:]}")

r = subprocess.run([sys.executable, str(ROOT / "core" / "tts" / "tts_router.py"), str(lp), str(tmp / "c"),
                    "--provider", "elevenlabs-dialogue", "--fallback", ""],
                   capture_output=True, text=True, env={**os.environ})
check(r.returncode == 0 and HITS[-1] == [TEX, LINDA], "router default → Linda")

# run_tts reads plan.json content_type (config field); explicit arg beats it
sys.path.insert(0, str(CTL))
from run_tts import run_tts  # noqa: E402

proj = tmp / "proj"
proj.mkdir()
(proj / "plan.json").write_text(json.dumps({"content_type": "english"}), encoding="utf-8")
meta = run_tts(proj, provider="elevenlabs-dialogue", fallback="", lines_path=lp, post_words=False)
check(HITS[-1] == [TEX, JOAN] and meta["contentType"] == "english", "plan.json content_type → Joan")
meta = run_tts(proj, provider="elevenlabs-dialogue", fallback="", lines_path=lp, post_words=False,
               content_type="market")
check(HITS[-1] == [TEX, LINDA], "explicit content_type beats plan.json")

print(f"elevenlabs content-type mock OK ({n} checks)")
