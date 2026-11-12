#!/usr/bin/env python3
"""
agents_completion_notifier.py — Telegram notification when BOTH ZAI agents finish.

Owner requirement (2026-11-13): when both ZAI agents (Agent 1 and Agent 2)
complete their work, a Telegram notification must be sent. The single-agent
notify_turn_complete.py was manual-only; this coordinator makes it automatic.

Design (shared-filesystem, lock-safe, no AI in the loop):
  data/agent_completion.json holds per-agent completion marks:
      {"agents": {"ZAI Agent 1": {"ts": epoch, "summary": "..."},
                  "ZAI Agent 2": {...}},
       "combined_sent_at": epoch}

  --mark "ZAI Agent 1" --summary "..."
      Atomically records this agent's completion, THEN checks whether the
      OTHER agent has a fresh mark (default window 6h). If both are fresh and
      no combined notification was sent after the later timestamp, it sends
      the combined "both agents complete" Telegram message immediately.

  --check
      Poll mode (for a cron watcher): same detection without marking.

  --status
      Print current state (no Telegram send).

  Dedup: combined_sent_at guard — re-running never double-pings the owner.
  Freshness: marks older than the window are ignored (stale sessions don't
  trigger a false "both done").
  Failure policy: Telegram problems are recorded in logs/turn_notifications.jsonl
  via the local ledger — they never crash a turn.

Credentials resolution is inherited from notify_turn_complete.send_turn_notification
(ZAI_NOTIFICATIONS_TOKEN env -> credentials.md -> legacy TELEGRAM_BOT_TOKEN).
"""
from __future__ import annotations

import argparse
import datetime
import fcntl
import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

from notify_turn_complete import send_turn_notification  # noqa: E402

STATE_FILE = REPO_ROOT / "data" / "agent_completion.json"
LOCK_FILE = REPO_ROOT / "data" / "agent_completion.lock"
AGENT_NAMES = ("ZAI Agent 1", "ZAI Agent 2")
DEFAULT_WINDOW_H = 6.0


def _now_ist() -> str:
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return datetime.datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")


def _load_state() -> dict:
    try:
        raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    raw.setdefault("agents", {})
    raw.setdefault("combined_sent_at", 0)
    return raw


def _save_state(state: dict) -> None:
    """Atomic write (temp file + os.replace) so parallel agents never corrupt state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(STATE_FILE.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, STATE_FILE)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _fresh_mark(state: dict, agent: str, window_h: float, now: float) -> dict | None:
    mark = state["agents"].get(agent)
    if not isinstance(mark, dict):
        return None
    ts = mark.get("ts", 0)
    if not ts or (now - ts) > window_h * 3600:
        return None
    return mark


def _both_complete(state: dict, window_h: float, now: float) -> tuple[bool, float]:
    """True when every agent has a fresh mark; also returns the later timestamp."""
    latest = 0.0
    for name in AGENT_NAMES:
        mark = _fresh_mark(state, name, window_h, now)
        if mark is None:
            return False, latest
        latest = max(latest, mark.get("ts", 0))
    return True, latest


def _send_combined(state: dict, window_h: float, now: float) -> tuple[bool, str]:
    both, latest = _both_complete(state, window_h, now)
    if not both:
        return False, "not all agents have fresh completion marks"
    if state.get("combined_sent_at", 0) >= latest:
        return True, "combined notification already sent after the latest marks (dedup)"
    lines = ["BOTH ZAI AGENTS COMPLETE", ""]
    for name in AGENT_NAMES:
        mark = state["agents"][name]
        ts_ist = datetime.datetime.fromtimestamp(
            mark["ts"], datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        ).strftime("%H:%M:%S")
        summary = (mark.get("summary") or "").strip() or "no summary provided"
        lines.append(f"{name} — done at {ts_ist} IST\n{summary}\n")
    lines.append(f"Coordinated check: [{_now_ist()}]")
    message = "\n".join(lines)
    sent, detail = send_turn_notification(message)
    if sent:
        state["combined_sent_at"] = now
    return sent, detail


def mark_complete(agent: str, summary: str, window_h: float) -> tuple[bool, str]:
    """Record this agent's completion; fire combined notification if we're last."""
    if agent not in AGENT_NAMES:
        return False, f"unknown agent '{agent}' (expected one of {AGENT_NAMES})"
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        state = _load_state()
        now = time.time()
        state["agents"][agent] = {"ts": now, "summary": summary}
        _save_state(state)
        sent, detail = _send_combined(state, window_h, now)
        _save_state(state)  # persist combined_sent_at if it changed
    return sent, detail


def check(window_h: float) -> tuple[bool, str]:
    """Poll mode: no marking, just detect-and-notify if both are fresh."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w", encoding="utf-8") as lock_fh:
        fcntl.flock(lock_fh, fcntl.LOCK_EX)
        state = _load_state()
        now = time.time()
        sent, detail = _send_combined(state, window_h, now)
        _save_state(state)
    return sent, detail


def print_status() -> None:
    state = _load_state()
    now = time.time()
    print(f"state file : {STATE_FILE}")
    print(f"agents     :")
    for name in AGENT_NAMES:
        mark = state["agents"].get(name)
        if not mark:
            print(f"  {name}: NO MARK")
            continue
        age_h = (now - mark.get("ts", 0)) / 3600
        print(f"  {name}: {age_h:.2f}h ago — {mark.get('summary', '')[:70]}")
    both, latest = _both_complete(state, DEFAULT_WINDOW_H, now)
    print(f"both fresh : {both}")
    print(f"combined_sent_at: {state.get('combined_sent_at', 0)} (latest mark: {latest:.0f})")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--mark", metavar="AGENT", help=f"mark agent complete — one of: {', '.join(AGENT_NAMES)}")
    p.add_argument("--summary", default="", help="what this agent accomplished")
    p.add_argument("--check", action="store_true", help="poll mode: notify if both agents fresh")
    p.add_argument("--status", action="store_true", help="print state, send nothing")
    p.add_argument("--window", type=float, default=DEFAULT_WINDOW_H, help="freshness window in hours (default 6)")
    args = p.parse_args(argv)

    if args.status:
        print_status()
        return 0
    if args.mark:
        sent, detail = mark_complete(args.mark, args.summary, args.window)
        print(f"[agents_completion_notifier] marked '{args.mark}': {detail}")
        if sent:
            print("[agents_completion_notifier] COMBINED NOTIFICATION SENT (both agents complete)")
        return 0
    if args.check:
        sent, detail = check(args.window)
        print(f"[agents_completion_notifier] check: {detail}")
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
