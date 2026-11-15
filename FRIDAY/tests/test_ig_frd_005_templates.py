"""TASK-IG-FRD-005 — workflow template tests."""

from __future__ import annotations

import pytest

from friday.workflows.templates import (
    TEMPLATES,
    TemplateError,
    get_template,
    instantiate,
    list_templates,
    render_plan,
)


class FakeQueue:
    def __init__(self):
        self.added = []

    def add(self, command, source="chat"):
        self.added.append((command, source))
        return {"id": f"m{len(self.added)}"}


class BrokenQueue:
    def add(self, command, source="chat"):
        raise RuntimeError("queue file locked")


def test_catalogue_integrity():
    ids = [t["id"] for t in TEMPLATES]
    assert len(ids) == len(set(ids)) >= 6
    categories = {t["category"] for t in TEMPLATES}
    assert {"content", "social", "business", "research"} <= categories
    for t in TEMPLATES:
        assert t["steps"], t["id"]
        # Every template instantiates with just its required params.
        required = {p["name"]: "x" for p in t["params"] if p.get("required")}
        plan = instantiate(t["id"], required)
        assert len(plan["steps"]) == len(t["steps"])
        for step in plan["steps"]:
            assert "{" not in step["detail"] and "{" not in step["title"]


def test_missing_required_param_is_an_error():
    with pytest.raises(TemplateError) as exc:
        instantiate("content_batch", {})
    assert "topic" in str(exc.value)


def test_defaults_fill_optional_params():
    plan = instantiate("content_batch", {"topic": "AI agents"})
    assert plan["params"]["count"] == 3
    assert "AI agents" in plan["steps"][0]["detail"]


def test_unknown_template():
    with pytest.raises(TemplateError):
        get_template("nope")
    assert list_templates("business")[0]["category"] == "business"


def test_enqueue_uses_mission_queue_shape():
    queue = FakeQueue()
    plan = instantiate("research_brief", {"question": "What is X?"}, enqueue=True, queue=queue)
    assert plan["enqueued"] is True
    assert plan["mission_ids"] == ["m1", "m2"]
    assert all(src == "workflow_template" for _, src in queue.added)
    assert "What is X?" in queue.added[0][0]


def test_enqueue_failure_is_reported_not_faked():
    plan = instantiate("research_brief", {"question": "Q"}, enqueue=True, queue=BrokenQueue())
    assert plan["enqueued"] is False
    assert "queue file locked" in plan["enqueue_error"]
    assert plan["mission_ids"] == []


def test_no_enqueue_by_default():
    plan = instantiate("weekly_review", {})
    assert plan["enqueued"] is False
    assert "enqueue_error" not in plan


def test_render_plan_readable():
    plan = instantiate("job_hunt_daily", {})
    text = render_plan(plan)
    assert "Job-hunt daily scan" in text
    assert "job_hunt_scan" not in text  # hints stay in metadata, plan reads clean
    assert plan["steps"][0]["tool_hint"] == "job_hunt_scan"
