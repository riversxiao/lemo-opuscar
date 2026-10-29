"""StepFun StepAudio 3 *free preview* client: per-line VO + instrumental music bed.

Only the two limited-time-free preview models are allowed (pricing page,
https://platform.stepfun.com/docs/zh/guides/pricing/details — 「限时免费」):

  stepaudio-3-gen-preview    POST /v1/audio/generate      (VO, voice designed by text)
  stepaudio-3-music-preview  POST /v1/audio/music/submit + /query (instrumental bed)

Never calls the paid TTS route (/v1/audio/speech, stepaudio-3-tts, step-tts-*) or any
ASR endpoint. Key comes from STEPFUN_API_KEY (or STEP_API_KEY); never printed or logged.
Ready only when a key is set. Limits respected: ≤ 4 concurrent requests (account cap 5),
≥ 0.7 s between request starts (< 100 RPM), retry 429/5xx with backoff; 401/402/404 stop.

Voice consistency: every line uses the SAME role name + description + instruction
(env LEMO_TTS_STEPAUDIO_ROLE overrides the description). The preview API has no
fixed voice id/seed (`voice` is unsupported), so cross-line timbre drift is possible;
check by ear / F0 spread.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
import soundfile as sf

SR = 24000
GEN_MODEL = "stepaudio-3-gen-preview"
MUSIC_MODEL = "stepaudio-3-music-preview"
FREE_MODELS = {GEN_MODEL, MUSIC_MODEL}
DEFAULT_ROLE = ("三十五岁左右的普通话男声，中低音，财经新闻解说，沉稳清晰、语速中等、吐字干净，"
                "音高平稳、整片始终是同一个人同一种语气，不夸张不煽情，像纪录片旁白")
DEFAULT_TONE = "（平稳讲解）"
DEFAULT_INSTRUCTION = "安静录音棚，纯人声旁白，无背景音乐，无音效"
MAX_CONCURRENT = 4
MIN_INTERVAL = 0.7


class StepFunError(RuntimeError):
    pass


def base_url() -> str:
    return os.environ.get("LEMO_TTS_STEPAUDIO_BASE", "https://api.stepfun.com/v1").rstrip("/")


def api_key() -> str | None:
    return (os.environ.get("STEPFUN_API_KEY") or os.environ.get("STEP_API_KEY") or "").strip() or None


_lock = threading.Lock()
_last = [0.0]


def _throttle() -> None:
    with _lock:
        wait = _last[0] + MIN_INTERVAL - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def _post(path: str, body: dict[str, Any], *, timeout: float = 240.0, retries: int = 4) -> tuple[bytes, str | None]:
    key = api_key()
    if not key:
        raise StepFunError("STEPFUN_API_KEY not set")
    model = body.get("model") or body.get("model_id")
    if model is not None and model not in FREE_MODELS:
        raise StepFunError(f"refusing non-free StepFun model {model!r} (allowed: {sorted(FREE_MODELS)})")
    if "/audio/speech" in path or "asr" in path or "transcri" in path:
        raise StepFunError(f"refusing paid StepFun route {path}")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(retries + 1):
        _throttle()
        req = urllib.request.Request(f"{base_url()}{path}", data=data, method="POST",
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type")
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503) and attempt < retries and "credit" not in msg:
                time.sleep(min(30, 2 ** attempt * 2))
                continue
            raise StepFunError(f"StepFun HTTP {e.code} on {path}: {msg}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(2 ** attempt * 2)
                continue
            raise StepFunError(f"StepFun transport error on {path}: {e}") from None
    raise StepFunError("unreachable")


def account() -> dict[str, Any] | None:
    """GET /v1/accounts (balance; free calls should leave it unchanged)."""
    key = api_key()
    if not key:
        return None
    req = urllib.request.Request(f"{base_url()}/accounts", headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except (urllib.error.URLError, ValueError, TimeoutError):
        return None


def _decode(raw: bytes, sr: int = SR) -> np.ndarray:
    a, s = sf.read(io.BytesIO(raw), dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    if s != sr:
        import soxr
        a = soxr.resample(a, s, sr, quality="HQ")
    return a.astype(np.float32)


def _trim(a: np.ndarray, sr: int = SR) -> np.ndarray:
    if not len(a):
        return a
    thr = float(np.abs(a).max()) * 0.02
    nz = np.where(np.abs(a) > thr)[0]
    if not len(nz):
        return a
    return a[max(0, nz[0] - int(0.03 * sr)): nz[-1] + int(0.08 * sr)]


def generate_line(text: str, *, role: str = DEFAULT_ROLE, tone: str = DEFAULT_TONE,
                  instruction: str = DEFAULT_INSTRUCTION, speed: float | None = None) -> np.ndarray:
    body = {"model": GEN_MODEL, "task": "text_to_audio",
            "roles": [{"name": "旁白", "description": role[:480]}],
            "scripts": [{"speaker": "旁白", "text": f"{tone}{text}"[:1000]}],
            "instruction": instruction[:500], "response_format": "wav", "sample_rate": SR}
    if speed and abs(speed - 1.0) > 1e-3:
        body["speed"] = round(float(speed), 3)
    raw, _ = _post("/audio/generate", body)
    if raw[:4] != b"RIFF":
        raise StepFunError(f"/audio/generate returned non-WAV ({raw[:120]!r})")
    return _trim(_decode(raw))


def _yin(x: np.ndarray, sr: int, fmin: float = 65, fmax: float = 320, th: float = 0.12) -> float | None:
    w = len(x) // 2
    tmax, tmin = int(sr / fmin), int(sr / fmax)
    d = np.array([np.sum((x[:w] - x[t:t + w]) ** 2) for t in range(tmax + 1)])
    c = np.cumsum(d[1:])
    dn = np.ones_like(d)
    dn[1:] = d[1:] * np.arange(1, tmax + 1) / np.maximum(c, 1e-12)
    for t in range(tmin, tmax):
        if dn[t] < th:
            while t + 1 < tmax and dn[t + 1] < dn[t]:
                t += 1
            return sr / t
    return None


def median_f0(a: np.ndarray, sr: int = SR) -> float | None:
    """Median voiced F0 (Hz) — used to pick the take that matches the film's voice."""
    fl, hop = int(0.05 * sr), int(0.02 * sr)
    if len(a) < fl:
        return None
    thr = float(np.sqrt(np.mean(a ** 2)))
    vals = []
    for i in range(0, len(a) - fl, hop):
        x = a[i:i + fl]
        if float(np.sqrt(np.mean(x ** 2))) < thr * 0.6:
            continue
        v = _yin(x, sr)
        if v:
            vals.append(v)
    return float(np.median(vals)) if vals else None


