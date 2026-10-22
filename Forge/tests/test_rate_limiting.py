"""
Regression tests for the dead rate-limiter bug.

`RateLimiter` and `verify_api_key` (app/security/api_keys.py) were a fully
implemented, independently-correct sliding-window rate limiter -- but they
were never attached to any route or middleware anywhere in the application.
No request was ever actually rate limited in production, regardless of the
`rate_limit_enabled`/`default_rate_limit` settings. These tests exercise the
real HTTP middleware stack (not the limiter class in isolation) to prove the
limiter is now actually enforced, and that it stays off by default for
dev/test traffic so the rest of the test suite's rapid-fire request patterns
are unaffected.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config.production import production_settings
from app.main import app
from app.security.api_keys import rate_limiter


def test_rate_limiting_is_off_by_default_outside_production():
    """The default test/dev environment must never rate limit, preserving
    every other test file's ability to fire many rapid requests."""
    assert production_settings.rate_limit_enabled is False


def test_rate_limit_middleware_enforces_burst_limit_when_enabled(monkeypatch):
    monkeypatch.setattr(production_settings, "rate_limit_enabled", True)
    monkeypatch.setattr(production_settings, "api_key_required", False)
    # Reset any shared state left over from other tests/limiter instances.
    rate_limiter.requests.clear()
    rate_limiter.limit_per_hour = 100
    rate_limiter.burst_limit_per_minute = 3

    with TestClient(app) as client:
        identifier_header = {"X-API-Key": "rate-limit-test-client"}
        statuses = [
            client.get("/api/tasks", headers=identifier_header).status_code for _ in range(5)
        ]

    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses[3:], f"expected a 429 after the burst limit, got {statuses}"


def test_rate_limit_scoped_to_api_paths_only(monkeypatch):
    """Non-API routes (health, dashboard) must never be rate limited even
    when the feature is enabled -- those are liveness/UX surfaces, not the
    data API this limiter protects."""
    monkeypatch.setattr(production_settings, "rate_limit_enabled", True)
    rate_limiter.requests.clear()
    rate_limiter.burst_limit_per_minute = 1

    with TestClient(app) as client:
        for _ in range(5):
            assert client.get("/health").status_code == 200
