"""TASK-IG2-VYR-02: the OpenMontage-pattern orchestration layer.

Behaviour pinned here:

* manifests adapt OpenMontage's pipelines to VyralX lanes/formats,
  with render stages marked off_fleet (the full stack cannot run
  on the ~956MB fleet);
* provider selection is scored and free-first — paid or GPU
  providers are ineligible at the default $0 budget;
* the storyboard stage is a hard approval gate;
* the quality gate enforces the Shorts <60s cap, captions,
  provenance and the finance-advice screen;
* runs publish nothing and stay unlisted.

On clean main every test fails:
app.services.pipeline_orchestration does not exist.
"""
from __future__ import annotations

import pytest

from app.services import pipeline_orchestration as po


def test_manifests_cover_vyralx_lanes_and_render_is_off_fleet():
    assert "explainer_short" in po.list_pipelines()
    run = po.create_run("explainer_short", "Nebula birth", lane="space_science")
    by_stage = {s["stage"]: s for s in run["stages"]}
    assert by_stage["compose"]["runs"] == "off_fleet"
    assert by_stage["research"]["runs"] == "on_fleet"
    assert run["budget_usd"] == 0.0
    assert run["publish"] is False
    assert run["privacy_if_published"] == "unlisted"


def test_lane_restrictions_enforced_per_pipeline():
    with pytest.raises(po.OrchestrationError):
        po.create_run("documentary_montage", "AI chips", lane="tech_ai")
    with pytest.raises(po.OrchestrationError):
        po.get_pipeline("hologram_factory")


def test_provider_selection_prefers_free_and_feasible():
    out = po.select_provider([
        {"name": "paid-cloud", "estimated_cost_usd": 2.50, "quality": 1.0,
         "fleet_feasible": False},
        {"name": "edge-tts", "estimated_cost_usd": 0.0, "quality": 0.7,
         "fleet_feasible": True},
        {"name": "gpu-local", "estimated_cost_usd": 0.0, "quality": 1.0,
         "fleet_feasible": False, "requires_gpu": True},
    ])
    assert out["selected"] == "edge-tts"
    by_name = {s["name"]: s for s in out["scored"]}
    assert by_name["paid-cloud"]["eligible"] is False
    assert by_name["gpu-local"]["eligible"] is False


def test_provider_selection_fails_honestly_when_none_eligible():
    with pytest.raises(po.OrchestrationError):
        po.select_provider([
            {"name": "paid-only", "estimated_cost_usd": 1.0, "quality": 1.0},
        ])


def test_storyboard_approval_gate_blocks_production():
    run = po.create_run("clip_factory", "Apollo", lane="history")
    run = po.advance_run(run)  # research
    run = po.advance_run(run)  # script
    assert run["current_stage"] == "storyboard"
    with pytest.raises(po.OrchestrationError):
        po.advance_run(run)  # no approval
    run = po.advance_run(run, approved=True)
    assert run["current_stage"] == "assets"


def test_quality_gate_enforces_shorts_cap_captions_provenance():
    bad = po.evaluate_quality_gate(
        {"kind": "video", "duration_seconds": 75, "has_captions": False,
         "provenance": []},
        pipeline="explainer_short")
    assert bad["passed"] is False
    good = po.evaluate_quality_gate(
        {"kind": "video", "duration_seconds": 45, "has_captions": True,
         "provenance": [{"catalog_id": "L1-001"}]},
        pipeline="explainer_short")
    assert good["passed"] is True


def test_quality_gate_screens_scripts_for_finance_advice():
    gate = po.evaluate_quality_gate(
        {"kind": "script",
         "text": "You should invest now for guaranteed returns."},
        pipeline="tech_explainer")
    assert gate["passed"] is False
    assert gate["checks"]["no_finance_advice"] is False


def test_full_run_completes_through_quality_gate():
    run = po.create_run("explainer_short", "Nebula", lane="space_science")
    for _ in range(6):  # research..compose (storyboard needs approval)
        if run["current_stage"] == "storyboard":
            run = po.advance_run(run, approved=True)
        else:
            run = po.advance_run(run)
    assert run["current_stage"] == "quality"
    artifact = {"kind": "video", "duration_seconds": 40,
                "has_captions": True, "provenance": [{"x": 1}]}
    run = po.advance_run(run, artifact=artifact)
    run = po.advance_run(run)  # approval stage (post-render sign-off record)
    run = po.advance_run(run)  # publish_plan
    assert run["current_stage"] == "complete"
    assert run["publish"] is False
