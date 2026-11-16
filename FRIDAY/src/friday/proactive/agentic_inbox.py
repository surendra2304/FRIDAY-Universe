"""TASK-IG2-FRD-01 — agentic email inbox for FRIDAY (agentic-inbox ADAPT).

Pattern adapted from Cloudflare's agentic-inbox (Apache-2.0,
https://github.com/cloudflare/agentic-inbox): an AI email client whose
agent classifies incoming mail, summarises it, drafts replies, and —
critically — sends NOTHING without a human approving the draft first,
with storage isolated per mailbox. The deployable itself is hard-wired
to Cloudflare Workers / Durable Objects / R2, a platform FRIDAY does
not run on, so this module adopts the WORKFLOW, not the stack:

    fetch → classify → summarise → draft → [owner approval] → send

mapped onto what FRIDAY already has:

- fetch: the same Gmail IMAP credentials the existing gmail tools use
  (``FRIDAY_EMAIL_ADDRESS`` / ``FRIDAY_EMAIL_APP_PASSWORD``);
- classify/summarise: a deterministic rule classifier (no LLM needed,
  no invented content) plus an OPTIONAL injected summariser/drafter
  callable — when no LLM is wired, summaries are extractive (verbatim
  sentences from the mail itself) and no reply body is invented;
- draft: a per-mailbox JSON draft queue under ``FRIDAY/.data/inbox/``
  (per-mailbox isolation, like the source's per-mailbox Durable
  Objects) — a draft sits at ``pending`` until the owner approves it;
- send: only ``approve_draft`` sends, through the fleet's shared SMTP
  sender (``email_tools._send_smtp_email``), exactly once per draft.

Honesty rules (same as every FRIDAY surface):

- unconfigured credentials → an explicit "no mail was read" result,
  never an empty-looking success;
- classification is rules over the mail's own text — signals are
  recorded per message so the owner can see WHY a mail was bucketed;
- a failed send leaves the draft ``approved`` (not ``sent``) and says so.
"""

from __future__ import annotations

import hashlib
import imaplib
import json
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from email import message_from_bytes
from email.header import decode_header
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_IMAP_SERVER = "imap.gmail.com"
_TIMEOUT = 12.0

#: Categories, in the priority order the classifier checks them. Security
#: and money mail outrank everything: a missed OTP/bank alert costs more
#: than a missed newsletter.
CATEGORY_SECURITY = "security"
CATEGORY_FINANCE = "finance"
CATEGORY_ACTION = "action_required"
CATEGORY_MEETING = "meeting"
CATEGORY_NEWSLETTER = "newsletter"
CATEGORY_PERSONAL = "personal"
CATEGORY_OTHER = "other"

#: (category, subject/sender/body keyword signals). Matched case-insensitively
#: against subject + sender + body text. Deliberately small and auditable —
#: the owner can read exactly why a mail landed where it did.
_CATEGORY_SIGNALS: list[tuple[str, tuple[str, ...]]] = [
    (CATEGORY_SECURITY, (
        "verification code", "one-time", "otp", "password reset", "sign-in",
        "signed in", "security alert", "suspicious", "2fa", "two-factor",
        "account recovery", "new device",
    )),
    (CATEGORY_FINANCE, (
        "invoice", "payment", "receipt", "bank", "transaction", "debited",
        "credited", "statement", "billing", "refund", "salary", "upi",
        "emi", "loan", "tax return", "income tax",
    )),
    (CATEGORY_ACTION, (
        "action required", "please review", "your approval", "approve",
        "deadline", "expires", "reminder:", "overdue", "action needed",
        "respond by", "rsvp", "confirm your", "verify your",
    )),
    (CATEGORY_MEETING, (
        "meeting", "invitation:", "calendar", "scheduled", "webinar",
        "appointment", "reschedule",
    )),
    (CATEGORY_NEWSLETTER, (
        "newsletter", "unsubscribe", "digest", "weekly roundup",
        "no-reply@", "noreply@", "marketing@", "promotions",
    )),
]

_URGENCY_SIGNALS = (
    "urgent", "asap", "immediately", "today", "tonight", "final notice",
    "last chance", "expiring",
)

#: Base priority per category (0–100); urgency signals and unread state add.
_CATEGORY_BASE_PRIORITY = {
    CATEGORY_SECURITY: 90,
    CATEGORY_FINANCE: 75,
    CATEGORY_ACTION: 70,
    CATEGORY_MEETING: 55,
    CATEGORY_PERSONAL: 45,
    CATEGORY_OTHER: 30,
    CATEGORY_NEWSLETTER: 10,
}


