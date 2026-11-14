"""TASK-REL-026: test generation must survive a single provider failure.

Pre-fix behaviour (live-reproduced 2026-11-14 against production): ONE
unified-manager call on the primary model inside the gateway's 60s
chat-scale deadline; a single gemini TimeoutError under strain produced
an empty suite, and the endpoint reported it as HTTP 200. Forge's
verification gate then failed good code for an infrastructure reason.

These tests pin the new contract with explicit provider fixtures:
- attempts walk the test_generator role's DECLARED provider/model ladder;
- a degraded or timed-out attempt fails only that attempt;
- unusable output fails only that attempt;
- exhausting the ladder yields an honest no-tests result (empty
  test_code, retryable=True, attempts counted) — never a fake suite;
- the HTTP endpoint returns 200 only when tests were generated, and a
  retryable 503 carrying the same body when they were not.
"""
import asyncio
from types import SimpleNamespace

import pytest
from app.providers.unified_manager import unified_provider_manager
from app.services import test_generation as tg
from app.services.test_generation import TestGenerationRequest, TestGenerationService

GOOD_SUITE = "def test_add():\n    assert 1 + 1 == 2\n"
SOURCE = "def is_palindrome(s: str) -> bool:\n    return s == s[::-1]\n"


def _ok(content):
    return SimpleNamespace(content=content, degraded=False, error=None)


def _degraded(error="provider unavailable"):
    return SimpleNamespace(content="", degraded=True, error=error)


@pytest.fixture
def captured(monkeypatch):
    """Install a scripted unified-manager stub; returns the request log.

    The script maps attempt index -> response/exception/sleep spec.
    """
    calls = []

    def install(script):
        async def provider(request):
            calls.append(request)
            action = script[min(len(calls) - 1, len(script) - 1)]
            if isinstance(action, tuple) and action and action[0] == "sleep":
                await asyncio.sleep(action[1])
                return _ok(GOOD_SUITE)
            if isinstance(action, BaseException):
                raise action
            return action

        monkeypatch.setattr(unified_provider_manager, "execute", provider)
        return calls

    return install


def test_attempt_sequence_matches_declared_test_generator_configs():
    assert tg.attempt_sequence() == [
        ("gemini", "gemini-flash-latest"),
        ("groq", "openai/gpt-oss-120b"),
        ("groq", "qwen/qwen3.8-27b"),
    ]


@pytest.mark.asyncio
async def test_first_attempt_success_makes_one_attempt(captured):
    calls = captured([_ok(GOOD_SUITE)])
    result = await TestGenerationService().generate_tests(TestGenerationRequest(code=SOURCE))
    assert result.generation_status == "generated"
    assert result.test_code.startswith("def test_add")
    assert result.attempts == 1
    assert result.provider_used == "gemini"
    assert result.model_used == "gemini-flash-latest"
    assert result.retryable is False
    assert len(calls) == 1
    assert calls[0].provider == "gemini" and calls[0].model == "gemini-flash-latest"


@pytest.mark.asyncio
async def test_degraded_primary_recovers_on_groq(captured):
    calls = captured([_degraded("gemini: TimeoutError"), _ok(GOOD_SUITE)])
    result = await TestGenerationService().generate_tests(TestGenerationRequest(code=SOURCE))
    assert result.generation_status == "generated"
    assert result.attempts == 2
    assert result.provider_used == "groq"
    assert result.model_used == "openai/gpt-oss-120b"
    assert [c.provider for c in calls] == ["gemini", "groq"]
    assert calls[1].model == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_timed_out_attempt_fails_only_that_attempt(captured, monkeypatch):
    monkeypatch.setattr(tg, "ATTEMPT_TIMEOUT_SECONDS", 0.2)
    calls = captured([("sleep", 30), _ok(GOOD_SUITE)])
    result = await TestGenerationService().generate_tests(TestGenerationRequest(code=SOURCE))
    assert result.generation_status == "generated"
    assert result.attempts == 2
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_invalid_output_fails_only_that_attempt(captured):
    calls = captured([_ok("Here is an exhaustive suite."), _ok(GOOD_SUITE)])
    result = await TestGenerationService().generate_tests(TestGenerationRequest(code=SOURCE))
    assert result.generation_status == "generated"
    assert result.attempts == 2
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_all_attempts_degraded_is_honest_no_tests(captured):
    calls = captured([_degraded("gemini: TimeoutError")])
    result = await TestGenerationService().generate_tests(TestGenerationRequest(code=SOURCE))
    assert result.generation_status == "degraded"
    assert result.test_code == ""
    assert result.coverage_estimate is None
    assert result.retryable is True
    assert result.attempts == 3
    assert len(calls) == 3
    # The error names every attempt so operators see the whole ladder failed.
    assert "attempt 1" in result.error and "attempt 3" in result.error


@pytest.mark.asyncio
async def test_all_attempts_invalid_is_invalid_output(captured):
    captured([_ok("prose, no tests")])
    result = await TestGenerationService().generate_tests(TestGenerationRequest(code=SOURCE))
    assert result.generation_status == "invalid_output"
    assert result.test_code == ""
    assert result.retryable is True
    assert result.attempts == 3


@pytest.mark.asyncio
async def test_attempt_exception_is_degraded_not_raised(captured):
    captured([RuntimeError("boom"), _ok(GOOD_SUITE)])
    result = await TestGenerationService().generate_tests(TestGenerationRequest(code=SOURCE))
    assert result.generation_status == "generated"
    assert result.attempts == 2


def _client(monkeypatch, service_result):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import forge_services

    async def fake_generate(req):
        return service_result

    monkeypatch.setattr(
        forge_services.test_generation_service, "generate_tests", fake_generate
    )
    app = FastAPI()
    app.include_router(forge_services.forge_router)
    return TestClient(app, raise_server_exceptions=False)


def test_endpoint_200_only_when_generated(monkeypatch):
    from app.services.test_generation import TestGenerationResponse

    client = _client(monkeypatch, TestGenerationResponse(
        test_code=GOOD_SUITE, test_strategy="Generated pytest suite; not executed, coverage not measured.",
        generation_status="generated", latency_ms=12.0, attempts=2,
        provider_used="groq", model_used="openai/gpt-oss-120b",
    ))
    resp = client.post("/v1/forge/generate-tests", json={"code": SOURCE})
    assert resp.status_code == 200
    body = resp.json()
    assert body["generation_status"] == "generated"
    assert "def test_add" in body["test_code"]
    assert body["attempts"] == 2


def test_endpoint_503_retryable_when_no_tests(monkeypatch):
    from app.services.test_generation import TestGenerationResponse

    client = _client(monkeypatch, TestGenerationResponse(
        test_code="", test_strategy="No tests generated: provider unavailable.",
        generation_status="degraded", error="attempt 1 (gemini/gemini-flash-latest): gemini: TimeoutError",
        latency_ms=61000.0, attempts=3, retryable=True,
    ))
    resp = client.post("/v1/forge/generate-tests", json={"code": SOURCE})
    assert resp.status_code == 503, "a no-tests outcome must not look like success"
    body = resp.json()
    assert body["generation_status"] == "degraded"
    assert body["test_code"] == ""
    assert body["retryable"] is True
    assert body["attempts"] == 3
