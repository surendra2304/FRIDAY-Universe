"""Nightly per-agent work summaries into the vault's Daily Logs (TASK-MEM-030).

One summary note per agent per night, rendered from that day's Memora
capture events (the ``SessionCaptureService`` event records MEM-029 wired
as production callers: every turn captured as a ``/v1/capture/events``
observation, sessions compressed at session end). A summary groups the
day's events by session and by kind, counts them, and links each event's
vault note — the same extractive shape as the capture digest
(``SessionCaptureService._digest``: per-kind first lines, duplicates
collapsed), extended from one session to one agent-day.

Honesty rule: an agent with no captured events for the day still gets a
note, and the note says so plainly ("No captured work for <agent> on
<date>"). A summary must never invent activity for a silent agent; the
note evidences that the cycle RAN for every agent, and the count (zero)
is the finding.

Stdlib only, like :mod:`core.memory.vault`. Dates are ``YYYY-MM-DD``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from core.memory.vault import (
    AGENTS,
    build_vault,
    normalize_record,
    safe_filename,
)

#: Event kinds the capture hooks emit (``core.memory.capture_service.
#: KNOWN_KINDS``). Free-form kinds are normalised to ``"observation"``
#: rather than rejected — capture must never lose an event over a label.
#: The set is repeated here instead of imported so this module stays
#: stdlib-only and importable without the service's SQLAlchemy stack.
KNOWN_KINDS = {"tool_call", "decision", "correction", "observation", "file_edit", "note"}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _kind_of(record: Mapping[str, Any]) -> str:
    kind = (record.get("event_kind") or "observation").strip().lower()
    return kind if kind in KNOWN_KINDS else "observation"


def _is_capture_event(record: Mapping[str, Any]) -> bool:
    """True for a session-capture event record.

    Capture events carry ``provenance.session_id`` (see
    ``SessionCaptureService.capture_event``) or the ``session_capture``
    source. Compressed-session digests are memories, not events, and are
    excluded here — the summary links them through their sessions.
    """
    if record.get("session_id"):
        return True
    return (record.get("source") or "") == "session_capture"


def _first_line(content: str) -> str:
    for line in (content or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return "(empty event)"


def summarize_agent_day(
    agent: str,
    date: str,
    events: Sequence[Mapping[str, Any]],
) -> str:
    """Markdown text of one agent's daily summary note.

    ``events`` are normalised capture-event records for this agent and
    day (any order; they are grouped by session, then by kind).
    """
    if not _DATE_RE.match(date):
        raise ValueError("date must be YYYY-MM-DD, got %r" % (date,))
    by_session: Dict[str, List[Mapping[str, Any]]] = {}
    for event in events:
        by_session.setdefault(event.get("session_id") or "unsessioned", []).append(event)
    by_kind: Dict[str, int] = {}
    for event in events:
        kind = _kind_of(event)
        by_kind[kind] = by_kind.get(kind, 0) + 1

    lines = [
        "---",
        "agent: '" + agent.replace("'", "''") + "'",
        "date: '" + date + "'",
        "kind: 'daily-summary'",
        "events: " + str(len(events)),
        "sessions: " + str(len(by_session)),
        "---",
        "",
        "# " + date + " — " + agent,
        "",
    ]
    if not events:
        lines.append("No captured work for " + agent + " on " + date + ".")
        lines.append("")
        lines.append(
            "The nightly cycle ran and found no capture events for this "
            "agent on this date — nothing is inferred, nothing is invented."
        )
        lines.append("")
        lines.append("Vault index: [[00 - Second Brain]]")
        lines.append("")
        return "\n".join(lines)

    lines.append(
        str(len(events)) + " captured event(s) across "
        + str(len(by_session)) + " session(s)."
    )
    lines.append("")
    lines.append("## By kind")
    lines.append("")
    for kind in sorted(by_kind):
        lines.append("- " + kind + ": " + str(by_kind[kind]))
    lines.append("")
    for session_id in sorted(by_session):
        session_events = sorted(
            by_session[session_id], key=lambda e: (e["created_at"], e["id"])
        )
        lines.append("## Session " + session_id)
        lines.append("")
        kinds: Dict[str, List[Mapping[str, Any]]] = {}
        for event in session_events:
            kinds.setdefault(_kind_of(event), []).append(event)
        for kind in sorted(kinds):
            lines.append("### " + kind)
            lines.append("")
            seen = set()
            for event in kinds[kind]:
                first = _first_line(event["content"])
                if first in seen:
                    continue
                seen.add(first)
                lines.append(
                    "- [[" + safe_filename(event["id"]) + "]] — " + first
                )
            lines.append("")
    lines.append("Vault index: [[00 - Second Brain]]")
    lines.append("")
    return "\n".join(lines)


def run_nightly(
    records: Iterable[Any],
    date: str,
    out_dir: Any,
    *,
    agents: Sequence[str] = AGENTS,
    include_private: bool = False,
) -> Dict[str, Any]:
    """Write one daily-summary note per agent for ``date``.

    ``records`` is the store export (same shape as for
    :func:`core.memory.vault.build_vault`); only capture events dated
    ``date`` are summarised. PRIVATE-scope events are excluded unless
    ``include_private=True`` — the same fail-closed rule as the vault
    build, so a summary can never surface an event whose own note the
    vault withholds. Every agent in ``agents`` gets a note, including
    silent ones (see the honesty rule in the module docstring).
    Extra agents found in the day's events get notes too. Returns a
    manifest ``{"date": ..., "agents": {agent: {"events", "sessions",
    "file"}}, "files": [...]}``.
    """
    if not _DATE_RE.match(date):
        raise ValueError("date must be YYYY-MM-DD, got %r" % (date,))
    root = Path(out_dir)
    (root / "Daily Logs").mkdir(parents=True, exist_ok=True)

    day_events: Dict[str, List[Dict[str, Any]]] = {}
    for raw in records:
        record = normalize_record(raw)
        if record is None or not _is_capture_event(record):
            continue
        if record["scope"] == "PRIVATE" and not include_private:
            continue
        if (record["created_at"] or "")[:10] != date:
            continue
        day_events.setdefault(record["agent"], []).append(record)

    manifest_agents: Dict[str, Dict[str, Any]] = {}
    files: List[str] = []
    for agent in sorted(set(agents) | set(day_events)):
        events = sorted(
            day_events.get(agent, []), key=lambda e: (e["created_at"], e["id"])
        )
        sessions = {e.get("session_id") or "unsessioned" for e in events}
        filename = date + "-" + agent + ".md"
        (root / "Daily Logs" / filename).write_text(
            summarize_agent_day(agent, date, events), encoding="utf-8"
        )
        manifest_agents[agent] = {
            "events": len(events),
            "sessions": len(sessions) if events else 0,
            "file": "Daily Logs/" + filename,
        }
        files.append("Daily Logs/" + filename)
    return {"date": date, "agents": manifest_agents, "files": sorted(files)}


def load_records_json(path: Any) -> List[Dict[str, Any]]:
    """Load a store export: a JSON list of record dicts, or JSONL."""
    text = Path(path).read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("record export must be a JSON list")
        return data
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def run_daily_cycle(
    records: Iterable[Any],
    date: str,
    out_dir: Any,
    *,
    agents: Sequence[str] = AGENTS,
    include_private: bool = False,
) -> Dict[str, Any]:
    """One nightly run: rebuild the vault view, then the day's summaries.

    ``records`` is consumed once (materialised here) so a caller can pass
    a generator. Returns ``{"vault": <build_vault manifest>,
    "nightly": <run_nightly manifest>}``.
    """
    materialised = list(records)
    vault_manifest = build_vault(
        materialised, out_dir, include_private=include_private
    )
    nightly_manifest = run_nightly(
        materialised, date, out_dir, agents=agents, include_private=include_private
    )
    return {"vault": vault_manifest, "nightly": nightly_manifest}
