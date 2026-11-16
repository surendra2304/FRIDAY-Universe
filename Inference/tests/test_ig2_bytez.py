"""TASK-IG2-INF-01: Bytez provider adapter + free-tier quota probe.

Pins the card's conditions: Bytez is an OpenAI-compatible adapter limited
to ≤7B free-tier models; its gateway rung is OFF by default
(INFERENCE_BYTEZ_RUNG_ENABLED); the quota ledger gives it NO declared
limit (state ``unproven_free_tier``); and the probe measures empirically —
stopping at the first 429 — without ever claiming a recurring allowance
from a single run.
"""

import httpx
import pytest

import app.providers
from app.providers.bytez import BYTEZ_BASE_URL, BYTEZ_SUPPORTED_MODELS, BytezProvider
from app.providers.bytez_probe import build_verdict, classify_status, run_probe
from app.providers.gateway import bytez_rung_enabled
from app.providers.quota_ledger import QuotaLedger


def test_adapter_shape_and_free_tier_models():
    provider = BytezProvider(api_key="test-key")
    assert provider.provider_name == "bytez"
    assert provider.base_url == BYTEZ_BASE_URL == "https://api.bytez.com/models/v2/openai/v1"
    # Free tier is ≤7B open models only; nothing credit-gated may be listed.
    assert provider.default_model in BYTEZ_SUPPORTED_MODELS
    caps = provider.capabilities()
    assert caps.provider_name == "bytez"
    assert "UNPROVEN" in caps.rate_limits["free_volume"]


def test_provider_factory_registration():
    provider = app.providers.get_provider("bytez", api_key="test-key")
    assert isinstance(provider, BytezProvider)


def test_rung_disabled_by_default(monkeypatch):
    monkeypatch.delenv("INFERENCE_BYTEZ_RUNG_ENABLED", raising=False)
    assert bytez_rung_enabled() is False


def test_rung_enable_is_explicit(monkeypatch):
    monkeypatch.setenv("INFERENCE_BYTEZ_RUNG_ENABLED", "true")
    assert bytez_rung_enabled() is True


def test_ledger_gives_bytez_no_declared_limit(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    ledger.record(provider="bytez", model="Qwen/Qwen2.5-7B-Instruct", api_key="k", outcome="success", total_tokens=10)
    entry = ledger.snapshot()["providers"]["bytez"]
    assert entry["state"] == "unproven_free_tier"
    assert entry["requests_today"] == 1
    for bucket in entry["daily_buckets"]:
        assert "limit_requests_per_day" not in bucket
        assert "used_fraction" not in bucket


def test_classify_status():
    assert classify_status(200) == "success"
    assert classify_status(429) == "rate_limited"
    assert classify_status(401) == "auth_error"
    assert classify_status(403) == "auth_error"
    assert classify_status(500) == "http_error"


def test_verdict_never_claims_recurring_allowance():
    attempts = [{"round": i, "outcome": "success"} for i in range(1, 6)]
    verdict = build_verdict(attempts, 5)
    assert verdict["verdict"] == "proven_for_this_run"
    assert "does NOT prove a recurring" in verdict["meaning"]


def test_verdict_rate_limited_round():
    attempts = [
        {"round": 1, "outcome": "success"},
        {"round": 2, "outcome": "success"},
        {"round": 3, "outcome": "rate_limited"},
    ]
    verdict = build_verdict(attempts, 5)
    assert verdict["verdict"] == "rate_limited"
    assert verdict["first_rate_limited_round"] == 3


@pytest.mark.asyncio
async def test_probe_stops_at_first_429(tmp_path, monkeypatch):
    monkeypatch.setattr("app.providers.bytez_probe.REPORT_DIR", tmp_path)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(200, json={"usage": {"total_tokens": 12}})
        return httpx.Response(429, json={"error": "rate limited"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        report = await run_probe(rounds=5, interval_seconds=0.0, api_key="probe-key", client=client)
    assert calls["n"] == 3  # stopped at the first 429 — the ceiling is the measurement
    assert report["verdict"] == "rate_limited"
    assert report["successes"] == 2
    assert report["attempts"][0]["total_tokens"] == 12


@pytest.mark.asyncio
async def test_probe_without_key_sends_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("app.providers.bytez_probe.REPORT_DIR", tmp_path)
    monkeypatch.delenv("BYTEZ_API_KEY", raising=False)
    monkeypatch.delenv("BYTEZ_API_KEYS", raising=False)
    report = await run_probe(rounds=3, interval_seconds=0.0, api_key=None)
    assert report["attempts"] == []
    assert report["verdict"] == "no_attempts"