@dataclass
class InboxMessage:
    """One fetched mail, normalised for triage."""

    uid: str
    sender: str
    subject: str
    date: str = ""
    snippet: str = ""
    body: str = ""
    unread: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TriageItem:
    """A message plus its classification, summary and suggested action."""

    message: InboxMessage
    category: str
    priority: int
    signals: list[str] = field(default_factory=list)
    summary: str = ""
    suggested_action: str = "read"  # reply | read | archive

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["message"] = self.message.to_dict()
        return data


# ----------------------------------------------------------------------
# credentials / fetch (same posture as tools/builtin/gmail_tools.py)
# ----------------------------------------------------------------------

def _mailbox_login() -> tuple[str, str]:
    """(address, app pw) from settings/env; empty when unconfigured."""
    try:
        from friday.core.config import get_settings

        settings = get_settings()
        address = getattr(settings, "email_address", None) or ""
        app_pw = getattr(settings, "email_app_password", None) or ""
    except Exception:
        address, app_pw = "", ""
    address = address or os.getenv("FRIDAY_EMAIL_ADDRESS") or ""
    app_pw = app_pw or os.getenv("FRIDAY_EMAIL_APP_PASSWORD") or ""
    return address.strip(), app_pw.strip()


def mailbox_id(address: str) -> str:
    """Stable per-mailbox storage key (isolation unit, never the address)."""
    return hashlib.sha256(address.lower().encode("utf-8")).hexdigest()[:16]


def _decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for part, enc in decode_header(value):
        if isinstance(part, bytes):
            parts.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(str(part))
    return "".join(parts)


def _body_text(msg: Any, limit: int = 4000) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="replace")[:limit]
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(errors="replace")[:limit] if payload else ""


def fetch_inbox(limit: int = 20, only_unread: bool = False) -> tuple[list[InboxMessage], str]:
    """Fetch recent mail via IMAP.

    Returns ``(messages, status)``. ``status`` is ``"ok"`` on success and
    a human-readable reason otherwise — an unconfigured or unreachable
    mailbox yields NO messages plus the reason, never a silent empty
    success (the gmail tools' honesty rule, kept here).
    """
    address, app_pw = _mailbox_login()
    if not address or not app_pw:
        return [], "not_configured: FRIDAY_EMAIL_ADDRESS / FRIDAY_EMAIL_APP_PASSWORD are unset"
    limit = min(max(1, limit), 50)
    try:
        mail = imaplib.IMAP4_SSL(_IMAP_SERVER, timeout=_TIMEOUT)
        mail.login(address, app_pw)
        mail.select("INBOX")
        criterion = "UNSEEN" if only_unread else "ALL"
        status, data = mail.search(None, criterion)
        if status != "OK" or not data or not data[0]:
            mail.logout()
            return [], "ok"
        ids = data[0].split()[-limit:]
        ids.reverse()
        messages: list[InboxMessage] = []
        for eid in ids:
            res, msg_data = mail.fetch(eid, "(RFC822 FLAGS)")
            if res != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            if not isinstance(raw, bytes):
                continue
            msg = message_from_bytes(raw)
            body = _body_text(msg)
            flags_blob = msg_data[0][0] if isinstance(msg_data[0][0], bytes) else b""
            messages.append(
                InboxMessage(
                    uid=eid.decode("ascii", errors="replace"),
                    sender=_decode_header_value(msg.get("From", "Unknown")),
                    subject=_decode_header_value(msg.get("Subject", "No Subject")),
                    date=str(msg.get("Date", "") or ""),
                    snippet=re.sub(r"\s+", " ", body).strip()[:200],
                    body=body,
                    unread=b"\\Seen" not in flags_blob,
                )
            )
        mail.logout()
        return messages, "ok"
    except Exception as exc:  # connection/auth failure — reported, not hidden
        logger.warning("[AGENTIC-INBOX] fetch failed: %s", exc)
        return [], f"fetch_failed: {type(exc).__name__}: {exc}"


# ----------------------------------------------------------------------
# classify / summarise / suggest (deterministic; optional LLM hooks)
# ----------------------------------------------------------------------

