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

Risk tiering (TASK-SEN-019, owner decision 2026-11-18): every submission is
classified by ``sentinel.gatekeeper.approval_policy`` before dispatch.
Low-risk items (caller risk LOW + read-only / internal / caller-attested
reversible, and no hard-bound pattern) are auto-approved by Sentinel
itself — no human is paged — and every auto-approval is written to the
tamper-evident audit ledger; if the ledger entry cannot be written, the
item falls back to the owner prompt (no ledger entry, no auto-approval).
Hard bounds — live-money actions, deletions, credential changes, and
changes to Sentinel's own approval policy — always prompt the owner, as
do GUARDED/MEDIUM/HIGH/CRITICAL or unrecognised risk levels.

Pending-queue persistence (TASK-SEN-019): the pending map used to live
only in RAM, so a restart lost every pending approval (the exposure named
in TASK-SEN-018). When ``SENTINEL_PENDING_APPROVALS_PATH`` is set, the
queue is written to that JSON file on every mutation (atomic tmp+replace,
mirroring the deploy watchdog's JsonDeployStateStore) and restored on
first use after a restart, so approve/deny links keep working across
restarts. Unset, behaviour is the historical RAM-only queue.
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

from sentinel.gatekeeper.approval_policy import ApprovalTier, classify_approval

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
    # TASK-SEN-019 tiering outcome (additive; pre-tiering records restore
    # with the OWNER_PROMPT default, which is how they were handled).
    policy_tier: str = "OWNER_PROMPT"
    policy_category: str | None = None

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
            "policy_tier": self.policy_tier,
            "policy_category": self.policy_category,
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
            cls._instance._queue_restored = False
            cls._instance._audit_logger = None
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
        """Create a new approval request and route it by risk tier.

        TASK-SEN-019: low-risk items are auto-approved (and written to the
        audit ledger) without paging the owner; everything else follows
        the historical path — dispatch to the owner's channels and wait.
        """
        self._ensure_restored()
        classification = classify_approval(
            agent_name=agent_name,
            action=action,
            risk_level=risk_level,
            details=details or {},
        )
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
            policy_tier=classification.tier.value,
            policy_category=classification.category,
        )

        self._pending[token] = pending
        self._events[token] = asyncio.Event()

        if classification.auto_approve:
            if self._record_auto_approval(pending, classification):
                pending.status = ApprovalStatus.APPROVED
                pending.decided_at = time.time()
                pending.decision_reason = (
                    "Auto-approved by Sentinel approval policy (TASK-SEN-019): "
                    f"{classification.category} — {classification.reason}"
                )
                self._events[token].set()
                logger.info(
                    "Approval %s (%s by %s) AUTO-APPROVED [%s]",
                    pending.request_id, pending.action, pending.agent_name,
                    classification.category,
                )
                self._persist_pending()
                return pending
            # Fail-closed: no ledger entry, no auto-approval. The item
            # falls through to the owner prompt with its tier corrected.
            logger.warning(
                "Auto-approval audit write failed for %s (%s); "
                "falling back to owner prompt",
                pending.request_id, pending.action,
            )
            pending.policy_tier = ApprovalTier.OWNER_PROMPT.value

        # Dispatch async notification
        self._dispatch_notifications(pending)
        self._persist_pending()
        return pending

    async def wait_for_decision(self, token: str, timeout_sec: float | None = None) -> bool:
        """Asynchronously wait until the approval is decided by Surendra or expires."""
        self._ensure_restored()
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
            self._persist_pending()
            return False

    def decide(self, token: str, approve: bool, reason: str = "") -> PendingApproval | None:
        """Record decision (approve or deny) and awaken waiting agent."""
        self._ensure_restored()
        pending = self._pending.get(token)
        if not pending:
            return None

        if pending.is_expired():
            pending.status = ApprovalStatus.EXPIRED
            self._persist_pending()
            return pending

        pending.status = ApprovalStatus.APPROVED if approve else ApprovalStatus.DENIED
        pending.decision_reason = reason or ("Approved by Sovereign Architect Surendra" if approve else "Denied by Surendra")
        pending.decided_at = time.time()

        event = self._events.get(token)
        if event:
            event.set()

        logger.info("Approval %s (%s) -> %s", pending.request_id, pending.action, pending.status.value)
        self._persist_pending()
        return pending

    def get_pending_list(self) -> list[dict[str, Any]]:
        """Return all non-expired pending approvals."""
        self._ensure_restored()
        now = time.time()
        active = []
        for p in self._pending.values():
            if p.status == ApprovalStatus.PENDING and p.expires_at > now:
                active.append(p.to_dict())
        return active

    # ------------------------------------------------------------------
    # TASK-SEN-019: auto-approval audit + pending-queue persistence
    # ------------------------------------------------------------------

    def _get_audit_logger(self):
        """Lazily build (and cache) the audit logger for auto-approvals.

        Constructed exactly as the PolicyEngine constructs its own —
        ``AuditLogger(settings.audit.log_file_path, settings.audit.signing_key)``.
        ``log_event`` re-reads the ledger tail before every append, so this
        instance continues the physical chain rather than forking it. The
        import is lazy so this module keeps its stdlib-only import surface
        for the many tools/tests that load it without the full app stack.
        Raises on failure (no signing key, unreadable ledger); callers
        treat that as "auto-approval unavailable" and fall back to the
        owner prompt.
        """
        cached = getattr(self, "_audit_logger", None)
        if cached is not None:
            return cached
        from sentinel.audit.audit_logger import AuditLogger
        from sentinel.config.settings import get_settings

        settings = get_settings()
        audit = AuditLogger(
            log_path=settings.audit.log_file_path,
            signing_key=settings.audit.signing_key,
        )
        self._audit_logger = audit
        return audit

    def _record_auto_approval(self, pending: PendingApproval, classification) -> bool:
        """Write an auto-approval to the tamper-evident audit ledger.

        Returns True only when the entry was written. The approval token
        is a bearer credential for the approve/deny links and is NEVER
        written to the ledger; the request_id identifies the entry.
        """
        try:
            audit = self._get_audit_logger()
            audit.log_event(
                entry_id=f"audit-appr-auto-{pending.request_id}",
                event_type="APPROVAL_AUTO_APPROVED",
                actor="sentinel-approval-policy",
                target=pending.agent_name,
                action_type=pending.action,
                scope_policy="gatekeeper-approvals",
                decision="AUTO_APPROVED",
                details={
                    "request_id": pending.request_id,
                    "agent_name": pending.agent_name,
                    "action": pending.action,
                    "risk_level": pending.risk_level,
                    "policy_category": classification.category,
                    "policy_reason": classification.reason,
                },
            )
            return True
        except Exception as e:
            logger.warning("Auto-approval audit write error: %s", e)
            return False

    def _queue_path(self) -> Path | None:
        """Pending-queue file, when persistence is configured.

        Mirrors the fleet's state-path convention
        (``SENTINEL_DEPLOY_WATCHDOG_STATE_PATH``): persistence is active
        only when the path is set. Resolved per call so tests and the
        unit environment can change it without a restart of the import.
        """
        raw = os.getenv("SENTINEL_PENDING_APPROVALS_PATH")
        return Path(raw) if raw else None

    def _ensure_restored(self) -> None:
        if getattr(self, "_queue_restored", False):
            return
        self._queue_restored = True
        path = self._queue_path()
        if path is None or not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            records = raw.get("pending", []) if isinstance(raw, dict) else []
        except (OSError, ValueError) as e:
            logger.warning("Pending-approval queue restore failed (%s): %s", path, e)
            return
        expired_any = False
        for record in records:
            pending = self._record_to_pending(record)
            if pending is None or pending.token in self._pending:
                continue
            if pending.status == ApprovalStatus.PENDING and pending.is_expired():
                pending.status = ApprovalStatus.EXPIRED
                pending.decision_reason = "Expired while Sentinel was offline (restored from the persisted queue)"
                expired_any = True
            self._pending[pending.token] = pending
            if pending.status == ApprovalStatus.PENDING:
                self._events[pending.token] = asyncio.Event()
        if expired_any:
            self._persist_pending()

    @staticmethod
    def _record_to_pending(record: Any) -> PendingApproval | None:
        """Rebuild one PendingApproval from its persisted record.

        Corrupt or partial records are skipped (returns None), mirroring
        JsonDeployStateStore's per-entry tolerance.
        """
        try:
            if not isinstance(record, dict):
                return None
            return PendingApproval(
                token=str(record["token"]),
                request_id=str(record["request_id"]),
                agent_name=str(record["agent_name"]),
                action=str(record["action"]),
                risk_level=str(record.get("risk_level") or "GUARDED"),
                details=dict(record.get("details") or {}),
                created_at=float(record["created_at"]),
                expires_at=float(record["expires_at"]),
                status=ApprovalStatus(str(record.get("status") or "PENDING")),
                decision_reason=record.get("decision_reason"),
                decided_at=(float(record["decided_at"]) if record.get("decided_at") is not None else None),
                policy_tier=str(record.get("policy_tier") or "OWNER_PROMPT"),
                policy_category=record.get("policy_category"),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _persist_pending(self) -> None:
        """Persist the approval queue when a queue path is configured.

        Atomic tmp+replace write of every known record (pending and
        decided alike, so a decided item's status still resolves after a
        restart instead of 404ing). Failures are logged, never raised:
        a persistence failure degrades this entry to the historical
        RAM-only behaviour, it must not break the approval itself.
        """
        path = self._queue_path()
        if path is None:
            return
        try:
            records = [
                {
                    "token": p.token,
                    "request_id": p.request_id,
                    "agent_name": p.agent_name,
                    "action": p.action,
                    "risk_level": p.risk_level,
                    "details": p.details,
                    "created_at": p.created_at,
                    "expires_at": p.expires_at,
                    "status": p.status.value,
                    "decision_reason": p.decision_reason,
                    "decided_at": p.decided_at,
                    "policy_tier": p.policy_tier,
                    "policy_category": p.policy_category,
                }
                for p in self._pending.values()
            ]
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"version": 1, "pending": records}, indent=2),
                encoding="utf-8",
            )
            tmp.replace(path)
        except (OSError, TypeError, ValueError) as e:
            logger.warning("Pending-approval queue persist failed (%s): %s", path, e)

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