def _st(a: float | None, b: float) -> float:
    return 99.0 if not a else abs(12 * np.log2(a / b))


SESSION_INSTRUCTION = ("安静录音棚，同一位男声旁白从头到尾连续念完整篇解说词，每句之间停顿约半秒，"
                       "纯人声，无背景音乐，无音效")


def _asr_words(a: np.ndarray, sr: int, texts: list[str]) -> list[tuple[float, float, str]]:
    """Local faster-whisper word timings (free, offline) used only to locate line boundaries."""
    import soxr
    from faster_whisper import WhisperModel

    a16 = soxr.resample(a, sr, 16000).astype(np.float32)
    m = WhisperModel(os.environ.get("LEMO_ASR_MODEL", "small"), device="cpu", compute_type="int8")
    segs, _ = m.transcribe(a16, language="zh", word_timestamps=True, initial_prompt="".join(texts)[:200])
    return [(w.start, w.end, w.word) for sg in segs for w in sg.words]


def synthesize_session(lines: list[dict[str, Any]], out_dir: str, *, role: str, speed: float,
                       words_fn=None) -> tuple[dict[str, float], dict[str, Any]]:
    """ONE request carries every line as consecutive `scripts` of the same speaker, so the
    whole narration comes from a single generation (one voice). gen-preview has no
    reference-audio / voice-id conditioning (reference_to_audio not open), so this is the
    only free way to hold one timbre. The take is split per line by aligning local-ASR
    character timings to the script and snapping cuts into pauses (providers/vo_split.py).
    """
    from . import vo_split  # noqa: PLC0415

    texts = [str(L.get("say") or L.get("text") or "") for L in lines]
    if sum(len(t) for t in texts) + len(DEFAULT_TONE) > 1000:
        raise StepFunError("script > 1000 chars: session mode needs one request; split the film or use per-line")
    body = {"model": GEN_MODEL, "task": "text_to_audio",
            "roles": [{"name": "旁白", "description": role[:480]}],
            "scripts": [{"speaker": "旁白", "text": (DEFAULT_TONE if i == 0 else "") + t} for i, t in enumerate(texts)],
            "instruction": SESSION_INSTRUCTION, "response_format": "wav", "sample_rate": SR}
    if speed and abs(speed - 1.0) > 1e-3:
        body["speed"] = round(float(speed), 3)
    raw, _ = _post("/audio/generate", body, timeout=900)
    if raw[:4] != b"RIFF":
        raise StepFunError(f"/audio/generate returned non-WAV ({raw[:120]!r})")
    a = _decode(raw)
    sf.write(os.path.join(out_dir, "_session.wav"), a, SR)
    words = (words_fn or _asr_words)(a, SR, texts)
    bounds, rep = vo_split.align_bounds(a, SR, texts, words)
    if rep["matchedChars"] < 0.85:
        raise StepFunError(f"session split: only {rep['matchedChars']:.0%} of script chars aligned — take is unusable")
    dur = {}
    for (t0, t1), L in zip(bounds, lines):
        clip = _trim(a[int(t0 * SR): int(t1 * SR)])
        sf.write(os.path.join(out_dir, f"{L['id']}.wav"), clip, SR)
        dur[L["id"]] = round(len(clip) / SR, 3)
    return dur, {"mode": "session", "requests": 1, "sessionSec": round(len(a) / SR, 3),
                 "split": rep, "bounds": [[round(x, 3), round(y, 3)] for x, y in bounds]}


