"""TASK-SEN-001 — Sentinel surface-honesty regression tests.

Each test pins a defect proven live on production (Server 2, 2026-11-14):
1. The vulnerability scanner returned 14 canned findings (3 critical,
   risk_score 190) for https://example.com — a fabricated dataset with
   invented file paths/lines in other agents' code, presented as a real
   scan of an arbitrary target with no simulation labelling.
2. The SOAR response orchestrator marked playbook actions "completed" /
   "Successfully executed" although nothing was executed, with a
   duration_ms derived from an md5 hash.
3. The behavioral detector's train_model invented training_samples and
   accuracy from md5 hashes (live: 1101 samples, 0.92 accuracy for
   entity_type "user" with zero training data).
4. GET /api/v1/friday/posture reported 100.0 with zero scans ever
   recorded and no disclosure of the basis for the score.
5. The /api/v1/sentinel/* service routers were unreachable at their
   documented paths (404) because their route paths embed the prefix
   that main.py also adds; they answered only at double-prefixed paths.
6. Dict-payload routers answered 500 (unhandled KeyError) instead of
   422 when a required field was missing.
"""

from fastapi.testclient import TestClient

from sentinel.apps.api.main import app

client = TestClient(app)


# 1. Vulnerability scanner must label its simulated dataset -----------------

def test_vuln_scan_labels_simulated_output():
    from app.services.vulnerability_scanner import VulnerabilityScanner

    scanner = VulnerabilityScanner()
    result = scanner.scan(target="https://example.com", scan_type="full")
    assert result.get("simulated") is True
    assert result.get("data_source") == "simulated_demo_dataset"
    assert "data_note" in result


def test_vuln_scan_results_and_report_label_simulated():
    from app.services.vulnerability_scanner import VulnerabilityScanner

    scanner = VulnerabilityScanner()
    scan = scanner.scan(target="https://example.org", scan_type="full")
    results = scanner.get_scan_results(scan["scan_id"])
    assert results.get("simulated") is True
    report = scanner.get_report()
    assert report.get("simulated") is True


# 2. SOAR actions must not claim execution that never happened ---------------

def test_response_actions_not_claimed_executed():
    from app.services.automated_response_orchestrator import AutomatedResponseOrchestrator

    orch = AutomatedResponseOrchestrator()
    playbook = orch.create_playbook(
        name="sen001-probe",
        trigger="alert:sen001",
        conditions=[],
        actions=["isolate host db-1"],
    )
    response = orch.trigger_response(
        incident_id="sen001-inc", severity="high", alert_type="sen001"
    )
    assert response.actions_executed == 0
    for action in orch._actions:
        assert action.status != "completed"
        assert "Successfully executed" not in (action.result or "")


# 3. Behavioral model training must not invent metrics -----------------------

def test_behavioral_train_reports_only_real_metrics():
    from app.services.behavioral_anomaly_detector import BehavioralAnomalyDetector

    detector = BehavioralAnomalyDetector()
    model = detector.train_model("user")
    # No profiles were ever supplied, so there is no training data and no
    # measured accuracy to report.
    assert model.training_samples == 0
    assert model.accuracy is None
    report = detector.get_report()
    assert report["avg_model_accuracy"] is None


# 5/6. Documented router paths work; missing fields are 422, not 500 ---------

def test_vuln_scan_reachable_at_documented_path():
    resp = client.post(
        "/api/v1/sentinel/vuln/scan",
        json={"target": "https://example.com", "scan_type": "full"},
    )
    assert resp.status_code == 200
    assert resp.json().get("simulated") is True


def test_threat_match_missing_field_is_422_not_500():
    resp = client.post("/api/v1/sentinel/threat-match/signatures", json={"name": "x"})
    assert resp.status_code == 422


def test_vuln_scan_missing_target_is_422_not_500():
    resp = client.post("/api/v1/sentinel/vuln/scan", json={})
    assert resp.status_code == 422
