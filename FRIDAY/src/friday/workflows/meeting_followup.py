"""Post-meeting follow-up automation (TASK-IG2-FRD-04).

Cluster #19 (IG wave-2 triage, BUILD/FRIDAY): after a meeting ends,
FRIDAY turns the meeting's notes/transcript into (a) a short extractive
summary, (b) structured action items (owner + due hint where the text
states them), and (c) a follow-up *draft* the owner can send.

Wiring to FRIDAY's existing surfaces — not a parallel system:

* the meeting is identified by title/time in the shape the existing
  calendar tool (``friday.tools.builtin.calendar``) already produces;
* extracted action items can be handed to the existing persistent
  follow-up registry (``friday.proactive.followup_registry``) via
  ``register_action_items`` — the same registry ``followup_add`` uses;
* the draft lives in an approval store in the shape of the existing
  errand/follow-up gates: **PENDING until the owner approves or rejects
  it, and nothing is ever auto-sent** — this module has no send function
  at all; an approved draft is returned as text for the owner to send
  through whatever channel he chooses.

Extraction is deterministic and extractive (stdlib only): summary lines
are the meeting's own sentences, action items are lines the notes mark
as actions (``TODO:``, ``Action:``, ``- [ ]``, ``AI:``) or sentences with
an explicit commitment verb + owner. Nothing is invented.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

_ACTION_MARKERS = ("todo:", "action:", "ai:", "- [ ]", "[ ]")
_COMMITMENT_RE = re.compile(
    r"^(?P<owner>[A-Z][A-Za-z]+)\s+will\s+(?P<task>.+?)(?:\s+by\s+(?P<due>[^.!?]+?))?[.!]?$")
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?")
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "we", "it", "is", "was", "are", "be", "by", "at", "that", "this",
})


@dataclass(slots=True)
class ActionItem:
    task: str
    owner: str = ""
    due_hint: str = ""
    source_line: str = ""


@dataclass(slots=True)
class MeetingFollowUp:
    meeting_title: str
    summary: str
    action_items: list[ActionItem] = field(default_factory=list)
    draft_text: str = ""
    status: str = "PENDING"  # PENDING -> APPROVED | REJECTED (owner gate)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())
    followup_ids: list[str] = field(default_factory=list)


def extract_action_items(notes: str) -> list[ActionItem]:
    """Pull action items from marked lines and explicit commitments."""
    items: list[ActionItem] = []
    seen: set[str] = set()
    for raw in (notes or "").splitlines():
        line = raw.strip().lstrip("-* ").strip()
        if not line:
            continue
        lowered = line.lower()
        task = ""
        if any(lowered.startswith(m) or m in lowered[:8] for m in _ACTION_MARKERS):
            task = re.sub(r"(?i)^(todo:|action:|ai:|\[ \])\s*", "", line).strip()
            task = re.sub(r"^\[ \]\s*", "", task).strip()
        else:
            match = _COMMITMENT_RE.match(line)
            if match:
                item = ActionItem(task=match.group("task").strip(),
                                  owner=match.group("owner"),
                                  due_hint=(match.group("due") or "").strip(),
                                  source_line=line)
                if item.task.lower() not in seen:
                    seen.add(item.task.lower())
                    items.append(item)
                continue
        if task and task.lower() not in seen:
            seen.add(task.lower())
            items.append(ActionItem(task=task, source_line=line))
    return items


def summarise(notes: str, *, max_sentences: int = 3) -> str:
    """Extractive summary: the most content-rich sentences, in order."""
    sentences = [s.strip() for s in _SENTENCE_RE.findall(notes or "")
                 if len(s.strip()) > 20
                 and not s.strip().lower().startswith(("todo:", "action:", "ai:", "- [ ]"))]
    if not sentences:
        return ""
    def richness(sentence: str) -> int:
        return len({w for w in re.findall(r"[a-z]+", sentence.lower())
                    if w not in _STOPWORDS})
    ranked = sorted(range(len(sentences)), key=lambda i: -richness(sentences[i]))
    chosen = sorted(ranked[:max_sentences])
    return " ".join(sentences[i] for i in chosen)


def build_followup(meeting_title: str, notes: str,
                   attendees: list[str] | None = None) -> MeetingFollowUp:
    """Build the summary + action items + owner-approval draft."""
    title = (meeting_title or "Meeting").strip() or "Meeting"
    summary = summarise(notes)
    items = extract_action_items(notes)
    lines = [f"Subject: Follow-up — {title}", ""]
    if attendees:
        lines.append(f"Attendees: {', '.join(attendees)}")
        lines.append("")
    lines.append("Summary:")
    lines.append(summary or "(no summary could be extracted from the notes)")
    lines.append("")
    lines.append("Action items:")
    if items:
        for item in items:
            owner = f" ({item.owner})" if item.owner else ""
            due = f" — due: {item.due_hint}" if item.due_hint else ""
            lines.append(f"- {item.task}{owner}{due}")
    else:
        lines.append("- None recorded.")
    lines.append("")
    lines.append("— Draft prepared by FRIDAY; not sent. Owner review required.")
    return MeetingFollowUp(meeting_title=title, summary=summary,
                            action_items=items, draft_text="\n".join(lines))


class MeetingFollowUpStore:
    """In-memory draft store behind the owner approval gate (thread-safe)."""

    def __init__(self) -> None:
        self._drafts: dict[str, MeetingFollowUp] = {}
        self._counter = 0
        self._lock = threading.RLock()

    def add(self, followup: MeetingFollowUp) -> str:
        with self._lock:
            self._counter += 1
            draft_id = f"mf-{self._counter}"
            self._drafts[draft_id] = followup
            return draft_id

    def get(self, draft_id: str) -> MeetingFollowUp:
        with self._lock:
            if draft_id not in self._drafts:
                raise KeyError(f"unknown meeting follow-up draft {draft_id!r}")
            return self._drafts[draft_id]

    def list(self, status: str = "") -> list[tuple[str, MeetingFollowUp]]:
        with self._lock:
            return [(k, v) for k, v in self._drafts.items()
                    if not status or v.status == status]

    def approve(self, draft_id: str) -> MeetingFollowUp:
        return self._set_status(draft_id, "APPROVED")

    def reject(self, draft_id: str) -> MeetingFollowUp:
        return self._set_status(draft_id, "REJECTED")

    def _set_status(self, draft_id: str, status: str) -> MeetingFollowUp:
        with self._lock:
            followup = self.get(draft_id)
            if followup.status != "PENDING":
                raise ValueError(f"draft {draft_id} is already {followup.status}")
            followup.status = status
            return followup

    def approved_text(self, draft_id: str) -> str:
        """The only way draft text leaves the store — after approval."""
        followup = self.get(draft_id)
        if followup.status != "APPROVED":
            raise ValueError(
                f"draft {draft_id} is {followup.status}; the owner must approve it first")
        return followup.draft_text


_store: MeetingFollowUpStore | None = None


def default_store() -> MeetingFollowUpStore:
    global _store
    if _store is None:
        _store = MeetingFollowUpStore()
    return _store


def register_action_items(followup: MeetingFollowUp, registry=None) -> list[str]:
    """Hand action items to FRIDAY's existing follow-up registry.

    Uses ``friday.proactive.followup_registry.default_registry`` unless a
    registry is injected (tests). Returns the registry record ids.
    """
    if registry is None:
        from friday.proactive.followup_registry import default_registry
        registry = default_registry()
    ids: list[str] = []
    for item in followup.action_items:
        detail = f"From meeting '{followup.meeting_title}'"
        if item.owner:
            detail += f" — owner: {item.owner}"
        if item.due_hint:
            detail += f" — due: {item.due_hint}"
        record = registry.add(item.task, detail, source="meeting_followup")
        ids.append(record["id"] if isinstance(record, dict) else str(record))
    followup.followup_ids = ids
    return ids


__all__ = ["ActionItem", "MeetingFollowUp", "MeetingFollowUpStore",
           "build_followup", "default_store", "extract_action_items",
           "register_action_items", "summarise"]
