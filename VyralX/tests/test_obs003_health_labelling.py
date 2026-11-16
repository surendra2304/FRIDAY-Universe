"""TASK-OBS-003 — VyralX /health must label its evidence class.

Every other agent's /health carries ``evidence_class: process_liveness``
(the fleet convention) so no consumer mistakes a liveness answer for a
dependency verdict. VyralX returned a bare {"status": "ok"} with no label
and no observation timestamp. Dependency truth stays in /ready.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_labels_process_liveness():
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["service"] == "vyralx"
    assert data["evidence_class"] == "process_liveness"
    assert "observed_at" in data
