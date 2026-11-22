"""TASK-REL-067 — FRIDAY's own /health capability contract (REL-004 §2.2/§3).

Pins the §3 mapping: orchestration from the import-check report,
memory_backend + database from the live DB round-trip /ready performs,
disk from the /ready disk check (>= 50 MB), environment from the runtime
validator, peer_mesh (optional) from observed in-process mesh outcomes.
Top-level status is derived (ok iff every required capability/dependency
is ok) and HTTP is 200 iff ok else 503. /ready behaviour is unchanged.

NOTE (standing order 5): this file is new, so the work PR must add it to
the contracts workflow file list in the same PR — wiring is owed at
work-PR time, on top of the rebase.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from friday.api.server import app
from friday_deep.health import Check, Health, Report


def _report(overall: Health) -> Report:
    return Report(
        overall=overall,
        checks=[Check("friday", overall, "stubbed for REL-067")],
    )


class _MeshStub:
    def __init__(self, status_payload):
        self._payload = status_payload

    def status(self):
        return self._payload


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_contract_ok_path() -> None:
    """All required capabilities ok -> 200, status ok, capability_report."""
    resp = _client().get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["evidence_class"] == "capability_report"
    assert set(data["capabilities"]) == {
        "orchestration",
        "memory_backend",
        "peer_mesh",
    }
    assert set(data["dependencies"]) == {"database", "disk", "environment"}
    for entry in list(data["capabilities"].values()) + list(
        data["dependencies"].values()
    ):
        assert entry["state"] in {"ok", "degraded", "unavailable", "unknown"}
        assert "evidence" in entry and "checked_at" in entry
        if entry["state"] != "ok":
            assert "detail" in entry
    assert data["capabilities"]["orchestration"]["state"] == "ok"
    assert data["capabilities"]["memory_backend"]["state"] == "ok"
    assert data["dependencies"]["database"]["state"] == "ok"
    assert data["dependencies"]["disk"]["state"] == "ok"
    assert data["dependencies"]["environment"]["state"] == "ok"
    # Legacy fields are kept (backwards-compatible additive change).
    assert data["overall"] == "healthy"
    assert data["service"] == "friday_core"
    assert data["agent"] == "FRIDAY"
    assert data["version"] == "2.0.0"
    assert "checks" in data and "peers_mesh" in data and "observed_at" in data


def test_degraded_orchestration_returns_503() -> None:
    """A failed import check degrades /health (never a constant ok)."""
    with patch(
        "friday.api.server.build_health_report",
        return_value=_report(Health.DEGRADED),
    ):
        resp = _client().get("/health")
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["capabilities"]["orchestration"]["state"] == "degraded"
    assert (
        data["capabilities"]["orchestration"]["detail"] == "IMPORT_CHECK_FAILED"
    )


def test_database_down_returns_503_without_exception_text() -> None:
    """DB probe failure -> memory_backend + database unavailable, 503.

    Only the exception TYPE name may appear (REL-004 §2.2 rule 8): the
    raw exception text — which could carry a secret — must not leak.
    """
    with patch(
        "friday.api.server.connect_sqlite",
        side_effect=RuntimeError("boom-sk-fake-secret"),
    ):
        resp = _client().get("/health")
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["capabilities"]["memory_backend"]["state"] == "unavailable"
    assert (
        data["capabilities"]["memory_backend"]["detail"]
        == "DATABASE_UNREACHABLE"
    )
    assert data["dependencies"]["database"]["state"] == "unavailable"
    assert data["dependencies"]["database"]["detail"] == "DATABASE_UNREACHABLE"
    assert "RuntimeError" in data["capabilities"]["memory_backend"]["evidence"]
    assert "boom-sk-fake-secret" not in resp.text


def test_database_unconfigured_returns_503() -> None:
    """No DSN configured -> DATABASE_UNCONFIGURED, not a silent ok."""
    with patch(
        "friday.api.server._probe_memory_database",
        return_value=("unavailable", "unconfigured", "NoOracleDSN"),
    ):
        resp = _client().get("/health")
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert (
        data["capabilities"]["memory_backend"]["detail"]
        == "DATABASE_UNCONFIGURED"
    )
    assert (
        data["dependencies"]["database"]["detail"] == "DATABASE_UNCONFIGURED"
    )


def test_disk_low_returns_503() -> None:
    """Under 50 MB free -> disk unavailable with LOW_DISK_SPACE, 503."""
    with patch(
        "shutil.disk_usage",
        return_value=(100 * 1024 * 1024, 90 * 1024 * 1024, 10 * 1024 * 1024),
    ):
        resp = _client().get("/health")
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["dependencies"]["disk"]["state"] == "unavailable"
    assert data["dependencies"]["disk"]["detail"] == "LOW_DISK_SPACE"


def test_environment_invalid_degrades_both_probes() -> None:
    """Invalid runtime environment degrades /health AND /ready (§2.5).

    /health must never contradict /ready: an env failure makes /ready 503,
    so /health must be degraded too.
    """
    client = _client()
    with patch(
        "friday.api.server.validate_runtime_environment",
        return_value={
            "valid": False,
            "environment": "test",
            "issues": ["data directory not writable"],
            "warnings": [],
        },
    ):
        ready = client.get("/ready")
        resp = client.get("/health")
    assert ready.status_code == 503
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["dependencies"]["environment"]["state"] == "degraded"
    assert (
        data["dependencies"]["environment"]["detail"] == "ENVIRONMENT_INVALID"
    )


def test_peer_mesh_unknown_does_not_degrade() -> None:
    """peer_mesh is optional (§2.4): unknown never changes top-level status."""
    mesh = _MeshStub(
        {"peers": [{"name": "inference"}], "state_counts": {"UNVERIFIED": 2}}
    )
    with patch("friday.api.server.get_mesh", return_value=mesh):
        resp = _client().get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["capabilities"]["peer_mesh"]["state"] == "unknown"
    assert (
        data["capabilities"]["peer_mesh"]["detail"] == "CONFIG_UNVERIFIED"
    )


def test_ready_unchanged() -> None:
    """Criterion 6 for FRIDAY: /ready behaviour is unchanged by the slice."""
    resp = _client().get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ready"] is True
    assert data["status"] == "ready"
    assert data["database"] == "healthy"
    assert data["database_backend"] == "sqlite"
    assert data["disk"] == "healthy"
    assert data["disk_free_mb"] >= 50.0
