#!/usr/bin/env python3
"""
notify_turn_complete.py — Send a Telegram notification when a work batch/turn finishes.

Owner directive (2026-11-11): every 10-task batch ends with a Telegram ping so the
owner knows the turn completed without getting cut off mid-stream.

Usage:
    python scripts/notify_turn_complete.py "Batch 1 complete: 10/10 tasks done"

Credentials (never hardcoded):
    TELEGRAM_BOT_TOKEN  — bot token (same token Stratex/FRIDAY bots use)
    TELEGRAM_CHAT_ID    — owner chat id

Both are read from the environment or a .env file (repo root or Stratex/.env).
If credentials are absent (e.g. a dev sandbox), the message is logged to
logs/turn_notifications.jsonl instead of sent — never fail the turn on a
notification problem.

Exit codes: 0 sent OR recorded locally · 1 hard failure (still non-fatal by design
when called via main()).
"""
from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

API_BASE = "https://api.telegram.org/bot"
DEFAULT_LOCAL_LEDGER = REPO_ROOT / "logs" / "turn_notifications.jsonl"


def _load_env_file() -> None:
    """Best-effort .env load (python-dotenv if present, else manual). — never fatal."""
    candidates = [REPO_ROOT / ".env", REPO_ROOT / "Stratex" / ".env"]
    try:
        from dotenv import load_dotenv  # type: ignore

        for cand in candidates:
            if cand.exists():
                load_dotenv(cand)
        return
    except ImportError:
        pass
    for cand in candidates:
        if not cand.exists():
            continue
        try:
            for line in cand.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        except OSError:
            continue


def _now_ist() -> str:
    """IST timestamp (project standard: IST everywhere — H1/D-026)."""
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return datetime.datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")


def _record_locally(message: str, reason: str) -> None:
    DEFAULT_LOCAL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp_ist": _now_ist(),
        "message": message,
        "delivery": "LOCAL_ONLY",
        "reason": reason,
    }
    try:
        with DEFAULT_LOCAL_LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def send_turn_notification(message: str) -> tuple[bool, str]:
    """Send (or record) the turn-complete notification. Returns (sent, detail)."""
    _load_env_file()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

    text = f"FRIDAY Universe — turn complete\n[{_now_ist()}]\n\n{message}"

    if not token or not chat_id:
        reason = "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set in this environment"
        _record_locally(message, reason)
        return False, f"recorded locally ({reason})"

    try:
        import requests

        resp = requests.post(
            f"{API_BASE}{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        data = resp.json() if resp.content else {}
        if 200 <= resp.status_code < 300 and data.get("ok"):
            return True, "sent"
        reason = f"Telegram API error: HTTP {resp.status_code} {data.get('description', '')}"
        _record_locally(message, reason)
        return False, f"recorded locally ({reason})"
    except Exception as exc:  # network down, DNS, timeout — never fatal
        reason = f"send failed: {exc}"
        _record_locally(message, reason)
        return False, f"recorded locally ({reason})"


def main(argv: list[str]) -> int:
    message = " ".join(argv).strip() or "Turn complete."
    sent, detail = send_turn_notification(message)
    prefix = "SENT" if sent else "LOCAL"
    print(f"[notify_turn_complete] {prefix}: {detail}")
    print(f"[notify_turn_complete] message: {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
