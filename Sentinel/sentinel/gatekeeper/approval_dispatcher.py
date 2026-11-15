"""Sentinel Human-in-the-Loop Approval Dispatcher.

Dispatches actionable approval requests when agents trigger Guarded actions:
- Live trade execution (Stratex)
- System modifications / code deployments (Forge)
- Security overrides / killswitch triggers (Sentinel)
- Sensitive external operations (FRIDAY / Cortex)

Channels:
- Telegram Bot: Dispatches interactive approval messages with direct action links.
- Discord Webhook: Dispatches rich embed alerts.
- REST Endpoints: GET/POST one-click approval & denial routes.
- Offline Queue: Buffers pending requests if Telegram credentials are not yet linked.

Credential resolution (TASK-SEN-006): channel credentials are resolved from
the process environment first, then from .env files in the fleet layout —
``$SENTINEL_ENV_FILE`` if set, then ``./.env`` (process CWD), then
``<repo>/Sentinel/.env``, then the fleet-shared ``<repo>/.env``. This mirrors
the candidate pattern already used by ``scripts/notify_turn_complete.py``.
Before this fallback existed, the dispatcher only read ``os.environ``; the
production systemd unit does not export the fleet's Telegram pair into the
Sentinel process, so every approval silently landed in the offline queue
(a journal line) and no human was ever notified. Resolved values are never
logged.

Shared channel (TASK-SEN-008): ``dispatch_notification`` exposes the same
credential resolution and transports to non-approval callers — the operations
AlertEngine dispatcher (``sentinel.modules.operations.dispatch``) sends its
alerts through it, so every Sentinel human notification uses one channel
configuration and one credential-resolution path.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc
try:
    from enum import StrEnum
except ImportError:  # Python < 3.11: behaviour-identical fallback
    from enum import Enum as _StrEnumBase

    class StrEnum(str, _StrEnumBase):
        """Stand-in for enum.StrEnum (3.11+) on older interpreters."""

        __str__ = str.__str__
        __format__ = str.__format__

        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()
from pathlib import Path
from typing import Any

logger = logging.getLogger("approval_dispatcher")


def _env_file_candidates() -> list[Path]:
    """Candidate .env files for channel credentials, highest priority first."""
    here = Path(__file__).resolve()
    # Layout: <repo>/Sentinel/sentinel/gatekeeper/approval_dispatcher.py
    sentinel_dir = here.parents[2]
    repo_root = here.parents[3]
    candidates: list[Path] = []
    override = os.getenv("SENTINEL_ENV_FILE")
    if override:
        candidates.append(Path(override))
    candidates.append(Path.cwd() / ".env")
    candidates.append(sentinel_dir / ".env")
    candidates.append(repo_root / ".env")
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _read_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines from a .env file. Never raises, never logs values."""
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export "):]
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


_FILE_ENV_CACHE: dict[str, str] | None = None


def _file_env() -> dict[str, str]:
    """Merged .env-file values (lowest-priority candidate applied first)."""
    global _FILE_ENV_CACHE
    if _FILE_ENV_CACHE is None:
        merged: dict[str, str] = {}
        for path in reversed(_env_file_candidates()):
            merged.update(_read_env_file(path))
        _FILE_ENV_CACHE = merged
    return _FILE_ENV_CACHE


