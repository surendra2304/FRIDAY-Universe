"""TASK-IG2-FRD-02 — WhatsApp channel gateway for FRIDAY (OpenClaw pattern).

OpenClaw's transferable lesson (card openclaw.md) is the channel-gateway
control plane: one gateway pattern, many messaging channels, the same
brain and the same permission gating behind each. FRIDAY already has
that pattern for Telegram (``proactive/telegram_gateway.py``); this
module adds WhatsApp as a second channel through the **WhatsApp Cloud
API** (Meta's official API, free tier — no paid service, no unofficial
library, no QR/session hacks):

- inbound: Meta pushes each message to FRIDAY's HTTPS webhook
  (``POST /whatsapp-webhook`` in the API server); the route verifies
  Meta's ``X-Hub-Signature-256`` HMAC and the webhook verify token,
  then hands the payload to :meth:`WhatsAppGateway.process_webhook_payload`
  — the same shape as the Telegram gateway's webhook mode;
- owner gate: identical posture to Telegram — only the owner's own
  WhatsApp number (``WHATSAPP_OWNER_NUMBER``) reaches the brain; any
  other sender is refused in one line and never processed;
- commands: ``/status`` and ``/missions`` are answered deterministically
  from the same supervision truth as Telegram/dashboard; all other text
  goes through the SAME brain callable the dashboard and Telegram use;
- outbound: ``send_message`` posts to the Cloud API graph endpoint,
  rate-paced and split to WhatsApp's 4096-char body limit, mirroring
  the Telegram gateway's send discipline.

ACTIVATION (one owner-side Meta setup step — deliberately NOT done by
this code): create a Meta developer app with the WhatsApp product,
register the owner's number as the test/own number, point the app's
webhook at ``https://friday-universe.duckdns.org/whatsapp-webhook``
with the verify token below, and put these in FRIDAY's root ``.env``:

    WHATSAPP_ACCESS_TOKEN=...        (Cloud API access token)
    WHATSAPP_PHONE_NUMBER_ID=...     (the app's sender number id)
    WHATSAPP_OWNER_NUMBER=91...      (owner's WhatsApp number, digits only)
    WHATSAPP_APP_SECRET=...          (for X-Hub-Signature-256 verification)
    WHATSAPP_VERIFY_TOKEN=...        (any owner-chosen string, echoed at setup)

Until those exist the gateway stays off and silent — exactly like the
Telegram gateway when unconfigured. The 24-hour customer-service window
is Meta's rule: FRIDAY can always REPLY inside a conversation the owner
started; proactive pushes outside 24h of the owner's last message need
an approved template, which this adapter does not fake around.

Note: ``tools/builtin/whatsapp_tools.py`` is a different surface (it
drives WhatsApp on the owner's phone/desktop via ADB/browser). This
gateway is the server-side channel, like Telegram's.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import threading
import time
from typing import Any, Callable

import requests

from friday.core.owner_time import owner_now_str

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"
HTTP_TIMEOUT = 20
#: WhatsApp text body hard limit; keep a small margin.
MAX_MESSAGE_CHARS = 4000
#: Cloud API free tier allows generous throughput, but bursts to one
#: recipient are paced like Telegram's (~1/s) to stay polite and safe.
DEFAULT_SEND_INTERVAL = 1.1


def _env_config() -> dict[str, str]:
    """WhatsApp Cloud API config from the environment (never hardcoded).

    Read from the process env first, then the repo-root .env — the same
    two places the Telegram gateway reads, so activation is just the
    lines in the root .env plus a restart.
    """
    keys = (
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_OWNER_NUMBER",
        "WHATSAPP_APP_SECRET",
        "WHATSAPP_VERIFY_TOKEN",
    )
    values = {key: (os.getenv(key) or "").strip() for key in keys}
    if not all(values[key] for key in keys[:3]):
        try:
            from dotenv import dotenv_values

            file_values = dotenv_values(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".env")
            )
            for key in keys:
                values[key] = values[key] or (file_values.get(key) or "").strip()
        except Exception:
            pass
    return values


def _digits(number: str) -> str:
    """Normalise a phone number to digits only (wa_id form)."""
    return "".join(ch for ch in (number or "") if ch.isdigit())


class WhatsAppGateway:
    """Owner-gated two-way bridge between WhatsApp and FRIDAY's brain.

    Mirrors ``TelegramGateway``'s public shape (set_brain / start /
    stop / send_message / process_webhook_*) so the server wires both
    channels identically.
    """

    def __init__(
        self,
        brain: Callable[[str], Any] | None = None,
        *,
        send_interval: float = DEFAULT_SEND_INTERVAL,
        api_base: str = GRAPH_API_BASE,
    ) -> None:
        self._brain = brain
        self._send_interval = send_interval
        self._api_base = api_base
        self._running = False
        self._last_sent_at = 0.0
        self._seen_message_ids: set[str] = set()
        self._state_lock = threading.Lock()

    # ------------------------------------------------------------------
    # configuration / state
    # ------------------------------------------------------------------
    @staticmethod
    def is_configured() -> bool:
        cfg = _env_config()
        return bool(cfg["WHATSAPP_ACCESS_TOKEN"] and cfg["WHATSAPP_PHONE_NUMBER_ID"] and cfg["WHATSAPP_OWNER_NUMBER"])

    @property
    def running(self) -> bool:
        return self._running

    def set_brain(self, brain: Callable[[str], Any]) -> None:
        """Wire the command executor (the same one /api/chat uses)."""
        self._brain = brain

    # ------------------------------------------------------------------
    # webhook verification (Meta's two handshakes)
    # ------------------------------------------------------------------
    def verify_subscription(self, mode: str, token: str, challenge: str) -> str | None:
        """Answer Meta's GET verification: echo the challenge only when
        the mode is ``subscribe`` and the token matches the configured
        verify token. Returns None (→ 403) otherwise."""
        expected = _env_config()["WHATSAPP_VERIFY_TOKEN"]
        if mode == "subscribe" and expected and hmac.compare_digest(token or "", expected):
            return challenge
        return None

    def signature_matches(self, raw_body: bytes, signature_header: str | None) -> bool:
        """Verify ``X-Hub-Signature-256`` (``sha256=<hmac>``) over the raw
        POST body with the app secret. When no app secret is configured
        there is nothing to verify against and the check FAILS CLOSED —
        unlike a shared-secret header, a missing HMAC key means any
        forged POST could reach the owner gate, so unconfigured means
        refuse. (The owner-id gate still applies to every message.)"""
        signing_key = _env_config().get("WHATSAPP_APP_SECRET", "")
        if not signing_key or not signature_header:
            return False
        expected = "sha256=" + hmac.new(signing_key.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature_header, expected)

    # ------------------------------------------------------------------
    # Cloud API primitives (thin, honest wrappers)
    # ------------------------------------------------------------------
    def _api_send(self, to_number: str, text: str) -> bool:
        cfg = _env_config()
        if not cfg["WHATSAPP_ACCESS_TOKEN"] or not cfg["WHATSAPP_PHONE_NUMBER_ID"]:
            return False
        try:
            resp = requests.post(
                f"{self._api_base}/{cfg['WHATSAPP_PHONE_NUMBER_ID']}/messages",
                headers={
                    "Authorization": f"Bearer {cfg['WHATSAPP_ACCESS_TOKEN']}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": _digits(to_number),
                    "type": "text",
                    "text": {"body": text},
                },
                timeout=HTTP_TIMEOUT,
            )
            if resp.status_code != 200:
                logger.warning(
                    "[WA-GATEWAY] send failed HTTP %s: %s",
                    resp.status_code,
                    (resp.text or "")[:200],
                )
                return False
            return True
        except requests.exceptions.RequestException as exc:
            logger.debug("[WA-GATEWAY] send request failed: %s", exc)
            return False

    def send_message(self, text: str, to_number: str | None = None) -> bool:
        """Send one message (paced, split to WhatsApp's size limit)."""
        cfg = _env_config()
        target = _digits(to_number or cfg["WHATSAPP_OWNER_NUMBER"])
        if not target:
            return False
        chunks = [text[i : i + MAX_MESSAGE_CHARS] for i in range(0, len(text), MAX_MESSAGE_CHARS)] or [""]
        sent_any = False
        for chunk in chunks:
            wait = self._send_interval - (time.monotonic() - self._last_sent_at)
            if wait > 0:
                time.sleep(wait)
            sent_any = self._api_send(target, chunk)
            self._last_sent_at = time.monotonic()
        return sent_any

    # ------------------------------------------------------------------
    # inbound processing
    # ------------------------------------------------------------------
    @staticmethod
    def extract_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Pull normalised text messages out of a Cloud API webhook payload.

        Returns dicts with ``id``, ``from`` (wa_id digits), ``text`` and
        ``name``. Non-text messages and status callbacks are skipped —
        statuses are delivery receipts, not owner input.
        """
        out: list[dict[str, Any]] = []
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                contacts = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in value.get("contacts") or []}
                for message in value.get("messages") or []:
                    if message.get("type") != "text":
                        continue
                    sender = _digits(str(message.get("from") or ""))
                    out.append(
                        {
                            "id": str(message.get("id") or ""),
                            "from": sender,
                            "text": str((message.get("text") or {}).get("body") or "").strip(),
                            "name": contacts.get(sender, "") or contacts.get(message.get("from"), "") or "unknown",
                        }
                    )
        return out

    def _handle_message(self, message: dict[str, Any]) -> None:
        """Owner gate → command dispatch → WhatsApp reply. Never raises."""
        text = str(message.get("text") or "").strip()
        sender = _digits(str(message.get("from") or ""))
        if not text or not sender:
            return
        owner = _digits(_env_config()["WHATSAPP_OWNER_NUMBER"])
        # OWNER-ONLY gate: same posture as the Telegram gateway — the
        # owner is the channel's single user by design.
        if not owner or sender != owner:
            logger.warning("[WA-GATEWAY] refused non-owner sender number=%s", sender)
            self.send_message(
                "This FRIDAY belongs to Surendra and answers only to him. "
                "Your message was not processed.",
                to_number=sender,
            )
            return

        low = text.lower()
        if low in ("/start", "/help", "hi", "hello"):
            self.send_message(
                "I'm here, Boss — same brain, WhatsApp line. Text me anything you'd "
                "type in the dashboard. Commands: /status (fleet), /missions (overnight queue)."
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
        except Exception:
            logger.exception("[WA-GATEWAY] brain dispatch failed")
            self.send_message(
                "I couldn't complete that, Boss — the engine raised an error. "
                "Nothing was faked; try again in a moment."
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

    def process_webhook_payload(self, payload: dict[str, Any]) -> int:
        """Dispatch ONE webhook payload's messages (signature already
        verified by the route). Duplicate deliveries (Meta retries) are
        dropped by message id, mirroring the Telegram gateway's
        update_id dedupe. Handling runs on a daemon thread so the HTTP
        route answers Meta immediately. Returns the count accepted.
        Never raises."""
        if not isinstance(payload, dict):
            return 0
        accepted = 0
        for message in self.extract_messages(payload):
            mid = message.get("id") or ""
            if mid and mid in self._seen_message_ids:
                continue
            if mid:
                self._seen_message_ids.add(mid)
                if len(self._seen_message_ids) > 5000:
                    self._seen_message_ids.clear()
            accepted += 1

            def _run(m: dict[str, Any] = message) -> None:
                try:
                    self._handle_message(m)
                except Exception:
                    logger.exception("[WA-GATEWAY] message handling failed")

            threading.Thread(target=_run, name="friday-whatsapp-webhook", daemon=True).start()
        return accepted

    # ------------------------------------------------------------------
    # lifecycle (webhook-only channel: no polling loop exists)
    # ------------------------------------------------------------------
    def start(self) -> bool:
        """Mark the gateway live when configured. WhatsApp Cloud API is
        push-only — there is no poller to start; inbound arrives via the
        /whatsapp-webhook route. False (and silent) when unconfigured."""
        if not self.is_configured():
            logger.info(
                "[WA-GATEWAY] not configured (WHATSAPP_ACCESS_TOKEN / "
                "WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_OWNER_NUMBER) — gateway stays off"
            )
            return False
        with self._state_lock:
            self._running = True
        logger.info("[WA-GATEWAY] WhatsApp channel live (webhook mode; owner-gated)")
        return True

    def stop(self) -> None:
        with self._state_lock:
            self._running = False

    # ------------------------------------------------------------------
    # test hooks
    # ------------------------------------------------------------------
    def process_message_for_tests(self, message: dict[str, Any]) -> None:
        """Test-only: run one normalised message through gate + brain."""
        self._handle_message(message)


#: Process-wide gateway singleton (the server wires its brain into this).
whatsapp_gateway = WhatsAppGateway()


def send_owner_message(text: str) -> bool:
    """Send a message to the owner's WhatsApp (outbound only)."""
    return whatsapp_gateway.send_message(text)
