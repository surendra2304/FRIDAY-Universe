"""Bytez free-tier quota probe — the empirical trial harness (TASK-IG2-INF-01).

The Bytez spec card's condition for counting Bytez in the quota ledger is
*empirical proof* of recurring free volume: the $0 tier's limits (≤7B open
models, 1 concurrent request) are documented, but no recurring free
credit/token allowance is. This probe is how that proof is gathered —
honestly, and without spending anything:

* It sends a small number of *sequential* (concurrency 1, matching the free
  tier) minimal chat completions — an 8-token reply to a one-line prompt —
  against a ≤7B open model, spaced a few seconds apart.
* It classifies every attempt (success / rate_limited / auth_error /
  http_error / transport_error) and stops at the first 429: the round at
  which the ceiling bites *is* the measurement.
* The verdict is deliberately narrow. ``proven`` means only "N consecutive
  minimal requests succeeded in this run" — a single run cannot prove a
  *recurring* (daily/monthly) allowance, and the report says so. Promotion
  of Bytez into the quota ledger (declaring a limit) and enabling its
  gateway rung remain operator decisions taken after repeated probe runs,
  e.g. across several days.

Probe traffic bypasses the gateway on purpose: it is measurement, not
serving, and must not pollute the production quota ledger's attempt counts.

Usage::

    BYTEZ_API_KEY=... python -m app.providers.bytez_probe [--rounds 5] [--interval 3]

The report is printed as JSON and also written (best-effort) to
``app/.data/bytez_probe-<utc>.json``; :func:`latest_probe_report` reads the
newest report back for the admin dashboard.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.providers.bytez import BYTEZ_BASE_URL, BYTEZ_DEFAULT_MODEL

PROBE_MODEL = os.environ.get("INFERENCE_BYTEZ_PROBE_MODEL", BYTEZ_DEFAULT_MODEL)
_DEFAULT_REPORT_DIR = Path(__file__).resolve().parent.parent / ".data"
REPORT_DIR = Path(os.environ.get("INFERENCE_BYTEZ_PROBE_DIR", str(_DEFAULT_REPORT_DIR)))

#: Outcomes that end a probe run immediately: the ceiling (or a dead key)
#: has been found, and further attempts would only add noise — or, on a
#: metered tier, risk.
_STOP_OUTCOMES = frozenset({"rate_limited", "auth_error"})


def _bytez_key() -> str | None:
    for name in ("BYTEZ_API_KEYS", "BYTEZ_API_KEY"):
        raw = os.environ.get(name)
        if raw:
            first = raw.split(",")[0].strip()
            if first:
                return first
    return None


def classify_status(status_code: int) -> str:
    if status_code == 200:
        return "success"
    if status_code == 429:
        return "rate_limited"
    if status_code in (401, 403):
        return "auth_error"
    return "http_error"


def build_verdict(attempts: list[dict[str, Any]], rounds_requested: int) -> dict[str, Any]:
    """Reduce raw attempts to an honest verdict. Pure function — unit-tested."""
    successes = sum(1 for a in attempts if a["outcome"] == "success")
    first_429 = next((a["round"] for a in attempts if a["outcome"] == "rate_limited"), None)
    if not attempts:
        verdict = "no_attempts"
    elif successes == len(attempts) == rounds_requested:
        verdict = "proven_for_this_run"
    elif first_429 is not None:
        verdict = "rate_limited"
    elif any(a["outcome"] == "auth_error" for a in attempts):
        verdict = "auth_error"
    else:
        verdict = "inconclusive"
    return {
        "verdict": verdict,
        "rounds_requested": rounds_requested,
        "rounds_attempted": len(attempts),
        "successes": successes,
        "first_rate_limited_round": first_429,
        "meaning": {
            "proven_for_this_run": (
                "Every probe request succeeded. This proves the key works and the free tier "
                "served this run only — it does NOT prove a recurring daily/monthly free "
                "allowance. Re-run across several days before declaring any ledger limit."
            ),
            "rate_limited": (
                "The free-tier ceiling bit during the run (see first_rate_limited_round). "
                "Whatever volume exists is smaller than this probe's demand."
            ),
            "auth_error": "The configured key was rejected (401/403). No free volume can be claimed.",
            "inconclusive": "Attempts failed for non-quota reasons; the free allowance remains unmeasured.",
            "no_attempts": "No attempts were made (no key configured).",
        }[verdict],
    }


async def run_probe(
    *,
    rounds: int = 5,
    interval_seconds: float = 3.0,
    model: str = PROBE_MODEL,
    api_key: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Run the probe and return the report dict (also persisted best-effort)."""
    key = api_key if api_key is not None else _bytez_key()
    started = time.time()
    attempts: list[dict[str, Any]] = []
    if key is None:
        report = {
            "service": "inference",
            "provider": "bytez",
            "model": model,
            "generated_at_utc": datetime.fromtimestamp(started, tz=timezone.utc).isoformat(),
            "attempts": attempts,
            **build_verdict(attempts, rounds),
            "note": "No BYTEZ_API_KEY(S) configured in this environment; nothing was sent.",
        }
        _persist(report)
        return report

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
    try:
        for round_no in range(1, rounds + 1):
            if round_no > 1:
                await asyncio.sleep(interval_seconds)
            t0 = time.perf_counter()
            attempt: dict[str, Any] = {"round": round_no, "ts": time.time()}
            try:
                resp = await client.post(
                    f"{BYTEZ_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
                        "max_tokens": 8,
                        "temperature": 0.0,
                    },
                )
                attempt["status_code"] = resp.status_code
                attempt["outcome"] = classify_status(resp.status_code)
                if resp.status_code == 200:
                    try:
                        usage = resp.json().get("usage") or {}
                        attempt["total_tokens"] = usage.get("total_tokens")
                    except ValueError:
                        attempt["total_tokens"] = None
            except httpx.HTTPError as exc:
                attempt["status_code"] = None
                attempt["outcome"] = "transport_error"
                attempt["error"] = type(exc).__name__
            attempt["latency_seconds"] = round(time.perf_counter() - t0, 3)
            attempts.append(attempt)
            if attempt["outcome"] in _STOP_OUTCOMES:
                break
    finally:
        if owns_client:
            await client.aclose()

    report = {
        "service": "inference",
        "provider": "bytez",
        "model": model,
        "generated_at_utc": datetime.fromtimestamp(started, tz=timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - started, 3),
        "attempts": attempts,
        **build_verdict(attempts, rounds),
        "ledger_rule": (
            "Bytez carries NO declared quota-ledger limit until an operator, having read "
            "repeated probe reports, declares one via configuration. This probe never "
            "promotes Bytez by itself."
        ),
    }
    _persist(report)
    return report


def _persist(report: dict[str, Any]) -> None:
    """Best-effort report persistence; a failed write never fails the probe."""
    try:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.fromtimestamp(time.time(), tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (REPORT_DIR / f"bytez_probe-{stamp}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    except OSError:
        pass


def latest_probe_report() -> dict[str, Any] | None:
    """The newest persisted probe report, or None when no probe has run."""
    try:
        files = sorted(REPORT_DIR.glob("bytez_probe-*.json"))
        if not files:
            return None
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe Bytez's free tier empirically (TASK-IG2-INF-01).")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds between attempts (concurrency is 1).")
    parser.add_argument("--model", default=PROBE_MODEL)
    args = parser.parse_args(argv)
    report = asyncio.run(run_probe(rounds=args.rounds, interval_seconds=args.interval, model=args.model))
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] in ("proven_for_this_run",) else 1


if __name__ == "__main__":
    raise SystemExit(main())
