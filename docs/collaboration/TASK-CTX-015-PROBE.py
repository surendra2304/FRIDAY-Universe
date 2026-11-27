#!/usr/bin/env python3
"""TASK-CTX-015 probe: Cortex escalation ratio, fires vs messages actually
sent over the last 48h of live Cortex logs.

Method (runs 1-8: TASK-CTX-004 / 006 / 007 / 010 / 011 / 012 / 013 / 014):
  fires    = supervisor cycles (SelfHealingLoop.cycles, 30 s tick) in the
             window, from the endpoint snapshot + journal /ready-probe
             counts; the aged-out journal head (retention ~47.8h < 48h) is
             estimated from measured cadence and labelled (est.).
  messages = Telegram deliveries: EscalationNotifier attempts/delivered in
             SelfHealingLoop.status() -> escalation_channel (endpoint
             snapshot); in-window events from the endpoint `escalations`
             list. The journal holds no escalation lines (runs 2/3/8), so
             the endpoint is authoritative for messages.
  ratio    = fires : delivered (in-window), plus attempts/fires and the
             delivery gap (attempts - delivered), read against the
             post-#1054 suppression layers (once per failure streak + 6h
             notifier dedupe, Cortex/packages/core/src/cortex_core/
             resilience.py).

This script does NOT touch the network, the bridge, or any server, and it
handles no key material. It takes the endpoint snapshot JSON and the
journal-aggregate JSON (both produced by the read-only live leg, Server 1)
as inputs and computes the ratio. --dry-run validates the arithmetic
against the published run-8 (CTX-014) figures.

Live-leg commands (read-only, Server 1, run via the bridge; key read
inside the server shell only, never printed/copied/committed):
  systemctl show Cortex.service -p ActiveState,SubState,MainPID,NRestarts
  KEY=$(grep -m1 '^FRIDAY_API_KEY=' /opt/friday_universe/FRIDAY/.env | cut -d= -f2-)
  curl -s -m 25 -H "X-Friday-Api-Key: $KEY" http://127.0.0.1:8009/v1/friday/self_healing
  journalctl -u Cortex.service --since '<window-start>' --until '<window-end>' --no-pager -o short-iso
    | wc -l ; | head -3 ; | tail -3
    | grep -e 'Stopped FRIDAY Universe' -e 'Started FRIDAY Universe' -e 'Stopping FRIDAY Universe'
    | grep -ci escalat ; | grep -ci deliver ; | grep -ci 'did not restore health'
    | grep -c '/ready'   (supervisor tick lines, counted as fires proxy)

Usage:
  python3 TASK-CTX-015-PROBE.py --snapshot SNAP.json --journal JOURNAL.json
  python3 TASK-CTX-015-PROBE.py --dry-run   # fixture from CTX-014 run 8
"""
import argparse
import json
import sys
from datetime import datetime, timezone

