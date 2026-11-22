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

from friday.ecosystem.fleet_client import FleetClient, _classify_health_response, _probe_failure


def _fleet() -> FleetClient:
    fleet = FleetClient(
        settings=SimpleNamespace(
            intelx_url="http://intelx:8000",
            intelx_api_key="unit-test-key",
            memora_url="http://memora:8000",
            memora_api_key="unit-test-key",
            stratex_url="http://stratex:8000",
            stratex_api_key="unit-test-key",
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
    # TASK-REL-067: the details now name the peer verdict, not the code.
    assert "peer reports status=degraded" in status.details


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
    # TASK-REL-067 (REL-004 section 4.2): a pre-contract {"status": "ok"}
    # body is REACHABLE, never ONLINE — ONLINE is earned only by a contract
    # body with all required capabilities ok.
    assert status.status == "REACHABLE"
    assert "capability unknown" in status.details
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


# ------------------------------------------------- REL-067: REL-004 section 4
# The classifier reads the section 2.2 contract fields first: a peer that
# sends a `capabilities` block is judged on its capability states; a peer
# with no capabilities block is reachability-only and never ONLINE.


def _contract_body(status="ok", **capabilities):
    return {
        "status": status,
        "service": "stratex",
        "evidence_class": "capability_report",
        "capabilities": {
            name: {
                "state": state,
                "evidence": "test",
                "checked_at": "2026-11-22T00:00:00Z",
                **({"detail": detail} if detail else {}),
            }
            for name, (state, detail) in capabilities.items()
        },
    }


def _response(status_code, body):
    request = httpx.Request("GET", "http://stratex:8000/health")
    return httpx.Response(status_code, json=body, request=request)


def test_classifier_contract_ok_body_is_online():
    status, note = _classify_health_response(
        _response(200, _contract_body(trading_engine=("ok", ""), market_data=("ok", "")))
    )
    assert status == "ONLINE"
    assert note == "capabilities ok"


def test_classifier_contract_503_degraded_names_failing_capability():
    status, note = _classify_health_response(
        _response(
            503,
            _contract_body(
                "degraded",
                trading_engine=("unavailable", "STALE_STRATEGY_EVALUATION"),
                market_data=("ok", ""),
            ),
        )
    )
    assert status == "DEGRADED"
    assert note == "trading_engine unavailable (STALE_STRATEGY_EVALUATION)"


def test_classifier_contract_degraded_body_over_200():
    # A peer that reports degraded in the body but still answers 200 is
    # DEGRADED: the body is the contract, the code has not migrated yet.
    status, note = _classify_health_response(
        _response(200, _contract_body("degraded", trading_engine=("degraded", "HEARTBEAT_FILE_MISSING")))
    )
    assert status == "DEGRADED"
    assert note == "trading_engine degraded (HEARTBEAT_FILE_MISSING)"


def test_classifier_precontract_ok_body_is_reachable_never_online():
    status, note = _classify_health_response(_response(200, {"status": "ok"}))
    assert status == "REACHABLE"
    assert note == "capability unknown — pre-contract /health"


def test_classifier_unknown_capability_is_reachable_never_online():
    # An unknown capability is never silently reported ok — but it is not a
    # failure either: the peer answered, its capability state is unknown.
    status, note = _classify_health_response(
        _response(200, _contract_body("ok", trading_engine=("unknown", "CONFIG_ONLY")))
    )
    assert status == "REACHABLE"
    assert note == "capability unknown — trading_engine unknown (CONFIG_ONLY)"


def test_classifier_malformed_capabilities_falls_back_to_legacy():
    status, note = _classify_health_response(
        _response(200, {"status": "ok", "capabilities": {"trading_engine": "ok"}})
    )
    assert status == "REACHABLE"
    assert "pre-contract" in note


def test_stratex_503_contract_body_is_degraded_with_reason():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json=_contract_body(
                "degraded",
                trading_engine=("unavailable", "STALE_STRATEGY_EVALUATION"),
                trading_capable=("unavailable", "STALE_STRATEGY_EVALUATION"),
                market_data=("ok", ""),
            ),
            request=request,
        )

    async def _go():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await _fleet().probe_stratex(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "DEGRADED"
    assert status.details == (
        "Stratex DEGRADED: trading_engine unavailable (STALE_STRATEGY_EVALUATION); "
        "trading_capable unavailable (STALE_STRATEGY_EVALUATION)"
    )


def test_stratex_contract_ok_body_is_online_with_capabilities_ok():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_contract_body(trading_engine=("ok", ""), market_data=("ok", "")),
            request=request,
        )

    async def _go():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        try:
            return await _fleet().probe_stratex(client)
        finally:
            await client.aclose()

    status = _run(_go())
    assert status.status == "ONLINE"
    assert "capabilities ok" in status.details
