"""TASK-IG2-FRD-04 — post-meeting follow-up automation tests.

Pins: extractive summary uses the meeting's own sentences, action-item
extraction (marked lines + commitments), the approval gate (draft text
only leaves the store after approval; double decisions refused), and
registry hand-off with an injected fake registry.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.workflows.meeting_followup import (  # noqa: E402
    MeetingFollowUpStore, build_followup, extract_action_items,
    register_action_items, summarise)

_NOTES = """We reviewed the Stratex demo results and the position sizing looked prudent.
The voice latency discussion covered greeting delays and provider quotas in detail.
TODO: Send the updated risk summary to the owner
Priya will prepare the staging checklist by Friday.
- [ ] Book the ARM capacity check
We agreed the next review happens after the forward record has more closed trades."""


def test_extracts_marked_and_commitment_action_items():
    items = extract_action_items(_NOTES)
    tasks = [i.task for i in items]
    assert "Send the updated risk summary to the owner" in tasks
    assert "Book the ARM capacity check" in tasks
    commitment = [i for i in items if i.owner == "Priya"]
    assert commitment and commitment[0].due_hint == "Friday"


def test_summary_is_extractive_and_bounded():
    summary = summarise(_NOTES)
    assert summary and all(part.strip() in _NOTES for part in summary.split(". ") if part.strip())
    assert summary.count(".") <= 3


def test_build_followup_draft_is_pending_and_complete():
    followup = build_followup("Weekly Review", _NOTES, attendees=["Surendra", "Priya"])
    assert followup.status == "PENDING"
    assert "Follow-up — Weekly Review" in followup.draft_text
    assert "not sent" in followup.draft_text
    assert len(followup.action_items) == 3


def test_gate_releases_text_only_after_approval():
    store = MeetingFollowUpStore()
    draft_id = store.add(build_followup("Weekly Review", _NOTES))
    with pytest.raises(ValueError):
        store.approved_text(draft_id)
    store.approve(draft_id)
    assert "Weekly Review" in store.approved_text(draft_id)
    with pytest.raises(ValueError):
        store.approve(draft_id)  # already decided


def test_rejected_draft_never_releases_text():
    store = MeetingFollowUpStore()
    draft_id = store.add(build_followup("Weekly Review", _NOTES))
    store.reject(draft_id)
    with pytest.raises(ValueError):
        store.approved_text(draft_id)


class _FakeRegistry:
    def __init__(self) -> None:
        self.records: list[tuple[str, str, str]] = []

    def add(self, title: str, detail: str, source: str = "") -> dict:
        self.records.append((title, detail, source))
        return {"id": f"fu-{len(self.records)}"}


def test_action_items_register_into_existing_followup_registry():
    followup = build_followup("Weekly Review", _NOTES)
    registry = _FakeRegistry()
    ids = register_action_items(followup, registry=registry)
    assert ids == ["fu-1", "fu-2", "fu-3"]
    assert all(r[2] == "meeting_followup" for r in registry.records)
    assert followup.followup_ids == ids


def test_module_has_no_send_surface():
    import friday.workflows.meeting_followup as mod
    names = [n.lower() for n in dir(mod)]
    assert not any("send" in n or "smtp" in n for n in names)
