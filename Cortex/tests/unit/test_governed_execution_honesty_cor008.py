"""TASK-COR-008 — governed execution must not claim a real execution it never made.

``GovernedOperationsEngine.execute()`` used to ignore the ``tool_bus`` it was
handed entirely, mutate only the in-memory ``state_snapshot`` dict of the
registered property (for 3 of the action types; for the rest it mutated
nothing at all), and still return ``status="EXECUTED"``,
``classification="REAL_EXECUTION"`` and ``side_effects_applied: 1``. A tool
failure on the governed path was structurally invisible, and an in-memory
bookkeeping update was labelled as a real-world execution.

The engine has no effector that reaches a real property (the only
same-named tool on the orchestrator's bus, ``banner_injection``, is a stub
lambda returning a canned dict; every other governed action is not
registered on the bus at all, and ``ToolBus.execute`` is async while the
engine is sync). The honest fix is reclassification: every record is a
SIMULATED_EXECUTION with zero external side effects, and the local snapshot
bookkeeping is reported for what it is via ``state_snapshot_updated``.

These tests pin that contract: whatever bus is passed — exploding,
recording, or None — the record must never say EXECUTED / REAL_EXECUTION,
and ``side_effects_applied`` must be 0.
"""

from __future__ import annotations

import copy

import pytest

from cortex_core.governed_operations import GovernedOperationsEngine
from cortex_core.web_property import PropertyRegistry


class ExplodingBus:
    """A tool_bus that raises on any attribute access or call."""

    def __getattr__(self, name):
        raise RuntimeError(f"tool bus exploded on access to {name!r}")

    def __call__(self, *args, **kwargs):
        raise RuntimeError("tool bus exploded on call")


