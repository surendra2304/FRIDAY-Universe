"""
Tier-1 Production Resilience & Health Contract Tests for Forge.
Verifies standardized endpoints (/health, /ready, /status, /metrics),
SQLite WAL/busy_timeout settings, and thread-safe in-memory caching.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.memory.db import DatabaseManager
from app.optimization.cache import TTLCache, cached


@pytest.fixture
def test_client():
    return TestClient(app, raise_server_exceptions=False)


def test_health_liveness_probe_contract(test_client: TestClient):
    """GET /health must return 200 with status=ok, service=forge, and process_liveness evidence."""
    resp = test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "healthy")
    assert data["service"] == "forge"
    assert data["evidence_class"] == "process_liveness"
    assert "uptime_seconds" in data
    assert "observed_at" in data


def test_ready_probe_contract(test_client: TestClient):
    """GET /ready and /health/ready must return 200 with status=ready, service=forge, and dependency_readiness."""
    for path in ("/health/ready", "/ready"):
        resp = test_client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "ready"
        assert data["service"] == "forge"
        assert data["evidence_class"] == "dependency_readiness"
        assert data["database_connected"] is True
        assert data["workspaces_writable"] is True


def test_status_diagnostics_endpoint(test_client: TestClient):
    """GET /status and /health/detailed must return 200 with service diagnostics."""
    for path in ("/health/detailed", "/status"):
        resp = test_client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["service"] == "forge"
        assert "database" in data
        assert "system_metrics" in data


def test_metrics_prometheus_endpoint(test_client: TestClient):
    """GET /metrics must return 200 with Prometheus text metrics."""
    resp = test_client.get("/metrics")
    assert resp.status_code == 200
    assert "forge_uptime_seconds" in resp.text
    assert "text/plain" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_sqlite_pragmas_and_wal_mode(tmp_path: Path):
    """Database connections must enforce WAL mode, busy_timeout >= 5000, and foreign keys."""
    db_file = tmp_path / "test_pragmas.db"
    mgr = DatabaseManager(db_path=db_file)
    await mgr.init_db()

    async with mgr.connection() as conn:
        # Check journal mode
        cursor = await conn.execute("PRAGMA journal_mode;")
        row = await cursor.fetchone()
        assert row is not None and row[0].lower() == "wal"

        # Check busy timeout
        cursor = await conn.execute("PRAGMA busy_timeout;")
        row = await cursor.fetchone()
        assert row is not None and row[0] >= 5000

        # Check foreign keys
        cursor = await conn.execute("PRAGMA foreign_keys;")
        row = await cursor.fetchone()
        assert row is not None and row[0] == 1


def test_ttl_lru_in_memory_cache():
    """TTLCache must handle insertion, retrieval, expiration, and LRU eviction cleanly."""
    cache = TTLCache(maxsize=3, default_ttl=0.1)

    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.get("c") == 3

    # Eviction test (LRU)
    cache.set("d", 4)
    assert len(cache) == 3
    # "a" was accessed, then "b", then "c", so oldest is handled properly
    assert cache.get("d") == 4

    # TTL Expiration test
    time.sleep(0.15)
    assert cache.get("d") is None
    assert cache.get("a") is None
    assert len(cache) == 0


@pytest.mark.asyncio
async def test_cached_decorator_sync_and_async():
    """The @cached decorator must cache both synchronous and asynchronous operations."""
    call_count_sync = 0
    call_count_async = 0

    @cached(ttl=10.0)
    def compute_sync(x: int) -> int:
        nonlocal call_count_sync
        call_count_sync += 1
        return x * 2

    @cached(ttl=10.0)
    async def compute_async(x: int) -> int:
        nonlocal call_count_async
        call_count_async += 1
        await asyncio.sleep(0.01)
        return x * 3

    # Sync caching
    assert compute_sync(5) == 10
    assert compute_sync(5) == 10
    assert call_count_sync == 1

    # Async caching
    assert await compute_async(7) == 21
    assert await compute_async(7) == 21
    assert call_count_async == 1


def test_port_configuration_from_env(monkeypatch):
    """Settings must respect the PORT environment variable."""
    monkeypatch.setenv("PORT", "8000")
    s = Settings()
    assert s.port == 8000

    monkeypatch.setenv("PORT", "9090")
    s2 = Settings()
    assert s2.port == 9090
