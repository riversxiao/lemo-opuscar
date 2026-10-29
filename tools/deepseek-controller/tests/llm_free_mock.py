#!/usr/bin/env python3
"""Mock tests for llm_free.FreeFirstClient — no network, no keys printed."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

CTL = Path(__file__).resolve().parents[1]
os.environ.setdefault("DC_QUOTA_LEDGER", "/tmp/dc-test-quota-ledger.jsonl")
os.environ["WORDFILM_QUOTA_LEDGER"] = os.environ["DC_QUOTA_LEDGER"]  # top-priority name: never the real ledger
sys.path.insert(0, str(CTL))

import llm_free as L  # noqa: E402

n = 0


def ok(cond, msg):
    global n
    if not cond:
        print("FAIL:", msg)
        sys.exit(1)
    n += 1
    print("ok", msg)


class FakeHTTP(Exception):
    def __init__(self, code: int, body: bytes):
        self.code = code
        self._body = body

    def read(self):
        return self._body


# Save/restore env so we don't leak test keys into the parent shell permanently —
# we only set placeholder strings, never real secrets.
_ENV_KEYS = ("TOKENHARBOR_API_KEY", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "DC_LLM_CHAIN",
             "DC_LLM_RATE_LIMIT_SLEEP", "DC_LLM_RATE_LIMIT_RETRIES")
_saved = {k: os.environ.get(k) for k in _ENV_KEYS}

try:
    os.environ["TOKENHARBOR_API_KEY"] = "test-th-key"
    os.environ["OPENROUTER_API_KEY"] = "test-or-key"
    os.environ.pop("DEEPSEEK_API_KEY", None)
    os.environ.pop("DC_LLM_CHAIN", None)

    # ---- parse_chain
    ch = L.parse_chain()
    ok(ch[0][0] == "tokenharbor" and "deepseek-v4.1-flash:free" in ch[0][1], "default #1 TokenHarbor flash:free")
    ok(any(c[1] == "nvidia/nemotron-3.5-lightning:free" for c in ch), "default includes nemotron:free")
    ok(any(c[1] == "recursive/flint-v1.0:free" for c in ch), "default includes flint:free")
    ok(not any("opencode" in c[0] or "opencode" in c[1] for c in ch), "OpenCode free models NOT in chain")
    ok(all(not c[4] for c in ch), "default chain is all free (paid=False)")
    try:
        L.parse_chain("openrouter:anthropic/claude-3-haiku")
        ok(False, "non-:free openrouter rejected")
    except L.ProviderError:
        ok(True, "non-:free openrouter rejected")

    # ---- no keys → clear error (no secret printed)
    for k in ("TOKENHARBOR_API_KEY", "OPENROUTER_API_KEY"):
        os.environ.pop(k, None)
    try:
        L.FreeFirstClient()
        ok(False, "missing keys raises")
    except L.ProviderError as e:
        ok("TOKENHARBOR_API_KEY" in str(e) and "sk-" not in str(e) and "test-" not in str(e),
           f"missing-key error names env vars only: {e}")
    os.environ["TOKENHARBOR_API_KEY"] = "test-th-key"
    os.environ["OPENROUTER_API_KEY"] = "test-or-key"

    sleeps: list[float] = []

    def sleep_fn(s):
        sleeps.append(s)

    # ---- happy path: TokenHarbor wins on first try
    calls: list[str] = []

    def transport_ok(url, headers, body):
        calls.append(body["model"])
        # never echo Authorization
        assert "test-th-key" not in json.dumps(headers) or headers["Authorization"].startswith("Bearer ")
        return {"choices": [{"message": {"content": '{"ok":1}'}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2}}

    c = L.FreeFirstClient(transport=transport_ok, sleep_fn=sleep_fn, rate_limit_sleep=0.01)
    r = c.chat_json("sys", "user")
    ok(r == {"ok": 1} and calls == ["deepseek-v4.1-flash:free"], "TokenHarbor used first")
    ok(c.model == "deepseek-v4.1-flash:free" and c.provider == "tokenharbor", "last model recorded")
    ok(c.call_log and c.call_log[0]["provider"] == "tokenharbor" and c.call_log[0]["paid"] is False,
       "call_log records free provider/model")
    ok(c.usage["calls"] == 1 and c.usage["prompt"] == 3, "usage counters")

    # ---- 429 rate-limit → wait + retry SAME model, then succeed
    sleeps.clear()
    seq = {"n": 0}

    def transport_rl(url, headers, body):
        seq["n"] += 1
        if seq["n"] <= 2:
            raise FakeHTTP(429, b'{"error":"rate limit, try again"}')
        return {"choices": [{"message": {"content": '{"ok":2}'}}], "usage": {}}

    # Monkeypatch urllib.error.HTTPError path: our FakeHTTP isn't urllib.error.HTTPError.
    # Inject via a wrapper that raises the real class.
    import urllib.error

    class H(urllib.error.HTTPError):
        def __init__(self, code, body):
            urllib.error.HTTPError.__init__(self, "http://x", code, "x", {}, None)
            self._b = body

        def read(self):
            return self._b

    def transport_rl2(url, headers, body):
        seq["n"] += 1
        if seq["n"] <= 2:
            raise H(429, b'{"error":"rate limit, try again soon"}')
        return {"choices": [{"message": {"content": '{"ok":2}'}}], "usage": {"prompt_tokens": 1}}

    seq["n"] = 0
    c = L.FreeFirstClient(transport=transport_rl2, sleep_fn=sleep_fn, rate_limit_sleep=0.5, rate_limit_retries=3)
    r = c.chat_json("s", "u")
    ok(r == {"ok": 2} and sleeps == [0.5, 0.5], f"rate-limit retried same model with sleep ({sleeps})")
    ok(all(x == "deepseek-v4.1-flash:free" for x in [c.model]), "still TokenHarbor after rate-limit retries")

    # ---- FreeUsageLimit / quota → skip to next model (no long retry loop on same)
    sleeps.clear()
    seq["n"] = 0
    used: list[str] = []

    def transport_quota(url, headers, body):
        used.append(body["model"])
        if "deepseek" in body["model"]:
            raise H(429, b'{"error":{"type":"FreeUsageLimitError","message":"Free usage limit reached"}}')
        if "nemotron" in body["model"]:
            raise H(402, b'{"error":"Insufficient credits / free quota"}')
        return {"choices": [{"message": {"content": '{"ok":3}'}}], "usage": {"prompt_tokens": 1}}

    c = L.FreeFirstClient(transport=transport_quota, sleep_fn=sleep_fn, rate_limit_sleep=60)
    r = c.chat_json("s", "u")
    ok(r == {"ok": 3} and used == ["deepseek-v4.1-flash:free", "nvidia/nemotron-3.5-lightning:free",
                                    "recursive/flint-v1.0:free"], f"quota advances: {used}")
    ok(sleeps == [], "quota does NOT sleep-retry")
    ok(c.model == "recursive/flint-v1.0:free", "flint used after prior free exhausted")

    # ---- all free fail → clear error, no paid without flag
    def transport_all_fail(url, headers, body):
        raise H(503, b'{"error":"unavailable"}')

    c = L.FreeFirstClient(transport=transport_all_fail, sleep_fn=sleep_fn, allow_paid=False)
    try:
        c.chat_json("s", "u")
        ok(False, "all-fail should raise")
    except L.ProviderError as e:
        msg = str(e)
        ok("all free LLM models failed" in msg and "allow-paid" in msg, f"all-fail message: {msg[:120]}")
        ok("api.deepseek.com" not in msg.lower() or "paid fallback disabled" in msg, "does not silently use paid")

    # ---- --allow-paid appends DeepSeek official ONLY after free fail
    os.environ["DEEPSEEK_API_KEY"] = "test-ds-key"
    used.clear()

    def transport_paid(url, headers, body):
        used.append((url, body["model"]))
        if "api.deepseek.com" in url:
            return {"choices": [{"message": {"content": '{"ok":9}'}}], "usage": {"prompt_tokens": 1}}
        raise H(429, b'{"error":{"type":"FreeUsageLimitError","message":"Free usage limit"}}')

    c = L.FreeFirstClient(transport=transport_paid, sleep_fn=sleep_fn, allow_paid=True)
    r = c.chat_json("s", "u")
    ok(r == {"ok": 9} and any("api.deepseek.com" in u for u, _ in used), "allow_paid reaches DeepSeek official")
    ok(used[0][1].endswith(":free"), "still tries free first even with allow_paid")
    ok(c.call_log[-1]["paid"] is True, "paid call flagged in call_log")

    # without allow_paid, DEEPSEEK key present must NOT be used
    used.clear()

    def transport_no_paid(url, headers, body):
        used.append(body["model"])
        raise H(503, b"down")

    c = L.FreeFirstClient(transport=transport_no_paid, sleep_fn=sleep_fn, allow_paid=False)
    try:
        c.chat_json("s", "u")
    except L.ProviderError:
        pass
    ok(all(m.endswith(":free") or m == "deepseek-v4.1-flash:free" for m in used)
       and "deepseek-flash" not in used, f"no paid model without flag: {used}")

    # ---- ledger row from dialogue_loop.log_cost uses call_log models (mock client skipped)
    import dialogue_loop as D
    os.environ["DC_BUDGET_LEDGER"] = str(Path(tempfile.mkdtemp()) / "ledger.jsonl")
    summary = {
        "status": "PASS", "rounds": 1, "cny": 0.0, "balanceBefore": None, "balanceAfter": None,
        "durationSec": 1.0, "model": "recursive/flint-v1.0:free", "provider": "openrouter",
        "allowPaid": False,
        "usage": {"calls": 2, "prompt": 10, "completion": 5, "reasoning": 0, "cacheHit": 0},
        "callLog": [
            {"provider": "tokenharbor", "model": "deepseek-v4.1-flash:free", "paid": False},
            {"provider": "openrouter", "model": "recursive/flint-v1.0:free", "paid": False},
        ],
    }
    # fool log_cost past the mock skip (model != mock and calls > 0)
    row = D.log_cost(summary, Path("."), "llm-free-mock")
    ok(row is not None and row["source"] == "free-first", f"ledger source free-first: {row and row.get('source')}")
    ok("tokenharbor/deepseek-v4.1-flash:free" in (row or {}).get("notes", ""), "ledger notes list models used")
    ok((row or {}).get("meta", {}).get("callLog") and not any(
        "test-" in json.dumps(row) or "sk-" in json.dumps(row) for _ in [0]
    ), "ledger has callLog and no key material")

    # ---- dialogue_loop.DeepSeekClient is free-first alias
    ok(issubclass(D.DeepSeekClient, L.FreeFirstClient), "DeepSeekClient aliases FreeFirstClient")

finally:
    for k, v in _saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

print(f"llm_free_mock: {n} checks OK")
