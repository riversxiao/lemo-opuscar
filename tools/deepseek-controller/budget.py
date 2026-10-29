"""Automated budget ledger for deepseek-controller runs.

Append-only JSONL under fixtures/budget-ledger.jsonl. Honest costs only —
never invent token/$ figures. Local controller steps log usd=0 with duration.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent
DEFAULT_LEDGER = ROOT / "fixtures" / "budget-ledger.jsonl"
# $WORDFILM_BUDGET_LEDGER (or the upstream name $DC_BUDGET_LEDGER) points runs and
# the test harness at another ledger so they do not append to the tracked fixture.
# Read at call time, so a test can set it after import.
LEDGER_ENV = ("WORDFILM_BUDGET_LEDGER", "DC_BUDGET_LEDGER")
SHANGHAI = timezone(timedelta(hours=8))

# OpenCode session DB of the current user (optional seed import).
DEFAULT_OPENCODE_DB = Path(
    os.environ.get("WORDFILM_OPENCODE_DB")
    or os.environ.get("LEMO_OPENCODE_DB")
    or Path.home() / ".local" / "share" / "opencode" / "opencode.db"
)


def now_iso_shanghai() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def ledger_path(path: Path | None = None) -> Path:
    """Explicit path > $WORDFILM_BUDGET_LEDGER > $DC_BUDGET_LEDGER > fixtures ledger."""
    if path is None:
        env = next((os.environ[k] for k in LEDGER_ENV if os.environ.get(k)), None)
        if env:
            path = Path(env)
    return (path or DEFAULT_LEDGER).resolve()


def append_entry(
    entry: dict[str, Any],
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    """Append one JSON object as a line. Returns the normalized entry."""
    lp = ledger_path(path)
    lp.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": entry.get("ts") or now_iso_shanghai(),
        "kind": entry.get("kind") or "manual",
        "item": entry.get("item") or "",
        "usd": float(entry.get("usd") if entry.get("usd") is not None else 0.0),
        "tokensIn": int(entry.get("tokensIn") or 0),
        "tokensOut": int(entry.get("tokensOut") or 0),
        "durationSec": entry.get("durationSec"),
        "path": entry.get("path"),  # controller | flash | handoff | …
        "project": entry.get("project"),
        "model": entry.get("model"),
        "source": entry.get("source") or "manual",
        "notes": entry.get("notes") or "",
        "meta": entry.get("meta") or {},
    }
    # Optional billed amount in CNY (e.g. DeepSeek official API balance delta).
    if entry.get("cny") is not None:
        row["cny"] = round(float(entry["cny"]), 4)
    # Drop null duration for cleaner lines
    if row["durationSec"] is None:
        del row["durationSec"]
    with lp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def log_local_step(
    item: str,
    *,
    duration_sec: float | None = None,
    project: str | None = None,
    path_label: str = "controller",
    notes: str = "",
    ledger: Path | None = None,
) -> dict[str, Any]:
    """Record a $0 local step (scaffold/mux/quality/handoff/…)."""
    return append_entry(
        {
            "kind": "local",
            "item": item,
            "usd": 0.0,
            "durationSec": round(duration_sec, 3) if duration_sec is not None else None,
            "path": path_label,
            "project": project,
            "source": "controller",
            "notes": notes or "local box CPU/GPU; no LLM cash",
        },
        path=ledger,
    )


def read_entries(path: Path | None = None) -> list[dict[str, Any]]:
    lp = ledger_path(path)
    if not lp.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in lp.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def summarize(path: Path | None = None) -> dict[str, Any]:
    rows = read_entries(path)
    total_usd = sum(float(r.get("usd") or 0) for r in rows)
    total_cny = sum(float(r.get("cny") or 0) for r in rows)
    tin = sum(int(r.get("tokensIn") or 0) for r in rows)
    tout = sum(int(r.get("tokensOut") or 0) for r in rows)
    by_kind: dict[str, float] = {}
    by_path: dict[str, float] = {}
    for r in rows:
        k = str(r.get("kind") or "unknown")
        by_kind[k] = by_kind.get(k, 0.0) + float(r.get("usd") or 0)
        p = str(r.get("path") or "unknown")
        by_path[p] = by_path.get(p, 0.0) + float(r.get("usd") or 0)
    return {
        "entries": len(rows),
        "totalUsd": round(total_usd, 6),
        "totalCny": round(total_cny, 4),
        "tokensIn": tin,
        "tokensOut": tout,
        "byKind": {k: round(v, 6) for k, v in sorted(by_kind.items())},
        "byPath": {k: round(v, 6) for k, v in sorted(by_path.items())},
        "ledger": str(ledger_path(path)),
    }


def import_opencode_sessions(
    *,
    db_path: Path | None = None,
    ledger: Path | None = None,
    title_substr: str | None = None,
    min_usd: float = 0.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """One-shot seed from OpenCode session_v2 cost columns.

    Only imports rows with known numeric cost. Skips sessions already present
    (matched by meta.sessionId). Never invents costs.
    """
    db = Path(db_path or DEFAULT_OPENCODE_DB)
    if not db.is_file():
        return {"ok": False, "error": f"opencode db missing: {db}", "imported": 0}

    existing = {
        (r.get("meta") or {}).get("sessionId")
        for r in read_entries(ledger)
        if (r.get("meta") or {}).get("sessionId")
    }

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    sql = """
        SELECT id, title, cost, tokens_input, tokens_output, tokens_reasoning,
               directory, model, time_created
        FROM session_v2
        WHERE cost IS NOT NULL
    """
    rows = cur.execute(sql).fetchall()
    con.close()

    imported = 0
    skipped = 0
    candidates: list[dict[str, Any]] = []
    for row in rows:
        sid = row["id"]
        if sid in existing:
            skipped += 1
            continue
        try:
            usd = float(row["cost"] or 0)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if usd < min_usd and usd != 0:
            # still allow exact 0 if min_usd==0; filter tiny noise only when min>0
            pass
        if usd < min_usd:
            skipped += 1
            continue
        title = row["title"] or ""
        directory = row["directory"] or ""
        if title_substr:
            blob = f"{title} {directory} {sid}"
            if title_substr.lower() not in blob.lower():
                skipped += 1
                continue
        # Prefer Asia/Shanghai wall time from unix ms/sec if present
        ts_raw = row["time_created"]
        ts = now_iso_shanghai()
        if isinstance(ts_raw, (int, float)) and ts_raw > 0:
            # OpenCode uses ms epoch
            sec = ts_raw / 1000.0 if ts_raw > 1e12 else float(ts_raw)
            ts = datetime.fromtimestamp(sec, tz=SHANGHAI).isoformat(timespec="seconds")
        entry = {
            "ts": ts,
            "kind": "opencode-session",
            "item": title or sid,
            "usd": round(usd, 8),
            "tokensIn": int(row["tokens_input"] or 0),
            "tokensOut": int(row["tokens_output"] or 0),
            "path": "flash",
            "project": directory or None,
            "model": row["model"],
            "source": "opencode.db",
            "notes": f"imported session {sid}",
            "meta": {
                "sessionId": sid,
                "tokensReasoning": int(row["tokens_reasoning"] or 0)
                if "tokens_reasoning" in row.keys()
                else 0,
            },
        }
        candidates.append(entry)

    if not dry_run:
        for e in candidates:
            append_entry(e, path=ledger)
            imported += 1
    else:
        imported = 0

    return {
        "ok": True,
        "db": str(db),
        "imported": imported if not dry_run else 0,
        "wouldImport": len(candidates),
        "skipped": skipped,
        "dryRun": dry_run,
        "sumUsdWould": round(sum(c["usd"] for c in candidates), 6),
    }


class timed_local:
    """Context manager: log a $0 local step with wall duration."""

    def __init__(
        self,
        item: str,
        *,
        project: str | None = None,
        path_label: str = "controller",
        notes: str = "",
        ledger: Path | None = None,
        enabled: bool = True,
    ):
        self.item = item
        self.project = project
        self.path_label = path_label
        self.notes = notes
        self.ledger = ledger
        self.enabled = enabled
        self.t0 = 0.0
        self.entry: dict[str, Any] | None = None

    def __enter__(self) -> "timed_local":
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self.enabled:
            return
        dur = time.perf_counter() - self.t0
        note = self.notes
        if exc_type is not None:
            note = (note + "; " if note else "") + f"failed:{exc_type.__name__}"
        self.entry = log_local_step(
            self.item,
            duration_sec=dur,
            project=self.project,
            path_label=self.path_label,
            notes=note,
            ledger=self.ledger,
        )
