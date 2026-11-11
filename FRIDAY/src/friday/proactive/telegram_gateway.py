"""Checklist G5 (MASTER_COMPLETION_CHECKLIST): two-way Telegram gateway.

The owner texts the FRIDAY Universe bot (@fridayuniverse_bot) from his phone;
FRIDAY answers from the SAME brain the dashboard uses (``execute_command``)
and replies on Telegram. This is the phone-side companion surface.

Design (owner decisions that shape it):
- Owner decision 2026-11-10 IST: the FRIDAY Universe bot is the ten-agent
  fleet's reporting channel and the owner is its only user, so the gateway
  is OWNER-ONLY by sender id (``TELEGRAM_CHAT_ID``): any other Telegram
  user is refused in one line and never reaches the brain.
- The chat surface itself is keyless/origin-gated by owner decision — the
  same posture applies here: the gate is the sender id, not a password.
- ``/status`` answers from the same supervision truth as the dashboard;
  ``/missions`` lists the overnight mission queue (G6/G12); any other text
  goes through ``execute_command`` verbatim — no separate mini-brain.

Honesty rules (unchanged from every FRIDAY surface):
- no LLM answer is fabricated here: a brain failure is reported as a
  failure; an unconfigured gateway stays silent (it never polls);
- one poller per bot token: the gateway refuses to start when another
  process is already polling (Telegram 409) — it backs off and retries
  rather than fighting, and logs the conflict honestly;
- never raises into the caller: the loop's failures are logged, the loop
  continues.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable

import requests

from friday.core.owner_time import OWNER_TZ_LABEL, owner_now_str

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "https://api.telegram.org/bot"
DEFAULT_POLL_INTERVAL_SECONDS = 3.0
DEFAULT_LONG_POLL_TIMEOUT = 25  # seconds; matches Telegram long-polling idiom
HTTP_TIMEOUT = DEFAULT_LONG_POLL_TIMEOUT + 10
#: Telegram hard limit for sendMessage text; keep a margin for the header.
MAX_MESSAGE_CHARS = 4000
#: After this many consecutive 409s, log at error level once (still not fatal).
CONFLICT_LOG_EVERY = 20


def _env_credentials() -> tuple[str, str]:
    """Bot token + owner chat id from the environment (never hardcoded)."""
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        # The server loads FRIDAY/.env through its EnvironmentFile; a manual
        # run may not have it. Try the repo-root .env the way Stratex's bot
        # does, but never print the values.
        try:
            from dotenv import dotenv_values

            values = dotenv_values(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env")
            )
            token = token or (values.get("TELEGRAM_BOT_TOKEN") or "").strip()
            chat_id = chat_id or (values.get("TELEGRAM_CHAT_ID") or "").strip()
        except Exception:
            pass
    return token, chat_id


class TelegramGateway:
    """Owner-gated two-way bridge between Telegram and FRIDAY's brain."""

    def __init__(
        self,
        brain: Callable[[str], Any] | None = None,
        *,
        poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
        send_interval: float = 1.1,
        api_base: str = DEFAULT_API_BASE,
    ) -> None:
        self._brain = brain
        self._poll_interval = poll_interval
        # Telegram rate limit: ~1 msg/s per chat, 30/s overall — send at a
        # polite 0.9/s so bursts of queued replies never hit 429.
        self._send_interval = send_interval
        self._api_base = api_base
        self._thread: threading.Thread | None = None
        self._running = False
        self._last_update_id = 0
        self._conflict_count = 0
        self._last_sent_at = 0.0
        self._state_lock = threading.Lock()

    # ------------------------------------------------------------------
    # configuration / state
    # ------------------------------------------------------------------
    @staticmethod
    def is_configured() -> bool:
        token, chat_id = _env_credentials()
        return bool(token and chat_id)

    @property
    def running(self) -> bool:
        return self._running

    def set_brain(self, brain: Callable[[str], Any]) -> None:
        """Wire the command executor (the same one /api/chat uses)."""
        self._brain = brain

    # ------------------------------------------------------------------
    # Telegram primitives (thin, honest wrappers)
    # ------------------------------------------------------------------
    def _api(self, method: str, params: dict[str, Any]) -> dict[str, Any] | None:
        token, _ = _env_credentials()
        if not token:
            return None
        try:
            resp = requests.post(
                f"{self._api_base}{token}/{method}",
                json=params,
                timeout=HTTP_TIMEOUT,
            )
            if resp.status_code == 409:
                self._conflict_count += 1
                if self._conflict_count % CONFLICT_LOG_EVERY == 1:
                    logger.error(
                        "[TG-GATEWAY] 409 Conflict: another process is polling this bot "
                        "token (seen %sx). Retrying with backoff — exactly one poller per "
                        "bot is allowed.",
                        self._conflict_count,
                    )
                return None
            self._conflict_count = 0
            data = resp.json()
            if not data.get("ok"):
                logger.debug("[TG-GATEWAY] %s not ok: %s", method, data.get("description"))
                return None
            return data
        except requests.exceptions.RequestException as exc:
            logger.debug("[TG-GATEWAY] %s request failed: %s", method, exc)
            return None

    def send_message(self, text: str, chat_id: str | None = None) -> bool:
        """Send one message (rate-limited, split to Telegram's size limit)."""
        _, owner_chat = _env_credentials()
        target = chat_id or owner_chat
        if not target:
            return False
        chunks = [text[i : i + MAX_MESSAGE_CHARS] for i in range(0, len(text), MAX_MESSAGE_CHARS)] or [""]
        sent_any = False
        for chunk in chunks:
            # Polite pacing between messages (1/s per chat is Telegram's cap).
            wait = self._send_interval - (time.monotonic() - self._last_sent_at)
            if wait > 0:
                time.sleep(wait)
            data = self._api(
                "sendMessage",
                {"chat_id": target, "text": chunk, "parse_mode": "HTML"},
            )
            self._last_sent_at = time.monotonic()
            sent_any = bool(data)
        return sent_any

    # ------------------------------------------------------------------
    # inbound processing
    # ------------------------------------------------------------------
    def _handle_update(self, update: dict[str, Any]) -> None:
        """Owner gate → command dispatch → Telegram reply. Never raises."""
        message = update.get("message") or update.get("edited_message") or {}
        text = str(message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = str(chat.get("id") or "")
        sender = message.get("from") or {}
        sender_id = str(sender.get("id") or "")
        sender_name = str(sender.get("first_name") or sender.get("username") or "unknown")
        if not text:
            return

        _, owner_chat = _env_credentials()
        # OWNER-ONLY gate: the owner is the bot's single user by design.
        if sender_id != owner_chat:
            logger.warning(
                "[TG-GATEWAY] refused non-owner sender id=%s name=%s",
                sender_id,
                sender_name,
            )
            self.send_message(
                "This FRIDAY belongs to Surendra and answers only to him. "
                "Your message was not processed.",
                chat_id=chat_id or None,
            )
            return

        # Owner-only commands, answered deterministically (no LLM needed).
        low = text.lower()
        if low in ("/start", "/help"):
            self.send_message(
                "I'm here, Boss — same brain, phone line. Text me anything you'd type "
                "in the dashboard. Commands: /status (fleet), /missions (overnight queue)."
            )
            return
        if low == "/status":
            self.send_message(self._status_line())
            return
        if low == "/missions":
            self.send_message(self._missions_line())
            return

        if self._brain is None:
            self.send_message(
                "I received your message, Boss, but my command engine isn't wired on "
                "this process — nothing was executed. This is a configuration problem, "
                "not a refusal."
            )
            return

        try:
            result = self._brain(text)
            reply = str(result.get("reply") or "").strip()
            if not reply:
                reply = "I processed that, Boss, but the reply came back empty — the engine is still learning. Nothing was faked."
            self.send_message(reply)
        except Exception as exc:
            logger.exception("[TG-GATEWAY] brain dispatch failed")
            self.send_message(
                f"I couldn't complete that, Boss — the engine raised "
                f"{type(exc).__name__}. Nothing was faked; try again in a moment."
            )

    def _status_line(self) -> str:
        """Fleet status from the supervision snapshot (same truth as the UI)."""
        try:
            from friday.api import server as _server  # late import: avoid cycle
        except Exception:
            return "I can't read the fleet state from this process, Boss — no supervision snapshot available."
        agents = list(_server.fleet_supervision_state.get("agents") or [])
        if not agents:
            return (
                "No fleet snapshot yet, Boss — the supervision loop hasn't completed "
                "its first pass. I won't guess agent states."
            )
        online = 0
        lines = []
        for a in agents:
            name = str(a.get("name") or a.get("agent") or "?")
            ok = bool(a.get("reachable") or a.get("online") or a.get("healthy"))
            online += int(ok)
            lines.append(f"{'✅' if ok else '❌'} {name}")
        head = f"Fleet: {online}/{len(agents)} reachable at {owner_now_str('%I:%M %p IST')}"
        return head + "\n" + "\n".join(lines[:12])

    def _missions_line(self) -> str:
        """Overnight mission queue (G6/G12) — honest empties."""
        try:
            from friday.proactive.mission_queue import mission_queue
        except Exception:
            return "The mission queue isn't available in this process, Boss."
        return mission_queue.render_status()

    # ------------------------------------------------------------------
    # polling loop
    # ------------------------------------------------------------------
    def _poll_once(self) -> None:
        data = self._api(
            "getUpdates",
            {
                "offset": self._last_update_id + 1,
                "timeout": DEFAULT_LONG_POLL_TIMEOUT,
                "allowed_updates": ["message", "edited_message"],
            },
        )
        if not data:
            return
        for update in data.get("result") or []:
            uid = int(update.get("update_id") or 0)
            if uid <= self._last_update_id:
                continue
            self._last_update_id = uid
            try:
                self._handle_update(update)
            except Exception:
                logger.exception("[TG-GATEWAY] update handling failed")

    def _loop(self) -> None:
        logger.info("[TG-GATEWAY] starting owner-gated Telegram gateway loop")
        backoff = self._poll_interval
        while self._running:
            try:
                self._poll_once()
                backoff = self._poll_interval
            except Exception as exc:  # never fatal
                logger.warning("[TG-GATEWAY] polling error: %s", exc)
                backoff = min(60.0, backoff * 2)
            time.sleep(max(0.2, backoff - DEFAULT_LONG_POLL_TIMEOUT if backoff > DEFAULT_LONG_POLL_TIMEOUT else 0.2))
        logger.info("[TG-GATEWAY] gateway loop stopped")

    def start(self) -> bool:
        """Start the background polling thread. False when unconfigured."""
        if not self.is_configured():
            logger.info("[TG-GATEWAY] not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID) — gateway stays off")
            return False
        with self._state_lock:
            if self._running:
                return True
            self._running = True
        # Clear any stale webhook so long polling works (Telegram rule).
        self._api("deleteWebhook", {"drop_pending_updates": False})
        self._thread = threading.Thread(target=self._loop, name="friday-telegram-gateway", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        with self._state_lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    # ------------------------------------------------------------------
    # test hooks
    # ------------------------------------------------------------------
    def process_update_for_tests(self, update: dict[str, Any]) -> None:
        """Test-only: run one update through the owner gate + brain."""
        self._handle_update(update)

    def _force_conflict_for_tests(self) -> None:
        self._conflict_count = CONFLICT_LOG_EVERY


#: Process-wide gateway singleton (the server wires its brain into this).
telegram_gateway = TelegramGateway()


def send_owner_message(text: str) -> bool:
    """Send a message to the owner's Telegram chat (outbound only).

    Used by the daily self-report (G7) and the weekly summary (G8); the
    morning brief stays on the existing notifications surface.
    """
    return telegram_gateway.send_message(text)