def classify_message(message: InboxMessage) -> TriageItem:
    """Rule-classify one message. Every matched signal is recorded."""
    haystack = f"{message.subject}\n{message.sender}\n{message.body[:1000]}".lower()
    category = CATEGORY_OTHER
    signals: list[str] = []
    for candidate, keywords in _CATEGORY_SIGNALS:
        matched = [kw for kw in keywords if kw in haystack]
        if matched:
            category = candidate
            signals = [f"{candidate}:{kw}" for kw in matched[:4]]
            break
    if category == CATEGORY_OTHER:
        # A human-looking sender (no bulk/list markers) reads as personal.
        sender = message.sender.lower()
        if "no-reply" not in sender and "noreply" not in sender and "list" not in haystack:
            category = CATEGORY_PERSONAL
    priority = _CATEGORY_BASE_PRIORITY[category]
    for kw in _URGENCY_SIGNALS:
        if kw in haystack:
            priority += 8
            signals.append(f"urgency:{kw}")
    if message.unread:
        priority += 5
    priority = max(0, min(100, priority))
    action = "read"
    if category == CATEGORY_ACTION:
        action = "reply"
    elif category == CATEGORY_NEWSLETTER:
        action = "archive"
    return TriageItem(
        message=message,
        category=category,
        priority=priority,
        signals=signals,
        summary=extractive_summary(message),
        suggested_action=action,
    )


def extractive_summary(message: InboxMessage, max_chars: int = 240) -> str:
    """Verbatim-first-sentences summary. Extractive on purpose: when no
    LLM summariser is wired, FRIDAY quotes the mail, it does not invent
    a paraphrase of it."""
    text = re.sub(r"\s+", " ", (message.body or message.snippet or "")).strip()
    if not text:
        return message.subject.strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for sentence in sentences:
        if len(out) + len(sentence) + 1 > max_chars and out:
            break
        out = f"{out} {sentence}".strip()
        if len(out) >= 60:
            break
    return out[:max_chars].strip() or message.subject.strip()


Summariser = Callable[[InboxMessage], Optional[str]]
Drafter = Callable[[InboxMessage, str], Optional[str]]


# ----------------------------------------------------------------------
# draft queue (per-mailbox, approval-gated)
# ----------------------------------------------------------------------

def _draft_store_path(address: str) -> str:
    override = os.getenv("FRIDAY_INBOX_DATA_DIR")
    if override:
        base = override
    else:
        here = os.path.dirname(__file__)
        base = os.path.abspath(os.path.join(here, "..", "..", ".data", "inbox"))
    return os.path.join(base, mailbox_id(address), "drafts.json")


