"""TASK-REL-067: IntelX /health returns the REL-004 §2.2 capability report.

/health (mounted at /health and /api/v1/health) is the contract endpoint:
derived status, HTTP 200 iff ok else 503, capabilities + dependencies in
the closed vocabulary, evidence_class capability_report. /healthz stays
process-only liveness per TASK-INT-012 (always 200/"ok", no database
work) and /readyz keeps its exact readiness behaviour; the three
endpoints are pinned against each other here so the split cannot
silently re-merge.
"""

import json

import pytest
from httpx import AsyncClient

import intelx.api.v1.health as health_module
from intelx.core.settings import Settings


@pytest.fixture
def db_check_spy(monkeypatch):
    """Replace the health module's database check with a recording spy."""
    calls: list[int] = []

    async def spy():
        calls.append(1)
        return True

    monkeypatch.setattr(health_module, "check_database_health", spy)
    return calls


def _assert_contract_shape(data):
    assert data["evidence_class"] == "capability_report"
    assert set(data["capabilities"]) == {"research", "model_provider"}
    assert set(data["dependencies"]) == {"database", "storage"}
    for entry in list(data["capabilities"].values()) + list(data["dependencies"].values()):
        assert entry["state"] in {"ok", "degraded", "unavailable", "unknown"}
        if entry["state"] != "ok":
            assert entry["detail"] and entry["detail"] == entry["detail"].upper()
            assert entry["evidence"]
        else:
            assert "detail" not in entry
    # Legacy fields are kept alongside the contract block.
    for key in ("service", "version", "mock_mode", "database", "observed_at", "timestamp"):
        assert key in data


@pytest.mark.asyncio
async def test_health_mock_mode_is_degraded_with_mock_research(client: AsyncClient):
    """Conftest runs MOCK_MODE=true: research is degraded/MOCK_MODE, so
    /health is 503 even though the database and storage probes pass."""
    response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    _assert_contract_shape(data)
    assert data["mock_mode"] is True
    assert data["capabilities"]["research"] == {
        "state": "degraded",
        "detail": "MOCK_MODE",
        "evidence": "mock mode: findings are synthetic; research cannot report ok",
    }
    assert data["capabilities"]["model_provider"] == {
        "state": "unknown",
        "detail": "MOCK_MODE",
        "evidence": "provider is a local mock in MOCK_MODE; no live provider to report",
    }
    assert data["dependencies"]["database"]["state"] == "ok"
    assert data["dependencies"]["storage"]["state"] == "ok"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_live_mode_research_unknown_no_live_probe(
    client: AsyncClient, monkeypatch, tmp_path
):
    """Outside MOCK_MODE with a configured provider, research is still
    unknown/NO_LIVE_PROBE — no probe exists — so /health stays 503.
    The provider is config-only (CONFIG_ONLY), never ok on config alone,
    and no key material appears anywhere in the payload."""
    settings = Settings(
        MOCK_MODE=False,
        LLM_PROVIDER="inference",
        DATA_DIR=str(tmp_path),
        INFERENCE_API_KEY="local-inference-test-key",
    )
    monkeypatch.setattr(health_module, "get_settings", lambda: settings)

    async def database_is_healthy():
        return True

    monkeypatch.setattr(health_module, "check_database_health", database_is_healthy)
    response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    _assert_contract_shape(data)
    assert data["mock_mode"] is False
    assert data["capabilities"]["research"] == {
        "state": "unknown",
        "detail": "NO_LIVE_PROBE",
        "evidence": "no live research probe exists; research ability is not verified by this endpoint",
    }
    assert data["capabilities"]["model_provider"] == {
        "state": "unknown",
        "detail": "CONFIG_ONLY",
        "evidence": "provider config present; no live probe",
    }
    assert "local-inference-test-key" not in json.dumps(data)


@pytest.mark.asyncio
async def test_health_provider_missing_key_stays_unknown_not_ok(
    client: AsyncClient, monkeypatch, tmp_path
):
    """Provider key/endpoint missing: model_provider is unknown/CONFIG_ONLY
    with the missing config named in evidence — never ok, and never
    unavailable on a config check alone (no live probe exists)."""
    settings = Settings(
        MOCK_MODE=False,
        LLM_PROVIDER="inference",
        DATA_DIR=str(tmp_path),
        INFERENCE_API_KEY=None,
    )
    monkeypatch.setattr(health_module, "get_settings", lambda: settings)

    async def database_is_healthy():
        return True

    monkeypatch.setattr(health_module, "check_database_health", database_is_healthy)
    response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["capabilities"]["model_provider"] == {
        "state": "unknown",
        "detail": "CONFIG_ONLY",
        "evidence": "provider key/endpoint missing; no live probe",
    }


@pytest.mark.asyncio
async def test_health_database_down_is_unavailable_and_readyz_agrees(
    client: AsyncClient, monkeypatch
):
    """DB down: dependencies.database is unavailable/DATABASE_UNREACHABLE
    and /health is 503 — and /readyz is 503 too, so /health never
    contradicts /ready (§2.5)."""
    async def database_down():
        return False

    monkeypatch.setattr(health_module, "check_database_health", database_down)
    response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["dependencies"]["database"] == {
        "state": "unavailable",
        "detail": "DATABASE_UNREACHABLE",
        "evidence": "live check_database_health() round-trip failed",
    }
    assert data["database"] == "unavailable"
    ready = await client.get("/readyz")
    assert ready.status_code == 503
    assert ready.json()["status"] == "not_ready"
    assert ready.json()["database"] == "unavailable"


@pytest.mark.asyncio
async def test_health_storage_failure_is_unavailable(
    client: AsyncClient, monkeypatch, tmp_path
):
    """Data dir unwritable: dependencies.storage is
    unavailable/STORAGE_UNWRITABLE and /readyz agrees (storage error)."""
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    settings = Settings(DATA_DIR=str(blocked))
    monkeypatch.setattr(health_module, "get_settings", lambda: settings)
    response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["dependencies"]["storage"] == {
        "state": "unavailable",
        "detail": "STORAGE_UNWRITABLE",
        "evidence": "writable data-dir probe failed (tempfile write, as /readyz)",
    }
    ready = await client.get("/readyz")
    assert ready.status_code == 503
    assert ready.json()["storage"] == "error"


@pytest.mark.asyncio
async def test_healthz_and_health_split(client: AsyncClient, db_check_spy):
    """The INT-012 / REL-067 boundary: /healthz never touches the
    database; /health probes it exactly once per call."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["evidence_class"] == "process_liveness"
    assert response.json()["database"] == "not_checked"
    assert db_check_spy == []
    response = await client.get("/health")
    assert response.status_code == 503
    assert len(db_check_spy) == 1


@pytest.mark.asyncio
async def test_readyz_fields_unchanged_in_mock_mode(client: AsyncClient):
    """Ready-gate behaviour is identical: mock mode + live DB + writable
    storage is ready/200 with the exact pre-contract field set."""
    response = await client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["ready"] is True
    assert data["evidence_class"] == "dependency_readiness"
    assert data["database"] == "connected"
    assert data["model_provider"] == "mock"
    assert data["model_provider_check"] == "local_mock"
    assert data["storage"] == "ok"
