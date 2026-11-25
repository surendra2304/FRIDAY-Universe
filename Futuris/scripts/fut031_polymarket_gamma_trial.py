#!/usr/bin/env python3
"""TASK-FUT-031 Polymarket Gamma trial (read-only, no auth, no keys).

Proves, with live evidence, whether the free unauthenticated Polymarket
Gamma API is readable as a Futuris forecasting signal — and that nothing
is integrated: this script performs GETs only, holds no credentials, and
creates no order/wallet path (Polymarket trading is a real-money venue and
out of scope; the registry verdict is reference-only, integrate nothing).

Usage:
    python3 Futuris/scripts/fut031_polymarket_gamma_trial.py [--limit N]
    python3 Futuris/scripts/fut031_polymarket_gamma_trial.py --offline
        Runs only the failure cases (malformed record + simulated
        disconnect) with no network access.

Exit 0 when the trial completes (signal readable or failure cases behave
as specified); exit 1 only when the trial itself cannot run.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

GAMMA_URL = "https://gamma-api.polymarket.com/markets?limit={limit}&active=true"
TIMEOUT_S = 20


def parse_market(record):
    """Parse one Gamma market into (question, [(outcome, prob), ...]).

    Returns None for a malformed record (missing question/outcomes/prices,
    or unparseable prices) — skipped, never repaired.
    """
    try:
        question = record.get("question")
        outcomes = json.loads(record.get("outcomes") or "null")
        prices = json.loads(record.get("outcomePrices") or "null")
        if not question or not isinstance(outcomes, list) or not isinstance(prices, list):
            return None
        if len(outcomes) != len(prices) or not outcomes:
            return None
        probs = [float(p) for p in prices]
        return question, list(zip(outcomes, probs))
    except (TypeError, ValueError, AttributeError):
        return None


def fetch_markets(limit):
    req = urllib.request.Request(
        GAMMA_URL.format(limit=limit),
        headers={"User-Agent": "FRIDAY-Futuris-FUT-031-trial"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.load(resp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--offline", action="store_true",
                    help="failure cases only, no network")
    args = ap.parse_args()

    print("TASK-FUT-031 Polymarket Gamma trial (read-only, no auth, no keys)")
    print("endpoint:", GAMMA_URL.format(limit=args.limit))

    # Failure case 1: malformed record parses to None, skipped.
    malformed = {"id": "x"}
    parsed = parse_market(malformed)
    print("failure-case malformed-record: parse ->", parsed,
          "(expected None: skipped, never repaired)")
    assert parsed is None, "malformed record must parse to None"

    # Failure case 2: simulated feed disconnect surfaces, no order path.
    try:
        req = urllib.request.Request("https://invalid.gamma-api.polymarket.invalid/markets")
        urllib.request.urlopen(req, timeout=5)
        print("failure-case disconnect: UNEXPECTED success (no error raised)")
        return 1
    except Exception as exc:  # noqa: BLE001 - the point is that it raises
        print(f"failure-case disconnect: {type(exc).__name__} surfaces "
              "(expected; read-only GET, no order/wallet path exists)")
    if args.offline:
        print("offline mode: live fetch skipped; failure cases behave as specified.")
        return 0

    try:
        markets = fetch_markets(args.limit)
    except Exception as exc:  # noqa: BLE001 - report, do not crash
        print(f"live fetch FAILED: {type(exc).__name__}: {exc}")
        print("verdict: signal NOT readable from this host right now; "
              "nothing integrated (reference-only stands).")
        return 0
    print(f"live fetch: {len(markets)} markets returned")
    readable = 0
    for m in markets:
        parsed = parse_market(m)
        if parsed is None:
            print("  skipped malformed record:", str(m)[:120])
            continue
        question, probs = parsed
        total = sum(p for _, p in probs)
        print(f"  - {question[:90]}")
        for outcome, p in probs:
            print(f"      {outcome}: {p:.4f}")
        print(f"      prob sum: {total:.4f} (expect ~1.0)")
        readable += 1
    print(f"verdict: signal readable YES ({readable}/{len(markets)} markets parsed); "
          "integrated into Futuris: NO (reference-only, integrate nothing).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