def synthesize(lines: list[dict[str, Any]], out_dir: str, **opts: Any) -> dict[str, float]:
    """tts_router provider entry: writes <id>.wav (24 kHz mono) + dur.json.

    LEMO_TTS_STEPAUDIO_MODE=session (default: whole script in one request → one voice)
    or per-line (one request per line + pitch retakes; voices can drift between lines).
    """
    if not api_key():
        sys.exit("tts_router: provider 'stepaudio' needs STEPFUN_API_KEY in the environment")
    if (opts.get("mode") or os.environ.get("LEMO_TTS_STEPAUDIO_MODE") or "session") == "session":
        role = os.environ.get("LEMO_TTS_STEPAUDIO_ROLE") or DEFAULT_ROLE
        speed = float(opts.get("speed") or os.environ.get("LEMO_TTS_STEPAUDIO_SPEED") or 1.0)
        os.makedirs(out_dir, exist_ok=True)
        try:
            dur, info = synthesize_session(lines, out_dir, role=role, speed=speed, words_fn=opts.get("words_fn"))
        except (StepFunError, ValueError) as e:
            sys.exit(f"tts_router: stepaudio session failed: {e}")
        for L in lines:
            print(L["id"], dur[L["id"]], str(L.get("say") or L.get("text") or ""))
        with open(os.path.join(out_dir, "dur.json"), "w", encoding="utf-8") as f:
            json.dump(dur, f, indent=1, ensure_ascii=False)
        with open(os.path.join(out_dir, "stepaudio_meta.json"), "w", encoding="utf-8") as f:
            json.dump({"model": GEN_MODEL, "route": "/v1/audio/generate", "role": role, "speed": speed,
                       "instruction": SESSION_INSTRUCTION, "pricing": "限时免费 (preview)", **info}, f,
                      ensure_ascii=False, indent=1)
        return dur
    role = os.environ.get("LEMO_TTS_STEPAUDIO_ROLE") or DEFAULT_ROLE
    v = opts.get("voice")
    if v and not str(v).startswith(("zh-", "en-")) and len(str(v)) > 8:
        role = str(v)  # a free-text voice description, not an edge/kokoro voice id
    os.makedirs(out_dir, exist_ok=True)
    todo = [(L["id"], str(L.get("say") or L.get("text") or "")) for L in lines]
    dur: dict[str, float] = {}

    speed = float(opts.get("speed") or os.environ.get("LEMO_TTS_STEPAUDIO_SPEED") or 1.0)
    takes = max(1, int(os.environ.get("LEMO_TTS_STEPAUDIO_TAKES", "4")))
    tol = float(os.environ.get("LEMO_TTS_STEPAUDIO_F0_TOL_ST", "2.0"))
    best: dict[str, tuple[np.ndarray, float | None, int]] = {}

    def one(item):
        lid, text = item
        a = generate_line(text, role=role, speed=speed)
        return lid, a, median_f0(a)

    # Voice consistency: gen-preview has no voice id, so timbre/pitch can drift between
    # requests. Pass 1 renders every line; the film target pitch is the median of medians;
    # lines more than `tol` semitones off are re-taken (up to `takes` total) and the
    # closest take is kept. Every take is a free gen-preview request.
    try:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as ex:
            for lid, a, f0 in ex.map(one, todo):
                best[lid] = (a, f0, 1)
        f0s = [v[1] for v in best.values() if v[1]]
        target = float(os.environ.get("LEMO_TTS_STEPAUDIO_F0") or (np.median(f0s) if f0s else 0) or 0)
        if target and takes > 1:
            for _ in range(takes - 1):
                redo = [(lid, t) for lid, t in todo if _st(best[lid][1], target) > tol]
                if not redo:
                    break
                with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as ex:
                    for lid, a, f0 in ex.map(one, redo):
                        old = best[lid]
                        n = old[2] + 1
                        best[lid] = (a, f0, n) if _st(f0, target) < _st(old[1], target) else (old[0], old[1], n)
    except StepFunError as e:
        sys.exit(f"tts_router: stepaudio failed: {e}")
    report = {}
    for lid, text in todo:
        a, f0, n = best[lid]
        sf.write(os.path.join(out_dir, f"{lid}.wav"), a, SR)
        dur[lid] = round(len(a) / SR, 3)
        report[lid] = {"f0": round(f0, 1) if f0 else None, "takes": n,
                       "offSt": round(_st(f0, target), 2) if target else None}
        print(lid, dur[lid], f"f0={report[lid]['f0']} takes={n}", text)
    with open(os.path.join(out_dir, "dur.json"), "w", encoding="utf-8") as f:
        json.dump(dur, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, "stepaudio_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"model": GEN_MODEL, "route": "/v1/audio/generate", "role": role, "tone": DEFAULT_TONE,
                   "instruction": DEFAULT_INSTRUCTION, "pricing": "限时免费 (preview)", "speed": speed,
                   "consistency": {"targetF0": round(target, 1) if target else None, "tolSt": tol,
                                   "maxTakes": takes, "requests": sum(v["takes"] for v in report.values()),
                                   "lines": report}}, f,
                  ensure_ascii=False, indent=1)
    return dur