class DraftQueue:
    """File-backed pending-reply queue for ONE mailbox.

    A draft is created ``pending`` and can only leave the queue two ways:
    ``approve`` (→ the caller sends it, then ``mark_sent``) or ``reject``.
    There is deliberately no auto-send path — that is the agentic-inbox
    pattern's core safety property.
    """

    def __init__(self, address: str, path: str | None = None) -> None:
        self._address = address
        self._path = path or _draft_store_path(address)
        self._lock = threading.Lock()

    # -- storage ------------------------------------------------------
    def _load(self) -> list[dict[str, Any]]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self, drafts: list[dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(drafts, fh, indent=1)
        os.replace(tmp, self._path)

    # -- operations ---------------------------------------------------
    def add_draft(self, item: TriageItem, body: str, subject: str | None = None) -> dict[str, Any]:
        with self._lock:
            drafts = self._load()
            draft = {
                "id": uuid.uuid4().hex[:12],
                "mailbox": mailbox_id(self._address),
                "message_uid": item.message.uid,
                "to": item.message.sender,
                "subject": subject or f"Re: {item.message.subject}",
                "in_reply_to_subject": item.message.subject,
                "category": item.category,
                "body": body,
                "status": "pending",
                "created_at": time.time(),
                "decided_at": None,
                "sent_at": None,
            }
            drafts.append(draft)
            self._save(drafts)
            return draft

    def list_drafts(self, status: str | None = None) -> list[dict[str, Any]]:
        drafts = self._load()
        if status:
            drafts = [d for d in drafts if d.get("status") == status]
        return drafts

    def _update(self, draft_id: str, **changes: Any) -> dict[str, Any] | None:
        with self._lock:
            drafts = self._load()
            for draft in drafts:
                if draft.get("id") == draft_id:
                    draft.update(changes)
                    self._save(drafts)
                    return draft
            return None

    def get(self, draft_id: str) -> dict[str, Any] | None:
        for draft in self._load():
            if draft.get("id") == draft_id:
                return draft
        return None

    def reject(self, draft_id: str) -> dict[str, Any] | None:
        draft = self.get(draft_id)
        if not draft or draft.get("status") != "pending":
            return None
        return self._update(draft_id, status="rejected", decided_at=time.time())

    def approve_and_send(self, draft_id: str, sender: Callable[..., Any] | None = None) -> dict[str, Any]:
        """Approve ONE pending draft and send it. The only send path.

        Returns a result dict with ``sent`` truthfully reflecting the
        SMTP outcome; a failed send leaves the draft ``approved`` so the
        owner can retry or reject it — it is never marked sent on hope.
        """
        draft = self.get(draft_id)
        if not draft:
            return {"sent": False, "error": "draft_not_found", "draft_id": draft_id}
        if draft.get("status") == "sent":
            return {"sent": True, "error": None, "draft_id": draft_id, "already_sent": True}
        if draft.get("status") != "pending":
            return {"sent": False, "error": f"draft_not_pending:{draft.get('status')}", "draft_id": draft_id}
        self._update(draft_id, status="approved", decided_at=time.time())
        send = sender or _smtp_send
        try:
            outcome = send(
                to_address=_bare_address(str(draft.get("to") or "")),
                subject=str(draft.get("subject") or ""),
                body=str(draft.get("body") or ""),
            )
            sent = bool(getattr(outcome, "sent", outcome))
            detail = str(getattr(outcome, "detail", "") or "")
        except Exception as exc:
            sent, detail = False, f"{type(exc).__name__}: {exc}"
        if sent:
            self._update(draft_id, status="sent", sent_at=time.time())
        return {"sent": sent, "error": None if sent else (detail or "send_failed"), "draft_id": draft_id}


def _bare_address(from_header: str) -> str:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", from_header)
    return match.group(0) if match else from_header.strip()


def _smtp_send(to_address: str, subject: str, body: str) -> Any:
    """Default sender: the fleet's shared SMTP path (gmail tools' owner).

    Positional call: (to, subject, body, from_address, app pw, host, port).
    """
    from friday.tools.builtin.email_tools import _send_smtp_email

    address, app_pw = _mailbox_login()
    return _send_smtp_email(to_address, subject, body, address, app_pw, "smtp.gmail.com", 587)


# ----------------------------------------------------------------------
# triage run (the pattern's main loop)
# ----------------------------------------------------------------------

@dataclass
class TriageReport:
    status: str
    mailbox: str = ""
    items: list[TriageItem] = field(default_factory=list)
    drafts_created: list[dict[str, Any]] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for item in self.items:
            out[item.category] = out.get(item.category, 0) + 1
        return out

    def render(self) -> str:
        """Owner-facing rendering for Telegram/dashboard (plain text)."""
        if self.status != "ok":
            return f"📥 Inbox triage: no mail was read — {self.status}"
        if not self.items:
            return "📥 Inbox triage: inbox is empty (nothing matched the fetch)."
        counts = self.counts()
        head = "📥 Inbox triage — " + ", ".join(
            f"{name} {count}" for name, count in sorted(counts.items())
        )
        lines = [head]
        for item in self.items[:10]:
            lines.append(
                f"• [{item.category} · p{item.priority}] {item.message.subject} "
                f"— {item.message.sender}\n  {item.summary}"
            )
        if self.drafts_created:
            lines.append(
                f"✍️ {len(self.drafts_created)} reply draft(s) queued — "
                "nothing sends until you approve them."
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mailbox": self.mailbox,
            "counts": self.counts(),
            "items": [item.to_dict() for item in self.items],
            "drafts_created": self.drafts_created,
        }


def triage_inbox(
    limit: int = 20,
    only_unread: bool = False,
    *,
    fetcher: Callable[..., tuple[list[InboxMessage], str]] = fetch_inbox,
    summariser: Summariser | None = None,
    drafter: Drafter | None = None,
    queue: DraftQueue | None = None,
) -> TriageReport:
    """One triage pass: fetch → classify → summarise → (draft replies).

    Drafts are created only for ``reply``-suggested items and only when a
    ``drafter`` callable is wired (the brain passes its LLM); without one
    the report still classifies and summarises, and no reply text is
    invented. Drafts land ``pending`` — sending needs explicit approval.
    """
    messages, status = fetcher(limit=limit, only_unread=only_unread)
    address, _ = _mailbox_login()
    report = TriageReport(status=status, mailbox=mailbox_id(address) if address else "")
    if status != "ok":
        return report
    items = [classify_message(m) for m in messages]
    if summariser is not None:
        for item in items:
            try:
                better = summariser(item.message)
            except Exception:
                better = None
            if better:
                item.summary = better
    items.sort(key=lambda i: (-i.priority, i.message.subject.lower()))
    report.items = items
    if drafter is not None:
        draft_queue = queue or DraftQueue(address)
        for item in items:
            if item.suggested_action != "reply":
                continue
            try:
                body = drafter(item.message, item.summary)
            except Exception:
                body = None
            if body:
                report.drafts_created.append(draft_queue.add_draft(item, body))
    return report
