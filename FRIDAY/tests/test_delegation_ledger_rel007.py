"""TASK-REL-007C regression tests: real delegations reach the unified ledger.

Round 1 (2026-11-14) production evidence: across research, forecast,
coding and status asks, the console's TASKS DELEGATED counter stayed 0 —
and a live-verified successful Forge build (task14714112026084837) never
entered the TaskRecordStore that ``GET /api/tasks/timeline`` (and hence
the counter) reads. Only FleetDispatchTool recorded; the specialist
tools (IntelX research, Futuris forecast, Forge code) and the server's
direct-agent path dispatched through FleetClient without recording.

These tests pin the fix: every specialist dispatch — success or failure —
writes a ledger record through ``record_specialist_dispatch``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parent.parent.parent
_CORE_SRC = _REPO / "FRIDAY" / "apps" / "core" / "src"
if str(_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_SRC))

import friday_core.task_records as tr_module
from friday_core.task_records import TaskRecordStore


@pytest.fixture()
def fresh_store(monkeypatch):
    store = TaskRecordStore()
    monkeypatch.setattr(tr_module, "get_shared_task_records", lambda: store)
    return store


def _records(store: TaskRecordStore) -> list:
    return store.list()


class _FakeResult:
    def __init__(self, status: str, result: dict[str, Any] | None = None,
                 error: str | None = None, summary: str = "", task_id: str = "task_fake1"):
        self.status = status
        self.result = result or {}
        self.error = error
        self.summary = summary
        self.task_id = task_id
        self.execution_time_ms = 1200


class _FakeFleetClient:
    def __init__(self, result):
        self._result = result

    async def dispatch_task(self, envelope):
        return self._result


class _BrokenFleetClient:
    async def dispatch_task(self, envelope):
        raise ConnectionError("peer unreachable")


# --------------------------------------------------------------------- Forge


def test_forge_success_is_recorded(fresh_store):
    from friday.tools.builtin.forge_code_task import ForgeCodeTool

    ok = _FakeResult("SUCCESS", result={
        "summary": "Built it.",
        "verification_manifest": {"stages": [{"status": "passed"}, {"status": "passed"}]},
    }, summary="Built it with 2/2 stages passed.", task_id="task_forge_ok")
    tool = ForgeCodeTool(fleet_client=_FakeFleetClient(ok))
    res = tool.execute(goal="write a palindrome checker")
    assert not res.is_error
    recs = [r for r in _records(fresh_store) if r.task_id == "task_forge_ok"]
    assert len(recs) == 1, f"expected the Forge dispatch in the ledger, got {_records(fresh_store)}"
    assert recs[0].owner_agent == "forge"
    assert recs[0].status == "completed"


def test_forge_unreachable_is_recorded_as_failure(fresh_store):
    from friday.tools.builtin.forge_code_task import ForgeCodeTool

    tool = ForgeCodeTool(fleet_client=_BrokenFleetClient())
    res = tool.execute(goal="write anything")
    assert res.is_error
    recs = _records(fresh_store)
    assert len(recs) == 1
    assert recs[0].owner_agent == "forge"
    assert recs[0].status == "failed"
    assert recs[0].task_id.startswith("task_"), "a missing upstream id must be synthesized"


# -------------------------------------------------------------------- IntelX


def test_intelx_success_is_recorded(fresh_store):
    from friday.tools.builtin.intelx_research import IntelXResearchTool

    ok = _FakeResult("success", result={
        "query": "semiconductor exports",
        "text_response": "Findings.",
        "citations_count": 3,
        "sources": [],
    }, task_id="task_intelx_ok")
    tool = IntelXResearchTool(fleet_client=_FakeFleetClient(ok))
    res = tool.execute(query="semiconductor exports")
    assert not res.is_error
    recs = [r for r in _records(fresh_store) if r.task_id == "task_intelx_ok"]
    assert len(recs) == 1
    assert recs[0].owner_agent == "intelx"
    assert recs[0].status == "completed"


def test_intelx_failure_status_is_recorded(fresh_store):
    from friday.tools.builtin.intelx_research import IntelXResearchTool

    bad = _FakeResult("failed", error="HTTP 502", task_id="task_intelx_bad")
    tool = IntelXResearchTool(fleet_client=_FakeFleetClient(bad))
    res = tool.execute(query="anything")
    assert res.is_error
    recs = [r for r in _records(fresh_store) if r.task_id == "task_intelx_bad"]
    assert len(recs) == 1
    assert recs[0].status == "failed"


# ------------------------------------------------------------------- Futuris


class _FakeFuturisClient:
    def __init__(self, reply: str):
        self._reply = reply

    async def request_futuris_forecast(self, target: str = "", horizon: str = ""):
        return {"reply": self._reply, "metadata": {}}


def test_futuris_success_is_recorded_with_synthesized_id(fresh_store):
    from friday.tools.builtin.futuris_forecast import FuturisForecastTool

    tool = FuturisForecastTool(fleet_client=_FakeFuturisClient("Rain likely tomorrow."))
    res = tool.execute(question="will it rain tomorrow", target="weather", horizon="1d")
    assert not res.is_error
    recs = _records(fresh_store)
    assert len(recs) == 1, "Futuris gives no task id — the delegation must still be counted"
    assert recs[0].owner_agent == "futuris"
    assert recs[0].status == "completed"
    assert recs[0].task_id.startswith("task_")


def test_futuris_empty_reply_is_recorded_as_failure(fresh_store):
    from friday.tools.builtin.futuris_forecast import FuturisForecastTool

    tool = FuturisForecastTool(fleet_client=_FakeFuturisClient(""))
    res = tool.execute(question="will it rain tomorrow", target="weather", horizon="1d")
    assert res.is_error
    recs = _records(fresh_store)
    assert len(recs) == 1
    assert recs[0].status == "failed"


# ------------------------------------------------------- counter (timeline)


def test_timeline_total_reflects_specialist_dispatches(fresh_store):
    """The console counter reads total_records — after one dispatch of
    each kind it must read 3, not 0."""
    from friday.tools.builtin.forge_code_task import ForgeCodeTool
    from friday.tools.builtin.futuris_forecast import FuturisForecastTool
    from friday.tools.builtin.intelx_research import IntelXResearchTool

    ForgeCodeTool(fleet_client=_FakeFleetClient(_FakeResult(
        "SUCCESS",
        result={"summary": "s", "verification_manifest": {"stages": [{"status": "passed"}]}},
        task_id="task_tl_forge",
    ))).execute(goal="build x")
    IntelXResearchTool(fleet_client=_FakeFleetClient(_FakeResult(
        "success", result={"query": "q", "text_response": "t"}, task_id="task_tl_intelx",
    ))).execute(query="q")
    FuturisForecastTool(fleet_client=_FakeFuturisClient("ok")).execute(
        question="q", target="t", horizon="1d")

    assert len(_records(fresh_store)) == 3
