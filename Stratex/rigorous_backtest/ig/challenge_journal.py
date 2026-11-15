"""Prop-firm challenge tracker + fully public trade journal.

TASK-IG-STR-10 (IG corpus item DappZ3Kz40y).

Tracks a prop-firm-style challenge as pure bookkeeping: starting
balance, profit target, maximum daily loss, maximum total drawdown —
with every event written to an append-only, hash-chained journal and
a public markdown report that shows the whole history, breaches
included. The point of the pattern is forward-test discipline: the
journal is public precisely so the record cannot be curated.

TRACKING ONLY. This module connects to no broker or prop firm, holds
no credentials, and places no trades. Whether the owner ever attempts
a real challenge is a separate, real-money decision this code does
not make. Rule basis (stated, since firms differ): daily-loss and
total-drawdown limits are measured against the STARTING balance;
a daily-loss breach and a total-drawdown breach both end the
challenge as failed, recorded distinctly.

Stdlib only, Python 3.10-compatible.
"""

import hashlib
import json
import os

GENESIS = "0" * 64


def _hash(prev_hash, payload):
    return hashlib.sha256((prev_hash + payload).encode("utf-8")).hexdigest()


def _append(path, event):
    prev = GENESIS
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        if lines:
            prev = json.loads(lines[-1])["hash"]
    rec = dict(event)
    rec["prev_hash"] = prev
    rec["hash"] = _hash(prev, json.dumps(rec, sort_keys=True))
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def create_challenge(name, start_balance, profit_target_pct,
                     max_daily_loss_pct, max_total_dd_pct,
                     journal_path=None):
    """Create a challenge state and journal its creation."""
    if start_balance <= 0:
        raise ValueError("start_balance must be > 0")
    for label, v in (("profit_target_pct", profit_target_pct),
                     ("max_daily_loss_pct", max_daily_loss_pct),
                     ("max_total_dd_pct", max_total_dd_pct)):
        if not 0 < v < 1:
            raise ValueError("%s must be in (0, 1)" % label)
    state = {
        "name": name,
        "start_balance": float(start_balance),
        "balance": float(start_balance),
        "profit_target_pct": profit_target_pct,
        "max_daily_loss_pct": max_daily_loss_pct,
        "max_total_dd_pct": max_total_dd_pct,
        "status": "active",  # active | passed | failed_daily | failed_total
        "days": 0,
        "journal_path": journal_path,
    }
    _append(journal_path, {"type": "challenge_created", "name": name,
                           "start_balance": state["start_balance"],
                           "profit_target_pct": profit_target_pct,
                           "max_daily_loss_pct": max_daily_loss_pct,
                           "max_total_dd_pct": max_total_dd_pct})
    return state


def apply_day(state, date, day_pnl):
    """Close one trading day: apply P&L, evaluate the rules in order
    (daily loss, total drawdown, profit target), journal the outcome.
    Mutates and returns state. Terminal states reject further days."""
    if state["status"] != "active":
        raise ValueError("challenge is %s; no further days" % state["status"])
    start = state["start_balance"]
    state["balance"] += day_pnl
    state["days"] += 1
    event = {"type": "day_closed", "date": date, "day_pnl": day_pnl,
             "balance": state["balance"], "day": state["days"]}
    if day_pnl <= -state["max_daily_loss_pct"] * start:
        state["status"] = "failed_daily"
        event["result"] = "breach_daily_loss"
    elif state["balance"] <= start * (1 - state["max_total_dd_pct"]):
        state["status"] = "failed_total"
        event["result"] = "breach_total_drawdown"
    elif state["balance"] >= start * (1 + state["profit_target_pct"]):
        state["status"] = "passed"
        event["result"] = "target_reached"
    else:
        event["result"] = "active"
    _append(state.get("journal_path"), event)
    return state


def read_journal(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh.read().splitlines() if ln.strip()]


def verify_journal(path):
    prev = GENESIS
    for rec in read_journal(path):
        stored = rec.get("hash")
        body = {k: v for k, v in rec.items() if k != "hash"}
        if body.get("prev_hash") != prev:
            return False
        if _hash(prev, json.dumps(body, sort_keys=True)) != stored:
            return False
        prev = stored
    return True


def public_report(state):
    """The full public report: rules, current status, and EVERY
    journal day — the journal is the product, so nothing is omitted."""
    lines = [
        "# Challenge journal — %s" % state["name"],
        "",
        "Start balance: %.2f | Target: +%.1f%% | Max daily loss: %.1f%% "
        "| Max total drawdown: %.1f%%" % (
            state["start_balance"], state["profit_target_pct"] * 100,
            state["max_daily_loss_pct"] * 100,
            state["max_total_dd_pct"] * 100),
        "Status: **%s** after %d day(s); balance %.2f"
        % (state["status"], state["days"], state["balance"]),
        "",
        "| Day | Date | P&L | Balance | Result |",
        "|---|---|---|---|---|",
    ]
    for rec in read_journal(state.get("journal_path")):
        if rec.get("type") == "day_closed":
            lines.append("| %d | %s | %+.2f | %.2f | %s |" % (
                rec["day"], rec["date"], rec["day_pnl"], rec["balance"],
                rec["result"]))
    return "\n".join(lines) + "\n"