class RecordingBus:
    """A tool_bus double that records every attempted use."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name):
        def _record(*args, **kwargs):
            self.calls.append(name)
            return {"status": "executed"}

        return _record


def _approved_engine(
    action: str, params: dict, property_id: str = "site_storefront"
) -> tuple[GovernedOperationsEngine, PropertyRegistry, str]:
    """Drive observe -> recommend -> authorize on a fresh, isolated registry."""
    registry = PropertyRegistry()
    engine = GovernedOperationsEngine(property_registry=registry)
    obs = engine.observe(property_id, {"source": "test", "timestamp": "2999-01-01T00:00:00Z"})
    rec = engine.recommend(
        observation=obs,
        proposed_action=action,
        params=params,
        rationale="TASK-COR-008 regression test",
        confidence=0.9,
        expected_outcomes={"conversion_lift_pct": 5.0},
    )
    appr = engine.authorize(rec.recommendation_id, approver_id="operator_test")
    return engine, registry, appr.approval_id


def _assert_honest_record(exec_rec) -> None:
    assert exec_rec.status == "SIMULATED"
    assert exec_rec.classification == "SIMULATED_EXECUTION"
    assert exec_rec.status != "EXECUTED"
    assert exec_rec.classification != "REAL_EXECUTION"
    assert exec_rec.result["status"] == "simulated"
    assert exec_rec.result["side_effects_applied"] == 0
    assert exec_rec.result["external_side_effects_applied"] == 0
    assert exec_rec.result["tool_bus_invoked"] is False
    assert exec_rec.result["execution_environment"] == "in_memory_property_snapshot"


def test_exploding_bus_yields_honestly_simulated_record():
    engine, _registry, approval_id = _approved_engine("banner_injection", {"variant": "honesty_v1"})
    exec_rec = engine.execute(approval_id, "idemp_cor008_exploding", tool_bus=ExplodingBus())
    _assert_honest_record(exec_rec)


def test_recording_bus_is_never_called():
    engine, _registry, approval_id = _approved_engine("banner_injection", {"variant": "honesty_v1"})
    bus = RecordingBus()
    exec_rec = engine.execute(approval_id, "idemp_cor008_recording", tool_bus=bus)
    _assert_honest_record(exec_rec)
    assert bus.calls == []


def test_no_bus_at_all_is_fine():
    engine, _registry, approval_id = _approved_engine("banner_injection", {"variant": "honesty_v1"})
    exec_rec = engine.execute(approval_id, "idemp_cor008_none", tool_bus=None)
    _assert_honest_record(exec_rec)


def test_snapshot_bookkeeping_still_works_and_is_reported_as_local():
    engine, registry, approval_id = _approved_engine("banner_injection", {"variant": "honesty_v1"})
    before = copy.deepcopy(registry.get("site_storefront").state_snapshot)
    exec_rec = engine.execute(approval_id, "idemp_cor008_snapshot", tool_bus=RecordingBus())
    _assert_honest_record(exec_rec)
    # The local bookkeeping really happens — and is labelled as local.
    # (The seeded snapshot starts with active_banner="default_welcome".)
    assert exec_rec.result["state_snapshot_updated"] is True
    assert before.get("active_banner") != "honesty_v1"
    assert registry.get("site_storefront").state_snapshot["active_banner"] == "honesty_v1"
    assert exec_rec.snapshot_before == before


def test_config_update_marks_snapshot_updated():
    engine, registry, approval_id = _approved_engine("config_update", {"config": {"theme": "dark"}})
    exec_rec = engine.execute(approval_id, "idemp_cor008_config", tool_bus=ExplodingBus())
    _assert_honest_record(exec_rec)
    assert exec_rec.result["state_snapshot_updated"] is True
    assert registry.get("site_storefront").state_snapshot["theme"] == "dark"


def test_action_without_snapshot_branch_reports_no_update():
    # cache_flush has no snapshot-mutation branch: pre-fix it still claimed
    # side_effects_applied == 1 and REAL_EXECUTION while changing nothing.
    engine, registry, approval_id = _approved_engine("cache_flush", {"cache_tier": "static_assets"})
    before = copy.deepcopy(registry.get("site_storefront").state_snapshot)
    exec_rec = engine.execute(approval_id, "idemp_cor008_cache", tool_bus=RecordingBus())
    _assert_honest_record(exec_rec)
    assert exec_rec.result["state_snapshot_updated"] is False
    assert registry.get("site_storefront").state_snapshot == before


def test_dry_run_remains_simulated_and_touches_nothing():
    engine, registry, approval_id = _approved_engine("banner_injection", {"variant": "honesty_v1"})
    before = copy.deepcopy(registry.get("site_storefront").state_snapshot)
    exec_rec = engine.execute(approval_id, "idemp_cor008_dry", tool_bus=ExplodingBus(), dry_run=True)
    assert exec_rec.dry_run is True
    _assert_honest_record(exec_rec)
    assert exec_rec.result["state_snapshot_updated"] is False
    assert registry.get("site_storefront").state_snapshot == before


def test_every_governed_action_is_honest():
    # Sweep the action types the router can send, incl. ones with no
    # snapshot branch and no registered bus tool at all. A dedicated
    # property is registered because the seeded properties do not all
    # allow every action (e.g. deployment_traffic_switch).
    from cortex_core.web_property import WebProperty

    actions = ("banner_injection", "config_update", "deployment_traffic_switch", "cache_flush", "email_dispatch")
    for action in actions:
        registry = PropertyRegistry()
        registry.register(
            WebProperty(
                property_id="cor008_site",
                name="COR-008 Test Property",
                allowed_domains=["example.com"],
                allowed_operations=list(actions),
                target_environment="staging",
                state_snapshot={},
            )
        )
        engine = GovernedOperationsEngine(property_registry=registry)
        obs = engine.observe("cor008_site", {"source": "test", "timestamp": "2999-01-01T00:00:00Z"})
        rec = engine.recommend(
            observation=obs,
            proposed_action=action,
            params={"variant": "v", "config": {}, "traffic_split_pct": 50},
            rationale="TASK-COR-008 regression test",
            confidence=0.9,
            expected_outcomes={"conversion_lift_pct": 5.0},
        )
        appr = engine.authorize(rec.recommendation_id, approver_id="operator_test")
        exec_rec = engine.execute(appr.approval_id, f"idemp_cor008_{action}", tool_bus=ExplodingBus())
        _assert_honest_record(exec_rec)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
