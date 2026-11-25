"""TASK-VYR-062: stick-figure template usable by the faceless-series automation.

Behaviour pinned here:

* the registry leg is already on main (TASK-IG3-VYR-02): the
  ``stick_figure_explainer`` template loads and validates like every
  other template — re-asserted first-hand here, because this task's
  acceptance rests on it;
* a series spec may name ``template_id``; an unknown id, or a template
  that does not serve the series lane, is rejected by
  ``validate_series`` with the problem named, and the resolved
  template is returned;
* ``plan_episodes`` with a template plans each brief against it: the
  brief carries ``template_id`` plus the instantiated ``format_plan``
  (beats with contiguous timings at the template range midpoint, hard
  rules included), its outline follows the template beats, and
  ``format_name`` defaults to the template name;
* without ``template_id`` nothing changes: briefs carry no template
  keys, the generic three-beat outline and the ``series_episode``
  default stand (regression guard for TASK-IG-VYR-04);
* templated briefs still flow through the daily queue and the review
  queue unchanged, and nothing in the module publishes.

On clean main the six template tests fail: series_automation knows
no template. (The registry-leg test and the no-template guard pass
on clean main by design — they pin what already exists.)
"""
from __future__ import annotations

from datetime import date

from app.services import format_templates as ft
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

TEMPLATE_ID = "stick_figure_explainer"
EXPECTED_BEATS = ["hook_pose", "setup", "build_up", "aha_pose",
                  "recap_line"]


def test_registry_stick_figure_template_valid():
    template = ft.get_template(TEMPLATE_ID)
    assert ft.validate_template(template) == []
    assert template["ig_sources"] == ["DemH26soPPx"]
    assert template["lanes"] == ["tech_ai", "history", "space_science"]
    assert [b["beat"] for b in template["structure"]] == EXPECTED_BEATS
    assert abs(sum(b["share"] for b in template["structure"]) - 1.0) < 0.011
    assert template["target_seconds"] == [30, 60]


def test_validate_accepts_stick_figure_template():
    spec = {**SERIES, "template_id": TEMPLATE_ID}
    out = sa.validate_series(spec)
    assert out["ok"] is True
    assert out["template"]["id"] == TEMPLATE_ID
    assert out["screened_seeds"] == SERIES["topic_seeds"]


def test_validate_rejects_unknown_template():
    out = sa.validate_series({**SERIES, "template_id": "no_such_format"})
    assert out["ok"] is False
    assert out["template"] is None
    assert any("unknown format template" in p for p in out["problems"])
    assert any("no_such_format" in p for p in out["problems"])


def test_validate_rejects_template_lane_mismatch():
    # ambient_longform serves space_science only; this series is tech_ai.
    spec = {**SERIES, "lane": "tech_ai",
            "template_id": "ambient_longform"}
    out = sa.validate_series(spec)
    assert out["ok"] is False
    assert out["template"] is None
    assert any("does not serve lane" in p for p in out["problems"])


def test_plan_briefs_carry_template_plan():
    spec = {k: v for k, v in SERIES.items() if k != "format_name"}
    spec["template_id"] = TEMPLATE_ID
    plan = sa.plan_episodes(spec)
    assert len(plan["briefs"]) == 3
    for brief in plan["briefs"]:
        assert brief["template_id"] == TEMPLATE_ID
        assert brief["format_name"] == "Stick-figure explainer"
        assert brief["status"] == "pending_review"
        assert brief["publish"] is False
        fmt = brief["format_plan"]
        assert fmt["template_id"] == TEMPLATE_ID
        assert fmt["registry_version"] == ft.REGISTRY_VERSION
        assert fmt["target_seconds"] == 45.0  # midpoint of [30, 60]
        assert fmt["within_template_range"] is True
        assert fmt["status"] == "pending_review"
        beats = fmt["beats"]
        assert [b["beat"] for b in beats] == EXPECTED_BEATS
        assert beats[0]["start"] == 0.0
        assert beats[-1]["end"] == 45.0
        for a, b in zip(beats, beats[1:]):
            assert a["end"] == b["start"]
        assert any("original vector" in r for r in fmt["hard_rules"])
        assert [o.split(":")[0] for o in brief["outline"]] == EXPECTED_BEATS


def test_explicit_format_name_wins_over_template():
    spec = {**SERIES, "template_id": TEMPLATE_ID,
            "format_name": "My Show"}
    plan = sa.plan_episodes(spec)
    assert plan["briefs"][0]["format_name"] == "My Show"
    assert plan["briefs"][0]["template_id"] == TEMPLATE_ID


def test_plan_without_template_unchanged():
    plan = sa.plan_episodes(SERIES)
    assert len(plan["briefs"]) == 3
    for brief in plan["briefs"]:
        assert "template_id" not in brief
        assert "format_plan" not in brief
        assert brief["format_name"] == "series_episode"
        assert brief["outline"] == [
            f"Open on the strongest documented moment of {brief['topic']}.",
            f"Build the story of {brief['topic']} in three documented beats.",
            f"Close with what {brief['topic']} changed — and what came next.",
        ]


def test_templated_briefs_flow_through_queue_and_review(tmp_path):
    spec = {**SERIES, "template_id": TEMPLATE_ID}
    plan = sa.plan_episodes(spec)
    due = sa.daily_queue([plan], [spec], date(2026, 11, 17))
    assert [b["episode_no"] for b in due] == [1]
    assert due[0]["template_id"] == TEMPLATE_ID
    assert due[0]["format_plan"]["beats"][-1]["end"] == 45.0
    queue = tmp_path / "q.jsonl"
    n = sa.enqueue_briefs(plan["briefs"][:2], queue)
    assert n == 2
    entries = rf.list_review_queue(queue)
    assert len(entries) == 2
    assert all(e["kind"] == "series_episode_brief" for e in entries)
    assert all(e["brief"]["template_id"] == TEMPLATE_ID
               for e in entries)
    assert all(e["publishes_anything"] is False for e in entries)
