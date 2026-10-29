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

Quota-aware routing (finance). PRIMARY signal: TokenHarbor response headers `x-th-free-used-pct`
(percent of the free quota used, e.g. "83.5") and `x-th-free-resets` (UTC reset time). Every TokenHarbor
response's headers are persisted to a small state file next to the ledger
(`<ledger stem>.header.json`); the header value is trusted until its reset time passes (no reset header →
for DC_TH_HEADER_TTL_SEC, default 6 h). FALLBACK when no fresh header exists: a local ledger of every
TokenHarbor call's total tokens (rolling 7-day window; there is no usage endpoint — /v1/usage, /v1/key,
/v1/me → 404) against DC_TH_WEEKLY_BUDGET (1,250,000 tokens). When used ≥ DC_TH_ROUTE_PCT (0.8),
the client routes to OpenRouter nemotron-3.5-lightning:free → flint-v1.0:free first
and keeps TokenHarbor only as the last free fallback. Checked at client start and before each batch
(`reroute()`, called by dialogue_loop / token_measure) and immediately mid-batch when a response header
crosses the threshold. Ledger: $WORDFILM_QUOTA_LEDGER (or the upstream $DC_QUOTA_LEDGER; tests), else
$WORDFILM_CACHE/tokenharbor-usage.jsonl, else ~/.cache/wordfilm/tokenharbor-usage.jsonl (shared by every
real run on this machine). Deliberately not beside $WORDFILM_BUDGET_LEDGER: a temp budget ledger must not
reset the quota count.
NVIDIA NIM is not in the chain (timeouts). Never paid.
"""
from __future__ import annotations

import email.utils
import json
import os
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request
from pathlib import Path
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


TH_WEEKLY_BUDGET = int(float(os.environ.get("DC_TH_WEEKLY_BUDGET", "1250000")))
TH_ROUTE_PCT = float(os.environ.get("DC_TH_ROUTE_PCT", "0.8"))
QUOTA_WINDOW_SEC = 7 * 86400
TH_HEADER_TTL_SEC = float(os.environ.get("DC_TH_HEADER_TTL_SEC", str(6 * 3600)))
TH_HDR_PCT = "x-th-free-used-pct"
TH_HDR_RESETS = "x-th-free-resets"


QUOTA_LEDGER_ENV = ("WORDFILM_QUOTA_LEDGER", "DC_QUOTA_LEDGER")


def quota_ledger_path() -> Path:
    """$WORDFILM_QUOTA_LEDGER > $DC_QUOTA_LEDGER (tests point it at a temp dir) > the shared real ledger
    under $WORDFILM_CACHE (default ~/.cache/wordfilm): real runs always count, even when their budget
    ledger is a temp file. Read at call time; empty = unset."""
    for k in QUOTA_LEDGER_ENV:
        v = os.environ.get(k, "").strip()
        if v:
            return Path(v).expanduser()
    cache = os.environ.get("WORDFILM_CACHE", "").strip()
    base = Path(cache).expanduser() if cache else Path.home() / ".cache" / "wordfilm"
    return base / "tokenharbor-usage.jsonl"


def record_usage(row: dict[str, Any], path: Path | None = None, now: float | None = None) -> None:
    p = path or quota_ledger_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": round(now or time.time(), 1), "provider": row.get("provider"),
                                "model": row.get("model"), "step": row.get("step"),
                                "total": int(row.get("total") or 0)}) + "\n")
    except OSError:
        pass


def quota_header_path(ledger: Path | None = None) -> Path:
    """Header state lives beside the ledger (so temp test ledgers get temp header state)."""
    lp = ledger or quota_ledger_path()
    return lp.with_name(lp.stem + ".header.json")


def _hget(headers: Any, name: str) -> str | None:
    if headers is None:
        return None
    try:
        items = headers.items()
    except AttributeError:
        return None
    for k, v in items:
        if str(k).lower() == name:
            return None if v is None else str(v).strip()
    return None


def parse_reset(raw: str | None) -> float | None:
    """UTC reset time → epoch seconds. Accepts ISO-8601 (Z / offset / naive=UTC), RFC 1123, epoch s/ms."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        x = float(raw)
        return x / 1000.0 if x > 1e11 else x
    except ValueError:
        pass
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00").replace("z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except ValueError:
        pass
    try:
        d = email.utils.parsedate_to_datetime(raw)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except (TypeError, ValueError):
        return None


