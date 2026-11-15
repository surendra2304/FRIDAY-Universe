"""TASK-IG-VYR-04: faceless series automation (IG corpus cluster).

Behaviour pinned here:

* a series spec must use an owner-approved lane and must not trip
  the compliance gate's excluded categories; finance-advice topic
  seeds are screened out and reported;
* episode briefs are deterministic, deduped against existing titles
  and within the plan, with skips recorded (never silent);
* the daily queue is pure date arithmetic over start + cadence;
* briefs enqueue into the VYR-004 review queue as pending_review,
  and nothing in the module publishes.

On clean main every test fails: app.services.series_automation
does not exist.
"""
from __future__ import annotations

from datetime import date

from app.services import remix_flow as rf
from app.services import series_automation as sa

SERIES = {
    "series_id": "silk-road-files",
    "lane": "history",
    "format_name": "series_episode",
    "cadence_days": 2,
    "episodes_planned": 3,
    "start_date": "2026-11-17",
    "topic_seeds": ["the Silk Road marketplace takedown",
                    "the first online black market",
                    "the mistakes that ended an empire"],
}


def test_validate_accepts_clean_series():
    out = sa.validate_series(SERIES)
    assert out["ok"] is True
    assert out["screened_seeds"] == SERIES["topic_seeds"]


def test_validate_rejects_excluded_and_unapproved():
    bad = {**SERIES, "lane": "movies", "format_name": "gameplay highlights"}
    out = sa.validate_series(bad)
    assert out["ok"] is False
    assert any("owner-approved" in p for p in out["problems"])
    assert any("excluded" in p for p in out["problems"])


def test_advice_seed_is_screened_out_and_reported():
    rigged = {**SERIES, "topic_seeds": [
        "how to double your money guaranteed with zero risk",
        "the Silk Road marketplace takedown"]}
    out = sa.validate_series(rigged)
    assert out["screened_seeds"] == ["the Silk Road marketplace takedown"]
    assert any("finance-advice" in p for p in out["problems"])


def test_plan_episodes_dedupes_and_records_skips():
    plan = sa.plan_episodes(
        SERIES, existing_titles=["The Silk Road Marketplace Takedown — Part 1"])
    titles = [b["title"] for b in plan["briefs"]]
    assert len(titles) == len(set(titles)) == 2  # seed 1 already ran
    assert plan["shortfall"] == 1
    assert any("collides" in s["reason"] for s in plan["skipped"])
    assert all(b["status"] == "pending_review" for b in plan["briefs"])
    assert all(b["publish"] is False for b in plan["briefs"])
    # re-planning against a full run of the same series yields no briefs
    full = sa.plan_episodes(SERIES)
    plan2 = sa.plan_episodes(
        SERIES, existing_titles=[b["title"] for b in full["briefs"]])
    assert plan2["briefs"] == []
    assert plan2["skipped"], "collisions must be recorded, not silent"


def test_plan_stops_instead_of_repeating_seeds():
    tiny = {**SERIES, "episodes_planned": 5}
    plan = sa.plan_episodes(tiny)
    assert len(plan["briefs"]) == 3  # only 3 seeds exist
    assert plan["shortfall"] == 2
    assert any("already used" in s["reason"] for s in plan["skipped"])


def test_daily_queue_date_arithmetic():
    plan = sa.plan_episodes(SERIES)
    due_day1 = sa.daily_queue([plan], [SERIES], date(2026, 11, 17))
    due_day2 = sa.daily_queue([plan], [SERIES], date(2026, 11, 18))
    due_day3 = sa.daily_queue([plan], [SERIES], date(2026, 11, 19))
    assert [b["episode_no"] for b in due_day1] == [1]
    assert due_day2 == []
    assert [b["episode_no"] for b in due_day3] == [2]


def test_enqueue_briefs_lands_pending_review(tmp_path):
    plan = sa.plan_episodes(SERIES)
    queue = tmp_path / "q.jsonl"
    n = sa.enqueue_briefs(plan["briefs"][:2], queue)
    assert n == 2
    entries = rf.list_review_queue(queue)
    assert len(entries) == 2
    assert all(e["kind"] == "series_episode_brief" for e in entries)
    assert all(e["status"] == "pending_review" for e in entries)
    assert all(e["publishes_anything"] is False for e in entries)


def test_invalid_series_raises_with_problems():
    try:
        sa.plan_episodes({**SERIES, "cadence_days": 0})
    except ValueError as exc:
        assert "cadence_days" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
