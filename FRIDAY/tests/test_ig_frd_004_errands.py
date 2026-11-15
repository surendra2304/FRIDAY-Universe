"""TASK-IG-FRD-004 — delegated-errand framework gate tests.

The point of this suite is the gates: nothing external executes without
approval, the budget ledger refuses over-cap approvals, execution is
dry-run and says so, and live channels cannot be registered.
"""

from __future__ import annotations

import pytest

from friday.autonomous.errands import (
    STATE_APPROVED,
    STATE_AWAITING,
    STATE_DONE,
    STATE_REJECTED,
    ChannelRegistry,
    DryRunChannel,
    ErrandEngine,
    ErrandError,
    ErrandStore,
)


def _engine(tmp_path, **kw):
    return ErrandEngine(store=ErrandStore(path=str(tmp_path / "errands.json")), **kw)


def _errand(engine, cap=0.0):
    return engine.create_errand(
        "Book a cab and email the receipt",
        [
            {"kind": "external", "channel": "purchase", "description": "Book cab", "estimated_cost": 500},
            {"kind": "external", "channel": "email", "description": "Email receipt", "estimated_cost": 0},
            {"kind": "internal", "description": "Summarise trip"},
        ],
        budget_cap=cap,
    )


def test_external_steps_start_awaiting_internal_approved(tmp_path):
    errand = _errand(_engine(tmp_path))
    states = {s["id"]: s["state"] for s in errand["steps"]}
    assert states["s1"] == STATE_AWAITING
    assert states["s2"] == STATE_AWAITING
    assert states["s3"] == STATE_APPROVED  # internal: no outside-world effect
    assert errand["framework_only"] is True


def test_run_before_approval_executes_nothing(tmp_path):
    engine = _engine(tmp_path, )
    errand = _errand(engine)
    with pytest.raises(ErrandError):
        engine.run(errand["id"])
    after = engine.store.get(errand["id"])
    assert all(s["result"] is None for s in after["steps"])
    assert engine.channels.get("dry_run").calls == []


def test_zero_cap_blocks_costed_approval(tmp_path):
    engine = _engine(tmp_path)
    errand = _errand(engine, cap=0.0)
    with pytest.raises(ErrandError):
        engine.approve_step(errand["id"], "s1")  # costs 500, cap 0
    # A free step can be approved under a zero cap.
    engine.approve_step(errand["id"], "s2")
    assert engine.store.get(errand["id"])["steps"][1]["state"] == STATE_APPROVED


def test_budget_ledger_refuses_overcommit(tmp_path):
    engine = _engine(tmp_path)
    errand = engine.create_errand(
        "Two purchases",
        [
            {"kind": "external", "channel": "purchase", "description": "A", "estimated_cost": 300},
            {"kind": "external", "channel": "purchase", "description": "B", "estimated_cost": 300},
        ],
        budget_cap=500,
    )
    engine.approve_step(errand["id"], "s1")
    with pytest.raises(ErrandError):
        engine.approve_step(errand["id"], "s2")  # 300 + 300 > 500


def test_full_flow_is_dry_run_and_labelled(tmp_path):
    engine = _engine(tmp_path)
    errand = _errand(engine, cap=1000)
    engine.approve_step(errand["id"], "s1")
    engine.approve_step(errand["id"], "s2")
    done = engine.run(errand["id"])
    assert done["status"] == "complete"
    for step in done["steps"]:
        assert step["state"] == STATE_DONE
        assert step["result"]["executed"] is False
        assert step["result"]["dry_run"] is True
    assert len(engine.channels.get("dry_run").calls) == 2  # external steps only
    summary = engine.summarise(errand["id"])
    assert "FRAMEWORK ONLY" in summary
    assert "no real-world action was taken" in summary


def test_rejected_step_is_skipped(tmp_path):
    engine = _engine(tmp_path)
    errand = _errand(engine, cap=1000)
    engine.reject_step(errand["id"], "s1")
    engine.approve_step(errand["id"], "s2")
    done = engine.run(errand["id"])
    assert done["steps"][0]["state"] == STATE_REJECTED
    assert done["status"] == "complete"


def test_live_channel_registration_refused(tmp_path):
    registry = ChannelRegistry()

    class FakeLiveChannel:
        def execute(self, step):  # pragma: no cover - must never run
            return {"executed": True}

    with pytest.raises(ErrandError):
        registry.register("phone", FakeLiveChannel())
    registry.register("echo", DryRunChannel())  # dry-run is fine
    with pytest.raises(ErrandError):
        registry.get("phone")


def test_persistence_round_trip(tmp_path):
    path = str(tmp_path / "errands.json")
    engine = ErrandEngine(store=ErrandStore(path=path))
    errand = _errand(engine, cap=100)
    engine2 = ErrandEngine(store=ErrandStore(path=path))
    loaded = engine2.store.get(errand["id"])
    assert loaded is not None
    assert loaded["budget_cap"] == 100
    assert loaded["steps"][0]["state"] == STATE_AWAITING


def test_validation_errors(tmp_path):
    engine = _engine(tmp_path)
    with pytest.raises(ErrandError):
        engine.create_errand("x", [{"kind": "external", "description": "no channel"}])
    with pytest.raises(ErrandError):
        engine.create_errand("x", [{"kind": "sideways", "description": "?"}])
    with pytest.raises(ErrandError):
        engine.create_errand("x", [], budget_cap=-1)
    with pytest.raises(ErrandError):
        engine.approve_step("errand-nope", "s1")