def parse_th_headers(headers: Any, now: float | None = None) -> dict[str, Any] | None:
    """`x-th-free-used-pct` (percent, "83.5" / "83.5%") + `x-th-free-resets` → state dict, or None."""
    raw = _hget(headers, TH_HDR_PCT)
    if raw is None or raw == "":
        return None
    try:
        pct = float(raw.rstrip("%").strip()) / 100.0
    except ValueError:
        return None
    if pct < 0:
        return None
    rraw = _hget(headers, TH_HDR_RESETS)
    return {"pct": round(pct, 4), "resetsAt": parse_reset(rraw), "resetsRaw": rraw,
            "observedAt": round(now or time.time(), 1)}


def record_header(state: dict[str, Any], ledger: Path | None = None) -> None:
    p = quota_header_path(ledger)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state) + "\n", encoding="utf-8")
    except OSError:
        pass


def header_quota(ledger: Path | None = None, now: float | None = None) -> dict[str, Any] | None:
    """Fresh header state, or None (missing, unreadable, past its reset, or older than the TTL w/o reset)."""
    p = quota_header_path(ledger)
    now = now or time.time()
    if not p.is_file():
        return None
    try:
        st = json.loads(p.read_text(encoding="utf-8"))
        pct = float(st["pct"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    ra = st.get("resetsAt")
    if ra is not None:
        if now >= float(ra):
            return None  # quota has reset since the header was seen
    elif now - float(st.get("observedAt") or 0) > TH_HEADER_TTL_SEC:
        return None
    return {"pct": round(pct, 4), "resetsAt": ra, "resetsRaw": st.get("resetsRaw"),
            "observedAt": st.get("observedAt"), "file": str(p)}


def quota_status(path: Path | None = None, now: float | None = None, budget: int | None = None) -> dict[str, Any]:
    """Routing signal: fresh TokenHarbor header (primary) else the local ledger estimate (fallback)."""
    q = quota_usage(path, now=now, budget=budget)
    h = header_quota(path, now=now)
    if h is None:
        return {**q, "header": None}
    return {**q, "pct": h["pct"], "source": f"header {TH_HDR_PCT}",
            "ledgerPct": q["pct"], "resetsAt": h["resetsAt"], "resetsRaw": h["resetsRaw"], "header": h}


def quota_usage(path: Path | None = None, now: float | None = None, budget: int | None = None) -> dict[str, Any]:
    """TokenHarbor tokens used in the rolling 7-day window (local ledger estimate)."""
    p = path or quota_ledger_path()
    now = now or time.time()
    budget = budget or TH_WEEKLY_BUDGET
    used = 0
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("provider") == "tokenharbor" and float(r.get("ts") or 0) >= now - QUOTA_WINDOW_SEC:
                used += int(r.get("total") or 0)
    return {"provider": "tokenharbor", "used": used, "budget": budget, "pct": round(used / budget, 4) if budget else 1.0,
            "windowDays": 7, "source": "local-ledger (no TokenHarbor usage API)", "ledger": str(p)}


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
        quota_route: bool | None = None,
        quota_path: Path | None = None,
        route_pct: float | None = None,
        weekly_budget: int | None = None,
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
        # one row per HTTP 200 response (incl. ones whose content then fails JSON parse: ok=False —
        # those tokens were still spent). `step` labels the pipeline step for per-step accounting.
        self.call_log: list[dict[str, Any]] = []
        self.step: str = ""
        self.model = self._slots[0]["model"]  # last-used (updated on success)
        self.provider = self._slots[0]["provider"]
        self.last_slot: dict[str, Any] | None = None
        self.quota_route = (os.environ.get("DC_QUOTA_ROUTE", "1") != "0") if quota_route is None else quota_route
        self.quota_path = quota_path
        self.route_pct = TH_ROUTE_PCT if route_pct is None else route_pct
        self.weekly_budget = weekly_budget or TH_WEEKLY_BUDGET
        self._base_order = list(self._slots)
        self.routing: dict[str, Any] = {}
        self.header_seen: dict[str, Any] | None = None
        self.reroute()

    def reroute(self) -> dict[str, Any]:
        """Before a batch: if TokenHarbor ≥ route_pct of the weekly budget, OpenRouter :free goes first and
        TokenHarbor becomes the last free fallback. Never adds paid slots."""
        q = quota_status(self.quota_path, budget=self.weekly_budget)
        others = [s for s in self._base_order if s["provider"] != "tokenharbor"]
        th = [s for s in self._base_order if s["provider"] == "tokenharbor"]
        hot = self.quota_route and q["pct"] >= self.route_pct and bool(others) and bool(th)
        self._slots = (others + th) if hot else list(self._base_order)
        self.routing = {**q, "routePct": self.route_pct, "routed": hot,
                        "order": [f"{s['provider']}/{s['model']}" for s in self._slots]}
        return self.routing

    def _observe_headers(self, slot: dict[str, Any], headers: Any) -> None:
        """TokenHarbor quota headers → state file; reroute now if they cross the threshold."""
        if slot.get("provider") != "tokenharbor":
            return
        st = parse_th_headers(headers)
        if st is None:
            return
        record_header(st, self.quota_path)
        self.header_seen = st
        if self.quota_route and st["pct"] >= self.route_pct and not self.routing.get("routed"):
            self.reroute()
            self.routing["trigger"] = "mid-batch header"

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

    def chat_json(self, system: str, user: str, retries: int = 2, step: str | None = None) -> dict[str, Any]:
        if step is not None:
            self.step = step
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
        t0 = time.time()
        resp_headers: Any = None
        try:
            if self._transport is not None:
                r = self._transport(url, headers, body)
                # mocks may return (dict, headers) or a dict carrying "__headers__"
                if isinstance(r, tuple) and len(r) == 2:
                    r, resp_headers = r
                elif isinstance(r, dict) and "__headers__" in r:
                    r = dict(r)
                    resp_headers = r.pop("__headers__")
            else:
                req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_headers = resp.headers
                    r = json.load(resp)
        except urllib.error.HTTPError as e:
            self._observe_headers(slot, getattr(e, "headers", None))
            raw = e.read().decode("utf-8", "replace")[:800]
            if _is_quota_body(e.code, raw):
                raise QuotaExhausted(f"{slot['provider']}/{slot['model']} quota: HTTP {e.code}") from None
            if _is_rate_limit(e.code, raw):
                raise RateLimitError(f"{slot['provider']}/{slot['model']} rate-limit: HTTP {e.code}") from None
            raise ProviderError(f"{slot['provider']}/{slot['model']} HTTP {e.code}: {raw[:300]!r}") from None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise ProviderError(f"{slot['provider']}/{slot['model']} transport: {e}") from None

        self._observe_headers(slot, resp_headers)
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
        row = {
            "step": self.step or None,
            "provider": slot["provider"], "model": slot["model"], "paid": slot["paid"],
            "servedModel": (r.get("model") if isinstance(r, dict) else None) or slot["model"],
            "prompt": int(u.get("prompt_tokens") or 0),
            "completion": int(u.get("completion_tokens") or 0),
            "reasoning": int(details.get("reasoning_tokens") or 0),
            "total": int(u.get("total_tokens") or 0) or (int(u.get("prompt_tokens") or 0) + int(u.get("completion_tokens") or 0)),
            "latencySec": round(time.time() - t0, 2),
            "ok": True,
        }
        self.call_log.append(row)
        if slot["provider"] == "tokenharbor":
            record_usage(row, self.quota_path)
        try:
            content = r["choices"][0]["message"].get("content")
            if not content:
                # reasoning-only models sometimes put the answer in reasoning — refuse & advance
                raise BadJSON("empty content (reasoning-only response)")
            return json.loads(content)
        except (KeyError, IndexError, ValueError, TypeError) as e:
            row["ok"] = False
            row["error"] = f"bad JSON: {str(e)[:120]}"
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
    r = c.routing
    print("slots:", r["order"])
    print(f"tokenharbor used {r['pct']:.1%} (route at {r['routePct']:.0%}) routed={r['routed']} — source: {r['source']}"
          + (f", resets {r.get('resetsRaw')}" if r.get('header') else "")
          + f"; ledger estimate {r['used']}/{r['budget']} ({r.get('ledgerPct', r['pct']):.1%}) {r['ledger']}")
