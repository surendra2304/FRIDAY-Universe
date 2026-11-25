"""
Memora/core/memory/session_needles.py — Needle observations + layered session index.

TASK-MEM-031: claude-mem adaptation (thedotmack/claude-mem, Apache-2.0,
v16.1.3, ~119.6k stars, 2026-11-25).

What claude-mem does that Memora did not: its hooks classify every captured
observation into a fixed needle taxonomy (``decision``, ``bugfix``,
``security_alert``, ``security_note``, ``sensitive``, ... — see
``src/ui/viewer/utils/category.ts``: KNOWN_OBSERVATION_TYPES /
CATEGORY_ORDER), and the next session opens with a compact, token-costed
index over past sessions — the mem-search skill's three steps are index,
then timeline, then details, so the agent pays tokens only for what it
opens. claude-mem itself is a Node/TypeScript hook + worker runtime for
coding-agent CLIs (Claude Code, Codex, Cursor, ...); it cannot run on the
~180 MB Python fleet, and its hosted observer is a paid trial — so the
pattern lands here as Memora-native Python over Memora's own capture store
(TASK-IG2-MEM-01), stdlib only:

- ``classify_needle`` — deterministic rule-based classification of captured
  content into claude-mem's needle taxonomy. No LLM, no invented content.
- ``list_actor_sessions`` / ``render_index`` — the L0 session-start index:
  one row per past session with needle counts and a token estimate.
- ``timeline`` — the L1 per-session timeline: first lines grouped by needle
  kind. ``sensitive`` rows never render their content here — claude-mem
  treats sensitive observations as awareness-only, and so do we.
- ``detail`` — the L2 single-event read, with the same withholding rule.

Wired in: ``SessionCaptureService.capture_event`` classifies every event
and stores ``needle_kind`` in provenance; ``build_session_context``
prepends the L0 index to the session-start pack; ``GET /v1/capture/
sessions`` serves the index; ``ForgeAdapter.record_session_observation``
classifies + stores Forge observations with the same taxonomy.
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from storage.relational.models import LifecycleState, MemoryRecord

#: The capture source this module reads. Mirrors
#: ``SessionCaptureService``'s CAPTURE_SOURCE in core/memory/capture_service.py.
CAPTURE_SOURCE = "session_capture"

#: claude-mem's needle taxonomy (KNOWN_OBSERVATION_TYPES, category.ts),
#: restricted to the kinds a session observation can carry. ``observation``
#: is the fallback for content that matches nothing.
NEEDLE_KINDS = (
    "decision",
    "bugfix",
    "security_alert",
    "security_note",
    "sensitive",
    "feature",
    "refactor",
    "discovery",
    "change",
    "observation",
)

#: Classification order. First match wins; security kinds outrank everything
#: else so a fix for a vulnerability reads as a security alert, not a bugfix,
#: and a sensitive marker outranks a decision so private content is never
#: injected as an ordinary decision.
_CLASSIFIER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("security_alert", (
        r"cve-\d{4}-\d+",
        r"vulnerabilit\w*",
        r"exploit\w*",
        r"sql injection",
        r"xss|cross-site scripting",
        r"\bcsrf\b",
        r"auth\w* bypass",
        r"privilege escalation",
        r"remote code execution",
        r"\brce\b",
        r"malware",
        r"data breach",
        r"leaked credential",
        r"hardcoded (secret|password|api key)",
    )),
    ("sensitive", (
        r"confidential",
        r"do not share",
        r"do not memoris\w*",
        r"do not memorize",
        r"private key",
        r"api key",
        r"secret key",
        r"access token",
        r"auth token",
        r"password",
        r"passphrase",
        r"credit card",
        r"social security",
        r"\bssn\b",
        r"passport",
        r"personal data",
        r"bank account",
    )),
    ("security_note", (
        r"security",
        r"encrypt\w*",
        r"permission\w*",
        r"authentication",
        r"authorization",
        r"\btls\b",
        r"\bhttps\b",
        r"\baudit\b",
        r"threat model",
    )),
    ("bugfix", (
        r"\bfix(es|ed|ing)?\b",
        r"\bbug\b",
        r"regression",
        r"\bbroken\b",
        r"\berror\b",
        r"exception",
        r"traceback",
        r"crash(ed|ing)?",
        r"fail(ed|ure|ing)?",
        r"hotfix",
        r"\bpatch\b",
    )),
    ("decision", (
        r"decid(e|ed|ing|es)?",
        r"\bdecision\b",
        r"\bchose\b",
        r"\bchosen\b",
        r"\bchoose\b",
        r"adopt(ed|ing)?",
        r"trade-?off",
        r"\bagreed\b",
        r"instead of",
        r"prefer(red|s)?",
    )),
    ("feature", (
        r"new feature",
        r"implement(ed|ing|s)?",
        r"add(ed|ing)? support",
        r"introduc(e|ed|ing|s)?",
        r"support for",
    )),
    ("refactor", (
        r"refactor(ed|ing|s)?",
        r"restructur(e|ed|ing)?",
        r"clean ?up",
        r"rename(d|s)?",
        r"extract(ed|s)?",
    )),
    ("discovery", (
        r"discover(ed|y|ing)?",
        r"found that",
        r"\blearned\b",
        r"realis(e|ed|ing)",
        r"noticed",
        r"turns out",
    )),
    ("change", (
        r"chang(e|ed|ing|s)?",
        r"updat(e|ed|ing|s)?",
        r"modif(y|ied|ying|ies)",
        r"migrat(e|ed|ing|ion)",
    )),
)

_COMPILED_RULES: tuple[tuple[str, tuple["re.Pattern[str]", ...]], ...] = tuple(
    (kind, tuple(re.compile(p, re.IGNORECASE) for p in patterns))
    for kind, patterns in _CLASSIFIER_RULES
)

_MAX_INDEX_SESSIONS = 10
_MAX_INDEX_EVENTS = 2000
_MAX_TIMELINE_CHARS = 2000

_SENSITIVE_PLACEHOLDER = "[sensitive — content withheld]"


def token_estimate(text: str) -> int:
    """Rough token count for an index row (same 4-chars-per-token rule as
    Memora's markdown memory runtime)."""
    return max(1, math.ceil(len(text or "") / 4.0))


def classify_needle(content: str) -> str:
    """Classify captured content into claude-mem's needle taxonomy.

    Deterministic and rule-based: the first matching kind in priority
    order wins, and content matching nothing is an ``observation``.
    Never raises on hostile input.
    """
    text = content or ""
    for kind, patterns in _COMPILED_RULES:
        for pattern in patterns:
            if pattern.search(text):
                return kind
    return "observation"


def _actor_events(
    db: Session,
    *,
    actor_name: str,
    session_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> List[MemoryRecord]:
    """Captured session events visible to ``actor_name``.

    Mirrors ``SessionCaptureService._session_events``' scope rule: the
    capture source, a live lifecycle state, the actor's own rows, and the
    tenant when one is given.
    """
    query = db.query(MemoryRecord).filter(
        MemoryRecord.source == CAPTURE_SOURCE,
        MemoryRecord.lifecycle_state.in_(
            [LifecycleState.ACTIVE, LifecycleState.VERIFIED, LifecycleState.CANDIDATE]
        ),
    )
    if tenant_id:
        query = query.filter(MemoryRecord.tenant_id == tenant_id)
    records = (
        query.order_by(MemoryRecord.created_at.asc(), MemoryRecord.id.asc())
        .limit(_MAX_INDEX_EVENTS)
        .all()
    )
    events = [
        r for r in records
        if (r.agent_id == actor_name or r.owner_agent == actor_name)
        and (session_id is None or (r.provenance or {}).get("session_id") == session_id)
    ]
    return events


def _needle_of(record: MemoryRecord) -> str:
    """The stored needle kind, falling back to classification for rows
    captured before needle kinds were recorded."""
    stored = (record.provenance or {}).get("needle_kind")
    if isinstance(stored, str) and stored in NEEDLE_KINDS:
        return stored
    return classify_needle(record.content_text or "")


def list_actor_sessions(
    db: Session,
    *,
    actor_name: str,
    tenant_id: Optional[str] = None,
    limit: int = _MAX_INDEX_SESSIONS,
) -> List[Dict[str, Any]]:
    """L0: one row per past captured session for ``actor_name``.

    Each row carries the event count, the needle-kind counts, first/last
    event timestamps and a token estimate — the compact index a session
    opens with, before any detail is read. Newest session first.
    """
    events = _actor_events(db, actor_name=actor_name, tenant_id=tenant_id)
    by_session: Dict[str, Dict[str, Any]] = {}
    for event in events:
        sid = str((event.provenance or {}).get("session_id") or "")
        if not sid:
            continue
        row = by_session.setdefault(
            sid,
            {
                "session_id": sid,
                "event_count": 0,
                "needles": {},
                "first_event_at": None,
                "last_event_at": None,
                "tokens": 0,
            },
        )
        row["event_count"] += 1
        needle = _needle_of(event)
        needles = row["needles"]
        needles[needle] = needles.get(needle, 0) + 1
        row["tokens"] += token_estimate(event.content_text or "")
        created = event.created_at
        stamp = created.isoformat() if isinstance(created, datetime) else str(created or "")
        if row["first_event_at"] is None:
            row["first_event_at"] = stamp
        row["last_event_at"] = stamp
    sessions = sorted(
        by_session.values(),
        key=lambda r: (r["last_event_at"] or "", r["session_id"]),
        reverse=True,
    )
    return sessions[: max(1, limit)]


def render_index(sessions: List[Dict[str, Any]]) -> str:
    """Render the L0 index as text with per-session token costs."""
    if not sessions:
        return ""
    lines = ["Past sessions (session index — open a timeline for details):"]
    for row in sessions:
        needles = " · ".join(
            f"{kind} {count}"
            for kind, count in sorted(row["needles"].items())
            if count
        )
        lines.append(
            f"- Session {row['session_id']}: {row['event_count']} event(s)"
            + (f" ({needles})" if needles else "")
            + f" ~{row['tokens']} tokens"
        )
    lines.append(f"Total ~{sum(r['tokens'] for r in sessions)} tokens across {len(sessions)} session(s).")
    return "\n".join(lines)


def timeline(
    db: Session,
    *,
    actor_name: str,
    session_id: str,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """L1: the per-session timeline — first lines grouped by needle kind.

    ``sensitive`` rows render as a placeholder, never their content.
    """
    events = _actor_events(db, actor_name=actor_name, session_id=session_id, tenant_id=tenant_id)
    by_kind: Dict[str, List[str]] = {}
    seen: set[str] = set()
    for event in events:
        needle = _needle_of(event)
        if needle == "sensitive":
            line = _SENSITIVE_PLACEHOLDER
        else:
            line = re.sub(r"\s+", " ", (event.content_text or "")).strip().split(". ")[0][:220]
        if not line or line in seen:
            continue
        seen.add(line)
        by_kind.setdefault(needle, []).append(line)
    lines = [f"Session {session_id}: {len(events)} captured event(s)."]
    for kind in sorted(by_kind):
        lines.append(f"{kind}:")
        for line in by_kind[kind]:
            lines.append(f"- {line}")
    text = "\n".join(lines)[:_MAX_TIMELINE_CHARS]
    return {
        "session_id": session_id,
        "event_count": len(events),
        "needles": {kind: len(v) for kind, v in by_kind.items()},
        "timeline": text,
    }


def detail(
    db: Session,
    *,
    event_id: str,
    actor_name: str,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """L2: one captured event in full — unless it is ``sensitive``.

    Returns ``withheld: True`` and no content for sensitive rows; the
    caller learns the kind and the session, never the text.
    """
    record = db.query(MemoryRecord).filter(MemoryRecord.id == event_id).one_or_none()
    if record is None:
        return {"found": False, "event_id": event_id}
    if record.agent_id != actor_name and record.owner_agent != actor_name:
        return {"found": False, "event_id": event_id, "reason": "not_visible_to_actor"}
    if tenant_id and record.tenant_id != tenant_id:
        return {"found": False, "event_id": event_id, "reason": "tenant_mismatch"}
    needle = _needle_of(record)
    base = {
        "found": True,
        "event_id": record.id,
        "session_id": (record.provenance or {}).get("session_id"),
        "needle_kind": needle,
        "event_kind": (record.provenance or {}).get("event_kind"),
        "created_at": record.created_at.isoformat() if isinstance(record.created_at, datetime) else str(record.created_at or ""),
    }
    if needle == "sensitive":
        return {**base, "withheld": True, "content": None}
    return {**base, "withheld": False, "content": record.content_text}
