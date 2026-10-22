from fastapi.testclient import TestClient

from app.config.production import EnvironmentType, production_settings
from app.main import app


def test_production_api_fails_closed_when_forge_key_missing(monkeypatch):
    monkeypatch.setattr(production_settings, "env", EnvironmentType.PRODUCTION)
    monkeypatch.setattr(production_settings, "api_key_required", True)
    monkeypatch.setattr(production_settings, "forge_api_key", None)

    response = TestClient(app).get("/agents")

    assert response.status_code == 503
    assert response.json()["error"] == "service_auth_unconfigured"


def test_production_api_checks_configured_key_and_keeps_health_public(monkeypatch):
    key = "owner-configured-forge-test-key-0123456789"
    monkeypatch.setattr(production_settings, "env", EnvironmentType.PRODUCTION)
    monkeypatch.setattr(production_settings, "api_key_required", True)
    monkeypatch.setattr(production_settings, "forge_api_key", key)
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/agents").status_code == 401
    assert client.get("/agents", headers={"X-API-Key": "wrong-key"}).status_code == 403
    assert client.get("/agents", headers={"X-API-Key": key}).status_code == 200


def test_production_with_api_key_not_required_allows_anonymous_access(monkeypatch):
    """Regression test for the docker-compose.yml self-lock bug.

    docker-compose.yml ships with `FORGE_ENV=production` +
    `API_KEY_REQUIRED=false` and no `FORGE_API_KEY` configured -- an
    intentional, explicit opt-out for a fresh `docker compose up` demo. The
    middleware used to gate purely on `env == PRODUCTION` and ignored
    `api_key_required` entirely, so this exact, documented configuration
    returned 503 "service_auth_unconfigured" on every `/api/*` call,
    locking operators out of their own default deployment.
    """
    monkeypatch.setattr(production_settings, "env", EnvironmentType.PRODUCTION)
    monkeypatch.setattr(production_settings, "api_key_required", False)
    monkeypatch.setattr(production_settings, "forge_api_key", None)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/api/tasks")
        assert response.status_code != 503
        assert response.status_code != 401
        assert response.status_code != 403


def test_production_dashboard_shell_is_public_but_data_apis_require_key(monkeypatch):
    key = "owner-configured-forge-test-key-0123456789"
    monkeypatch.setattr(production_settings, "env", EnvironmentType.PRODUCTION)
    monkeypatch.setattr(production_settings, "api_key_required", True)
    monkeypatch.setattr(production_settings, "forge_api_key", key)
    # Context manager runs the real app lifespan, which initializes the SQLite
    # schema exactly as a fresh deployment would; without it /api/tasks hits a
    # database with no tables (proven on CI: 'no such table: tasks').
    with TestClient(app) as client:
        for path in ("/", "/dashboard"):
            response = client.get(path)
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            assert key not in response.text
            assert client.head(path).status_code == 200

        assert client.get("/api/tasks").status_code == 401
        assert client.get("/api/analytics/summary").status_code == 401
        assert client.get("/api/tasks", headers={"X-API-Key": key}).status_code != 401
