#!/usr/bin/env python3
"""FREE-first OpenAI-compatible LLM chain for dialogue_loop (and similar).

Order (env DC_LLM_CHAIN overrides as comma-separated provider:model):
  1. TokenHarbor  deepseek-v4.1-flash:free   (TOKENHARBOR_API_KEY → https://tokenharbor.ai/v1)
  2. OpenRouter   nvidia/nemotron-3.5-lightning:free
  3. OpenRouter   recursive/flint-v1.0:free  (OPENROUTER_API_KEY)

Paid DeepSeek official / paid OpenRouter are NEVER used unless allow_paid=True
(--allow-paid). OpenCode free models are intentionally omitted (quota exhausted).

Error classes:
  RateLimitError  — per-minute 429: wait ~60s and retry the SAME model (max 3).
  QuotaExhausted  — rolling free quota / FreeUsageLimit: advance to next free model.
  ProviderError   — other HTTP/transport failures: advance (or stop if last).

Never prints API keys. Per-call model is recorded in self.call_log and usage.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

TOKENHARBOR_BASE = os.environ.get("DC_TOKENHARBOR_BASE", "https://tokenharbor.ai/v1")
OPENROUTER_BASE = os.environ.get("DC_OPENROUTER_BASE", "https://openrouter.ai/api/v1")
DEEPSEEK_BASE = os.environ.get("DC_DEEPSEEK_BASE", "https://api.deepseek.com")

# (provider, model, env_key, base_url, paid)
DEFAULT_FREE_CHAIN: list[tuple[str, str, str, str, bool]] = [
    ("tokenharbor", "deepseek-v4.1-flash:free", "TOKENHARBOR_API_KEY", TOKENHARBOR_BASE, False),
    ("openrouter", "nvidia/nemotron-3.5-lightning:free", "OPENROUTER_API_KEY", OPENROUTER_BASE, False),
    ("openrouter", "recursive/flint-v1.0:free", "OPENROUTER_API_KEY", OPENROUTER_BASE, False),
]
PAID_FALLBACK: list[tuple[str, str, str, str, bool]] = [
    ("deepseek", "deepseek-flash", "DEEPSEEK_API_KEY", DEEPSEEK_BASE, True),
]

RATE_LIMIT_SLEEP_SEC = float(os.environ.get("DC_LLM_RATE_LIMIT_SLEEP", "60"))
RATE_LIMIT_RETRIES = int(os.environ.get("DC_LLM_RATE_LIMIT_RETRIES", "3"))


class ProviderError(RuntimeError):
    pass


class RateLimitError(ProviderError):
    """Per-minute / soft 429 — retry the same model after a short wait."""


class QuotaExhausted(ProviderError):
    """Rolling free quota exhausted — skip this model permanently in this run."""


class BadJSON(ValueError):
    pass


def _is_quota_body(code: int, body: str) -> bool:
    b = (body or "").lower()
    markers = (
        "freeusagelimit", "free usage limit", "quota", "quota exceeded",
        "insufficient_quota", "credits", "spend limit", "rate limit exceeded for free",
        "daily limit", "weekly limit", "7-day", "free tier",
    )
    if any(m in b for m in markers):
        # OpenRouter free daily / TokenHarbor free rollups often come as 402/403/429
        return True
    # bare 402 Payment Required on a :free model = free quota gone
    if code == 402:
        return True
    return False


def _is_rate_limit(code: int, body: str) -> bool:
    if code != 429:
        return False
    # Prefer classifying FreeUsageLimit as quota, not rate-limit
    if _is_quota_body(code, body):
        return False
    return True


def parse_chain(spec: str | None = None) -> list[tuple[str, str, str, str, bool]]:
    """Parse DC_LLM_CHAIN like 'tokenharbor:deepseek-v4.1-flash:free,openrouter:recursive/flint-v1.0:free'."""
    raw = (spec if spec is not None else os.environ.get("DC_LLM_CHAIN") or "").strip()
    if not raw:
        return list(DEFAULT_FREE_CHAIN)
    out: list[tuple[str, str, str, str, bool]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ProviderError(f"bad DC_LLM_CHAIN entry {part!r} (need provider:model)")
        provider, model = part.split(":", 1)
        provider = provider.strip().lower()
        model = model.strip()
        if provider == "tokenharbor":
            out.append((provider, model, "TOKENHARBOR_API_KEY", TOKENHARBOR_BASE, False))
        elif provider == "openrouter":
            if not model.endswith(":free"):
                raise ProviderError(f"openrouter model must end with :free in free chain: {model}")
            out.append((provider, model, "OPENROUTER_API_KEY", OPENROUTER_BASE, False))
        elif provider == "deepseek":
            out.append((provider, model, "DEEPSEEK_API_KEY", DEEPSEEK_BASE, True))
        else:
            raise ProviderError(f"unknown LLM provider {provider!r}")
    return out


class FreeFirstClient:
    """chat_json / balance compatible with dialogue_loop.DeepSeekClient."""

    def __init__(
        self,
        *,
        effort: str = "high",
        timeout: int = 300,
        allow_paid: bool = False,
        chain: list[tuple[str, str, str, str, bool]] | None = None,
        sleep_fn=time.sleep,
        rate_limit_sleep: float | None = None,
        rate_limit_retries: int | None = None,
        transport=None,  # injectable for mocks: (url, headers, body) -> dict | raises HTTPError-like
    ):
        self.effort = effort
        self.timeout = timeout
        self.allow_paid = allow_paid
        self.sleep = sleep_fn
        self.rate_limit_sleep = RATE_LIMIT_SLEEP_SEC if rate_limit_sleep is None else rate_limit_sleep
        self.rate_limit_retries = RATE_LIMIT_RETRIES if rate_limit_retries is None else rate_limit_retries
        self._transport = transport
        free = list(chain) if chain is not None else parse_chain()
        # drop paid entries unless allow_paid
        self.chain = [c for c in free if (not c[4]) or allow_paid]
        if allow_paid:
            for p in PAID_FALLBACK:
                if p not in self.chain:
                    self.chain.append(p)
        if not self.chain:
            raise ProviderError("no free LLM models available (chain empty)")
        # resolve keys up front — missing key skips that slot (don't print the name's value)
        self._slots: list[dict[str, Any]] = []
        missing = []
        for provider, model, env_key, base, paid in self.chain:
            key = os.environ.get(env_key) or ""
            if not key:
                missing.append(f"{provider}/{model} (need {env_key})")
                continue
            if paid and not allow_paid:
                continue
            if provider == "openrouter" and not paid and not model.endswith(":free"):
                raise ProviderError(f"refusing non-:free OpenRouter model without --allow-paid: {model}")
            self._slots.append({
                "provider": provider, "model": model, "env_key": env_key,
                "base": base.rstrip("/"), "paid": paid, "key": key, "exhausted": False,
            })
        if not self._slots:
            raise ProviderError(
                "no usable free LLM slot — set TOKENHARBOR_API_KEY and/or OPENROUTER_API_KEY. "
                + (("missing: " + "; ".join(missing)) if missing else "")
            )
        self.usage = {"calls": 0, "prompt": 0, "completion": 0, "reasoning": 0, "cacheHit": 0}
        self.call_log: list[dict[str, Any]] = []  # one row per successful chat
        self.model = self._slots[0]["model"]  # last-used (updated on success)
        self.provider = self._slots[0]["provider"]
        self.last_slot: dict[str, Any] | None = None

    def balance(self) -> float | None:
        """Paid DeepSeek balance only; free providers return None (no CNY spend)."""
        for s in self._slots:
            if s["provider"] == "deepseek" and s["paid"]:
                req = urllib.request.Request(
                    f"{s['base']}/user/balance",
                    headers={"Authorization": f"Bearer {s['key']}"},
                )
                try:
                    d = json.load(urllib.request.urlopen(req, timeout=30))
                    for b in d.get("balance_infos") or []:
                        if b.get("currency") == "CNY":
                            return float(b["total_balance"])
                except (urllib.error.URLError, ValueError, KeyError, TimeoutError):
                    return None
        return None

    def chat_json(self, system: str, user: str, retries: int = 2) -> dict[str, Any]:
        last_err: Exception | None = None
        tried: list[str] = []
        for slot in self._slots:
            if slot["exhausted"]:
                continue
            label = f"{slot['provider']}/{slot['model']}"
            tried.append(label)
            for attempt in range(self.rate_limit_retries + 1):
                try:
                    data = self._chat_once(slot, system, user)
                    self.model = slot["model"]
                    self.provider = slot["provider"]
                    self.last_slot = slot
                    return data
                except BadJSON as e:
                    last_err = e
                    if attempt >= retries:
                        # treat persistent bad JSON as advance-to-next
                        break
                    continue
                except RateLimitError as e:
                    last_err = e
                    if attempt >= self.rate_limit_retries:
                        break  # give up on this model for this call; try next
                    self.sleep(self.rate_limit_sleep)
                    continue
                except QuotaExhausted as e:
                    slot["exhausted"] = True
                    last_err = e
                    break
                except ProviderError as e:
                    last_err = e
                    break
        raise ProviderError(
            "all free LLM models failed"
            + ("" if self.allow_paid else " (paid fallback disabled; pass --allow-paid to use DeepSeek official)")
            + f"; tried: {tried}; last: {last_err}"
        )

    def _chat_once(self, slot: dict[str, Any], system: str, user: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": slot["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 16000,
        }
        # DeepSeek official still accepts reasoning_effort; others ignore unknown fields — keep for paid only
        if slot["provider"] == "deepseek":
            body["reasoning_effort"] = self.effort
        url = f"{slot['base']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {slot['key']}",
            "Content-Type": "application/json",
        }
        if slot["provider"] == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/riversxiao/wordfilm"
            headers["X-Title"] = "wordfilm-dialogue-loop"
        try:
            if self._transport is not None:
                r = self._transport(url, headers, body)
            else:
                req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
                r = json.load(urllib.request.urlopen(req, timeout=self.timeout))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", "replace")[:800]
            if _is_quota_body(e.code, raw):
                raise QuotaExhausted(f"{slot['provider']}/{slot['model']} quota: HTTP {e.code}") from None
            if _is_rate_limit(e.code, raw):
                raise RateLimitError(f"{slot['provider']}/{slot['model']} rate-limit: HTTP {e.code}") from None
            raise ProviderError(f"{slot['provider']}/{slot['model']} HTTP {e.code}: {raw[:300]!r}") from None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise ProviderError(f"{slot['provider']}/{slot['model']} transport: {e}") from None

        if isinstance(r, dict) and r.get("error"):
            err = r["error"]
            msg = err if isinstance(err, str) else json.dumps(err)
            if _is_quota_body(429, msg):
                raise QuotaExhausted(f"{slot['provider']}/{slot['model']} quota: {msg[:200]}")
            raise ProviderError(f"{slot['provider']}/{slot['model']} error: {msg[:300]}")

        u = (r.get("usage") or {}) if isinstance(r, dict) else {}
        self.usage["calls"] += 1
        self.usage["prompt"] += int(u.get("prompt_tokens") or 0)
        self.usage["completion"] += int(u.get("completion_tokens") or 0)
        details = u.get("completion_tokens_details") or {}
        self.usage["reasoning"] += int(details.get("reasoning_tokens") or 0)
        self.usage["cacheHit"] += int(u.get("prompt_cache_hit_tokens") or 0)
        self.call_log.append({
            "provider": slot["provider"], "model": slot["model"], "paid": slot["paid"],
            "prompt": int(u.get("prompt_tokens") or 0),
            "completion": int(u.get("completion_tokens") or 0),
        })
        try:
            content = r["choices"][0]["message"].get("content")
            if not content:
                # reasoning-only models sometimes put the answer in reasoning — refuse & advance
                raise BadJSON("empty content (reasoning-only response)")
            return json.loads(content)
        except (KeyError, IndexError, ValueError, TypeError) as e:
            raise BadJSON(str(e)) from None


def make_client(*, mock: str | None = None, allow_paid: bool = False, effort: str = "high",
                model: str | None = None, **kw):
    """Factory used by dialogue_loop.main. model= is ignored in free mode (chain decides)."""
    if mock:
        # local import to keep MockClient in dialogue_loop (tests already patch there)
        from dialogue_loop import MockClient
        return MockClient(__import__("pathlib").Path(mock))
    return FreeFirstClient(effort=effort, allow_paid=allow_paid, **kw)


if __name__ == "__main__":
    # never print keys — only slot labels
    c = FreeFirstClient(allow_paid=False)
    print("slots:", [f"{s['provider']}/{s['model']}" for s in c._slots])
