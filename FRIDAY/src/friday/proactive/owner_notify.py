"""TASK-FRD-025: FRIDAY's severity-gated Telegram reach to the owner.

Owner decision 2026-11-18 (decision 1A): when something matters, FRIDAY
messages the owner on Telegram the moment it happens — not in the next
morning briefing. This module is that path, and just as importantly the
gate that keeps it from becoming a chatty channel:

- Only ``Severity.ALERT`` sends. ``Severity.ROUTINE`` is briefing
  material: ``notify_owner`` returns ``BELOW_BAR`` and nothing is sent.
- Anti-spam, all persisted so a restart cannot reset the limits:
  a per-event-key cooldown (the same event cannot re-alert for 6h),
  identical-text dedupe (the same words cannot re-alert for 1h, under
  any key), a global floor between any two sends (120s), and a daily
  cap (20, counted on the owner's IST day). A fleet outage that flaps
  a hundred times still reaches the owner once.
- ``FRIDAY_OWNER_NOTIFY=off`` is the kill switch, re-checked on every
  call. An unconfigured Telegram gateway is reported honestly as
  ``NOT_CONFIGURED`` — never as a send.

The send itself reuses the fleet's existing Bot API path —
``friday.proactive.telegram_gateway.send_owner_message`` (the
@fridayuniverse_bot credentials from the server env, the same
``sendMessage`` shape Cortex's escalations use). This module adds no
new credentials and no second sender; it decides WHETHER a message
may go, the gateway decides HOW.

Callers: anything that learns something the owner would want to know
now — a fleet agent going down, the autonomous daemon's task source
reporting a real finding, a governed trade event. Callers pass a
stable ``event_key`` per distinct event (e.g. ``fleet_down:stratex``)
so the cooldown can recognise repeats. A failed send never latches
state: the caller may retry and the gate will let a genuine retry
through, exactly like the G7/G8 report latching rule.

Never raises into a caller: every outcome is a ``NotifyResult``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from enum import Enum, IntEnum
from typing import Any, Callable

from friday.core.owner_time import owner_today

logger = logging.getLogger(__name__)

#: Kill switch (owner/coordinator): FRIDAY_OWNER_NOTIFY=off silences the
#: path immediately, checked on every call like the daemon's flags.
KILL_SWITCH_ENV = "FRIDAY_OWNER_NOTIFY"
_KILL_VALUES = {"off", "0", "false", "no"}

#: Anti-spam defaults (env-tunable; the reasoning is in the docstring —
#: these are the widest values that still make spam impossible).
DEFAULT_PER_KEY_COOLDOWN_SECONDS = 6 * 3600.0
DEFAULT_TEXT_DEDUPE_SECONDS = 3600.0
DEFAULT_GLOBAL_FLOOR_SECONDS = 120.0
DEFAULT_DAILY_CAP = 20


class Severity(IntEnum):
    """How much a candidate message matters. The bar is ALERT."""

    ROUTINE = 0  # briefing material — never sent from here
    ALERT = 1  # the owner would want to know now


#: Only severities at or above this are ever sent.
MIN_SEND_SEVERITY = Severity.ALERT


class NotifyResult(str, Enum):
    SENT = "sent"
    BELOW_BAR = "below_bar"  # severity under the bar; briefing material
    DUPLICATE = "duplicate"  # identical text already sent within the dedupe window
    COOLDOWN = "cooldown"  # per-key cooldown or the global floor is active
    DAILY_CAP = "daily_cap"  # today's cap reached; the briefing carries it
    DISABLED = "disabled"  # kill switch off
    NOT_CONFIGURED = "not_configured"  # Telegram gateway has no credentials
    FAILED = "failed"  # send attempted (or text unusable) and did not land


def _kill_switch_active() -> bool:
    return (os.getenv(KILL_SWITCH_ENV) or "").strip().lower() in _KILL_VALUES


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except (TypeError, ValueError):
        return default


def _gateway_sender(text: str) -> bool:
    """The one real send path — FRIDAY's existing Telegram gateway."""
    from friday.proactive.telegram_gateway import send_owner_message

    return bool(send_owner_message(text))


