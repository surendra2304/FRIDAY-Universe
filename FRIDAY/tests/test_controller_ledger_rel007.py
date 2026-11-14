"""TASK-REL-007C follow-up: autonomous-controller delegations reach the ledger.

Live evidence (2026-11-14, after PR #127 deployed): "ask forge what you
are working on" was answered by Forge through the autonomous
controller's mesh path — and the unified task ledger did NOT move
(total_records stayed 1). The controller was a fourth dispatch surface
(FleetDispatchTool, specialist tools and the server direct path were
covered by PR #127) that dispatched real peer work without recording.

These tests pin the controller's recording: a verified mesh completion
lands as a completed record under the mesh task id; an unverified
outcome lands as failed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent.parent
_CORE_SRC = _REPO / "FRIDAY" / "apps" / "core" / "src"
if str(_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_SRC))

import friday_core.task_records as tr_module
from friday_core.task_records import TaskRecordStore

from friday.autonomous import controller as controller_module


@pytest.fixture()
def fresh_store(monkeypatch):
    store = TaskRecordStore()
    monkeypatch.setattr(tr_module, "get_shared_task_records", lambda: store)
    return store


def _mesh(monkeypatch, controller, behaviour=None):
    from friday.cognition.mesh import HarnessBehaviour, Mesh, build_contracts

    contracts = build_contracts(controller_module.fleet_client)
    mesh, transport = Mesh.in_process(contracts, attempts=1, backoff_seconds=0.0)
    if behaviour is not None:
        transport.behave("forge", behaviour)
    monkeypatch.setattr(controller, "_peer_mesh", mesh, raising=False)
    return transport


@pytest.mark.asyncio
async def test_verified_mesh_completion_is_recorded(fresh_store, monkeypatch):
    from friday.cognition.mesh import HarnessBehaviour

    controller = controller_module.AutonomousController()
    _mesh(monkeypatch, controller, HarnessBehaviour(receipt=True))

    result = await controller.execute_agent_control("forge", "report your status")
    assert result["metadata"]["task_completion_verified"] is True

    recs = fresh_store.list()
    assert len(recs) == 1, f"expected the controller delegation in the ledger, got {recs}"
    assert recs[0].owner_agent == "forge"
    assert recs[0].status == "completed"
    assert recs[0].task_id == result["metadata"]["task_id"]


@pytest.mark.asyncio
async def test_unverified_mesh_outcome_is_recorded_as_failed(fresh_store, monkeypatch):
    from friday.cognition.mesh import HarnessBehaviour

    controller = controller_module.AutonomousController()
    _mesh(monkeypatch, controller, HarnessBehaviour(receipt=False))

    result = await controller.execute_agent_control("forge", "report your status")
    assert result["metadata"]["task_completion_verified"] is False

    recs = fresh_store.list()
    assert len(recs) == 1
    assert recs[0].owner_agent == "forge"
    assert recs[0].status == "failed"
