"""TASK-REL-007D regression tests: fleet-status latency + peer-call bounds.

Round 1 (2026-11-14) production evidence: the agent-status fast path
took 30-35s and the console showed a red "API offline" indicator
throughout. Code-level causes pinned here:

* every status caller force-refreshed, bypassing the 4s probe cache;
* status tools built a NEW FleetClient per call (cold cache, new pool);
* the 9-probe gather had no overall deadline;
* ``safe_peer_call`` awaited peers with no timeout of its own;
* sync Memora urllib calls ran on the event loop (fixed in server.py by
  ``asyncio.to_thread`` wraps at the recall/record sites).

(Hardware context, not code: Server 1 is ~956MB under swap pressure —
these fixes remove the avoidable software stacks, not the physics.)
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import pytest

from friday.core.resilience import safe_peer_call
from friday.ecosystem import fleet_client as fc_module
from friday.ecosystem.fleet_client import AgentStatus, FleetClient, get_shared_fleet_client


def _status(agent_id: str) -> AgentStatus:
    return AgentStatus(
        id=agent_id, name=agent_id, role="r", icon="x", status="ONLINE",
        latency_ms=5, endpoint="http://x", details="ok",
        last_checked=datetime.now(timezone.utc).isoformat(),
    )


def _client_with_counting_probes(calls: list[str], slow: str | None = None) -> FleetClient:
    client = FleetClient()
    # Probes are stubbed below and never touch the HTTP client; stubbing the
    # factory also keeps the test hermetic (real httpx client construction
    # reads proxy env vars, which are malformed in some dev environments).
    client.get_shared_client = lambda: object()  # type: ignore[method-assign]

    def make(aid: str):
        async def _probe(_client):
            calls.append(aid)
            if slow == aid:
                await asyncio.sleep(30)
            return _status(aid)
        return _probe

    for aid in ("inference", "memora", "stratex", "intelx", "futuris",
                "cortex", "forge", "sentinel", "vyralx"):
        setattr(client, f"probe_{aid}", make(aid))
    return client


# --------------------------------------------------------------------- cache


def test_status_sweep_is_cached_and_summary_reuses_it():
    calls: list[str] = []
    client = _client_with_counting_probes(calls)

    async def _run():
        first = await client.get_all_statuses()
        second = await client.get_all_statuses()
        summary = await client.get_fleet_summary()
        return first, second, summary

    first, second, summary = asyncio.run(_run())
    assert len(first) == len(second) == 9
    assert len(calls) == 9, f"cache bypassed: probes ran {len(calls)} times"
    assert "9/9 AGENTS ACTIVE" in str(summary.get("reply") or "")


# ------------------------------------------------------------------ deadline


def test_slow_probe_hits_deadline_instead_of_stalling_the_matrix(monkeypatch):
    monkeypatch.setattr(fc_module, "FLEET_PROBE_DEADLINE_SECONDS", 0.5)
    calls: list[str] = []
    client = _client_with_counting_probes(calls, slow="stratex")

    async def _run():
        start = time.monotonic()
        statuses = await client.get_all_statuses()
        return statuses, time.monotonic() - start

    statuses, elapsed = asyncio.run(_run())
    assert elapsed < 5, f"probe sweep not deadline-bounded (took {elapsed:.1f}s)"
    assert len(statuses) == 9
    slow = next(s for s in statuses if s.id == "stratex")
    assert slow.status == "UNREACHABLE"
    assert "deadline" in slow.details
    assert all(s.status == "ONLINE" for s in statuses if s.id != "stratex")


# --------------------------------------------------------------- shared client


def test_tools_share_one_fleet_client():
    shared = get_shared_fleet_client()
    assert get_shared_fleet_client() is shared

    from friday.tools.builtin.fleet_status import FleetStatusTool
    from friday.tools.builtin.forge_code_task import ForgeCodeTool
    from friday.tools.builtin.futuris_forecast import FuturisForecastTool
    from friday.tools.builtin.intelx_research import IntelXResearchTool

    assert FleetStatusTool()._client() is shared
    assert ForgeCodeTool()._client() is shared
    assert FuturisForecastTool()._client() is shared
    assert IntelXResearchTool()._client() is shared


# -------------------------------------------------------------- safe_peer_call


def test_safe_peer_call_times_out_to_fallback():
    async def _hang():
        await asyncio.sleep(30)
        return {"reply": "never"}

    async def _run():
        start = time.monotonic()
        out = await safe_peer_call(_hang(), fallback_data={"reply": "fallback"}, peer_name="forge", timeout=0.3)
        return out, time.monotonic() - start

    out, elapsed = asyncio.run(_run())
    assert out == {"reply": "fallback"}
    assert elapsed < 5


def test_safe_peer_call_passes_through_fast_results_and_errors():
    async def _fast():
        return {"reply": "real"}

    async def _bad():
        raise ConnectionError("down")

    async def _run():
        ok = await safe_peer_call(_fast(), fallback_data={"reply": "fb"}, peer_name="x", timeout=2)
        bad = await safe_peer_call(_bad(), fallback_data={"reply": "fb"}, peer_name="x", timeout=2)
        return ok, bad

    ok, bad = asyncio.run(_run())
    assert ok == {"reply": "real"}
    assert bad == {"reply": "fb"}