def _gateway_configured() -> bool:
    from friday.proactive.telegram_gateway import TelegramGateway

    return TelegramGateway.is_configured()


def _default_state_path() -> str:
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        return os.path.abspath(os.path.join(cwd, ".data", "owner_notify", "state.json"))
    here = os.path.dirname(__file__)  # .../friday/proactive
    return os.path.abspath(
        os.path.join(here, "..", "..", ".data", "owner_notify", "state.json")
    )


class OwnerNotifier:
    """The gate. One instance is shared process-wide (see notify_owner)."""

    def __init__(
        self,
        *,
        sender: Callable[[str], bool] | None = None,
        configured: Callable[[], bool] | None = None,
        state_path: str | None = None,
        clock: Callable[[], float] | None = None,
        per_key_cooldown_seconds: float | None = None,
        text_dedupe_seconds: float | None = None,
        global_floor_seconds: float | None = None,
        daily_cap: int | None = None,
    ) -> None:
        # An injected sender (tests) brings its own configuration story;
        # the configured check only guards the real gateway path.
        self._sender = sender if sender is not None else _gateway_sender
        self._configured = configured
        if self._configured is None and sender is None:
            self._configured = _gateway_configured
        self._state_path = state_path or _default_state_path()
        self._clock = clock or time.time
        self._per_key_cooldown = (
            per_key_cooldown_seconds
            if per_key_cooldown_seconds is not None
            else _env_float(
                "FRIDAY_OWNER_NOTIFY_KEY_COOLDOWN_S", DEFAULT_PER_KEY_COOLDOWN_SECONDS
            )
        )
        self._text_dedupe = (
            text_dedupe_seconds
            if text_dedupe_seconds is not None
            else _env_float("FRIDAY_OWNER_NOTIFY_DEDUPE_S", DEFAULT_TEXT_DEDUPE_SECONDS)
        )
        self._global_floor = (
            global_floor_seconds
            if global_floor_seconds is not None
            else _env_float("FRIDAY_OWNER_NOTIFY_FLOOR_S", DEFAULT_GLOBAL_FLOOR_SECONDS)
        )
        self._daily_cap = (
            daily_cap
            if daily_cap is not None
            else _env_int("FRIDAY_OWNER_NOTIFY_DAILY_CAP", DEFAULT_DAILY_CAP)
        )
        self._lock = threading.RLock()
        self._state: dict[str, Any] | None = None

    # -- state (agent_watch pattern: file-backed, tmp + os.replace) ------
    def _load(self) -> dict[str, Any]:
        if self._state is not None:
            return self._state
        try:
            with open(self._state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._state = data if isinstance(data, dict) else {}
        except FileNotFoundError:
            self._state = {}
        except Exception as exc:
            logger.warning("[OWNER-NOTIFY] state unreadable (%s) — starting empty", exc)
            self._state = {}
        self._state.setdefault("keys", {})
        self._state.setdefault("texts", {})
        self._state.setdefault("last_sent_at", 0.0)
        self._state.setdefault("day", "")
        self._state.setdefault("day_count", 0)
        return self._state

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._state_path), exist_ok=True)
            tmp = f"{self._state_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, sort_keys=True)
            os.replace(tmp, self._state_path)
        except Exception as exc:
            # A lost state file weakens the anti-spam memory; it must
            # never break the caller or fake a send outcome.
            logger.warning("[OWNER-NOTIFY] state save failed: %s", exc)

    # -- the gate ---------------------------------------------------------
    def notify(
        self,
        text: str,
        *,
        severity: Severity = Severity.ALERT,
        event_key: str = "",
    ) -> NotifyResult:
        """Offer one message to the gate. Returns what happened, always."""
        try:
            if _kill_switch_active():
                return NotifyResult.DISABLED
            if Severity(severity) < MIN_SEND_SEVERITY:
                return NotifyResult.BELOW_BAR
            body = (text or "").strip()
            if not body:
                logger.warning("[OWNER-NOTIFY] empty text offered — not sent")
                return NotifyResult.FAILED
            with self._lock:
                return self._notify_locked(body, event_key.strip())
        except Exception as exc:  # the gate never raises into a caller
            logger.warning("[OWNER-NOTIFY] notify failed open-safe: %s", exc)
            return NotifyResult.FAILED

    def _notify_locked(self, body: str, event_key: str) -> NotifyResult:
        state = self._load()
        now = float(self._clock())

        today = owner_today()
        if state.get("day") != today:
            state["day"] = today
            state["day_count"] = 0
        if int(state.get("day_count") or 0) >= self._daily_cap:
            logger.info("[OWNER-NOTIFY] daily cap reached — held for the briefing")
            return NotifyResult.DAILY_CAP

        keys: dict[str, Any] = state["keys"]
        if event_key:
            last_for_key = float(keys.get(event_key) or 0.0)
            if now - last_for_key < self._per_key_cooldown:
                return NotifyResult.COOLDOWN

        texts: dict[str, Any] = state["texts"]
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        if now - float(texts.get(digest) or 0.0) < self._text_dedupe:
            return NotifyResult.DUPLICATE

        if now - float(state.get("last_sent_at") or 0.0) < self._global_floor:
            return NotifyResult.COOLDOWN

        if self._configured is not None and not self._configured():
            logger.info("[OWNER-NOTIFY] Telegram not configured — not sent")
            return NotifyResult.NOT_CONFIGURED

        try:
            sent = bool(self._sender(body))
        except Exception as exc:
            logger.warning("[OWNER-NOTIFY] sender raised: %s", exc)
            return NotifyResult.FAILED
        if not sent:
            # No state latches on failure — a genuine retry stays possible.
            logger.info("[OWNER-NOTIFY] gateway reported a failed send")
            return NotifyResult.FAILED

        if event_key:
            keys[event_key] = now
        texts[digest] = now
        state["last_sent_at"] = now
        state["day_count"] = int(state.get("day_count") or 0) + 1
        # Prune so the state file stays bounded: entries older than
        # their window can no longer suppress anything.
        state["keys"] = {
            k: v for k, v in keys.items() if now - float(v or 0.0) < self._per_key_cooldown
        }
        state["texts"] = {
            k: v for k, v in texts.items() if now - float(v or 0.0) < self._text_dedupe
        }
        self._save()
        logger.info(
            "[OWNER-NOTIFY] sent to owner (key=%s, today=%d/%d)",
            event_key or "-",
            state["day_count"],
            self._daily_cap,
        )
        return NotifyResult.SENT


_default_notifier: OwnerNotifier | None = None
_default_lock = threading.Lock()


def _get_default_notifier() -> OwnerNotifier:
    global _default_notifier
    if _default_notifier is None:
        with _default_lock:
            if _default_notifier is None:
                _default_notifier = OwnerNotifier()
    return _default_notifier


def notify_owner(
    text: str,
    *,
    severity: Severity = Severity.ALERT,
    event_key: str = "",
) -> NotifyResult:
    """Send ``text`` to the owner's Telegram — if it clears the bar.

    The one entry point callers use. ``event_key`` is a stable id for
    the distinct event (``fleet_down:stratex``, ``trade_close:470``);
    repeats of the same key inside the cooldown are suppressed, so a
    flapping source cannot spam the owner. Routine matters pass
    ``severity=Severity.ROUTINE`` and are answered ``BELOW_BAR`` —
    they belong to the morning briefing, not to this path.
    """
    return _get_default_notifier().notify(text, severity=severity, event_key=event_key)