def _resolve_credential(*names: str) -> str | None:
    """Resolve a channel credential: process environment first, then .env files."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    file_env = _file_env()
    for name in names:
        value = file_env.get(name)
        if value:
            return value
    return None


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"


@dataclass
class PendingApproval:
    token: str
    request_id: str
    agent_name: str
    action: str
    risk_level: str
    details: dict[str, Any]
    created_at: float = field(default_factory=lambda: time.time())
    expires_at: float = field(default_factory=lambda: time.time() + 300.0)  # 5 min default
    status: ApprovalStatus = ApprovalStatus.PENDING
    decision_reason: str | None = None
    decided_at: float | None = None

    def is_expired(self) -> bool:
        return self.status == ApprovalStatus.PENDING and time.time() > self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "request_id": self.request_id,
            "agent_name": self.agent_name,
            "action": self.action,
            "risk_level": self.risk_level,
            "details": self.details,
            "created_at": datetime.fromtimestamp(self.created_at, UTC).isoformat(),
            "expires_at": datetime.fromtimestamp(self.expires_at, UTC).isoformat(),
            "status": self.status.value,
            "decision_reason": self.decision_reason,
            "decided_at": datetime.fromtimestamp(self.decided_at, UTC).isoformat() if self.decided_at else None,
        }


class ApprovalDispatcher:
    """Singleton dispatcher managing pending approvals and multi-channel notifications."""
    _instance: ApprovalDispatcher | None = None
    _pending: dict[str, PendingApproval]
    _events: dict[str, asyncio.Event]

    def __new__(cls) -> ApprovalDispatcher:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pending = {}
            cls._instance._events = {}
        return cls._instance

    @property
    def public_base_url(self) -> str:
        return os.getenv("FRIDAY_PUBLIC_URL", "http://friday-universe.duckdns.org/sentinel").rstrip("/")

    @property
    def telegram_bot_token(self) -> str | None:
        return _resolve_credential("TELEGRAM_BOT_TOKEN", "SENTINEL_TELEGRAM_BOT_TOKEN")

    @property
    def telegram_chat_id(self) -> str | None:
        return _resolve_credential("TELEGRAM_CHAT_ID", "SENTINEL_TELEGRAM_CHAT_ID")

    @property
    def discord_webhook_url(self) -> str | None:
        return _resolve_credential("DISCORD_WEBHOOK_URL", "SENTINEL_DISCORD_WEBHOOK_URL")

    @property
    def channel_configured(self) -> bool:
        """True when at least one human-notification channel can be dispatched to."""
        return bool((self.telegram_bot_token and self.telegram_chat_id) or self.discord_webhook_url)

    def dispatch_notification(
        self,
        html_text: str,
        discord_payload: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """Send a free-form notification through the shared human channels.

        This is the single dispatch entry point for non-approval Sentinel
        notifications (TASK-SEN-008: operations alerts). It uses the same
        credential resolution and transports as approval dispatch. Returns a
        per-channel success map; an unconfigured channel reports False and no
        exception is raised for transport failures.
        """
        sent = {"telegram": False, "discord": False}
        if self.telegram_bot_token and self.telegram_chat_id:
            sent["telegram"] = self._send_telegram(html_text)
        if discord_payload and self.discord_webhook_url:
            sent["discord"] = self._send_discord_payload(discord_payload)
        return sent

    def submit_approval(
        self,
        agent_name: str,
        action: str,
        details: dict[str, Any] | None = None,
        risk_level: str = "GUARDED",
        timeout_sec: float = 300.0,
    ) -> PendingApproval:
        """Create and dispatch a new approval request."""
        token = secrets.token_hex(16)
        req_id = f"appr_{secrets.token_hex(6)}"
        pending = PendingApproval(
            token=token,
            request_id=req_id,
            agent_name=agent_name.upper(),
            action=action,
            risk_level=risk_level.upper(),
            details=details or {},
            created_at=time.time(),
            expires_at=time.time() + timeout_sec,
            status=ApprovalStatus.PENDING,
        )

        self._pending[token] = pending
        self._events[token] = asyncio.Event()

        # Dispatch async notification
        self._dispatch_notifications(pending)
        return pending

    async def wait_for_decision(self, token: str, timeout_sec: float | None = None) -> bool:
        """Asynchronously wait until the approval is decided by Surendra or expires."""
        pending = self._pending.get(token)
        if not pending:
            return False

        event = self._events.get(token)
        if not event:
            return False

        timeout = timeout_sec or max(0.1, pending.expires_at - time.time())
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return pending.status == ApprovalStatus.APPROVED
        except TimeoutError:
            pending.status = ApprovalStatus.EXPIRED
            pending.decision_reason = "Approval request timed out without response"
            return False

    def decide(self, token: str, approve: bool, reason: str = "") -> PendingApproval | None:
        """Record decision (approve or deny) and awaken waiting agent."""
        pending = self._pending.get(token)
        if not pending:
            return None

        if pending.is_expired():
            pending.status = ApprovalStatus.EXPIRED
            return pending

        pending.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.DENIED
        pending.decision_reason = reason or ("Approved by Sovereign Architect Surendra" if approve else "Denied by Surendra")
        pending.decided_at = time.time()

        event = self._events.get(token)
        if event:
            event.set()

        logger.info("Approval %s (%s) -> %s", pending.request_id, pending.action, pending.status.value)
        return pending

    def get_pending_list(self) -> list[dict[str, Any]]:
        """Return all non-expired pending approvals."""
        now = time.time()
        active = []
        for p in self._pending.values():
            if p.status == ApprovalStatus.PENDING and p.expires_at > now:
                active.append(p.to_dict())
        return active

    def _dispatch_notifications(self, pending: PendingApproval) -> None:
        """Dispatch notification to Telegram, Discord, and system log."""
        approve_url = f"{self.public_base_url}/api/v1/approvals/{pending.token}/approve"
        deny_url = f"{self.public_base_url}/api/v1/approvals/{pending.token}/deny"

        # 1. Telegram Dispatch
        if self.telegram_bot_token and self.telegram_chat_id:
            msg = (
                f"🛡️ <b>SENTINEL GUARDED ACTION APPROVAL</b>\n\n"
                f"<b>Agent:</b> <code>{pending.agent_name}</code>\n"
                f"<b>Action:</b> <code>{pending.action}</code>\n"
                f"<b>Risk Level:</b> {pending.risk_level}\n"
                f"<b>Details:</b> <pre>{json.dumps(pending.details, indent=2)}</pre>\n\n"
                f"✅ <a href=\"{approve_url}\"><b>APPROVE ACTION</b></a>\n"
                f"❌ <a href=\"{deny_url}\"><b>DENY ACTION</b></a>\n\n"
                f"<i>Expires in 5 minutes.</i>"
            )
            self._send_telegram(msg)
        else:
            logger.info(
                f"[SENTINEL APPROVAL QUEUED] Action '{pending.action}' by '{pending.agent_name}'. "
                f"Approve URL: {approve_url} | Deny URL: {deny_url} | "
                f"(Telegram alerts ready: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID "
                f"in the process environment or a fleet .env file when desired)."
            )

        # 2. Discord Dispatch
        if self.discord_webhook_url:
            self._send_discord(pending, approve_url, deny_url)

    def _send_telegram(self, html_text: str) -> bool:
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": html_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5.0)
            return True
        except Exception as e:
            logger.warning("Telegram notification dispatch error: %s", e)
            return False

    def _send_discord(self, pending: PendingApproval, approve_url: str, deny_url: str) -> bool:
        payload = {
            "content": "🛡️ **SENTINEL GUARDED ACTION APPROVAL REQUIRED**",
            "embeds": [
                {
                    "title": f"Action: {pending.action} ({pending.agent_name})",
                    "description": f"Risk Level: **{pending.risk_level}**\n\n[✅ APPROVE]({approve_url}) | [❌ DENY]({deny_url})",
                    "fields": [
                        {"name": "Details", "value": f"```{json.dumps(pending.details)[:1000]}```"}
                    ],
                    "color": 16753920,
                }
            ]
        }
        if not self.discord_webhook_url:
            return False
        return self._send_discord_payload(payload)

    def _send_discord_payload(self, payload: dict[str, Any]) -> bool:
        if not self.discord_webhook_url:
            return False
        try:
            req = urllib.request.Request(
                self.discord_webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5.0)
            return True
        except Exception as e:
            logger.warning("Discord notification dispatch error: %s", e)
            return False


# Global singleton instance
approval_dispatcher = ApprovalDispatcher()
