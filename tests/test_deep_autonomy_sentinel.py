from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent

# Requirement: audit signing key in test environment
os.environ["SENTINEL_AUDIT_SIGNING_KEY"] = "1234567890123456"


def _ensure_sentinel_app():
    to_remove = [k for k in list(sys.modules.keys()) if k == "app" or k.startswith("app.") or k == "sentinel" or k.startswith("sentinel.")]
    for k in to_remove:
        sys.modules.pop(k, None)
    sentinel_path = str(ROOT / "Sentinel")
    if sentinel_path in sys.path:
        sys.path.remove(sentinel_path)
    sys.path.insert(0, sentinel_path)


def test_incident_creation_auto_attaches_attack_and_playbook():
    _ensure_sentinel_app()
    from sentinel.api.incident_routes import incident_router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(incident_router)
    client = TestClient(app)

    # 1. Create incident via POST /v1/incidents
    res = client.post("/v1/incidents", json={
        "id": "inc-auto-001",
        "tenant_id": "tenant-sec-1",
        "title": "Credential dumping via LSASS memory access",
        "severity": "CRITICAL",
        "reason": "Mimikatz detected executing from unauthorized path accessing lsass.exe memory",
        "evidence_refs": ["ev-101", "ev-102"],
    })
    assert res.status_code == 200, res.text
    data = res.json()["incident"]

    # Hard failures if missing
    assert "attack_techniques" in data, "Incident must contain attack_techniques"
    assert len(data["attack_techniques"]) >= 1, "Must have at least one ATT&CK technique"
    assert "playbook_steps" in data, "Incident must contain playbook_steps"
    assert len(data["playbook_steps"]) >= 1, "Must have at least one playbook step"

    # Verify subsequent GET returns the persisted fields
    list_res = client.get("/v1/incidents?tenant_id=tenant-sec-1")
    assert list_res.status_code == 200
    incidents = list_res.json()["incidents"]
    saved = next((i for i in incidents if i["id"] == "inc-auto-001"), None)
    assert saved is not None
    assert saved["attack_techniques"] == data["attack_techniques"]
    assert saved["playbook_steps"] == data["playbook_steps"]


def test_destructive_playbook_actions_block_pending_approval():
    _ensure_sentinel_app()
    from app.services.cyber_skills_service import CyberSkillsService

    service = CyberSkillsService()

    # Destructive action without approval -> fails closed
    result = service.execute_playbook_action("isolate host", target="192.168.1.50", approved=False)
    assert result["status"] == "blocked_pending_approval"
    assert "requires human authorization" in result["reason"]

    # Another destructive action: block IP
    block_res = service.execute_playbook_action("block IP", target="203.0.113.5", approved=False)
    assert block_res["status"] == "blocked_pending_approval"

    # With explicit approval -> executes
    approved_res = service.execute_playbook_action("isolate host", target="192.168.1.50", approved=True)
    assert approved_res["status"] == "executed"


def test_detection_coverage_dynamically_reflects_rules():
    _ensure_sentinel_app()
    from app.services.cyber_skills_service import CyberSkillsService

    service = CyberSkillsService()
    techniques = ["T1059", "T1190", "T1046"]

    # Initial evaluation with single rule
    rules_initial = [
        {"id": "r1", "name": "PowerShell Script Block Logging", "techniques": ["T1059"], "fidelity": 0.9}
    ]
    cov1 = service.detection_coverage(techniques, rules=rules_initial)
    assert "T1059" in cov1.get("covered", [])
    assert "T1190" in cov1.get("gaps", [])

    # Add detection rule for T1190
    rules_updated = rules_initial + [
        {"id": "r2", "name": "WAF Exploit Signature", "techniques": ["T1190"], "fidelity": 0.95}
    ]
    cov2 = service.detection_coverage(techniques, rules=rules_updated)
    assert "T1059" in cov2.get("covered", [])
    assert "T1190" in cov2.get("covered", [])
    assert cov2["weighted_coverage"] > cov1["weighted_coverage"]


def test_posture_report_includes_csf_and_detection_coverage():
    _ensure_sentinel_app()
    from app.services.security_posture_assessor import SecurityPostureAssessor

    assessor = SecurityPostureAssessor()
    assessor.update_vulnerability_status(10, 1, 2, 4, 3, 5.0, 15)
    assessor.update_patch_compliance(100, 92, 0, 12.0)
    assessor.update_config_drift(50, 48, 0)
    assessor.assess()

    report = assessor.get_report()
    assert "nist_csf" in report, "Posture report must include nist_csf"
    assert report["nist_csf"].get("available") is True
    assert "overall" in report["nist_csf"]
    assert "function_scores" in report["nist_csf"]

    assert "detection_coverage" in report, "Posture report must include detection_coverage"
    assert report["detection_coverage"].get("available") is True
    assert "weighted_coverage" in report["detection_coverage"]


def test_csf_compliance_normalization():
    _ensure_sentinel_app()
    from app.services.security_posture_assessor import SecurityPostureAssessor

    # Ratios (0.0 - 1.0)
    assert SecurityPostureAssessor._maturity(0.8) == 4
    assert SecurityPostureAssessor._maturity(1.0) == 5
    assert SecurityPostureAssessor._maturity(0.2) == 1

    # Scale 1 - 5
    assert SecurityPostureAssessor._maturity(3.0) == 3
    assert SecurityPostureAssessor._maturity(5.0) == 5

    # Percentages (0 - 100)
    assert SecurityPostureAssessor._maturity(80.0) == 4
    assert SecurityPostureAssessor._maturity(95.0) == 5
    assert SecurityPostureAssessor._maturity(25.0) == 1
