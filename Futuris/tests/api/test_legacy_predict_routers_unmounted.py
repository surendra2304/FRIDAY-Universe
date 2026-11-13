"""
tests/api/test_legacy_predict_routers_unmounted.py — TASK-TRUST-001.

The legacy ``predict/*`` routers generated values from md5 hashes while
looking like real forecasts. They are unmounted from the live app; the real
surfaces (/v1/forecasts, /v1/friday/*, the market router) remain mounted.
"""

from futuris.api.app import app, iter_route_paths


def _all_paths() -> set[str]:
    return set(iter_route_paths(app))


def test_fake_predict_route_families_are_unmounted():
    paths = _all_paths()
    for fake in ("/api/v1/futuris/forecast/series",):
        assert not any(p == fake or p.startswith(fake + "/") for p in paths), fake
    assert not any(p.startswith("/api/v1/futuris/stress") for p in paths)
    assert not any(p.startswith("/api/v1/futuris/event-probability") for p in paths)
    # The doubled mount paths (prefix + full decorator path) are gone too.
    assert not any("api/v1/futuris/api/v1/futuris" in p for p in paths)


def test_real_surfaces_stay_routed():
    paths = _all_paths()
    assert "/api/v1/futuris/forecast" in paths  # market router (telemetry-gated)
    assert "/v1/market/forecast" in paths
    assert "/api/v1/task/execute" in paths
    # The real pipeline surfaces
    assert any(p.startswith("/v1/friday/forecast") for p in paths)
    assert any(p.startswith("/v1/forecasts") for p in paths)


def test_openapi_has_no_legacy_predict_operations():
    schema = app.openapi()
    leaked = [p for p in schema["paths"] if (
        p.startswith("/api/v1/futuris/forecast/")
        or p.startswith("/api/v1/futuris/stress")
        or p.startswith("/api/v1/futuris/event-probability")
    )]
    assert leaked == []