# Run-8 baseline (CTX-014, snapshot 2026-11-27T15:37:24Z = 21:07:24 IST).
# Cumulative counters at that snapshot; the in-window event is the
# ai_universe escalation 2026-11-27T10:45:11Z (16:15:11 IST).
RUN8_FIXTURE = {
    "snapshot": {
        "observed_at": "2026-11-27T15:37:24Z",
        "background": {"cycles": 8292, "running": True},
        "escalation_delivery": {
            "channel": "telegram:api.telegram.org",
            "attempts": 2, "delivered": 2, "suppressed_duplicates": 0,
            "consecutive_failed_deliveries": 0, "channel_broken": False,
        },
        "escalations": [
            {"subsystem": "redis", "at": "2026-11-24T14:06:06Z"},
            {"subsystem": "ai_universe", "at": "2026-11-27T10:45:11Z"},
        ],
        "ratio_check": {"consecutive_failed_deliveries": 0,
                        "channel_broken": False, "last_alert": None},
    },
    "journal": {
        "window_start": "2026-11-25T15:37:24Z",
        "window_end": "2026-11-27T15:37:24Z",
        "retained_since": "2026-11-25T15:47:25Z",
        "ready_probes": 5367,
        "keyword_counts": {"escalat": 0, "deliver": 0, "Telegram": 0,
                           "notif": 0, "repair": 0, "SelfHealing": 0,
                           "supervisor": 0, "streak": 0,
                           "did not restore health": 0, "cycle": 0,
                           "ERROR": 0, "CRITICAL": 0, "WARN": 7},
    },
    # Previous run-7 cumulative counters, for the delta check.
    # (Only attempts/delivered are used; cycles are cumulative and are
    # compared via the journal derivation instead.)
    "prev_cumulative": {"attempts": 1, "delivered": 1},
}


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def compute(snapshot, journal, prev_cumulative=None):
    bg = snapshot.get("background", {})
    ed = snapshot.get("escalation_delivery", {})
    escs = snapshot.get("escalations", []) or []
    observed = parse_ts(snapshot["observed_at"])
    w_start = parse_ts(journal["window_start"])
    w_end = parse_ts(journal["window_end"])
    retained = parse_ts(journal["retained_since"])
    window_h = (w_end - w_start).total_seconds() / 3600.0
    covered_h = (w_end - retained).total_seconds() / 3600.0
    head_h = (retained - w_start).total_seconds() / 3600.0

    counted = int(journal["ready_probes"])
    cadence = counted / covered_h if covered_h > 0 else 0.0
    head_est = round(head_h * cadence)
    fires = counted + head_est

    # In-window escalations: endpoint list, filtered to the window.
    in_window = [e for e in escs
                 if w_start <= parse_ts(e["at"]) <= w_end]
    attempts = int(ed.get("attempts", 0))
    delivered = int(ed.get("delivered", 0))
    if prev_cumulative is not None:
        attempts = attempts - int(prev_cumulative.get("attempts", 0))
        delivered = delivered - int(prev_cumulative.get("delivered", 0))

    return {
        "window_hours_requested": round(window_h, 2),
        "window_hours_covered": round(covered_h, 2),
        "window_head_hours_aged_out": round(head_h, 2),
        "fires_counted": counted,
        "fires_head_est": head_est,
        "fires_total": fires,
        "cadence_per_hour": round(cadence, 1),
        "attempts_in_window": attempts,
        "delivered_in_window": delivered,
        "delivery_gap": attempts - delivered,
        "in_window_events": len(in_window),
        "ratio_fires_per_delivery": (round(fires / delivered, 1)
                                     if delivered else None),
        "attempt_rate_pct": (round(100.0 * attempts / fires, 2)
                             if fires else None),
        "suppressed_duplicates": ed.get("suppressed_duplicates"),
        "consecutive_failed_deliveries":
            ed.get("consecutive_failed_deliveries"),
        "channel_broken": ed.get("channel_broken"),
        "journal_keyword_counts": journal.get("keyword_counts", {}),
        "verdict": ("RATIO FILED" if delivered else
                    "NO DELIVERY IN WINDOW (ratio is fires:0, not a gap)"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot")
    ap.add_argument("--journal")
    ap.add_argument("--prev-cumulative")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        fx = RUN8_FIXTURE
        res = compute(fx["snapshot"], fx["journal"], fx["prev_cumulative"])
        print(json.dumps(res, indent=2))
        # Assertions against the published run-8 figures (CTX-014 §0/§3):
        # ~5,390 fires, 1 attempt, 1 delivered, no delivery gap.
        assert 5300 <= res["fires_total"] <= 5500, res["fires_total"]
        assert res["attempts_in_window"] == 1, res
        assert res["delivered_in_window"] == 1, res
        assert res["delivery_gap"] == 0, res
        assert res["in_window_events"] == 1, res
        assert res["channel_broken"] is False, res
        assert res["consecutive_failed_deliveries"] == 0, res
        print("DRY-RUN OK: run-8 fixture reproduces "
              f"~{res['fires_total']} fires, "
              f"{res['attempts_in_window']} attempt, "
              f"{res['delivered_in_window']} delivered, gap 0")
        return 0

    if not args.snapshot or not args.journal:
        ap.error("--snapshot and --journal are required (or --dry-run)")
    with open(args.snapshot) as f:
        snapshot = json.load(f)
    with open(args.journal) as f:
        journal = json.load(f)
    prev = None
    if args.prev_cumulative:
        with open(args.prev_cumulative) as f:
            prev = json.load(f)
    res = compute(snapshot, journal, prev)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
