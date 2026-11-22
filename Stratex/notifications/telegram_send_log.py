"""notifications/telegram_send_log.py — persistent Telegram-send log.

TASK-STR-DAEMON-004 (follow-up 3 of TASK-STR-DAEMON-001).

DAEMON-001 (2026-11-21) root-caused the per-restart triple-send, but its
evidence was limited honestly: the systemd journal retains only ~2h of the
daemon's output, so a future recurrence could not be investigated with its
full history intact. This module persists every daemon Telegram send in
Stratex/state/telegram_sends.jsonl (STRATEX_STATE_DIR override), one JSON
object per line:

    {"ts": "2026-11-22T04:30:00.123456+00:00", "send_type": "startup_online",
     "dedupe_key": "<sha1 of the message text>", "message_id": 12345,
     "chars": 392, "first_line": "Stratex Online - Multi-Venue"}

The log survives restarts (a plain file in state/, which is gitignored)
and retains at least 7 days of sends: every append prunes entries older
than RETENTION_DAYS. Logging is best-effort and never raises — a logging
failure must never break a send, and only Telegram-confirmed deliveries
are recorded (dedupe-suppressed and failed sends are never logged; the
caller logs after delivery is confirmed, not before).
"""

from __future__ import annotations

import datetime
import json
import os
import re
import threading
from typing import Any

# The log keeps at least a week of sends (acceptance: >= 7 days).
RETENTION_DAYS = 7

_SEND_LOG_FILENAME = "telegram_sends.jsonl"

# First line kept in the log, truncated: enough to identify the send in a
# later investigation, without storing the whole message body.
_MAX_FIRST_LINE_CHARS = 120

_TAG_RE = re.compile(r"<[^>]*>")

# Known daemon messages, matched on the tag-stripped, upper-cased first
# line, most specific first. Anything unrecognised is "other".
_CLASSIFICATION_RULES: tuple[tuple[str, str], ...] = (
    ("STRATEX ONLINE", "startup_online"),
    ("STRATEX STARTED", "startup_started"),
    ("DAILY SUMMARY", "daily_summary"),
    ("TRADE EXECUTED", "trade_executed"),
    ("TRADE OPENED", "trade_opened"),
    ("TRADE CLOSED", "trade_closed"),
    ("POSITION CLOSED", "position_closed"),
    ("STRATEX TRADE", "trade_intent"),
    ("RISK GATE BLOCKED", "risk_rejection"),
    ("EMERGENCY PANIC HALT", "emergency_halt"),
    ("STRATEX BOT CONFLICT", "poll_conflict"),
    ("EQUITY CURVE", "equity_curve"),
)

# Sends from several daemon threads (engine + polling) can land here at
# once; serialise append+prune so two writers cannot interleave a rewrite.
_LOCK = threading.Lock()


def send_log_path() -> str:
    """Path of the persistent send log.

    Same state-dir convention as the daemon heartbeat, the daily summary
    and the startup pair: STRATEX_STATE_DIR overrides, otherwise
    Stratex/state/telegram_sends.jsonl. state/ is gitignored; the file is
    runtime state only, regenerated on first send.
    """
    override = os.getenv("STRATEX_STATE_DIR")
    base = override if override else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state"
    )
    return os.path.join(base, _SEND_LOG_FILENAME)


def _strip_tags(text: str) -> str:
    """Remove Telegram HTML tags so classification sees the plain words."""
    return _TAG_RE.sub("", text)


def _first_line(text: str) -> str:
    """First line of the message, tag-stripped, truncated for the log."""
    stripped = _strip_tags(text).strip()
    line = stripped.splitlines()[0].strip() if stripped else ""
    return line[:_MAX_FIRST_LINE_CHARS]


def classify_send_type(text: str) -> str:
    """Stable send type for a message, from its first line.

    Known daemon messages map to their type; anything else is "other"
    (still logged, with its first line, so a new message kind is visible
    in the log rather than silently dropped).
    """
    first = _first_line(text).upper()
    for needle, send_type in _CLASSIFICATION_RULES:
        if needle in first:
            return send_type
    return "other"


def _utcnow_iso() -> str:
    """Current UTC time as an ISO-8601 string (the log's timestamp)."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _parse_ts(value: Any) -> datetime.datetime | None:
    """Parse a log timestamp; None when missing or unparseable."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed


def _retained(line: str, cutoff: datetime.datetime) -> bool:
    """True when a raw log line should survive pruning.

    A well-formed entry survives only while its timestamp is within
    retention. A line that cannot be parsed is kept verbatim — pruning
    must never delete data it cannot judge.
    """
    try:
        raw = json.loads(line)
    except (ValueError, TypeError):
        return True
    if not isinstance(raw, dict):
        return True
    ts = _parse_ts(raw.get("ts"))
    if ts is None:
        return True
    return ts >= cutoff


def read_send_log() -> list[dict]:
    """All parseable log entries, oldest first. Never raises.

    Corrupt lines are skipped (they are still preserved on disk by the
    pruner); a missing file reads as an empty log.
    """
    try:
        with open(send_log_path(), "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError:
        return []
    except Exception:
        return []
    entries: list[dict] = []
    for line in lines:
        try:
            raw = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(raw, dict):
            entries.append(raw)
    return entries


def prune_send_log(now: datetime.datetime | None = None) -> int:
    """Drop entries older than RETENTION_DAYS. Returns the count removed.

    Never raises. Unparseable lines are kept (see _retained).
    """
    try:
        with _LOCK:
            path = send_log_path()
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    lines = fh.read().splitlines()
            except FileNotFoundError:
                return 0
            moment = now or datetime.datetime.now(datetime.timezone.utc)
            cutoff = moment - datetime.timedelta(days=RETENTION_DAYS)
            kept = [line for line in lines if _retained(line, cutoff)]
            removed = len(lines) - len(kept)
            if removed:
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    fh.write("\n".join(kept))
                    if kept:
                        fh.write("\n")
                os.replace(tmp, path)
            return removed
    except Exception:
        return 0


def append_send_log(
    *,
    text: str,
    send_type: str | None = None,
    dedupe_key: str | None = None,
    message_id: int | None = None,
    ts: str | None = None,
) -> dict | None:
    """Append one confirmed Telegram send to the persistent log.

    Returns the entry written, or None when logging failed (never raises).
    Prunes entries older than RETENTION_DAYS on every append, so the file
    holds at least 7 days of sends without growing without bound.
    """
    entry = {
        "ts": ts or _utcnow_iso(),
        "send_type": send_type or classify_send_type(text),
        "dedupe_key": dedupe_key,
        "message_id": message_id,
        "chars": len(text),
        "first_line": _first_line(text),
    }
    try:
        with _LOCK:
            path = send_log_path()
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    lines = fh.read().splitlines()
            except FileNotFoundError:
                lines = []
            cutoff = datetime.datetime.now(
                datetime.timezone.utc
            ) - datetime.timedelta(days=RETENTION_DAYS)
            kept = [line for line in lines if _retained(line, cutoff)]
            kept.append(json.dumps(entry, ensure_ascii=False))
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write("\n".join(kept) + "\n")
            os.replace(tmp, path)
        return entry
    except Exception:
        return None
