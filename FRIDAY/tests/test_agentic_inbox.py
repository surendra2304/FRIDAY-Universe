"""TASK-IG2-FRD-01 — agentic inbox (agentic-inbox pattern ADAPT).

Contracts locked here:
- classification is deterministic rules over the mail's own text, with
  the matched signals recorded (security > finance > action > meeting
  > newsletter in check order);
- summaries without an LLM are extractive — verbatim sentences, never
  an invented paraphrase;
- drafts are created ONLY for reply-suggested items and ONLY when a
  drafter callable is wired; they land ``pending``;
- the ONLY send path is ``DraftQueue.approve_and_send`` on a pending
  draft, and a failed send leaves the draft ``approved``, never ``sent``;
- an unconfigured mailbox reports ``not_configured`` — no mail read,
  no empty-looking success.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.proactive import agentic_inbox as ai  # noqa: E402


def _msg(subject: str, sender: str = "Someone <s@example.com>", body: str = "", unread: bool = False) -> ai.InboxMessage:
    return ai.InboxMessage(
        uid="1", sender=sender, subject=subject, body=body,
        snippet=body[:200], unread=unread,
    )


# ----------------------------------------------------------------------
# classification
# ----------------------------------------------------------------------

def test_security_outranks_everything():
    item = ai.classify_message(_msg("Your verification code is 123456 — also an invoice is attached"))
    assert item.category == ai.CATEGORY_SECURITY
    assert item.priority >= 90
    assert any(s.startswith("security:") for s in item.signals)


def test_finance_and_newsletter_and_action_categories():
    fin = ai.classify_message(_msg("Invoice #42 for your payment", body="Amount debited from your bank account."))
    assert fin.category == ai.CATEGORY_FINANCE
    news = ai.classify_message(_msg("Weekly digest", sender="news@noreply@example.com", body="Unsubscribe here."))
    assert news.category == ai.CATEGORY_NEWSLETTER
    assert news.suggested_action == "archive"
    act = ai.classify_message(_msg("Action required: please review the proposal", body="The deadline is Friday."))
    assert act.category == ai.CATEGORY_ACTION
    assert act.suggested_action == "reply"


def test_urgency_and_unread_raise_priority():
    calm = ai.classify_message(_msg("Invoice attached"))
    hot = ai.classify_message(_msg("Invoice attached — urgent", unread=True))
    assert hot.priority > calm.priority


def test_summary_is_extractive_not_invented():
    body = "The server migration finished at midnight. Backups were verified twice. Nothing else changed."
    item = ai.classify_message(_msg("Migration done", body=body))
    assert item.summary in body or body.startswith(item.summary[:30])


# ----------------------------------------------------------------------
# draft queue: approval gate is the only send path
# ----------------------------------------------------------------------

class _Outcome:
    def __init__(self, sent: bool, detail: str = ""):
        self.sent = sent
        self.detail = detail


def _queue(tmp_path) -> ai.DraftQueue:
    return ai.DraftQueue("owner@example.com", path=str(tmp_path / "drafts.json"))


def _draft(queue: ai.DraftQueue) -> dict:
    item = ai.classify_message(_msg("Action required: please review", body="Please review the attached plan."))
    return queue.add_draft(item, "Thanks — reviewing today.")


def test_draft_lands_pending_and_lists(tmp_path):
    queue = _queue(tmp_path)
    draft = _draft(queue)
    assert draft["status"] == "pending"
    assert [d["id"] for d in queue.list_drafts(status="pending")] == [draft["id"]]


def test_approve_and_send_marks_sent_exactly_once(tmp_path):
    queue = _queue(tmp_path)
    draft = _draft(queue)
    calls = []

    def sender(**kwargs):
        calls.append(kwargs)
        return _Outcome(True)

    result = queue.approve_and_send(draft["id"], sender=sender)
    assert result["sent"] is True
    assert queue.get(draft["id"])["status"] == "sent"
    # Second approval is a no-op: the mail is never sent twice.
    again = queue.approve_and_send(draft["id"], sender=sender)
    assert again.get("already_sent") is True
    assert len(calls) == 1
    assert calls[0]["to_address"] == "s@example.com"


def test_failed_send_stays_approved_never_sent(tmp_path):
    queue = _queue(tmp_path)
    draft = _draft(queue)
    result = queue.approve_and_send(draft["id"], sender=lambda **kw: _Outcome(False, "SMTP refused"))
    assert result["sent"] is False
    assert "SMTP refused" in (result["error"] or "")
    assert queue.get(draft["id"])["status"] == "approved"


def test_rejected_draft_cannot_be_sent(tmp_path):
    queue = _queue(tmp_path)
    draft = _draft(queue)
    assert queue.reject(draft["id"])["status"] == "rejected"
    result = queue.approve_and_send(draft["id"], sender=lambda **kw: _Outcome(True))
    assert result["sent"] is False


def test_mailbox_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_INBOX_DATA_DIR", str(tmp_path))
    path_a = ai._draft_store_path("a@example.com")
    path_b = ai._draft_store_path("b@example.com")
    assert path_a != path_b
    assert ai.mailbox_id("a@example.com") in path_a


# ----------------------------------------------------------------------
# triage run
# ----------------------------------------------------------------------

def _fetcher(messages):
    def fetch(limit=20, only_unread=False):
        return list(messages), "ok"
    return fetch


def test_triage_sorts_by_priority_and_drafts_only_with_drafter(tmp_path, monkeypatch):
    monkeypatch.setenv("FRIDAY_EMAIL_ADDRESS", "owner@example.com")
    monkeypatch.setenv("FRIDAY_EMAIL_APP_PASSWORD", "app-password")
    messages = [
        _msg("Weekly digest", sender="news@noreply@example.com", body="Unsubscribe."),
        _msg("Action required: please review the contract", body="Please review and respond by Friday."),
        _msg("Your verification code", body="Your verification code is 998877."),
    ]
    queue = _queue(tmp_path)
    # No drafter wired: classify + summarise only, no invented replies.
    report = ai.triage_inbox(fetcher=_fetcher(messages), queue=queue)
    assert report.status == "ok"
    assert report.items[0].category == ai.CATEGORY_SECURITY
    assert report.drafts_created == []
    assert queue.list_drafts() == []
    # Drafter wired: exactly the action_required item gets a pending draft.
    report2 = ai.triage_inbox(
        fetcher=_fetcher(messages),
        drafter=lambda msg, summary: "Draft reply body.",
        queue=queue,
    )
    assert len(report2.drafts_created) == 1
    assert report2.drafts_created[0]["status"] == "pending"
    assert "nothing sends until you approve" in report2.render()


def test_triage_unconfigured_mailbox_is_honest(monkeypatch):
    monkeypatch.delenv("FRIDAY_EMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("FRIDAY_EMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setattr(ai, "_mailbox_login", lambda: ("", ""))
    report = ai.triage_inbox(fetcher=lambda limit=20, only_unread=False: ([], "not_configured: unset"))
    assert report.status.startswith("not_configured")
    assert report.items == []
    assert "no mail was read" in report.render()
