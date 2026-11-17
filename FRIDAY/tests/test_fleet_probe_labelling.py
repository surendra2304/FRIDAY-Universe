"""WEB FLEET-PANEL FIX regression tests: probe failure labelling honesty.

Production evidence (2026-11-17, probe verdict: the website fleet panel
showed IntelX + Futuris UNREACHABLE while both peers answered healthy via
direct routes seconds later): FRIDAY's in-process probes time out under
swap-stall latency on the 956MB host, and EVERY probe exception used to be
labelled UNREACHABLE with an empty reason (httpx timeout exceptions have
an empty str()). The panel therefore reported dead peers that were alive.

Pinned behaviour:
* timeout-class probe failures -> DEGRADED, details carry "probe timed
  out" plus the exception type (via _error_text);
* connect-level failures (httpx ConnectError / ConnectTimeout) ->
  UNREACHABLE, preserved — nothing accepted a connection at all;
* probe_futuris answers DEGRADED when /health returns 200 with
  {"status": "degraded"}, like every other probe (it returned
  UNREACHABLE);
* the Futuris cloud probe budget is 8s, matching peers (was 5s, the
  tightest in the fleet).

The get_all_statuses sweep-deadline synthesis stays UNREACHABLE and is
pinned separately by test_fleet_latency_rel007.py.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx

from friday.ecosystem.fleet_client import FleetClient, _probe_failure


def _fleet() -> FleetClient:
    fleet = FleetClient(
        settings=SimpleNamespace(
            intelx_url="http://intelx:8000",
            intelx_api_key="unit-test-key",
            memora_url="http://memora:8000",
            memora_api_key="unit-test-key",
            futuris_url="http://futuris:8000",
            futuris_api_key="unit-test-key",
            vyralx_url="http://vyralx:8000",
            vyralx_api_key="unit-test-key",
        )
    )
    # The local Futuris attempt is env-driven; keep the cloud path alone
    # under test regardless of the ambient environment.
    fleet.futuris_local_url = ""
    return fleet


def _raising_client(exc: BaseException) -> httpx.AsyncClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise exc

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------- the helper


def test_helper_timeout_class_is_degraded_with_type():
    status, reason = _probe_failure(httpx.ReadTimeout(""))
    assert status == "DEGRADED"
    assert "probe timed out" in reason
    assert "ReadTimeout" in reason

    status, reason = _probe_failure(httpx.PoolTimeout(""))
    assert status == "DEGRADED"
    assert "probe timed out" in reason
    assert "PoolTimeout" in reason


def test_helper_connect_level_is_unreachable():
    status, reason = _probe_failure(httpx.ConnectError("[Errno 111] Connection refused"))
    assert status == "UNREACHABLE"
    assert "ConnectError" in reason

    # httpx 0.28: ConnectTimeout subclasses TimeoutException, NOT
    # ConnectError — it must still classify as connect-level.
    status, reason = _probe_failure(httpx.ConnectTimeout(""))
    assert status == "UNREACHABLE"
    assert "ConnectTimeout" in reason


def test_helper_other_exceptions_are_degraded_not_unreachable():
    status, reason = _probe_failure(RuntimeError("boom"))
    assert status == "DEGRADED"
    assert "RuntimeError" in reason
    assert "boom" in reason


# ------------------------------------------------------- probe-level: intelx


def test_intelx_read_timeout_is_degraded_with_reason():
    async def _go():
        client = _raising_client(httpx.ReadTimeout("", request=httpx.Request("GET", "http://intelx:8000")))
        try:
            return await _fleet().probe_intelx(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "DEGRADED"
    assert "probe timed out" in status.details
    assert "ReadTimeout" in status.details


def test_intelx_connect_refused_stays_unreachable():
    async def _go():
        client = _raising_client(
            httpx.ConnectError("[Errno 111] Connection refused", request=httpx.Request("GET", "http://intelx:8000"))
        )
        try:
            return await _fleet().probe_intelx(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "UNREACHABLE"
    assert "ConnectError" in status.details


# ------------------------------------------------------- probe-level: memora


def test_memora_read_timeout_is_degraded_with_reason():
    async def _go():
        client = _raising_client(httpx.ReadTimeout("", request=httpx.Request("GET", "http://memora:8000")))
        try:
            return await _fleet().probe_memora(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "DEGRADED"
    assert "probe timed out" in status.details
    assert "ReadTimeout" in status.details


# ------------------------------------------------------ probe-level: futuris


def test_futuris_read_timeout_is_degraded_with_reason():
    async def _go():
        client = _raising_client(httpx.ReadTimeout("", request=httpx.Request("GET", "http://futuris:8000")))
        try:
            return await _fleet().probe_futuris(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "DEGRADED"
    assert "probe timed out" in status.details
    assert "ReadTimeout" in status.details


def test_futuris_connect_refused_stays_unreachable():
    async def _go():
        client = _raising_client(
            httpx.ConnectError("[Errno 111] Connection refused", request=httpx.Request("GET", "http://futuris:8000"))
        )
        try:
            return await _fleet().probe_futuris(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "UNREACHABLE"
    assert "ConnectError" in status.details


def test_futuris_degraded_health_body_is_degraded_not_unreachable():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "degraded"}, request=request)

    async def _go():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await _fleet().probe_futuris(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "DEGRADED"
    assert "200" in status.details


def test_futuris_cloud_probe_budget_is_8s_like_peers():
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["timeout"] = request.extensions.get("timeout") or {}
        return httpx.Response(200, json={"status": "ok"}, request=request)

    async def _go():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await _fleet().probe_futuris(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "ONLINE"
    assert captured["timeout"].get("read") == 8.0


# ------------------------------------------------------- probe-level: vyralx


def test_vyralx_read_timeout_is_degraded_with_reason():
    async def _go():
        client = _raising_client(httpx.ReadTimeout("", request=httpx.Request("GET", "http://vyralx:8000")))
        try:
            return await _fleet().probe_vyralx(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "DEGRADED"
    assert "probe timed out" in status.details
    assert "ReadTimeout" in status.details


def test_vyralx_connect_refused_stays_unreachable():
    async def _go():
        client = _raising_client(
            httpx.ConnectError("[Errno 111] Connection refused", request=httpx.Request("GET", "http://vyralx:8000"))
        )
        try:
            return await _fleet().probe_vyralx(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "UNREACHABLE"
    assert "ConnectError" in status.details
