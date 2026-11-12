"""Unit tests for the LiveKit token minting endpoint."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure paths are added before imports
apps_core_src = Path(__file__).resolve().parents[2] / "FRIDAY" / "apps" / "core" / "src"
friday_src = Path(__file__).resolve().parents[2] / "FRIDAY" / "src"
if str(apps_core_src) not in sys.path:
    sys.path.insert(0, str(apps_core_src))
if str(friday_src) not in sys.path:
    sys.path.insert(0, str(friday_src))

# NOTE (2026-11-12 battery pass): this module used to set FRIDAY_ENV /
# DATABASE_URL (a REAL Oracle ADB endpoint, with credentials) at MODULE
# level, which leaked a live-Oracle configuration into every later test in
# the session - the long-running-task suites then attempted real oracledb
# connections and failed with connection resets. Environment is now scoped
# to the client fixture only, and the DSN is the CI-standard loopback mock
# (nothing listens on localhost:1521 in a test environment, so any
# connection attempt fails fast and never leaves the runner).

import pytest
from fastapi.testclient import TestClient


_MOCK_ORACLE_DSN = "oracle+oracledb://mock:mock@localhost:1521/FREE"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("FRIDAY_ENV", "testing")
    monkeypatch.setenv("DATABASE_URL", _MOCK_ORACLE_DSN)
    monkeypatch.setenv("SYNC_DATABASE_URL", _MOCK_ORACLE_DSN)
    monkeypatch.setenv("ASYNC_DATABASE_URL", "oracle+oracledb_async://mock:mock@localhost:1521/FREE")
    from friday.api.server import app
    with TestClient(app) as test_client:
        yield test_client


def test_livekit_token_unconfigured_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)

    resp = client.get("/api/livekit/token")
    assert resp.status_code == 503
    data = resp.json()
    assert "LiveKit is not configured" in data.get("detail", "") or "LiveKit is not configured" in data.get("message", "")


def test_livekit_token_invalid_parameters_return_400(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test_key_1234567890123456")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test_secret_12345678901234567890123456")

    # Invalid room name
    resp_room = client.get("/api/livekit/token?room=invalid%20room%20!")
    assert resp_room.status_code == 400

    # Invalid identity
    resp_id = client.get("/api/livekit/token?identity=bad%20id%20!")
    assert resp_id.status_code == 400


def test_livekit_token_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://friday-voice.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "APItest12345678901234567890")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "SECRETtest123456789012345678901234567890")

    resp = client.get("/api/livekit/token?room=friday&identity=owner-test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["server_url"] == "wss://friday-voice.livekit.cloud"
    assert data["room"] == "friday"
    assert data["identity"] == "owner-test"
    assert isinstance(data["token"], str)
    assert data["token"].startswith("eyJ")  # Valid JWT format
