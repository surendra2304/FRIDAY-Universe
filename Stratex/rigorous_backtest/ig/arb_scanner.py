"""Cross-venue arbitrage scanner — PAPER ONLY.

TASK-IG-STR-07 (IG corpus item DXYCIhsjHKY).

Scans quote snapshots from multiple venues for the same symbol and
reports price discrepancies that survive fees: buy at venue A's ask,
sell at venue B's bid, net of both sides' taker fees and a caller-set
slippage buffer. Survivors are recorded to an append-only,
hash-chained PAPER journal.

THERE IS NO EXECUTION PATH IN THIS MODULE — no order functions, no
venue clients, no keys. A paper opportunity is a measurement, not a
trade: apparent discrepancies are usually latency, withdrawal limits,
or stale quotes, which is exactly why this family is registered as an
RD-programme candidate (see the claim/PR): any strategy use must pass
the full programme bar (expectancy/PF/folds/2x costs/Bonferroni/
holdout) on realistically-modelled fills first. RD-006's lesson
applies: paper edges that ignore frictions do not survive contact
with costs.

Input quotes: dicts {venue, symbol, bid, ask, ts} (ts = any sortable
timestamp value, carried through, never interpreted). Stdlib only,
Python 3.10-compatible.
"""

import hashlib
import json
import os

GENESIS = "0" * 64


def find_opportunities(quotes, fee_bps_per_side=10.0, buffer_bps=0.0,
                       min_net_bps=0.0):
    """All ordered venue pairs (buy != sell) whose net edge clears
    min_net_bps. Returns records sorted by net edge, best first."""
    if fee_bps_per_side < 0 or buffer_bps < 0:
        raise ValueError("fees and buffer must be >= 0")
    by_symbol = {}
    for q in quotes:
        if q["ask"] <= 0 or q["bid"] <= 0 or q["bid"] > q["ask"]:
            raise ValueError("invalid quote: %r" % (q,))
        by_symbol.setdefault(q["symbol"], []).append(q)
    out = []
    for symbol, qs in by_symbol.items():
        for buy in qs:
            for sell in qs:
                if buy["venue"] == sell["venue"]:
                    continue
                gross_bps = (sell["bid"] - buy["ask"]) / buy["ask"] * 10000.0
                net_bps = gross_bps - 2 * fee_bps_per_side - buffer_bps
                if net_bps > min_net_bps:
                    out.append({
                        "symbol": symbol,
                        "buy_venue": buy["venue"], "sell_venue": sell["venue"],
                        "buy_ask": buy["ask"], "sell_bid": sell["bid"],
                        "gross_bps": gross_bps, "net_bps": net_bps,
                        "fee_bps_per_side": fee_bps_per_side,
                        "buffer_bps": buffer_bps,
                        "ts": buy.get("ts"),
                        "paper_only": True,
                    })
    out.sort(key=lambda o: o["net_bps"], reverse=True)
    return out


def _hash(prev_hash, payload):
    return hashlib.sha256((prev_hash + payload).encode("utf-8")).hexdigest()


def record_opportunities(path, opportunities):
    """Append paper opportunities to the hash-chained journal at
    `path`. Returns the number appended. The journal is evidence for
    the RD evaluation — entries are never edited or deleted."""
    prev = GENESIS
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        if lines:
            prev = json.loads(lines[-1])["hash"]
    n = 0
    with open(path, "a", encoding="utf-8") as fh:
        for opp in opportunities:
            rec = dict(opp)
            rec["prev_hash"] = prev
            rec["hash"] = _hash(prev, json.dumps(rec, sort_keys=True))
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
            prev = rec["hash"]
            n += 1
    return n


def verify_journal(path):
    if not os.path.exists(path):
        return True
    prev = GENESIS
    with open(path, "r", encoding="utf-8") as fh:
        for ln in fh.read().splitlines():
            if not ln.strip():
                continue
            rec = json.loads(ln)
            stored = rec.get("hash")
            body = {k: v for k, v in rec.items() if k != "hash"}
            if body.get("prev_hash") != prev:
                return False
            if _hash(prev, json.dumps(body, sort_keys=True)) != stored:
                return False
            prev = stored
    return True