def music_instrumental(caption: str, *, poll: float = 5.0, timeout: float = 900.0,
                       sr: int = 48000) -> tuple[np.ndarray, int, dict[str, Any]]:
    """Submit an instrumental text_to_music task and poll until SUCCESS. Returns (stereo, sr, info)."""
    raw, _ = _post("/audio/music/submit", {"task": "text_to_music", "model_id": MUSIC_MODEL,
                                           "instrumental": True, "caption": caption,
                                           "response_format": "wav", "sample_rate": sr})
    task_id = json.loads(raw)["task_id"]
    t0 = time.time()
    while True:
        time.sleep(poll)
        raw, _ = _post("/audio/music/query", {"task_id": task_id}, timeout=120)
        d = json.loads(raw)
        st = d.get("status")
        if st == "SUCCESS":
            a, s = sf.read(io.BytesIO(base64.b64decode(d["audio"])), dtype="float32", always_2d=True)
            if a.shape[1] == 1:
                a = np.repeat(a, 2, axis=1)
            info = {"taskId": task_id, "model": MUSIC_MODEL, "caption": caption,
                    "rewrittenCaption": d.get("rewritten_caption"), "sr": s,
                    "durSec": round(len(a) / s, 2), "elapsedSec": round(time.time() - t0, 1)}
            return a[:, :2], s, info
        if st == "FAILED":
            raise StepFunError(f"music task {task_id} FAILED: {json.dumps(d.get('error'), ensure_ascii=False)[:300]}")
        if time.time() - t0 > timeout:
            raise StepFunError(f"music task {task_id} timed out after {timeout}s (last status {st})")
