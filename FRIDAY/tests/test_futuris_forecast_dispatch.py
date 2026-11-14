"""Checklist F10/C10 (MASTER_COMPLETION_CHECKLIST): Futuris forecasts via chat.

"Forecast X over the next 24 hours" / "what does Futuris predict for Y" must
reach Futuris's REAL FRIDAY delegation contract (POST /v1/friday/forecast —
research enrichment, forecasting pipeline, honest calibration), never the
LLM's invented numbers.

Contracts locked here:
- the routing table sends forecast requests to TOOL_EXECUTION
  (futuris_forecast), never VISION_MODEL, never DIRECT_REASONING;
- the forecast fast-path fires only on explicit forecast ACTION phrasing
  (a sentence that merely mentions a prediction does not hijack);
- target and horizon extraction (quoted targets kept verbatim, horizons
  mapped 1h/24h/7d/30d, sane default);
- FleetClient.request_futuris_forecast posts the real contract and reports
  honest failures (HTTP errors, connection errors) and Futuris's honest
  statuses (BLOCKED / INSUFFICIENT_DATA) as-is;
- every answer states that a prediction is never an authorization.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.agent.agent import FridayAgent  # noqa: E402
from friday.core.config import Settings  # noqa: E402
from friday.llm.mock_provider import MockLLMProvider  # noqa: E402
from friday.routing.capability_router import CapabilityRouter  # noqa: E402
from friday.tools.builtin.futuris_forecast import (  # noqa: E402
    FuturisForecastTool,
    _extract_horizon,
    _extract_target,
)


# ---------------------------------------------------------------------------
# routing table
# ---------------------------------------------------------------------------

class TestRouting:
    @pytest.mark.parametrize(
        "phrase",
        [
            "forecast the api request rate over the next 24 hours",
            "predict the fleet load",
            "what does futuris predict for btc",
            "give me a forecast for the checkout service",
        ],
    )
    def test_forecast_requests_route_to_tool_execution(self, phrase: str) -> None:
        decision = CapabilityRouter().route_request(phrase)
        assert decision.selected_capability.value == "TOOL_EXECUTION"
        assert any(
            "futuris_forecast" in (c.required_tools or [])
            for c in decision.candidate_evaluations
        )

    def test_forecast_never_conversational(self) -> None:
        decision = CapabilityRouter().route_request("forecast the api request rate")
        assert decision.selected_capability.value != "DIRECT_REASONING"


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------

class TestExtraction:
    def test_quoted_target_kept_verbatim(self) -> None:
        assert _extract_target("forecast 'service:checkout:capacity_exceedance_24h' please") == (
            "service:checkout:capacity_exceedance_24h"
        )

    def test_target_stripped_of_verbs_and_horizon(self) -> None:
        target = _extract_target("forecast the api request rate over the next 24 hours")
        assert "forecast" not in target
        assert "api request rate" in target
        assert "24" not in target

    def test_default_target_is_explicit_not_fake(self) -> None:
        assert _extract_target("give me a forecast") == "fleet:api:request_rate"

    def test_qualified_forecast_extracts_the_real_target(self) -> None:
        # TASK-REL-007: the exact console round-1 phrasing. Before the fix the
        # qualifier ("short") defeated extraction and the whole sentence (or
        # the default) became the target.
        phrase = "Give me a short forecast: what should I expect for my portfolio this week?"
        assert _extract_target(phrase) == "my portfolio"
        assert _extract_horizon(phrase) == "7d"

    @pytest.mark.parametrize(
        "text,horizon",
        [
            ("forecast x over the next 24 hours", "24h"),
            ("forecast x over the next hour", "1h"),
            ("predict x for the next 7 days", "7d"),
            ("what about next month", "30d"),
            ("forecast x", "24h"),
        ],
    )
    def test_horizon_mapping(self, text: str, horizon: str) -> None:
        assert _extract_horizon(text) == horizon


# ---------------------------------------------------------------------------
# tool contract
# ---------------------------------------------------------------------------

_REAL_FORECAST = {
    "futuris_forecast_id": "fc_123",
    "prediction": {"point_estimate": 128.5, "lower_bound": 110.0, "upper_bound": 145.0},
    "status": "SUCCESS",
    "confidence": "MEDIUM",
    "calibration_score": 0.72,
    "model_metadata": {"model": "ensemble-v3"},
    "drivers_identified": [{"name": "api traffic trend"}],
    "prediction_is_not_authorization": True,
}


class _FakeFuturisClient:
    def __init__(self, response: dict[str, Any] | None = None, error: Exception | None = None):
        self.response = response if response is not None else _REAL_FORECAST
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def request_futuris_forecast(self, target: str, horizon: str = "24h") -> dict[str, Any]:
        self.calls.append({"target": target, "horizon": horizon})
        if self.error:
            raise self.error
        return {
            "reply": (
                f"🔮 [FUTURIS FORECAST] target '{target}' over {horizon}:\n"
                "• Point estimate: 128.5 (band 110.0 – 145.0)\n"
                "• A prediction is not an authorization."
            ),
            "metadata": {"status": "SUCCESS", "point_estimate": 128.5},
            "success": True,
        }


class TestToolContract:
    def test_real_forecast_formatted(self) -> None:
        client = _FakeFuturisClient()
        result = FuturisForecastTool(fleet_client=client).execute(
            question="forecast the api request rate over the next 24 hours"
        )
        assert result.is_error is False
        assert "128.5" in result.content
        assert "not an authorization" in result.content
        assert client.calls[0]["target"] != ""
        assert client.calls[0]["horizon"] == "24h"

    def test_explicit_target_and_horizon(self) -> None:
        client = _FakeFuturisClient()
        FuturisForecastTool(fleet_client=client).execute(
            question="forecast it", target="service:checkout:errors", horizon="7d"
        )
        assert client.calls[0]["target"] == "service:checkout:errors"
        assert client.calls[0]["horizon"] == "7d"

    def test_invalid_horizon_falls_back_to_extraction(self) -> None:
        client = _FakeFuturisClient()
        FuturisForecastTool(fleet_client=client).execute(
            question="forecast x over the next hour", horizon="bogus"
        )
        assert client.calls[0]["horizon"] == "1h"

    def test_connection_failure_is_honest(self) -> None:
        client = _FakeFuturisClient(error=RuntimeError("no route to host"))
        result = FuturisForecastTool(fleet_client=client).execute(question="forecast x")
        assert result.is_error is True
        assert "no route to host" in result.content
        assert "won't invent" in result.content

    def test_empty_reply_is_honest(self) -> None:
        class _Empty:
            async def request_futuris_forecast(self, target, horizon="24h"):
                return {"reply": "", "metadata": {}}

        result = FuturisForecastTool(fleet_client=_Empty()).execute(question="forecast x")
        assert result.is_error is True
        assert "nothing was invented" in result.content


# ---------------------------------------------------------------------------
# FleetClient.request_futuris_forecast (HTTP-level contract)
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _FakeHTTPClient:
    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.timeouts: list[Any] = []

    async def post(self, url: str, json: dict[str, Any] | None = None, **kwargs: Any) -> _FakeResponse:
        self.posts.append((url, json or {}))
        self.timeouts.append(kwargs.get("timeout"))
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


class _FakeBreaker:
    async def can_execute(self) -> bool:
        return True

    async def record_success(self, *_a: Any, **_k: Any) -> None:
        pass

    async def record_failure(self, *_a: Any, **_k: Any) -> None:
        pass


class _FleetClientForForecasts:
    futuris_url = "http://futuris.internal:8000"
    futuris_key = "test-futuris-key"

    def __init__(self, response: _FakeResponse | None = None, error: Exception | None = None):
        self._http = _FakeHTTPClient(response=response, error=error)
        self._breaker = _FakeBreaker()

    def get_circuit_breaker(self, target: str):
        return self._breaker

    def get_shared_client(self):
        return self._http


class TestRequestFuturisForecast:
    def test_posts_the_real_contract(self) -> None:
        import asyncio

        from friday.ecosystem.fleet_client import FleetClient

        client = _FleetClientForForecasts(response=_FakeResponse(201, _REAL_FORECAST))
        result = asyncio.run(FleetClient.request_futuris_forecast(client, target="fleet:api:request_rate", horizon="24h"))
        url, body = client._http.posts[0]
        assert url.endswith("/v1/friday/forecast")
        assert body["target"] == "fleet:api:request_rate"
        assert body["horizon"] == "24h"
        assert result["success"] is True
        assert "128.5" in result["reply"]
        assert "not an authorization" in result["reply"]

    def test_blocked_status_reported_as_is(self) -> None:
        import asyncio

        from friday.ecosystem.fleet_client import FleetClient

        blocked = {**_REAL_FORECAST, "status": "INSUFFICIENT_DATA", "prediction": {}}
        client = _FleetClientForForecasts(response=_FakeResponse(201, blocked))
        result = asyncio.run(FleetClient.request_futuris_forecast(client, target="x", horizon="24h"))
        assert result["success"] is True  # the request succeeded; the FORECAST is honestly blocked
        assert "INSUFFICIENT_DATA" in result["reply"]

    def test_http_error_honest(self) -> None:
        import asyncio

        from friday.ecosystem.fleet_client import FleetClient

        client = _FleetClientForForecasts(response=_FakeResponse(503, {"detail": "unavailable"}))
        result = asyncio.run(FleetClient.request_futuris_forecast(client, target="x"))
        assert result["success"] is False
        assert "503" in result["reply"]

    def test_connection_error_honest(self) -> None:
        import asyncio

        from friday.ecosystem.fleet_client import FleetClient

        client = _FleetClientForForecasts(error=RuntimeError("connection refused"))
        result = asyncio.run(FleetClient.request_futuris_forecast(client, target="x"))
        assert result["success"] is False
        assert "connection refused" in result["reply"]

    def test_forecast_post_timeout_covers_real_pipeline_latency(self) -> None:
        # TASK-REL-007: the POST timeout was 20s while Futuris' measured live
        # latency is ~40s warm / ~114s cold on the fleet host — every chat
        # forecast timed out as "Error connecting to Futuris". The budget
        # must cover a real pipeline run.
        import asyncio

        from friday.ecosystem.fleet_client import FleetClient

        client = _FleetClientForForecasts(response=_FakeResponse(201, _REAL_FORECAST))
        asyncio.run(FleetClient.request_futuris_forecast(client, target="x", horizon="24h"))
        assert client._http.timeouts, "the forecast POST must pass an explicit timeout"
        assert client._http.timeouts[0] >= 60.0


# ---------------------------------------------------------------------------
# fast-path behavior
# ---------------------------------------------------------------------------

def _agent() -> FridayAgent:
    return FridayAgent(
        settings=Settings(env="testing", embedding_provider="none"),
        llm_provider=MockLLMProvider(),
        authorizer=__import__("friday.core.auth", fromlist=["AutoApproveAuthorizer"]).AutoApproveAuthorizer.create_for_testing(),
    )


class TestForecastFastPath:
    @pytest.mark.parametrize(
        "phrase,horizon",
        [
            ("forecast the api request rate over the next 24 hours", "24h"),
            ("predict the fleet load", "24h"),
            ("what does futuris predict for btc", "24h"),
            ("forecast service errors over the next 7 days", "7d"),
        ],
    )
    def test_forecast_phrasings_fire(self, phrase: str, horizon: str) -> None:
        agent = _agent()
        client = _FakeFuturisClient()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(FuturisForecastTool, "_client", lambda self: client)
            response = agent.process_message(phrase)
        assert response is not None
        assert response.metadata.get("forecast_dispatch") is True
        assert client.calls, "the forecast tool must have run"
        assert client.calls[0]["horizon"] == horizon

    @pytest.mark.parametrize(
        "phrase",
        [
            "tell Futuris to forecast the market",  # delegation owns this
            "assign a forecast task to Futuris",  # delegation
            "hello friday",
            "what time is it",
            "how's the fleet",
        ],
    )
    def test_non_forecast_phrasings_untouched(self, phrase: str) -> None:
        agent = _agent()
        client = _FakeFuturisClient()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(FuturisForecastTool, "_client", lambda self: client)
            response = agent.process_message(phrase)
        if response is not None and response.metadata.get("fast_path"):
            assert response.metadata.get("forecast_dispatch") is None

    def test_tool_registered_in_default_registry(self) -> None:
        agent = _agent()
        registered = getattr(agent.tools, "_tools", {}) or {}
        assert any(
            getattr(t, "name", "") == "futuris_forecast" for t in registered.values()
        ), "futuris_forecast must be registered in the default tool registry"

    def test_qualified_forecast_phrasing_fires(self) -> None:
        # TASK-REL-007: "give me a SHORT forecast" must dispatch to Futuris;
        # before the fix it fell through to the LLM, which invented an
        # outlook instead of asking Futuris (console round 1, 2026-11-14).
        agent = _agent()
        client = _FakeFuturisClient()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(FuturisForecastTool, "_client", lambda self: client)
            response = agent.process_message(
                "Give me a short forecast: what should I expect for my portfolio this week?"
            )
        assert response is not None
        assert response.metadata.get("forecast_dispatch") is True
        assert client.calls, "the forecast tool must have run"
        assert client.calls[0]["target"] == "my portfolio"
        assert client.calls[0]["horizon"] == "7d"
