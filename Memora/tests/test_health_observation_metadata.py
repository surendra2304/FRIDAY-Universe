from datetime import datetime
import json

from apps.api.routers import health


class DatabaseProbe:
    def execute(self, _statement):
        return 1


def test_health_reports_server_observation_timestamp_and_evidence_class(monkeypatch):
    # TASK-REL-013 repair: dropped a patch of health.production_mode, a name
    # that has never existed in the health module (the patch errored on main).
    monkeypatch.setattr(
        health.vector_adapter,
        "readiness",
        lambda: {"status": "connected", "available": True, "backend": "qdrant"},
    )

    body = json.loads(health.health_check(db=DatabaseProbe()).body)

    # REL-004 §2.2 rule 3: a /health that carries capability states is a
    # capability report, not a liveness report.
    assert body["evidence_class"] == "capability_report"
    observed_at = datetime.fromisoformat(body["observed_at"])
    assert observed_at.tzinfo is not None
