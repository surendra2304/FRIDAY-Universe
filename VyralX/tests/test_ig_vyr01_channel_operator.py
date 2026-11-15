"""TASK-IG-VYR-01: the channel operator (Uplika pattern, implemented natively).

Behaviour pinned here (owner direction 2026-11-15; repos/uplika.md
verdict **adapt** — pattern yes, paid hosted service no):

* analytics name a winning format ONLY from real metrics; with no
  metrics the operator says so and names no winner (production
  VIDEO_METRICS is empty — a "winner" without views would be fake);
* packaging proposals are deterministic, scored, screened for finance
  advice, and every one is ``pending_review`` / approval-gated;
* schedule entries are plans only: ``publish`` is always False and
  privacy always ``unlisted``;
* comment handling produces drafts and *suggested* actions — nothing
  is posted or hidden by the operator;
* a full cycle states on its face that it publishes nothing, and the
  plan enqueues into the VYR-004 review queue as ``pending_review``.

On clean main every test fails: app.services.channel_operator does
not exist.
"""
from __future__ import annotations

from datetime import datetime

from app.services import channel_operator as co
from app.services import remix_flow as rf


def _video(title, fmt, views=None):
    v = {"title": title, "lane": "space_science", "format_name": fmt}
    if views is not None:
        v["metrics"] = {"views": views, "likes": views // 20,
                        "comments": views // 100}
    return v


# --------------------------------------------------------------------------- #
# Analytics honesty
# --------------------------------------------------------------------------- #
def test_no_metrics_names_no_winner():
    out = co.analyse_channel([_video("A", "remix"), _video("B", "remix")])
    assert out["metrics_available"] is False
    assert out["winning_formats"] == []
    assert out["basis"] == "none"
    assert any("no winning format" in n for n in out["notes"])


def test_winners_come_from_measured_views_only():
    out = co.analyse_channel([
        _video("A", "remix", views=1000),
        _video("B", "remix", views=3000),
        _video("C", "explainer", views=500),
        _video("D", "explainer"),  # unmeasured: listed, not ranked on
    ])
    assert out["metrics_available"] is True
    assert out["winning_formats"] == ["remix", "explainer"]
    remix = next(f for f in out["formats"] if f["format_name"] == "remix")
    assert remix["views_mean"] == 2000.0
    assert remix["measured_videos"] == 2


# --------------------------------------------------------------------------- #
# Packaging proposals
# --------------------------------------------------------------------------- #
def test_proposals_are_gated_and_scored():
    pack = co.propose_packaging("the Apollo 11 landing", "space_science",
                                count=3)
    assert len(pack["proposals"]) == 3
    for p in pack["proposals"]:
        assert p["status"] == "pending_review"
        assert p["requires_approval"] is True
        assert p["publish"] is False
        assert p["title_strength"] is not None
        assert "Apollo 11" in p["title"]


def test_unknown_lane_and_empty_topic_rejected():
    for bad in (lambda: co.propose_packaging("x", "movies"),
                lambda: co.propose_packaging("  ", "history")):
        try:
            bad()
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError")


def test_advice_screen_drops_candidates():
    hits = co._screen_text(
        "Invest now — this strategy guarantees you will double your "
        "money with zero risk.")
    assert hits  # the compliance gate's finder must trip on this
    clean = co._screen_text("The strange true story of the Silk Road.")
    assert clean == []


# --------------------------------------------------------------------------- #
# Schedule planning
# --------------------------------------------------------------------------- #
def test_schedule_is_plan_only_unlisted_and_ordered():
    pack = co.propose_packaging("the Silk Road", "history", count=3)
    start = datetime(2026, 11, 16, 9, 0, tzinfo=co.IST)  # a Monday
    entries = co.build_schedule(pack["proposals"], start)
    assert len(entries) == 3
    times = [e["planned_for"] for e in entries]
    assert times == sorted(times)
    for e in entries:
        assert e["publish"] is False
        assert e["privacy"] == "unlisted"
        assert e["status"] == "pending_review"
        assert e["requires_approval"] is True


# --------------------------------------------------------------------------- #
# Comment drafts
# --------------------------------------------------------------------------- #
def test_comment_drafts_post_nothing():
    drafts = co.draft_comment_replies([
        {"comment_id": "1", "author": "a", "text": "How did you get this footage?"},
        {"comment_id": "2", "author": "b", "text": "sub4sub — check my channel, free money!"},
        {"comment_id": "3", "author": "c", "text": "Loved this one."},
    ])
    assert drafts[0]["action"] == "reply" and drafts[0]["reply"]
    assert drafts[1]["action"] == "hide" and drafts[1]["reply"] is None
    assert drafts[2]["action"] == "reply"
    for d in drafts:
        assert d["status"] == "draft_pending_approval"
        assert d["posted"] is False
        assert d["requires_approval"] is True


# --------------------------------------------------------------------------- #
# Full cycle + review-queue wiring
# --------------------------------------------------------------------------- #
def test_cycle_publishes_nothing_and_enqueues_pending_review(tmp_path):
    snapshot = {
        "videos": [_video("A", "remix", views=10)],
        "topics": [{"topic": "the Voyager probes", "lane": "space_science"}],
        "comments": [{"comment_id": "9", "author": "z", "text": "Nice!"}],
    }
    plan = co.run_operator_cycle(
        snapshot, datetime(2026, 11, 16, 9, 0, tzinfo=co.IST))
    assert plan["publishes_anything"] is False
    assert plan["status"] == "pending_review"
    assert plan["proposals"] and plan["schedule"]
    assert plan["schedule"][0]["publish"] is False

    queue = tmp_path / "queue.jsonl"
    co.enqueue_operator_plan(plan, queue)
    entries = rf.list_review_queue(queue)
    assert len(entries) == 1
    assert entries[0]["kind"] == "channel_operator_plan"
    assert entries[0]["status"] == "pending_review"
    assert entries[0]["publishes_anything"] is False
