"""
tests/test_search_provenance.py — TASK-TRUST-001 regression coverage.

Locks in the synthetic-fallback provenance contract for the OSINT search
surface: without a live Intelligence X API key the engine's deterministic
fallback produces hash-seeded PLACEHOLDER records, and every layer now says
so. These records must never be mistaken for live OSINT evidence.
"""

import os

import pytest

from app.agents.real_intelx_osint import IntelXSearchEngine, IntelXSearchQuery


@pytest.fixture
def no_api_key(monkeypatch):
    monkeypatch.delenv("INTELX_API_KEY", raising=False)


def test_fallback_results_are_marked_simulated(no_api_key):
    engine = IntelXSearchEngine()
    results = engine.search(IntelXSearchQuery(selector="victim@example.com", limit=50))
    assert engine.last_search_simulated is True
    assert len(results) > 0
    assert all(r.simulated for r in results)


def test_engine_defaults_to_not_simulated(no_api_key):
    engine = IntelXSearchEngine()
    assert engine.last_search_simulated is False


def test_invalid_selector_returns_empty_not_fabricated(no_api_key):
    engine = IntelXSearchEngine()
    results = engine.search(IntelXSearchQuery(selector="!!!not a selector!!!", limit=50))
    assert results == []
    # An invalid selector never reaches the fallback, so nothing is simulated.
    assert engine.last_search_simulated is False


def test_route_labels_synthetic_fallback():
    """The /osint/search route reports data_source/simulated/status honestly."""
    from fastapi.testclient import TestClient

    from routers.real_osint_routes import router as osint_router

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(osint_router)
    client = TestClient(app)

    resp = client.post("/api/v1/intelx/osint/search", json={"query": "victim@example.com", "max_results": 5})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["data_source"] in ("live_intelx", "synthetic_fallback")
    assert payload["simulated"] is (payload["data_source"] == "synthetic_fallback")
    if payload["simulated"]:
        assert payload["status"] == "simulated"
        assert all(r.get("simulated") for r in payload["results"])
    else:
        assert payload["status"] == "success"
        assert all(not r.get("simulated") for r in payload["results"])
